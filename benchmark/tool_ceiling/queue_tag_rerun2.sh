#!/bin/bash
# v0.3.0 (3fb6826) server footprint and local-app totals: real 95.6M, synthetic 150M (drawn)
# and 160M (refused) with every cell; subset reach at 1B (default subset and 1M subset).
cd "$(dirname "$0")"
PY=.venv/bin/python EXE=$ENVS_ROOT/annzarro_v030_3fb6826/.venv/bin/annzarro OLD=$DATA_ROOT/tahoe_scale_ceiling
az() {  # az VARIANT N STORE [extra]
  local v=$1 n=$2 st=$3; shift 3
  $PY run.py --web --tool annzarro --variant $v --n $n --note "AnnZarro v0.3.0 3fb6826, local server" -- \
    $PY annzarro_task.py default $st {out} --exe $EXE --inprocess --version-label 3fb6826 "$@"
}
az v030_tag 95624334 $DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
for n in 150000000 160000000; do az v030_tag $n $OLD/syn_$n.zarr --cat cell_type --gene GENE0; done
az v030_tag_sub 1000000000 $OLD/syn_master_1000000000.zarr --cat cell_type --gene GENE0 --subset absent
az v030_tag_sub1m 1000000000 $OLD/syn_master_1000000000.zarr --cat cell_type --gene GENE0 --subset '{"n": 1000000, "seed": 0}'
