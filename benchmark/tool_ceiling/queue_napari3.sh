#!/bin/bash
# napari-spatialdata after the layer-wait fix: 1M as r1 (r0 driver bug), then up; both variants.
cd "$(dirname "$0")"
PY=.venv/bin/python NP=$DEMO_ROOT/napari-spatialdata/.venv/bin/python D=$DATA_ROOT/tool_ceiling_data
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
for v in allpoints sub100k; do
  flag=""; [ $v = allpoints ] && flag=--all-points
  for n in 1000000 2000000 5000000 10000000 20000000 50000000 95624334; do
    z=$D/sdata/first$n.zarr; rep=0; [ $n = 1000000 ] && rep=1
    [ -d $z ] || $PY run.py --tool napari --variant to_sdata --phase convert --n $n --timeout 7200 -- \
        $NP to_sdata.py $D/h5ad/tahoe_first$n.h5ad $z
    [ -d $z ] || break
    $PY run.py --tool napari --variant $v --n $n --run $rep -- $NP napari_task.py $z {out} --n $n $flag
    last_ok || break
  done
done
