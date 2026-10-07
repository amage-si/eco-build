#!/usr/bin/env python3
"""Run shell commands in parallel; report each one's wall, CPU and max RSS.

    par.py 'label1=cmd one' 'label2=cmd two' ...

Uses wait4, so each line's max RSS is that command's largest process.
"""
import os
import shlex
import sys
import time


def main():
    jobs = {}
    for arg in sys.argv[1:]:
        label, cmd = arg.split("=", 1)
        pid = os.spawnvp(os.P_NOWAIT, "sh", ["sh", "-c", cmd])
        jobs[pid] = (label, time.time())
    bad = 0
    while jobs:
        pid, status, ru = os.wait4(-1, 0)
        if pid not in jobs:
            continue
        label, t0 = jobs.pop(pid)
        code = os.waitstatus_to_exitcode(status)
        bad |= code != 0
        print(f"{label}: exit={code} wall={time.time() - t0:.2f}s "
              f"user={ru.ru_utime:.2f}s sys={ru.ru_stime:.2f}s "
              f"maxrss={ru.ru_maxrss >> 10}MiB", flush=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
