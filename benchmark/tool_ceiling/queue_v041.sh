#!/bin/bash
# AnnZarro's ladder on v0.4.1 (notes/v041_remeasure_plan.md step 2), from the tag's clean build, one rung per
# call of run.py, each rung one run-timed call (RUN_TIMED: exclusive bench lock + timing marker, <= 30 min):
#   main     every cell 1M-95.6M (real, v041); synthetic every cell from 150M up to the guard's refusal
#            (v041_syn: 150M-200M prefixes, 250M, 300M master, 500M); subset reach 150M-1.5B (v041_sub default
#            subset, v041_sub1m a 1M subset)
#   noguard  every cell with ui.memory.enforce off and the JS heap logged per sample (v041_noguard) at 250M,
#            300M and 500M (500M asked by scale-fixes: v0.4.1 draws 200M; the guard's 200M cap is the largest
#            size tested). Free RAM is checked before each rung (500M: ~34 GB renderer expected).
#   profile  1B server, the default-subset requests one at a time (profile_1b_subset_requests.py)
# Runs from this checkout. Usage: queue_v041.sh main|noguard|profile
set -u
cd "$(dirname "$0")"
SHA=78c9da657ecbff30163fd29055f0e6b10e915c5c   # tag v0.4.1
SP=$TMPDIR
export RUN_TIMED=$SP/teamlead-bench/run-timed
EXE=$ANNZARRO_SRC/.venv-bench/bin/annzarro   # setup_build.sh 78c9da6 v041-bench
PY=.venv/bin/python
TREE=$(git -C $ANNZARRO_SRC rev-parse $SHA^{tree})
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix OLD=$DATA_ROOT/tahoe_scale_ceiling
"$(dirname $EXE)/python" -c "import annzarro, sys; sys.exit(annzarro.__version__ != '0.4.1')" || { echo "not 0.4.1: $EXE" >&2; exit 1; }
az() {  # az VARIANT N STORE [extra]
  local v=$1 n=$2 st=$3; shift 3
  $PY run.py --web --tool annzarro --variant $v --n $n --note "AnnZarro v0.4.1 $SHA (tree $TREE), local server" -- \
    $PY annzarro_task.py default $st {out} --exe $EXE --inprocess --version-label $SHA "$@"
}
status() { grep "^annzarro_$1_run_$2_r0," results.csv | tail -1 | cut -d, -f8; }
store() {  # the masters for 300M, 1B and 2B, else the prefix store
  case $1 in 300000000|1000000000|2000000000) echo $OLD/syn_master_$1.zarr ;; *) echo $OLD/syn_$1.zarr ;; esac
}
free_gb() { echo $(( $(sysctl -n kern.memorystatus_level) * $(sysctl -n hw.memsize) / 100 / 1073741824 )); }
log() { echo "$(date +%T) $*" >> logs/v041.log; }
case ${1:?main|noguard|profile} in
main)
  for n in 1000000 2000000 5000000 10000000 20000000 50000000; do
    [ -n "$(status v041 $n)" ] || az v041 $n $P/tahoe95_first$n.zarr; log "v041 $n $(status v041 $n)"
  done
  [ -n "$(status v041 95624334)" ] || az v041 95624334 $DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
  log "v041 95624334 $(status v041 95624334)"
  for n in 150000000 160000000 167000000 175000000 182000000 190000000 200000000 250000000 300000000 500000000; do
    [ -n "$(status v041_syn $n)" ] || az v041_syn $n $(store $n) --cat cell_type --gene GENE0
    r=$(status v041_syn $n); log "v041_syn $n $r"; [ "$r" = ok ] || break
  done
  for n in 150000000 200000000 300000000 500000000 1000000000 1250000000 1400000000 1500000000; do
    st=$(store $n)
    [ -n "$(status v041_sub $n)" ] || az v041_sub $n $st --cat cell_type --gene GENE0 --subset absent
    [ -n "$(status v041_sub1m $n)" ] || az v041_sub1m $n $st --cat cell_type --gene GENE0 --subset '{"n": 1000000, "seed": 0}'
    log "v041_sub $n $(status v041_sub $n) / sub1m $(status v041_sub1m $n)"
  done ;;
noguard)
  for n in 250000000 300000000 500000000; do
    [ -n "$(status v041_noguard $n)" ] && continue
    f=$(free_gb); log "noguard $n: free ${f} GB before"
    [ $f -ge 60 ] || { log "noguard $n: skipped, only ${f} GB free"; continue; }
    az v041_noguard $n $(store $n) --cat cell_type --gene GENE0 --guard-off --heap-series
    log "v041_noguard $n $(status v041_noguard $n)"
  done ;;
profile)
  mkdir -p $DATA_ROOT/tool_ceiling_data/probe/prof_home
  TC_EXE=$EXE $RUN_TIMED $PY profile_1b_subset_requests.py > logs/profile_1b_subset_requests_v041.log 2>&1
  log "profile 1b rc=$?" ;;
esac
