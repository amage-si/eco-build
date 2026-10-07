"""eco: fast builds of AMAGE Eco programs.

    eco build <target>... [--release] [--fork] [-O N] [-j N]
    eco test <target>...          build, run, show the output's last lines
    eco targets                   list the targets in targets.toml
    eco cache [--clean]           size of the object cache, or empty it

A build runs under the shared Eco build lock at nice 10:

  1. bend <src> -o <work>/out.c       check and emit C (the official
                                      compiler, or the local fork with
                                      --fork); the JS heap is capped with
                                      BUN_JSC_forceRAMSize so bend's peak
                                      stays near 1.3 GiB instead of 3+
  2. split the C into units           see csplit.py; skipped by --release
  3. clang -c each unit, in parallel  objects are cached by the unit's
                                      text, flags and clang version, so
                                      an edit recompiles only the units
                                      whose text changed
  4. link

--release builds the unsplit C with bend's own clang line (-std=c11 -O3
in one unit), which is what `bend <src> -o <out>` produces, without
bend's 3 GiB heap staying resident while clang runs.
"""

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import tomllib

from . import csplit

LOCK = "/tmp/amage-eco-bend-build.lock"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.sysconf("SC_PAGE_SIZE")


# Memory sampling
# ---------------

def _children():
    kids = {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open(f"/proc/{d}/stat", "rb") as f:
                    s = f.read().decode("latin-1")
            except OSError:
                continue
            ppid = int(s[s.rfind(")") + 2:].split(" ", 3)[1])
            kids.setdefault(ppid, []).append(int(d))
    return kids


def _tree_rss(root):
    kids, todo, total = _children(), [root], 0
    while todo:
        pid = todo.pop()
        try:
            with open(f"/proc/{pid}/statm") as f:
                total += int(f.read().split()[1]) * PAGE
        except OSError:
            pass
        todo.extend(kids.get(pid, []))
    return total


class Sampler(threading.Thread):
    """Samples the RSS of this process and its descendants."""

    def __init__(self, every=0.05):
        super().__init__(daemon=True)
        self.every, self.peak, self.phase_peak, self.stop = every, 0, 0, False

    def run(self):
        me = os.getpid()
        while not self.stop:
            r = _tree_rss(me)
            self.peak = max(self.peak, r)
            self.phase_peak = max(self.phase_peak, r)
            time.sleep(self.every)

    def phase(self):
        p, self.phase_peak = self.phase_peak, 0
        return p


# Config
# ------

def load_targets(root):
    with open(os.path.join(HERE, "targets.toml"), "rb") as f:
        targets = tomllib.load(f)
    for name, t in targets.items():
        t["name"] = name
        t["dir"] = os.path.join(root, t["dir"])
    return targets


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "eco-build")


def clang_id():
    out = subprocess.run(["clang", "--version"], capture_output=True,
                         text=True).stdout
    return out.splitlines()[0] if out else "clang"


def link_libs(c_text):
    libs = []
    if "#include <X11/" in c_text:
        libs.append("-lX11")
    if "#include <alsa/" in c_text:
        libs.append("-lasound")
    return libs


# Build
# -----

class Report:
    def __init__(self, name):
        self.name, self.rows, self.t0 = name, [], time.time()

    def add(self, what, secs, note=""):
        self.rows.append((what, secs, note))
        print(f"  {what:<12} {secs:7.2f} s  {note}", flush=True)


def compile_c(t, args, work, rep, sampler):
    c_path = os.path.join(work, "out.c")
    env = dict(os.environ)
    env.setdefault("BEND_NO_TELEMETRY", "1")
    if args.heap_cap:
        env.setdefault("BUN_JSC_forceRAMSize", str(args.heap_cap * 2**20))
    if args.fork:
        main = os.path.join(args.fork_dir, "bend2", "main.ts")
        cmd = ["bun", main, t["src"], "-o", c_path]
        who = "fork"
        if args.flat_max and not args.release:
            env["BEND_FLAT_MAX"] = str(args.flat_max)
    else:
        cmd = ["bend", t["src"], "-o", c_path]
        who = "bend"
    s = time.time()
    p = subprocess.run(cmd, cwd=t["dir"], env=env)
    if p.returncode != 0:
        raise SystemExit(f"eco: {who} failed on {t['src']} (exit {p.returncode})")
    with open(c_path) as f:
        text = f.read()
    rep.add(f"{who} -> C", time.time() - s,
            f"peak {sampler.phase() / 2**30:.2f} GiB, {len(text) / 1e6:.1f} MB of C")
    return c_path, text


def clang_units(units, args, work, rep, sampler, pie=True):
    objs_dir = os.path.join(cache_dir(), "objs")
    os.makedirs(objs_dir, exist_ok=True)
    flags = ["-std=c11", f"-O{args.opt}", "-Wno-unused-function",
             *([] if pie else ["-fno-pie"])]
    ident = clang_id() + "\0" + " ".join(flags) + "\0"
    todo, objs = [], []
    for i, u in enumerate(units):
        key = hashlib.blake2b((ident + u).encode(), digest_size=16).hexdigest()
        obj = os.path.join(objs_dir, key + ".o")
        objs.append(obj)
        if not os.path.exists(obj):
            src = os.path.join(work, f"u{i}.c")
            with open(src, "w") as f:
                f.write(u)
            todo.append((len(u), i, src, obj))
    todo.sort(reverse=True)
    s = time.time()
    # Start a unit only while the estimated memory of the running ones fits
    # the budget (one always runs). The estimate grows with the unit's text.
    budget = args.mem_budget * 2**20
    est = lambda n: (160 + n / 2**10 * 0.12) * 2**20
    running, failed = {}, []
    queue = list(todo)
    while queue or running:
        while queue and len(running) < args.jobs and (not running or sum(
                e for _, e, _ in running.values()) + est(queue[0][0]) <= budget):
            n, i, src, obj = queue.pop(0)
            tmp = obj + f".{os.getpid()}.tmp"
            p = subprocess.Popen(["clang", *flags, "-c", src, "-o", tmp])
            running[p.pid] = (p, est(n), (src, obj, tmp))
        pid, status = os.wait()
        if pid not in running:
            continue
        p, _, (src, obj, tmp) = running.pop(pid)
        if os.waitstatus_to_exitcode(status) != 0:
            failed.append(src)
        else:
            os.replace(tmp, obj)
    if failed:
        raise SystemExit("eco: clang failed on " + ", ".join(failed))
    rep.add("clang", time.time() - s,
            f"{len(todo)} of {len(units)} units compiled (-O{args.opt}, "
            f"up to {args.jobs} at once), peak {sampler.phase() / 2**30:.2f} GiB")
    return objs


def link(objs, libs, out, rep, sampler, fids=None, work=None):
    s = time.time()
    tmp = out + ".eco-tmp"
    extra = []
    if fids is not None:
        # the FID numbers, as absolute symbols the units use as immediates
        rsp = os.path.join(work, "fids.rsp")
        with open(rsp, "w") as f:
            f.writelines(f"-Wl,--defsym=eco_{k}={v}\n" for k, v in fids.items())
        extra = ["-no-pie", "@" + rsp]
    p = subprocess.run(["clang", "-o", tmp, *extra, *objs, "-lpthread", "-lm",
                        *libs])
    if p.returncode != 0:
        raise SystemExit("eco: link failed")
    os.replace(tmp, out)
    rep.add("link", time.time() - s)


def build(t, args, sampler):
    rep = Report(t["name"])
    mode = "release" if args.release else f"dev -O{args.opt}"
    who = "official bend"
    if args.fork:
        who = "fork" + (f", flat-max {args.flat_max}"
                        if args.flat_max and not args.release else "")
    load = open("/proc/loadavg").read().split()[0]
    print(f"eco build {t['name']} ({mode}, {who}, load {load})", flush=True)
    work = os.path.join(cache_dir(), "work", t["name"])
    os.makedirs(work, exist_ok=True)
    out = os.path.join(t["dir"], t["out"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sampler.phase()
    c_path, text = compile_c(t, args, work, rep, sampler)
    libs = link_libs(text)
    units, fids = None, None
    if not args.release:
        s = time.time()
        if args.stable:
            got = csplit.split_stable(text, args.units)
            units, fids = got if got is not None else (None, None)
        else:
            units = csplit.split(text, args.units)
        if units is None:
            print("  (GPU calls: built as one unit)")
        else:
            rep.add("split", time.time() - s, f"{len(units)} units"
                    + (", stable names" if args.stable else ""))
    if units is None:
        s = time.time()
        tmp = out + ".eco-tmp"
        p = subprocess.run(["clang", "-std=c11", "-O3", c_path, "-lpthread",
                            "-lm", *libs, "-o", tmp])
        if p.returncode != 0:
            raise SystemExit("eco: clang failed")
        os.replace(tmp, out)
        rep.add("clang -O3", time.time() - s,
                f"one unit, peak {sampler.phase() / 2**30:.2f} GiB")
    else:
        objs = clang_units(units, args, work, rep, sampler,
                           pie=fids is None)
        link(objs, libs, out, rep, sampler, fids, work)
    total = time.time() - rep.t0
    print(f"  {'total':<12} {total:7.2f} s  peak {sampler.peak / 2**30:.2f} GiB"
          f" -> {os.path.relpath(out, args.root)}", flush=True)
    return {"target": t["name"], "mode": mode, "fork": args.fork,
            "flat_max": args.flat_max if args.fork and not args.release else 0,
            "units": args.units, "load": float(load),
            "total_s": round(total, 2), "peak_mib": sampler.peak >> 20,
            "phases": [(w, round(s, 2), n) for w, s, n in rep.rows]}


# CLI
# ---

def main(argv=None):
    ap = argparse.ArgumentParser(prog="eco", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "test"):
        b = sub.add_parser(name)
        b.add_argument("targets", nargs="+")
        b.add_argument("--release", action="store_true",
                       help="one unit at -O3, as bend builds it")
        b.add_argument("--official", action="store_true",
                       help="use the installed bend even if the fork is present")
        b.add_argument("--fork", action="store_true",
                       help="use the local compiler fork (the default for dev"
                            " builds when it is present; see --fork-dir)")
        b.add_argument("--flat-max", type=int, default=32,
                       help="fork dev builds box datatypes wider than this"
                            " many words (BEND_FLAT_MAX; 0: as bend does)")
        b.add_argument("--fork-dir", default=os.path.join(
                           os.path.dirname(HERE), "bend-fork", "src"),
                       help="checkout of the fork (default ../bend-fork/src)")
        b.add_argument("-O", dest="opt", default="1",
                       help="clang -O level for dev builds (default 1)")
        b.add_argument("-j", dest="jobs", type=int, default=os.cpu_count(),
                       help="most clang processes at once")
        b.add_argument("--units", type=int, default=16,
                       help="segment units to split into (default 16)")
        b.add_argument("--no-stable", dest="stable", action="store_false",
                       help="split without stable names (PIE, positional FIDs)")
        b.add_argument("--mem-budget", type=int, default=1536,
                       help="MiB the parallel clangs may use together (default 1536)")
        b.add_argument("--heap-cap", type=int, default=2400,
                       help="MiB of RAM bend's JS heap sizes itself for (0: off)")
        b.add_argument("--root", default=os.path.dirname(HERE),
                       help="the Eco root (default: this repo's parent)")
        b.add_argument("--no-lock", action="store_true",
                       help="do not take the shared build lock (already held)")
        b.add_argument("--json", help="append a JSON line per build here")
    sub.add_parser("targets")
    c = sub.add_parser("cache")
    c.add_argument("--clean", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "cache":
        d = cache_dir()
        if args.clean:
            shutil.rmtree(d, ignore_errors=True)
            print("emptied", d)
        else:
            n = sum(os.path.getsize(os.path.join(r, f))
                    for r, _, fs in os.walk(d) for f in fs) if os.path.isdir(d) else 0
            print(f"{d}: {n / 2**20:.0f} MiB")
        return
    root = os.path.dirname(HERE)
    if args.cmd == "targets":
        for name, t in load_targets(root).items():
            print(f"{name:<18} {os.path.relpath(t['dir'], root)}/{t['src']}")
        return

    args.root = os.path.abspath(args.root)
    fork_main = os.path.join(args.fork_dir, "bend2", "main.ts")
    if args.official:
        args.fork = False
    elif not args.release and os.path.exists(fork_main):
        args.fork = True
    if args.fork and not os.path.exists(fork_main):
        raise SystemExit(f"eco: no fork at {fork_main}")
    targets = load_targets(args.root)
    for name in args.targets:
        if name not in targets:
            raise SystemExit(f"eco: no target {name} (see eco targets)")
    os.nice(10)
    lock = None
    if not args.no_lock:
        lock = open(LOCK, "a")
        s = time.time()
        fcntl.flock(lock, fcntl.LOCK_EX)
        waited = time.time() - s
        if waited > 0.5:
            print(f"eco: waited {waited:.1f} s for the build lock", flush=True)
    sampler = Sampler()
    sampler.start()
    for name in args.targets:
        t = targets[name]
        sampler.peak = 0
        res = build(t, args, sampler)
        if args.json:
            with open(args.json, "a") as f:
                f.write(json.dumps(res) + "\n")
        if args.cmd == "test":
            run = t.get("run")
            if run is None:
                print(f"  ({name} has no run line)")
                continue
            s = time.time()
            p = subprocess.run([os.path.join(t["dir"], t["out"]), *run],
                               cwd=t["dir"], capture_output=True, text=True)
            lines = (p.stdout + p.stderr).strip().splitlines()
            for line in lines[-3:]:
                print("  | " + line)
            print(f"  run exit {p.returncode} in {time.time() - s:.2f} s")
            if p.returncode != 0:
                raise SystemExit(p.returncode)
    sampler.stop = True


if __name__ == "__main__":
    main()
