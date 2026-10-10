#!/bin/bash
# Kana (hosted live build) up the N ladder, after the AnnZarro 120f322 ladder.
cd "$(dirname "$0")"
PY=.venv/bin/python D=$DATA_ROOT/tool_ceiling_data
while pgrep -f queue_fixed.sh >/dev/null; do sleep 60; done
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
for n in 1000000 2000000 5000000 10000000 20000000 50000000 95624334; do
  f=$D/h5ad/tahoe_first$n.h5ad; [ -f $f ] || { echo "no h5ad $n"; break; }
  $PY run.py --web --tool kana --variant default --n $n -- $PY web_task.py kana default $f {out} --n $n
  last_ok || break
done
