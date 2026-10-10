#!/bin/bash
# CELLxGENE --backed from 2M again (r1): the r0 run at 2M timed out waiting for
# the gene suggestion list (harness; fixed by retries in web_task.py).
cd "$(dirname "$0")"
D=$DATA_ROOT/tool_ceiling_data
PY=.venv/bin/python
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
for n in 2000000 5000000 10000000 20000000 50000000 95624334; do
  f=$D/h5ad/tahoe_first$n.h5ad; until [ -f $f ]; do sleep 60; done
  $PY run.py --web --tool cellxgene --variant backed --n $n --run 1 -- $PY web_task.py cellxgene backed $f {out} --n $n --port 8939
  last_ok || break
done
