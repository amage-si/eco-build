#!/usr/bin/env python3
"""Run a command and sample its whole process tree.

Every --every seconds it walks /proc for the command's descendants and
records the summed RSS of the tree, the RSS of each process name, and
when each process name was first and last seen (so a bend build splits
into its bend phase and its clang phase). Prints one JSON object.

    treemon.py [--t0 EPOCH] [--every S] [--label L] [--out F] -- cmd...

--t0 is the time the caller started waiting for the build lock; the
difference to our own start is reported as lock_wait_s, apart from the
build's own wall time.
"""
import argparse
import json
import os
import resource
import subprocess
import sys
import time

PAGE = os.sysconf("SC_PAGE_SIZE")


def children_map():
    kids = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat", "rb") as f:
                s = f.read().decode("latin-1")
        except OSError:
            continue
        r = s.rfind(")")
        comm = s[s.find("(") + 1:r]
        ppid = int(s[r + 2:].split(" ", 3)[1])
        kids.setdefault(ppid, []).append((int(d), comm))
    return kids


def rss_of(pid):
    try:
        with open(f"/proc/{pid}/statm") as f:
            return int(f.read().split()[1]) * PAGE
    except OSError:
        return 0


def tree(root, root_comm):
    kids = children_map()
    out, todo = [], [(root, root_comm)]
    while todo:
        pid, comm = todo.pop()
        out.append((pid, comm))
        todo.extend(kids.get(pid, []))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--t0", type=float)
    ap.add_argument("--every", type=float, default=0.05)
    ap.add_argument("--label", default="")
    ap.add_argument("--out")
    ap.add_argument("--timeline", action="store_true")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    start = time.time()
    p = subprocess.Popen(cmd)
    peak, peak_at = 0, 0.0
    by = {}
    line = []
    while p.poll() is None:
        t = time.time() - start
        total = 0
        names = {}
        for pid, comm in tree(p.pid, os.path.basename(cmd[0])[:15]):
            r = rss_of(pid)
            total += r
            names[comm] = names.get(comm, 0) + r
        for comm, r in names.items():
            e = by.setdefault(comm, {"first_s": t, "last_s": t, "peak_rss": 0})
            e["last_s"] = t
            e["peak_rss"] = max(e["peak_rss"], r)
        if total > peak:
            peak, peak_at = total, t
        if a.timeline:
            line.append([round(t, 2), total >> 20, sorted(names)])
        time.sleep(a.every)
    wall = time.time() - start
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    res = {
        "label": a.label,
        "cmd": cmd,
        "exit": p.returncode,
        "lock_wait_s": round(start - a.t0, 3) if a.t0 else None,
        "wall_s": round(wall, 3),
        "user_s": round(ru.ru_utime, 2),
        "sys_s": round(ru.ru_stime, 2),
        "max_single_rss_mib": ru.ru_maxrss >> 10,
        "tree_peak_rss_mib": peak >> 20,
        "tree_peak_at_s": round(peak_at, 2),
        "procs": {k: {"first_s": round(v["first_s"], 2),
                      "last_s": round(v["last_s"], 2),
                      "peak_rss_mib": v["peak_rss"] >> 20}
                  for k, v in by.items()},
        "load": open("/proc/loadavg").read().split()[:3],
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(start)),
    }
    if a.timeline:
        res["timeline"] = line
    text = json.dumps(res, indent=1)
    if a.out:
        with open(a.out, "w") as f:
            f.write(text + "\n")
    print(text, file=sys.stderr)
    sys.exit(p.returncode if p.returncode >= 0 else 128 - p.returncode)


if __name__ == "__main__":
    main()
