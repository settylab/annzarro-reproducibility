#!/bin/bash
# napari allpoints from 1M (r2: r1 waited on the screen lock), after the standby pause lifts.
cd "$(dirname "$0")"
PY=.venv/bin/python NP=$DEMO_ROOT/napari-spatialdata/.venv/bin/python D=$DATA_ROOT/tool_ceiling_data
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
for n in 1000000 2000000 5000000 10000000; do
  rep=0; [ $n = 1000000 ] && rep=2
  $PY run.py --tool napari --variant allpoints --n $n --run $rep -- $NP napari_task.py $D/sdata/first$n.zarr {out} --n $n --all-points
  last_ok || break
done
