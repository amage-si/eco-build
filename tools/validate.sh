#!/bin/sh
# validate.sh ROOT REFDIR [eco flags...] — build every suite and the demo's
# CPU reference renderer with eco, run them, and compare with the outputs
# of the official build (REFDIR/<Lib>-<suite>.out, REFDIR/reference-ppm.sha256).
set -eu
root=$1 ref=$2
shift 2
here=$(dirname "$(readlink -f "$0")")
eco="$here/../eco"
bad=0
for t in runika-tests:Runika:tests chromi-tests:Chromi:tests voltra-tests:Voltra:tests \
         chromi-gpu-tests:Chromi:gpu_tests voltra-gpu-tests:Voltra:gpu_tests; do
  target=${t%%:*} rest=${t#*:} lib=${rest%%:*} name=${rest#*:}
  "$eco" build "$target" --root "$root" "$@" > /dev/null
  (cd "$root/$lib" && ./build/"$name" --threads 2 --gpu off > build/"$name".eco.out 2>&1) || true
  if cmp -s "$root/$lib/build/$name.eco.out" "$ref/$lib-$name.out"; then
    echo "same output: $target"
  else
    echo "DIFFERENT: $target"; bad=1
  fi
done
"$eco" build reference --root "$root" "$@" > /dev/null
cd "$root/Chromi"
for sz in "900 560" "640 760"; do
  # shellcheck disable=SC2086
  ./build/reference $sz --threads 2 --gpu off > /dev/null
done
if sha256sum build/eco-reference-640x760.ppm build/eco-reference-900x560.ppm | cmp -s - "$ref/reference-ppm.sha256"; then
  echo "same frames: reference 900x560, 640x760"
else
  echo "DIFFERENT: reference frames"; bad=1
fi
exit $bad
