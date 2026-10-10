#!/bin/bash
# Second pass (after the large-plot retention fix 8438a14): recolour at the memory edge with the guard on (coordinator's condition 3 for
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
    $L bash -c "$(declare -f fits_now); fits_now $est || exit 75; R=$R; $(declare -f snap); snap 'recolour_edge $tag'; ../ceiling/.venv/bin/python recolour_edge.py $* --worktree $WT --k 5 --out $OUT --tag $tag" >> $R/memguard_recolour_edge.log 2>&1
    [ $? -ne 75 ] && break
  done
}
run edge2_95.6M 15 $F95 --gene FN1 --cat cell_line_id
run edge2_150M 25 $D/syn_150000000.zarr --gene GENE0 --cat cell_type
run edge2_175M 10 $D/syn_175000000.zarr --gene GENE0 --cat cell_type
run edge2_175M_off 30 $D/syn_175000000.zarr --gene GENE0 --cat cell_type --enforce off
