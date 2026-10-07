#!/bin/sh
# refs.sh ROOT REFDIR — the official build's outputs, for validate.sh:
# each suite built with `bend x.bend -o …` under the build lock and run,
# and the demo's CPU reference frames (900x560, 640x760).
set -eu
root=$1 ref=$2
mkdir -p "$ref"
here=$(dirname "$(readlink -f "$0")")
for t in Runika:tests Chromi:tests Voltra:tests Chromi:gpu_tests Voltra:gpu_tests; do
  lib=${t%%:*} name=${t#*:}
  (cd "$root/$lib" && mkdir -p build &&
    BEND_NO_TELEMETRY=1 flock /tmp/amage-eco-bend-build.lock nice -n 10 \
      bend "$name.bend" -o "build/$name.official" &&
    ./build/"$name".official --threads 2 --gpu off > "$ref/$lib-$name.out" 2>&1) || true
  echo "$lib $name: $(grep -c PASS "$ref/$lib-$name.out") PASS lines"
done
cd "$root/Chromi"
BEND_NO_TELEMETRY=1 flock /tmp/amage-eco-bend-build.lock nice -n 10 \
  bend examples/eco/reference.bend -o build/reference.official
for sz in "900 560" "640 760"; do
  # shellcheck disable=SC2086
  ./build/reference.official $sz --threads 2 --gpu off > /dev/null
done
sha256sum build/eco-reference-640x760.ppm build/eco-reference-900x560.ppm > "$ref/reference-ppm.sha256"
cat "$ref/reference-ppm.sha256"
