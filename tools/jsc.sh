#!/bin/sh
# jsc.sh ROOT — time the fork's C emission of the demo under JavaScriptCore
# settings (heap sizing and JIT thresholds), twice each, under the lock.
set -eu
root=$1
here=$(dirname "$(readlink -f "$0")")
fork="$here/../../bend-fork/src/bend2/main.ts"
cd "$root/Chromi"
for v in "cap2400:BUN_JSC_forceRAMSize=2516582400" "nocap:" \
         "cap3200:BUN_JSC_forceRAMSize=3355443200" \
         "cap2400-jit0.3:BUN_JSC_forceRAMSize=2516582400 BUN_JSC_jitPolicyScale=0.3"; do
  name=${v%%:*} envs=${v#*:}
  for i in 1 2; do
    # shellcheck disable=SC2086
    "$here/locked.sh" "$here/../results/jsc-$name-$i.json" "jsc $name" -- \
      env BEND_NO_TELEMETRY=1 BEND_FLAT_MAX=32 $envs bun "$fork" \
      examples/eco/main.bend -o /tmp/eco-jsc.c > /dev/null 2>&1
    python3 -c "import json; d=json.load(open('$here/../results/jsc-$name-$i.json')); print('$name', d['wall_s'], 's', d['tree_peak_rss_mib'], 'MiB', 'load', d['load'][0])"
  done
done
