#!/bin/bash
# Repeat: 10 gene recolours at 95.6M with the crash cause captured (flushed stderr, GPU RSS, contexts) (coordinator's condition 3 for
# the replace semantics): 5x gene -> category -> gene at 95.6M (real), 150M
# and 175M (synthetic), on 12f93f8 + the fix. 175M also with enforce off: the
# guard refuses its first draw, so this checks the recolour itself is safe.
# Bench lock and the GUI window (:00-:15); ps recorded at every start.
set -u
cd benchmark/scale/memguard
R=benchmark/scale/results
WT=$ANNZARRO_SRC
F95=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
D=$DATA_ROOT/tahoe_scale_ceiling
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
OUT=$R/memguard_recolour_edge.jsonl
snap() { (echo "== $1"; date -u '+%F %TZ'; uptime; ps -axo pid,etime,%cpu,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | cut -c1-200) >> $R/ps_memguard.txt; }
fits_now() { local m=$((10#$(date +%M))); [ $m -ge 15 ] && [ $((m + $1)) -lt 60 ]; }
run() {  # run TAG MINUTES ARGS...
  local tag=$1 est=$2; shift 2
  while true; do
    while ! fits_now $est; do sleep 30; done
    $L bash -c "$(declare -f fits_now); fits_now $est || exit 75; R=$R; $(declare -f snap); snap 'recolour_edge $tag'; ../ceiling/.venv/bin/python recolour_edge.py $* --worktree $WT --k 10 --out $OUT --tag $tag" >> $R/memguard_recolour_edge.log 2>&1
    [ $? -ne 75 ] && break
  done
}
run rep_95.6M 25 $F95 --gene FN1 --cat cell_line_id
