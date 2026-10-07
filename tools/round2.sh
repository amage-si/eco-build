#!/bin/sh
# round2.sh OUT.jsonl — the edit cycle with stable units (eco's default).
# snap0: libraries at fixed commits; snap1: a Mokko theme color changed
# (value edit); snap2: a Mokko helper def added and called (logic edit).
set -eu
out=$1
here=$(dirname "$(readlink -f "$0")")
eco="$here/../eco"
w="$here/../.work"
run() { echo "## $*" >&2; "$eco" "$@" --json "$out"; }

for who in "" "--official"; do
  "$eco" cache --clean
  # shellcheck disable=SC2086
  run build demo --root "$w/snap0" $who     # cold
  run build demo --root "$w/snap0" $who     # no change
  run build demo --root "$w/snap1" $who     # value edit
  run build demo --root "$w/snap2" $who     # logic edit
  run build demo --root "$w/snap0" $who     # back (cached)
done

# suites: cold (empty cache) then again with no change
for who in "" "--official"; do
  "$eco" cache --clean
  for t in runika-tests chromi-tests voltra-tests; do
    # shellcheck disable=SC2086
    run test "$t" --root "$w/snap0" $who
    run test "$t" --root "$w/snap0" $who
  done
done
