#!/bin/bash
# TissUUmaps up the ladder (1M as r1; r0 was a harness wait): CSC h5ad per N (to_h5ad.py --csc, indptr int32 while nnz < 2^31,
# then add_colors.py: scanpy's category colours), then the viewer. Stops at the first failure.
cd "$(dirname "$0")"
PY=.venv/bin/python D=$DATA_ROOT/tool_ceiling_data/h5ad_csc M=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
mkdir -p $D
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
for n in 1000000 2000000 5000000 10000000 20000000 50000000 95624334; do
  f=$D/tahoe_first${n}_csc.h5ad
  if [ ! -f $f ]; then
    $PY run.py --tool input_h5ad_csc --variant to_h5ad_csc --phase convert --n $n --timeout 7200 -- \
      .venv-conv/bin/python to_h5ad.py $M $n $f --csc
    last_ok || break
    $PY add_colors.py $f
  fi
  rep=0; [ $n = 1000000 ] && rep=1
  $PY run.py --web --tool tissuumaps --variant default --n $n --run $rep -- $PY web_task.py tissuumaps default $f {out} --n $n --port 8944
  last_ok || break
done
