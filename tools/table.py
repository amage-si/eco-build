#!/usr/bin/env python3
"""Print the eco builds recorded in a JSON-lines file as a markdown table.

    table.py results/round1.jsonl
"""
import json
import sys


def main():
    rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
    print("| # | target | compiler | mode | total | peak | units compiled | load |")
    print("|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        who = "fork" if r.get("fork") else "official"
        if r.get("flat_max"):
            who += f", flat {r['flat_max']}"
        units = next((n for w, _, n in r["phases"] if w == "clang"), "one unit -O3")
        units = units.split(" units compiled")[0] if "units compiled" in units else units
        print(f"| {i} | {r['target']} | {who} | {r['mode']} | {r['total_s']:.1f} s"
              f" | {r['peak_mib'] / 1024:.2f} GiB | {units} | {r.get('load', '')} |")


if __name__ == "__main__":
    main()
