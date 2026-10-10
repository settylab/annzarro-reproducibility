#!/bin/bash
# AnnZarro v030-preview at SHA (after the memory-guard fix): env snapshot, the real
# ladder 1M-95.6M, tiled synthetic 150M/200M, and the guard's edge on
# build_stores.py's synthetic stores (hard-link prefixes of the 300M master).
# Usage: queue_fixed.sh SHA
set -u
cd "$(dirname "$0")"
SHA=$1
W=$ANNZARRO_SRC
E=$ENVS_ROOT/annzarro_v030p_$SHA
PY=.venv/bin/python
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
if [ ! -x $E/.venv/bin/annzarro ]; then
  mkdir -p $E && git -C $W archive $SHA | tar -x -C $E && cp -R $W/static/vendor $E/static/ &&
  (cd $E && uv venv -q -p 3.11 .venv && VIRTUAL_ENV=$E/.venv uv pip install -q -e .) || exit 1
fi
EXE=$E/.venv/bin/annzarro
OLD=$DATA_ROOT/tahoe_scale_ceiling
$L benchmark/scale/ceiling/.venv/bin/python \
  benchmark/scale/ceiling/build_stores.py $OLD --sizes 160000000,167000000 --master-n 300000000
az() {  # az VARIANT N STORE [extra]
  local v=$1 n=$2 st=$3; shift 3
  $PY run.py --web --tool annzarro --variant $v --n $n --note "AnnZarro v030-preview $SHA, local server" -- \
    $PY annzarro_task.py default $st {out} --exe $EXE --inprocess --version-label $SHA "$@"
}
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix
for n in 1000000 2000000 5000000 10000000 20000000 50000000; do az v030 $n $P/tahoe95_first$n.zarr; done
az v030 95624334 $DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
for n in 150000000 200000000; do az v030_synth $n $DATA_ROOT/tool_ceiling_data/synth/synth_tahoe_$n.zarr; done
for n in 150000000 160000000 167000000 175000000 182000000 200000000; do
  az v030_syn $n $OLD/syn_$n.zarr --cat cell_type --gene GENE0
done
