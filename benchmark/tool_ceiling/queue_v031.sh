#!/bin/bash
# AnnZarro's complete ladder on one release (v0.3.1), from a clean export of the tag:
# every cell 1M-95.6M (real) + 150M and the guard edge 160M (build_stores.py synthetic);
# subset reach (default subset and a 1M subset) 150M-1B. Client and server measured as before.
# Usage: queue_v031.sh SHA
set -u
cd "$(dirname "$0")"
SHA=$1
E=$ENVS_ROOT/annzarro_v031_$SHA
VENDOR=$ANNZARRO_SRC/static/vendor   # git-excluded vendored JS
if [ ! -x $E/.venv/bin/annzarro ]; then
  mkdir -p $E && git -C $ANNZARRO_SRC archive $SHA | tar -x -C $E && cp -R $VENDOR $E/static/ &&
  (cd $E && uv venv -q -p 3.11 .venv && VIRTUAL_ENV=$E/.venv uv pip install -q -e .) || exit 1
fi
EXE=$E/.venv/bin/annzarro PY=.venv/bin/python
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix OLD=$DATA_ROOT/tahoe_scale_ceiling
az() {  # az VARIANT N STORE [extra]
  local v=$1 n=$2 st=$3; shift 3
  $PY run.py --web --tool annzarro --variant $v --n $n --note "AnnZarro v0.3.1 $SHA, local server" -- \
    $PY annzarro_task.py default $st {out} --exe $EXE --inprocess --version-label $SHA "$@"
}
for n in 1000000 2000000 5000000 10000000 20000000 50000000; do az v031 $n $P/tahoe95_first$n.zarr; done
az v031 95624334 $DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
for n in 150000000 160000000; do az v031_syn $n $OLD/syn_$n.zarr --cat cell_type --gene GENE0; done
for n in 150000000 200000000 300000000 500000000 1000000000; do
  case $n in 300000000) st=$OLD/syn_master_300000000.zarr ;; 1000000000) st=$OLD/syn_master_1000000000.zarr ;; *) st=$OLD/syn_$n.zarr ;; esac
  az v031_sub $n $st --cat cell_type --gene GENE0 --subset absent
  az v031_sub1m $n $st --cat cell_type --gene GENE0 --subset '{"n": 1000000, "seed": 0}'
done
