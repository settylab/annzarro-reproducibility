#!/bin/bash
# Successor to loupe_build_rest.sh after 5M (operator priority, 2026-10-05 20:5x): wait for the
# running 10M build (pid given) and mark it .done; then build 20M alone. The 20M build starts only with
# >= 110 GiB free + inactive: the measured build peaks (1M 5.9, 2M 9.0, 5M 27.1 GB) put it near
# 100-110 GB, so the earlier 3 GiB/M estimate (83 GiB) was too low. Untimed preparation; the ladder's
# memory comes from memmon on Loupe, so this does not touch any measured number.
set -u
cd "$(dirname "$0")"
OUT=$HOME/annzarro_compare/loupe/session_v031/cloupe
R=$HOME/annzarro_compare/_mamba/envs/loupe/bin/Rscript
avail_gib() { vm_stat | awk '/page size of/ {ps=$8} /Pages free/ {f=$3} /Pages inactive/ {i=$3} END {printf "%d", (f+i)*ps/2^30}'; }
while [ -n "${1:-}" ] && kill -0 $1 2>/dev/null; do sleep 10; done
if grep -q "cloupe: 10000000 cells" logs/loupe_build_10000000.log; then
  date > $OUT/tahoe_first10000000.cloupe.done
  echo "built 10000000: $(grep -E 'cloupe:|maximum resident' logs/loupe_build_10000000.log | tr '\n' ' ')"
else
  echo "build 10000000 failed (logs/loupe_build_10000000.log)"; exit 1
fi
n=20000000; need=110
until [ "$(avail_gib)" -ge $need ]; do sleep 30; done
{
  echo "build $n started $(date "+%F %T %Z"); alone, after the desktop session ended, under the bench lock (other benchmarks resumed);"
  echo "moot for the ceiling: Loupe failed at 10M on gene colouring; kept as evidence about the LoupeR input path (dgCMatrix near 2^31 values);"
  echo "untimed input preparation: the ladder's memory is memmon on the Loupe app, so this build touches no measured number;"
  echo "free+inactive at start $(avail_gib) GiB, needed $need GiB"
} > logs/loupe_build_$n.log
/usr/bin/lockf -k $HOME/.annzarro-bench.lock /usr/bin/time -l $R loupe_build.R $DATA_ROOT/tool_ceiling_data/h5ad/tahoe_first$n.h5ad $OUT tahoe_first$n >> logs/loupe_build_$n.log 2>&1 \
  || { echo "build $n failed (logs/loupe_build_$n.log)"; exit 1; }
date > $OUT/tahoe_first$n.cloupe.done
echo "built $n: $(grep -E 'cloupe:|maximum resident' logs/loupe_build_$n.log | tr '\n' ' ')"
echo "all .cloupe built $(date '+%T')"
