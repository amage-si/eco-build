#!/usr/bin/env python3
"""Summarize a .cpuprofile (V8/JSC format, as written by bun --cpu-prof).

Prints inclusive time per function counted once per sample (so recursion
does not inflate it) and self time, both keyed by name:line.

    cpuprof.py FILE.cpuprofile [--top N] [--under NAME]

--under NAME restricts to samples whose stack contains a frame named NAME.
"""
import json
import sys
from collections import Counter


def main():
    path = sys.argv[1]
    top = 40
    under = None
    args = sys.argv[2:]
    while args:
        a = args.pop(0)
        if a == "--top":
            top = int(args.pop(0))
        elif a == "--under":
            under = args.pop(0)
    prof = json.load(open(path))
    nodes = {n["id"]: n for n in prof["nodes"]}
    parent = {}
    for n in prof["nodes"]:
        for c in n.get("children", []):
            parent[c] = n["id"]

    def label(n):
        cf = n["callFrame"]
        url = cf.get("url", "").rsplit("/", 1)[-1]
        name = cf.get("functionName") or "(anon)"
        return f"{name} {url}:{cf.get('lineNumber', -1) + 1}"

    incl, self_t = Counter(), Counter()
    total = 0.0
    stacks = {}
    for sid, dt in zip(prof["samples"], prof["timeDeltas"]):
        if sid not in stacks:
            st, i = [], sid
            while i in nodes:
                st.append(label(nodes[i]))
                i = parent.get(i)
            stacks[sid] = st
        st = stacks[sid]
        if under and not any(s.startswith(under + " ") for s in st):
            continue
        dt = max(dt, 0) / 1e6
        total += dt
        self_t[st[0]] += dt
        for s in set(st):
            incl[s] += dt
    print(f"total {total:.2f}s")
    print("-- inclusive (once per sample)")
    for k, v in incl.most_common(top):
        print(f"{v:8.2f}s {100 * v / total:5.1f}%  {k}")
    print("-- self")
    for k, v in self_t.most_common(top):
        print(f"{v:8.2f}s {100 * v / total:5.1f}%  {k}")


if __name__ == "__main__":
    main()
