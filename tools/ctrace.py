#!/usr/bin/env python3
"""Summarize a clang -ftime-trace JSON: totals per event name and the
functions that cost the most (events whose detail names a function).

    ctrace.py TRACE.json [--top N]
"""
import json
import sys
from collections import Counter, defaultdict


def main():
    path = sys.argv[1]
    top = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[2] == "--top" else 25
    tr = json.load(open(path))
    evs = [e for e in tr["traceEvents"] if e.get("ph") == "X"]
    totals = {e["name"][len("Total "):]: e["dur"] / 1e6
              for e in evs if e["name"].startswith("Total ")}
    print("-- totals (s)")
    for k, v in sorted(totals.items(), key=lambda kv: -kv[1])[:top]:
        print(f"{v:8.2f}  {k}")
    per_fn = defaultdict(Counter)
    for e in evs:
        d = e.get("args", {}).get("detail")
        if d and not e["name"].startswith("Total "):
            per_fn[e["name"]][d] += e["dur"] / 1e6
    for name in ("OptFunction", "CodeGen Function", "RunLoopPass",
                 "Machine function"):
        if name in per_fn:
            c = per_fn[name]
            s = sum(c.values())
            print(f"-- {name}: {len(c)} functions, {s:.2f}s")
            for k, v in c.most_common(top):
                print(f"{v:8.3f}  {k}")
    names = Counter({k: sum(c.values()) for k, c in per_fn.items()})
    print("-- events with a detail, by name (s)")
    for k, v in names.most_common(top):
        print(f"{v:8.2f}  {k} ({len(per_fn[k])} details)")


if __name__ == "__main__":
    main()
