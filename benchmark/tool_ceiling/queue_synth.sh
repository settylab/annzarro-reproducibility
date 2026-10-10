#!/bin/bash
# AnnZarro v030-preview past 95.6M: real 95.6M, then the synthetic stores.
# Server on this laptop, footprint measured separately (client, server, total).
cd "$(dirname "$0")"
PY=.venv/bin/python
EXE=$ENVS_ROOT/annzarro_v030p_12f93f8/.venv/bin/annzarro
SY=$DATA_ROOT/tool_ceiling_data/synth
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
az() {  # az VARIANT N STORE
  $PY run.py --web --tool annzarro --variant $1 --n $2 --note "AnnZarro v030-preview 12f93f8, local server" -- \
    $PY annzarro_task.py default $3 {out} --exe $EXE --inprocess --version-label 12f93f8
}
az v030p 95624334 $DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
while pgrep -f "build_synth.py" >/dev/null; do sleep 60; done
for n in ${SIZES:-150000000 200000000}; do
  [ -d $SY/synth_tahoe_$n.zarr ] || { echo "no store $n"; break; }
  az v030p_synth $n $SY/synth_tahoe_$n.zarr
  last_ok || break
done
