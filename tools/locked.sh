#!/bin/sh
# locked.sh OUT.json LABEL -- cmd...
# Runs cmd under the shared Eco build lock at nice 10, sampled by treemon.
# The time spent waiting for the lock is reported apart (lock_wait_s).
set -eu
out=$1 label=$2
shift 2
[ "${1:-}" = "--" ] && shift
here=$(dirname "$(readlink -f "$0")")
t0=$(date +%s.%N)
exec flock /tmp/amage-eco-bend-build.lock nice -n 10 \
  python3 "$here/treemon.py" --t0 "$t0" --label "$label" --out "$out" --timeline -- "$@"
