#!/bin/bash
# Loupe after ManiVault, as DESKTOP_PROMPT_v031.md orders it. ManiVault's sizes come first: each
# .cloupe is built (under the bench lock; input preparation, not measured) only in a gap the
# ManiVault watcher offers between two sizes (.gap_<N>_<k> in its channel; one build per gap,
# removing the file hands the gap back), and only up to 2M; 5M and up wait until the ManiVault
# ladder has stopped.
# Then the Loupe ladder runs through its own file channel.
set -u
cd "$(dirname "$0")"
MV=$HOME/annzarro_compare/manivault/session_v031
OUT=$HOME/annzarro_compare/loupe/session_v031/cloupe
R=$HOME/annzarro_compare/_mamba/envs/loupe/bin/Rscript
SIZES="250000 500000 1000000 2000000 5000000 10000000 20000000"
built=""
for n in $SIZES; do
  if [ ! -s $OUT/tahoe_first$n.cloupe ]; then
    g=""
    # 2M and below in a ManiVault gap; larger builds take minutes, so they wait for its stop
    until [ -e $MV/stop ]; do
      [ $n -gt 2000000 ] && { rm -f $MV/.gap_*; sleep 2; continue; }   # hand any gap straight back
      g=$(ls $MV/.gap_* 2>/dev/null | head -1)
      [ -n "$g" ] && break
      sleep 2
    done
    /usr/bin/lockf -k $HOME/.annzarro-bench.lock /usr/bin/time -l $R loupe_build.R \
      $DATA_ROOT/tool_ceiling_data/h5ad/tahoe_first$n.h5ad $OUT tahoe_first$n > logs/loupe_build_$n.log 2>&1
    rc=$?
    [ -n "$g" ] && rm -f "$g"   # the gap goes back to ManiVault
    [ $rc -eq 0 ] || { echo "build $n failed (logs/loupe_build_$n.log)"; break; }
  fi
  echo "built $n: $(grep -E 'cloupe:|maximum resident' logs/loupe_build_$n.log | tr '\n' ' ')"
  built="$built${built:+,}$n"
done
until [ -e $MV/stop ]; do sleep 30; done
echo "ManiVault ladder stopped; Loupe ladder on $built"
[ -n "$built" ] && .venv/bin/python -u desktop_watch.py --tool loupe --app "Loupe Browser 9" --sizes $built
