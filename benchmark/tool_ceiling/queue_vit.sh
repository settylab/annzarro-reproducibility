#!/bin/bash
# Vitessce up the N ladder on the AnnData zarr stores (no conversion).
cd "$(dirname "$0")"
M=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix
D=$DATA_ROOT/tool_ceiling_data/vitessce
PY=.venv/bin/python
LADDER="${LADDER:-1000000 2000000 5000000 10000000 20000000 50000000 95624334}"
zstore() { [ $1 = 95624334 ] && echo $M || echo $P/tahoe95_first$1.zarr; }
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
for n in $LADDER; do
  $PY vitessce_config.py $(zstore $n) $D/first$n 8937
  $PY run.py --web --tool vitessce --variant default --n $n -- $PY web_task.py vitessce default $D/first$n {out} --n $n --port 8937
  last_ok || break
done
