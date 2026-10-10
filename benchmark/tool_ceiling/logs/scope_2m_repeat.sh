#!/bin/bash
cd "$(dirname "$0")/.."
export RUN_TIMED=$TMPDIR/teamlead-bench/run-timed
NOTE="SCope 1.8.2 (9ae5207) image scope:1.8.2-9ae5207-final (sha256:dd89d344b6c3), linux/amd64 under emulation; server memory: container (docker stats); repeat of 2M with JS-heap series"
.venv/bin/python run.py --web --tool scope --variant default --n 2000000 --run 1 --note "$NOTE" -- \
  .venv/bin/python scope_task.py $DATA_ROOT/tool_ceiling_data/loom/tahoe_first2000000.loom {out} --n 2000000 --heap-series > /dev/null 2>&1
echo "$(date +%T) $(grep '^scope_default_run_2000000_r1,' results.csv | cut -d, -f1,8,9,10,11,15) | done" >> logs/scope_ladder.log
