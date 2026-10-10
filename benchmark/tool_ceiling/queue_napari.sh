#!/bin/bash
# napari-spatialdata up the N ladder (after Kana): to_sdata.py (conversion, charged to
# the tool), then napari_task.py; the whole process is the client.
cd "$(dirname "$0")"
PY=.venv/bin/python NP=$DEMO_ROOT/napari-spatialdata/.venv/bin/python D=$DATA_ROOT/tool_ceiling_data
while pgrep -f "queue_fixed.sh|queue_kana.sh" >/dev/null; do sleep 60; done
mkdir -p $D/sdata
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
for n in 1000000 2000000 5000000 10000000 20000000; do
  f=$D/h5ad/tahoe_first$n.h5ad z=$D/sdata/first$n.zarr
  if [ ! -d $z ]; then
    $PY run.py --tool napari --variant to_sdata --phase convert --n $n --timeout 7200 -- $NP to_sdata.py $f $z
    last_ok || break
  fi
  $PY run.py --tool napari --variant default --n $n -- $NP napari_task.py $z {out} --n $n
  last_ok || break
done
