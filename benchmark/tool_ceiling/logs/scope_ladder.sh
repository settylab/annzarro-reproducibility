#!/bin/bash
# SCope ladder 1M, 2M, 5M: one run-timed call per rung (run.py with RUN_TIMED), stop at the first rung that
# is not ok; one line per rung to logs/scope_ladder.log.
cd "$(dirname "$0")/.."
export RUN_TIMED=$TMPDIR/teamlead-bench/run-timed
NOTE="SCope 1.8.2 (9ae5207) image scope:1.8.2-9ae5207-final (sha256:dd89d344b6c3), linux/amd64 under emulation; server memory: container (docker stats)"
for n in 1000000 2000000 5000000; do
  .venv/bin/python run.py --web --tool scope --variant default --n $n --note "$NOTE" -- \
    .venv/bin/python scope_task.py $DATA_ROOT/tool_ceiling_data/loom/tahoe_first$n.loom {out} --n $n > /dev/null 2>&1
  r=$(grep "^scope_default_run_${n}_r0," results.csv | cut -d, -f1,8,9,10,11,15)
  echo "$(date +%T) $r" >> logs/scope_ladder.log
  case "$r" in *",ok,,True,"*) ;; *) break ;; esac
done
echo "$(date +%T) scope ladder done" >> logs/scope_ladder.log
