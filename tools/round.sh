#!/bin/sh
# round.sh OUT.jsonl — the measurement round behind README's Results table.
# Snapshots under .work: snap0 (the libraries at fixed commits), snap1 (a
# Mokko theme color changed: a value edit), snap2 (a Mokko helper def
# added and called on the button's text color: a logic edit that adds a
# def and its segment). Each eco line takes the build lock.
set -eu
out=$1
here=$(dirname "$(readlink -f "$0")")
eco="$here/../eco"
w="$here/../.work"
run() { echo "## $*" >&2; "$eco" "$@" --json "$out"; }

# official bend through eco
"$eco" cache --clean
run build demo --root "$w/snap0" --official          # cold
run build demo --root "$w/snap0" --official          # no change
run build demo --root "$w/snap1" --official          # value edit
run build demo --root "$w/snap2" --official          # logic edit
# fork (dev default: flat-max 32)
"$eco" cache --clean
run build demo --root "$w/snap0"                     # cold
run build demo --root "$w/snap0"                     # no change
run build demo --root "$w/snap1"                     # value edit
run build demo --root "$w/snap2"                     # logic edit
# release (official, one unit, -O3)
run build demo --root "$w/snap0" --release
# suites, cold then warm, official and fork
"$eco" cache --clean
for t in runika-tests chromi-tests voltra-tests; do
  run test "$t" --root "$w/snap0" --official
  run test "$t" --root "$w/snap0" --official
done
"$eco" cache --clean
for t in runika-tests chromi-tests voltra-tests; do
  run test "$t" --root "$w/snap0"
  run test "$t" --root "$w/snap0"
done
