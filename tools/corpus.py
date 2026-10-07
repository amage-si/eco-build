#!/usr/bin/env python3
"""Check the compiler fork against the official bend on a corpus.

    corpus.py same  [--jobs N] [--limit N] FILES...   C byte for byte
    corpus.py run   [--jobs N] [--flat-max N] FILES... run the C lane

`same` emits C for every file with the installed bend and with the fork
(BEND_FLAT_MAX unset) and compares the bytes. `run` builds each upstream
test with the fork (BEND_FLAT_MAX as given) and with the official bend,
runs both, and compares each to the test's `#|` lines.

Work runs in batches under the shared Eco build lock, released between
batches so other sessions get their turn.
"""
import argparse
import concurrent.futures as cf
import fcntl
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import time

LOCK = "/tmp/amage-eco-bend-build.lock"
FORK = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "bend-fork", "src", "bend2", "main.ts")


def want_of(src):
    return "\n".join(l[2:] for l in src.splitlines() if l.startswith("#|"))


def tidy(text):
    return re.sub(r"[ \t]+$", "", text, flags=re.M).strip()


def runnable(path):
    src = open(path).read()
    if not re.search(r"^import Base$", src, re.M):
        return False
    if not re.search(r"^(def|law) main(\(|:)", src, re.M):
        return False
    effs = re.findall(r'^\s*import "\./[a-z0-9_]+\.(c|js)"$', src, re.M)
    if effs and "c" not in effs:
        return False
    return not re.match(r"^(SOME PROOFS FAIL|Error:)", tidy(want_of(src)))


def emit(cmd, path, out, env):
    p = subprocess.run(cmd + [os.path.basename(path), "-o", out],
                       cwd=os.path.dirname(path), env=env,
                       capture_output=True, text=True, timeout=600)
    return p.returncode, (p.stdout + p.stderr)[-400:]


CACHE = os.path.join(os.path.expanduser("~/.cache/eco-build"), "corpus")


def emit_cached(path, out, env):
    """The official bend's C for path, cached by the file's text (the
    imports of a test live beside it; a stale import is not detected)."""
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.blake2b((path + "\0" + open(path).read()).encode(),
                          digest_size=12).hexdigest()
    hit = os.path.join(CACHE, key + ".c")
    if os.path.exists(hit):
        with open(hit, "rb") as f, open(out, "wb") as g:
            g.write(f.read())
        return 0, ""
    r, e = emit(["bend"], path, out, env)
    if r == 0:
        with open(out, "rb") as f, open(hit + ".tmp", "wb") as g:
            g.write(f.read())
        os.replace(hit + ".tmp", hit)
    return r, e


def job_same(path, tmp, flat=0):
    h = hashlib.blake2b(path.encode(), digest_size=6).hexdigest()
    a, b = os.path.join(tmp, h + ".orig.c"), os.path.join(tmp, h + ".fork.c")
    env = dict(os.environ, BEND_NO_TELEMETRY="1")
    env.pop("BEND_FLAT_MAX", None)
    ra, ea = emit_cached(path, a, env)
    fenv = dict(env, BEND_FLAT_MAX=str(flat)) if flat else env
    rb, eb = emit(["bun", FORK], path, b, fenv)
    if ra != 0 or rb != 0:
        same = ra == rb
        return path, ("both-fail" if same else "EXIT-DIFF"), ea if ra else eb
    sa, sb = open(a, "rb").read(), open(b, "rb").read()
    os.remove(a)
    os.remove(b)
    return path, ("same" if sa == sb else "DIFFERENT"), ""


def job_run(path, tmp, flat):
    h = hashlib.blake2b(path.encode(), digest_size=6).hexdigest()
    want = tidy(want_of(open(path).read()))
    out = {}
    for lane, cmd, extra in (("orig", ["bend"], {}),
                             ("fork", ["bun", FORK],
                              {"BEND_FLAT_MAX": str(flat)} if flat else {})):
        env = dict(os.environ, BEND_NO_TELEMETRY="1", **extra)
        if not extra:
            env.pop("BEND_FLAT_MAX", None)
        c = os.path.join(tmp, f"{h}.{lane}.c")
        b = os.path.join(tmp, f"{h}.{lane}")
        r, e = emit(cmd, path, c, env)
        if r != 0:
            out[lane] = "emit-fail"
            continue
        text = open(c).read()
        libs = (["-lX11"] if "#include <X11/" in text else []) + \
            (["-lasound"] if "#include <alsa/" in text else [])
        p = subprocess.run(["clang", "-std=c11", "-O1", "-w", c, "-lpthread",
                            "-lm", *libs, "-o", b], capture_output=True)
        os.remove(c)
        if p.returncode != 0:
            out[lane] = "cc-fail"
            continue
        try:
            p = subprocess.run([b], cwd=os.path.dirname(path),
                               capture_output=True, text=True, timeout=10)
            got = tidy(p.stdout)
            out[lane] = "pass" if got == want else "FAIL"
        except subprocess.TimeoutExpired:
            out[lane] = "timeout"
        os.remove(b)
    return path, out.get("orig"), out.get("fork")


def batches(items, n):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["same", "run"])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--batch", type=int, default=48)
    ap.add_argument("--flat-max", type=int, default=0)
    ap.add_argument("--only-runnable", action="store_true")
    a = ap.parse_args()
    files = [os.path.abspath(f) for f in a.files]
    if a.mode == "run" or a.only_runnable:
        files = [f for f in files if runnable(f)]
    os.nice(10)
    tmp = tempfile.mkdtemp(prefix="eco-corpus-")
    counts, bad = {}, []
    t0 = time.time()
    for group in batches(files, a.batch):
        with open(LOCK, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with cf.ThreadPoolExecutor(a.jobs) as ex:
                if a.mode == "same":
                    futs = [ex.submit(job_same, f, tmp, a.flat_max) for f in group]
                else:
                    futs = [ex.submit(job_run, f, tmp, a.flat_max) for f in group]
                for fu in cf.as_completed(futs):
                    res = fu.result()
                    if a.mode == "same":
                        path, verdict, err = res
                        counts[verdict] = counts.get(verdict, 0) + 1
                        if verdict not in ("same", "both-fail"):
                            bad.append((path, verdict, err))
                    else:
                        path, o, f = res
                        key = f"orig={o} fork={f}"
                        counts[key] = counts.get(key, 0) + 1
                        if o != f:
                            bad.append((path, key, ""))
        done = sum(counts.values())
        print(f"{done}/{len(files)} {counts} {time.time() - t0:.0f}s", flush=True)
    for path, verdict, err in bad:
        print("!!", verdict, path, err.replace("\n", " | ")[:300])
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
