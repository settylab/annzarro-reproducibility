#!/bin/bash
# Fig. 7 laptop series on the v0.3.0 tag (annzarro 3fb6826, worktree $ANNZARRO_SRC
# every-cell real Tahoe 1M-95.6M (tag all_v030) and synthetic 95.6M/150M (ceil_v030), plus one 175M
# guard-outcome run. App defaults (automatic point size, LARGE_PLOT_POINTS 1M, memory guard).
# One bench-lock acquisition per run (one N, one colour, one rep), ps inside the lock, 30 s between runs;
# holds while $HOME/.scale-rerun.PAUSE exists. A run already in the results is skipped (resumable).
cd benchmark/scale/ceiling
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix
F95=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
D=$DATA_ROOT/tahoe_scale_ceiling
REAL="$P/tahoe95_first1000000.zarr $P/tahoe95_first2000000.zarr $P/tahoe95_first5000000.zarr $P/tahoe95_first10000000.zarr $P/tahoe95_first20000000.zarr $P/tahoe95_first50000000.zarr $F95"
EXE=$ANNZARRO_SRC/.venv-bench/bin/annzarro
R=../results
OUT_REAL=$R/browser_v030.jsonl
OUT_SYN=$R/browser_v030_ceiling.jsonl
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
C=".venv/bin/python ceiling.py --exe $EXE --point-size default --opacity default --port 8963 --cold-dir $DATA_ROOT/tahoe_scale/stores/_cold_rerun --cold --reps 1"
note() { echo "- $(date -u '+%F %TZ') $1" >> results/PROGRESS_rerun.md; }
snap() { (date -u '+%F %TZ'; uptime; sysctl -n kern.memorystatus_level; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | grep -v 'Google Chrome.app' | cut -c1-180) >> $R/ps_v030.txt; }
done_already() {  # store stem, colour, rep, tag, out
  [ -f "$5" ] && grep -q "\"store\": \"$1_$2_r$3.zarr\", \"n\": [0-9]*, \"color\": \"$2\", \"rep\": $3, .*\"event\": \"first_plot\".*\"tag\": \"$4\"" "$5"
}
run() {
  while [ -e $HOME/.scale-rerun.PAUSE ]; do sleep 30; done
  $L bash -c "$(declare -f snap); R=$R; snap; $*" >> $R/browser_v030.log 2>&1
  sleep 30
}
note "v0.3.0 Fig. 7 rerun started (queue_v030.sh)"
for st in $REAL; do for c in gene cat; do for r in 0 1 2; do
  done_already $(basename $st .zarr) $c $r all_v030 $OUT_REAL && continue
  run $C $st --emb X_umap --cat cell_line_id --genes FN1,VIM,CD44 --subset null --colors $c --recolour 2 --recolour-cat cell_line_id --zoom 4 --drag 3 --limit 900 --rep-base $r --out $OUT_REAL --tag all_v030
done; done; done
note "v0.3.0: real every-cell series done"
for st in $D/syn_95624334.zarr $D/syn_150000000.zarr; do for c in gene cat; do for r in 0 1 2; do
  done_already $(basename $st .zarr) $c $r ceil_v030 $OUT_SYN && continue
  run $C $st --emb X_umap --cat cell_type --genes GENE0,GENE1,GENE2 --subset null --colors $c --recolour 1 --recolour-cat cell_type --zoom 2 --drag 1 --limit 900 --min-free 15 --rep-base $r --out $OUT_SYN --tag ceil_v030
done; done; done
for c in gene cat; do
  done_already syn_175000000 $c 0 guard175_v030 $OUT_SYN && continue
  run $C $D/syn_175000000.zarr --emb X_umap --cat cell_type --genes GENE0 --subset null --colors $c --recolour 0 --limit 300 --min-free 15 --rep-base 0 --out $OUT_SYN --tag guard175_v030
done
note "v0.3.0 Fig. 7 rerun finished"
