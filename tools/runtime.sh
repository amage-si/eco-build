#!/bin/sh
# runtime.sh ROOT — build the demo's CPU reference renderer four ways and
# compare the frames (must be the same bytes) and the paint times.
#   release : official bend, one unit, -O3 (what `bend -o` builds)
#   dev     : fork, BEND_FLAT_MAX=32, stable units, -O1 (eco's default)
#   dev -O0 : the same at -O0
#   dev off : official bend, stable units, -O1
set -eu
root=$1
here=$(dirname "$(readlink -f "$0")")
eco="$here/../eco"
cd "$root/Chromi"
for v in "release:--release" "dev:" "dev-O0:-O 0" "dev-official:--official"; do
  name=${v%%:*}; flags=${v#*:}
  # shellcheck disable=SC2086
  "$eco" build reference --root "$root" $flags >/dev/null
  cp build/reference "build/reference-$name"
done
for name in release dev dev-O0 dev-official; do
  rm -f build/eco-reference-900x560.ppm
  times="" walls=""
  for i in 1 2 3 4 5; do
    s=$(date +%s%N)
    t=$(./build/reference-$name 900 560 --threads 2 --gpu off | sed -n 's/.*painted in \([0-9]*\) ms.*/\1/p')
    e=$(date +%s%N)
    times="$times $t" walls="$walls $(( (e - s) / 1000000 ))"
  done
  echo "$name: paint ms$times; whole run ms$walls; frame $(sha256sum build/eco-reference-900x560.ppm | cut -c1-16); binary $(stat -c %s build/reference-$name) bytes"
done
