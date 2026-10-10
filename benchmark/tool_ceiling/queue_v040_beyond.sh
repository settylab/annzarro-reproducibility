#!/bin/bash
# AnnZarro v0.4.0 past the two budgets, one rung per call (each reported as it ends):
#   noguard N   every cell with ui.memory.enforce off and the JS heap logged per sample
#               (OUT.heap.jsonl; variant v040_noguard; outside FINAL
#               and Fig. 1c), on the build_stores.py synthetic stores of the guarded 150M/160M runs
#   build2b     the 2B synthetic master and its 1.25B/1.4B/1.5B hard-link prefixes, under the
#               bench lock (heavy I/O, not measured)
#   sub N       subset reach (v040_sub and v040_sub1m) at N, as in queue_v040.sh
# Usage: queue_v040_beyond.sh noguard 160000000 | build2b | sub 1250000000
set -u
cd "$(dirname "$0")"
SHA=${SHA:?set SHA to the v0.4.0 tag commit}
EXE=$ANNZARRO_SRC/.venv-bench/bin/annzarro PY=.venv/bin/python   # installed by queue_v040.sh
TREE=$(git -C $ANNZARRO_SRC rev-parse $SHA^{tree})
OLD=$DATA_ROOT/tahoe_scale_ceiling
az() {  # az VARIANT N STORE [extra]
  local v=$1 n=$2 st=$3; shift 3
  $PY run.py --web --tool annzarro --variant $v --n $n --note "AnnZarro v0.4.0 $SHA (tree $TREE), local server" -- \
    $PY annzarro_task.py default $st {out} --exe $EXE --inprocess --version-label $SHA "$@"
}
store() {  # the existing master for 300M and 1B, else the prefix store
  case $1 in 300000000|1000000000|2000000000) echo $OLD/syn_master_$1.zarr ;; *) echo $OLD/syn_$1.zarr ;; esac
}
case $1 in
  noguard)
    az v040_noguard $2 $(store $2) --cat cell_type --gene GENE0 --guard-off --heap-series ;;
  build2b)
    /usr/bin/lockf -k $HOME/.annzarro-bench.lock ../scale/ceiling/.venv/bin/python ../scale/ceiling/build_stores.py \
      $OLD --master-n 2000000000 --sizes 1250000000,1400000000,1500000000 ;;
  sub)
    st=$(store $2)
    az v040_sub $2 $st --cat cell_type --gene GENE0 --subset absent
    az v040_sub1m $2 $st --cat cell_type --gene GENE0 --subset '{"n": 1000000, "seed": 0}' ;;
  *) echo "usage: $0 noguard N | build2b | sub N" >&2; exit 2 ;;
esac
