#!/bin/bash
# Scanpy and Seurat up the N ladder: each variant climbs until its first
# non-ok run. Inputs are built on first use. Every run takes the bench lock
# itself (run.py), so other queues interleave between runs.
cd "$(dirname "$0")"
M=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix
D=$DATA_ROOT/tool_ceiling_data
R=$ENVS_ROOT/rceiling/bin/Rscript
PY=.venv/bin/python
LADDER="${LADDER:-1000000 2000000 5000000 10000000 20000000 50000000 95624334}"

h5ad() {  # path of the h5ad for N, built if missing
  local f=$D/h5ad/tahoe_first$1.h5ad
  [ -f $f ] || $PY run.py --tool input_h5ad --variant to_h5ad --phase convert --n $1 -- \
      .venv-conv/bin/python to_h5ad.py $M $1 $f >&2
  echo $f
}
zstore() { [ $1 = 95624334 ] && echo $M || echo $P/tahoe95_first$1.zarr; }
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }

for v in ${VARIANTS:-scanpy:default scanpy:backed scanpy:lazy_h5ad scanpy:lazy_zarr seurat:default seurat:bpcells}; do
  tool=${v%%:*}; var=${v#*:}
  for n in $LADDER; do
    case $v in
      scanpy:lazy_zarr) in=$(zstore $n) ;;
      *) in=$(h5ad $n) ;;
    esac
    case $tool in
      scanpy) $PY run.py --tool scanpy --variant $var --n $n -- $PY scanpy_task.py $var $in {out} ;;
      seurat)
        if [ $var = bpcells ]; then
          bp=$D/bpcells/first$n
          [ -d $bp ] || $PY run.py --tool seurat --variant bpcells_write --phase convert --n $n -- \
              $R seurat_task.R bpcells_write $in {out} $bp
          last_ok || break
          $PY run.py --tool seurat --variant bpcells --n $n -- $R seurat_task.R bpcells $in {out} $bp
        else
          $PY run.py --tool seurat --variant $var --n $n -- $R seurat_task.R $var $in {out}
        fi ;;
    esac
    last_ok || break
  done
done
