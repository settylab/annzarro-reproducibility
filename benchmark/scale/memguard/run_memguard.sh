#!/bin/bash
# The browser memory guard's measurements (annzarro dominik/memory-guard).
# Every run holds the shared bench lock; ps (python/annzarro/chrome, and the
# user's own Chrome) is appended to $R/ps_memguard.txt at its start.
# Usage: run_memguard.sh BATCH...   (export | all | panel | leak)
set -u
cd benchmark/scale/memguard
R=benchmark/scale/results
WT=$ANNZARRO_SRC
PY=$ANNZARRO_SRC/.venv-test/bin/python
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix
F95=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
S1=$P/tahoe95_first1000000.zarr; S5=$P/tahoe95_first5000000.zarr; S20=$P/tahoe95_first20000000.zarr; S50=$P/tahoe95_first50000000.zarr
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
OUT=$R/memguard.jsonl
M="../ceiling/.venv/bin/python measure.py"
snap() { (echo "== $1"; date -u '+%F %TZ'; uptime; sysctl -n kern.memorystatus_level;
          ps -axo pid,etime,%cpu,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | cut -c1-200) >> $R/ps_memguard.txt; }
# GUI captures own :00-:15 of every hour: a run starts only when its
# estimated length (minutes, by store) ends before :00 and it is not inside
# :00-:15. Checked again once the lock is held (the wait can be long);
# a run that does not fit gives the lock back and waits for :15.
est() {
  case "$1" in *95.6M*) echo 7;; *first50000000*) echo 5;; *first20000000*) echo 3;; *) echo 2;; esac
}
fits_now() {  # fits_now MINUTES
  local m=$((10#$(date +%M)))
  [ $m -ge 15 ] && [ $((m + $1)) -lt 60 ]
}
wait_slot() {
  while ! fits_now $1; do sleep 30; done
}
done_already() {  # done_already TAG STORE COLOR (a 'load' step recorded ok)
  grep -q "\"tag\": \"$1\", \"store\": \"$(basename $2)\", \"color\": \"$3\".*\"step\": \"load\".*\"verdict\": \"ok\"" $OUT 2>/dev/null
}
run() {  # run TAG STORE ARGS...
  local tag=$1 store=$2; shift 2
  local color=gene; [[ " $* " == *" --color cat "* ]] && color=cat
  [ -n "${EXTRA_EST:-}" ] || EXTRA_EST=0
  local m=$(( $(est $store) + EXTRA_EST ))
  if done_already $tag $store $color; then return; fi
  while true; do
    wait_slot $m
    $L bash -c "$(declare -f fits_now); fits_now $m || exit 75; R=$R; $(declare -f snap); snap '$tag $(basename $store) $*'; $M $store --worktree $WT --python $PY --out $OUT --tag $tag $*" >> $R/memguard.log 2>&1
    [ $? -ne 75 ] && break
  done
}
for batch in "$@"; do
  case $batch in
  f1)       # the guard-off check at 95.6M: a full export of an every-cell plot, ours and v030's
    for c in cat gene; do
      run f1_full $F95 --color $c --steps load,panel,snapshot,export_full
      run f1_plotly $F95 --color $c --steps load,panel,export_plotly
    done ;;
  export)   # panel, as shown, full export (ours), Plotly.toImage (v030's path, last: it may crash)
    for rep in 1 2; do for c in cat gene; do
      # (b: the first regular runs created the plot before the cell names had arrived)
      for st in $S1 $S5; do run "export_b_r$rep" $st --color $c --steps load,panel,snapshot,export_full,export_plotly; done
      for st in $S1 $S5; do run "export_large_r$rep" $st --large-threshold 0 --color $c --steps load,panel,snapshot,export_full,export_plotly; done
      for st in $S20 $S50 $F95; do run "export_r$rep" $st --color $c --steps load,panel,snapshot,export_full,export_plotly; done
    done; done ;;
  all)      # every cell from the default subset, with 1-3 plots open
    for rep in 1 2; do for k in 1 2 3; do
      for st in $S5 $S20 $S50 $F95; do run "all_k${k}_r$rep" $st --color cat --subset absent --panels $k --steps load,all; done
    done; done ;;
  panel)    # a new plot, a duplicate, a third
    for rep in 1 2; do for c in cat gene; do
      for st in $S1 $S5 $S20 $S50 $F95; do run "panel_r$rep" $st --color $c --steps load,panel,dup,panel:cell-plot-C; done
    done; done ;;
  leak)     # open/close cycles, repeated exports, subset changes
    EXTRA_EST=4
    run leak_cycle_b $S5 --color cat --steps load,panel,close,cycle:10
    run leak_cycle_large $S50 --color cat --steps load,panel,close,cycle:10
    run leak_exports_b $S5 --color cat --steps load,panel,exports:20,close
    run leak_exports_large $S50 --color cat --steps load,panel,exports:20,close
    run leak_subset $S50 --color cat --subset absent --panels 1 --steps load,subset:1000000,subset:200000,subset:2000000,subset:100000,subset:5000000,subset:100000
    EXTRA_EST=0 ;;
  leak2)    # the +80 MB after subset swaps: cache or leak? (cache cleared between)
    EXTRA_EST=4
    run leak_subset2 $S50 --color cat --subset absent --panels 1 --steps load,clearcache,subset:5000000,subset:100000,clearcache,subset:2000000,subset:100000,clearcache,subset:5000000,subset:100000,clearcache
    EXTRA_EST=0 ;;
  rerun)    # rows flagged for a user Chrome renderer: tag suffix _rr
    for c in cat gene; do
      run f1_full_rr $F95 --color $c --steps load,panel,snapshot,export_full
    done ;;
  esac
done
