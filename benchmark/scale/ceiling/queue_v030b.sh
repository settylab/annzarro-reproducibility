#!/bin/bash
# v0.3.0 tag, after queue_v030.sh: default-subset browser series (sub_v030) and the server per-click
# series (bench_http.py --client 0.3), one bench-lock acquisition per run, ps inside the lock, 30 s apart.
cd benchmark/scale/ceiling
until grep -q "v0.3.0 Fig. 7 rerun finished" results/PROGRESS_rerun.md; do sleep 60; done
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix
F95=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
REAL="$P/tahoe95_first1000000.zarr $P/tahoe95_first2000000.zarr $P/tahoe95_first5000000.zarr $P/tahoe95_first10000000.zarr $P/tahoe95_first20000000.zarr $P/tahoe95_first50000000.zarr $F95"
EXE=$ANNZARRO_SRC/.venv-bench/bin/annzarro
R=../results
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
C=".venv/bin/python ceiling.py --exe $EXE --point-size default --opacity default --port 8963 --cold-dir $DATA_ROOT/tahoe_scale/stores/_cold_rerun --cold --reps 1"
note() { echo "- $(date -u '+%F %TZ') $1" >> results/PROGRESS_rerun.md; }
snap() { (date -u '+%F %TZ'; uptime; sysctl -n kern.memorystatus_level; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | grep -v 'Google Chrome.app' | cut -c1-180) >> $R/ps_v030.txt; }
run() {
  while [ -e $HOME/.scale-rerun.PAUSE ]; do sleep 30; done
  $L bash -c "$(declare -f snap); R=$R; snap; $*" >> $R/browser_v030.log 2>&1
  sleep 30
}
note "v0.3.0 subset + HTTP series started (queue_v030b.sh)"
for st in $REAL; do for c in gene cat; do for r in 0 1 2; do
  run $C $st --emb X_umap --cat cell_line_id --genes FN1,VIM,CD44 --subset absent --colors $c --recolour 2 --recolour-cat cell_line_id --part-steps 2 --balance cell_line_id --zoom 2 --limit 600 --rep-base $r --out $R/browser_v030.jsonl --tag sub_v030
done; done; done
note "v0.3.0: subset series done"
for st in $REAL; do for r in 0 1 2; do
  run "cd .. && ceiling/.venv/bin/python bench_http.py $st --site laptop --client 0.3 --exe $EXE --emb X_umap --out results/http_v030.csv --scratch $DATA_ROOT/tahoe_scale/stores/_scratch_http_rerun --port 8964 --reps 1 --rep-base $r --slow 300"
done; done
note "v0.3.0 subset + HTTP series finished"
