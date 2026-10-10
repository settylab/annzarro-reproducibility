#!/bin/bash
# The Loupe inputs 5M-20M, built while the desktop ladders run (operator request, 2026-10-05):
# no bench lock (no timed benchmark runs while DESKTOP_SESSION_ACTIVE exists), one build at a time.
# Memory guard: a build starts only when free + inactive memory exceeds its estimated peak plus
# 20 GiB (estimates from the measured 1M/2M peaks, about 3 GiB per million cells plus 3).
# Each finished file gets a .done marker, which desktop_watch.py --wait-inputs waits for.
set -u
cd "$(dirname "$0")"
OUT=$HOME/annzarro_compare/loupe/session_v031/cloupe
R=$HOME/annzarro_compare/_mamba/envs/loupe/bin/Rscript
avail_gib() { vm_stat | awk '/page size of/ {ps=$8} /Pages free/ {f=$3} /Pages inactive/ {i=$3} END {printf "%d", (f+i)*ps/2^30}'; }
while pgrep -f "loupe_build.R" >/dev/null; do sleep 10; done   # a build started earlier finishes first
for n in 5000000 10000000 20000000; do
  if [ -s $OUT/tahoe_first$n.cloupe ] && grep -q "cloupe: $n cells" logs/loupe_build_$n.log 2>/dev/null; then
    date > $OUT/tahoe_first$n.cloupe.done; echo "already built $n"; continue
  fi
  need=$(( 3 * n / 1000000 + 3 + 20 ))
  until [ "$(avail_gib)" -ge $need ]; do sleep 30; done
  {
    echo "build $n started $(date '+%F %T %Z'); concurrent with the desktop ladders (ManiVault/Loupe), no bench lock;"
    echo "free+inactive at start $(avail_gib) GiB, needed $need GiB"
  } > logs/loupe_build_$n.log
  /usr/bin/time -l $R loupe_build.R $DATA_ROOT/tool_ceiling_data/h5ad/tahoe_first$n.h5ad $OUT tahoe_first$n >> logs/loupe_build_$n.log 2>&1 \
    || { echo "build $n failed (logs/loupe_build_$n.log)"; exit 1; }
  date > $OUT/tahoe_first$n.cloupe.done
  echo "built $n: $(grep -E 'cloupe:|maximum resident' logs/loupe_build_$n.log | tr '\n' ' ')"
done
echo "all .cloupe built $(date '+%T')"
