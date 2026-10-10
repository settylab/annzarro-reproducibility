#!/bin/bash
# Release-0.3 rerun (annzarro d5be664, worktree tahoe95-run): real Tahoe-100M prefixes + the 95.6M store.
# Every timed batch holds the shared bench lock; `ps` of python/annzarro/chrome is recorded at its start.
# Usage: queue_rerun.sh [sub|all|http]...  (default: all three, in that order)
cd benchmark/scale/ceiling
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix
STORES="$P/tahoe95_first1000000.zarr $P/tahoe95_first2000000.zarr $P/tahoe95_first5000000.zarr $P/tahoe95_first10000000.zarr $P/tahoe95_first20000000.zarr $P/tahoe95_first50000000.zarr $DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr"
EXE=$ANNZARRO_SRC/.venv-test/bin/annzarro
R=../results
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
C=".venv/bin/python ceiling.py $STORES --exe $EXE --emb X_umap --cat cell_line_id --genes FN1,VIM,CD44 --point-size default --opacity default --port 8963 --cold-dir $DATA_ROOT/tahoe_scale/stores/_cold_rerun --out $R/browser_rerun.jsonl"
snap() { (date '+%F %T'; uptime; sysctl -n kern.memorystatus_level; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | grep -v 'Google Chrome.app' | cut -c1-180) > $R/ps_rerun_$1.txt; }
note() { echo "- $(date '+%F %T') $1" >> results/PROGRESS_rerun.md; }
for step in ${@:-sub all http}; do case $step in
sub) note "item 2 (default subset) browser sweep started"
     $L bash -c "R=$R; $(declare -f snap); snap browser_sub; $C --subset absent --colors gene,cat --recolour 2 --recolour-cat cell_line_id --part-steps 2 --balance cell_line_id --zoom 2 --cold --reps 3 --limit 600 --tag sub_cold" > $R/browser_rerun_sub.log 2>&1
     note "item 2 browser sweep finished: $(tail -1 $R/browser_rerun_sub.log | cut -c1-120)";;
all) note "item 1 (every cell) browser sweep started"
     $L bash -c "R=$R; $(declare -f snap); snap browser_all; $C --subset null --colors gene,cat --recolour 2 --recolour-cat cell_line_id --zoom 4 --drag 3 --cold --reps 3 --limit 900 --tag all_cold" > $R/browser_rerun_all.log 2>&1
     note "item 1 browser sweep finished: $(tail -1 $R/browser_rerun_all.log | cut -c1-120)";;
http) note "item 3 (server per click) sweep started"
     $L bash -c "R=$R; $(declare -f snap); snap http; cd ..; ceiling/.venv/bin/python bench_http.py $STORES --site laptop --client 0.3 --exe $EXE --emb X_umap --out results/http_rerun.csv --scratch $DATA_ROOT/tahoe_scale/stores/_scratch_http_rerun --port 8964 --reps 3 --slow 300" > $R/http_rerun.log 2>&1
     note "item 3 sweep finished: $(tail -1 $R/http_rerun.log | cut -c1-120)";;
esac; done
