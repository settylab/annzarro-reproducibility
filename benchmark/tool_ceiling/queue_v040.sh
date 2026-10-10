#!/bin/bash
# AnnZarro's complete ladder on one release (v0.4.0), from a clean export of the tag:
# every cell 1M-95.6M (real) + 150M and the guard edge 160M (build_stores.py synthetic);
# subset reach (default subset and a 1M subset) 150M-1B. Client and server measured as before.
# Usage: queue_v040.sh SHA
set -u
cd "$(dirname "$0")"
SHA=$1
# one verified install of the tag, shared with scale-benchmarker: its setup_build.sh makes a detached worktree
# at the tag, fetches static/vendor with the tag's own scripts/vendor_assets.py and checks it (--check)
EXE=$(../scale/ceiling/setup_build.sh $SHA v040-bench) || exit 1
PY=.venv/bin/python
TREE=$(git -C $ANNZARRO_SRC rev-parse $SHA^{tree})
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix OLD=$DATA_ROOT/tahoe_scale_ceiling
az() {  # az VARIANT N STORE [extra]
  local v=$1 n=$2 st=$3; shift 3
  $PY run.py --web --tool annzarro --variant $v --n $n --note "AnnZarro v0.4.0 $SHA (tree $TREE), local server" -- \
    $PY annzarro_task.py default $st {out} --exe $EXE --inprocess --version-label $SHA "$@"
}
for n in 1000000 2000000 5000000 10000000 20000000 50000000; do az v040 $n $P/tahoe95_first$n.zarr; done
az v040 95624334 $DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
# every cell past 95.6M on the synthetic stores, up to the guard's refusal (v0.4.0 may move it)
for n in 150000000 160000000 167000000 175000000 182000000 190000000 200000000; do
  az v040_syn $n $OLD/syn_$n.zarr --cat cell_type --gene GENE0
  r=$(grep "^annzarro_v040_syn_run_${n}_r0," results.csv | cut -d, -f8); [ "$r" = ok ] || break
done
for n in 150000000 200000000 300000000 500000000 1000000000; do
  case $n in 300000000) st=$OLD/syn_master_300000000.zarr ;; 1000000000) st=$OLD/syn_master_1000000000.zarr ;; *) st=$OLD/syn_$n.zarr ;; esac
  az v040_sub $n $st --cat cell_type --gene GENE0 --subset absent
  az v040_sub1m $n $st --cat cell_type --gene GENE0 --subset '{"n": 1000000, "seed": 0}'
done
