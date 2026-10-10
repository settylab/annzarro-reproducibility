#!/bin/bash
# The browser memory guard's measurements (annzarro dominik/memory-guard).
# Every run holds the shared bench lock; ps (python/annzarro/chrome, and the
# user's own Chrome) is appended to $R/ps_memguard.txt at its start.
# Usage: run_memguard_c.sh leakc
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
# Reruns of the regular-path leak runs: the _b ones still created the plot
# before the cell names had arrived (the harness's wait did not wait).
for batch in "$@"; do
  case $batch in
  leakc)
    EXTRA_EST=4
    run leak_cycle_c $S5 --color cat --steps load,panel,close,cycle:10
    run leak_exports_c $S5 --color cat --steps load,panel,exports:20,close
    EXTRA_EST=0 ;;
  esac
done
