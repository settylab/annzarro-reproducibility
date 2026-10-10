#!/bin/bash
# napari-spatialdata up the ladder, after Kana: allpoints (every cell, POINT_THRESHOLD
# raised) and sub100k (its default 100,000-point subsample), each until its first failure.
cd "$(dirname "$0")"
PY=.venv/bin/python NP=$DEMO_ROOT/napari-spatialdata/.venv/bin/python D=$DATA_ROOT/tool_ceiling_data
while pgrep -f "queue_fixed.sh|queue_kana.sh|queue_subset.sh|queue_guard_r1.sh" >/dev/null; do sleep 60; done
mkdir -p $D/sdata
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
sdata() {  # the SpatialData input for N, built once (conversion row)
  local n=$1 z=$D/sdata/first$1.zarr
  [ -d $z ] || $PY run.py --tool napari --variant to_sdata --phase convert --n $n --timeout 7200 -- \
      $NP to_sdata.py $D/h5ad/tahoe_first$n.h5ad $z
  [ -d $z ]
}
for v in allpoints sub100k; do
  flag=""; [ $v = allpoints ] && flag=--all-points
  for n in 1000000 2000000 5000000 10000000 20000000 50000000 95624334; do
    [ -f $D/h5ad/tahoe_first$n.h5ad ] || { echo "no h5ad $n"; break; }
    sdata $n || break
    $PY run.py --tool napari --variant $v --n $n -- $NP napari_task.py $D/sdata/first$n.zarr {out} --n $n $flag
    last_ok || break
  done
done
