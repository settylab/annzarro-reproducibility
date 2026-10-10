#!/bin/bash
# Fig. 7 on v0.3.1: the full laptop series as on v0.3.0, then conf95, then the Fig. 7a-d shots.
# Usage: queue_v031.sh REV   (the v0.3.1 tag or its sha; coordinator sends it)
#  1. setup_build.sh: clean detached worktree $ANNZARRO_SRC vendor assets, venv
#  2. queue_series.sh EXE v031: every cell 1M-95.6M (all_v031), synthetic 95.6M/150M (ceil_v031), 175M guard
#  3. default-subset browser series (sub_v031), as queue_v030b.sh
#  4. 95.6M every cell at point size 1 / opacity 0.2 (conf95_v031), as queue_v030c.sh
#  5. server per click, bench_http.py --client 0.3 (http_v031.csv)
#  6. shots_fig7ad.sh EXE
# One bench lock per run, ps inside it; resumable (runs already in the results are skipped);
# holds while $HOME/.scale-rerun.PAUSE exists.
set -e
REV=${1:?usage: queue_v031.sh REV}
cd benchmark/scale/ceiling
S=v031
EXE=$(./setup_build.sh $REV v031-bench)
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix
F95=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
REAL="$P/tahoe95_first1000000.zarr $P/tahoe95_first2000000.zarr $P/tahoe95_first5000000.zarr $P/tahoe95_first10000000.zarr $P/tahoe95_first20000000.zarr $P/tahoe95_first50000000.zarr $F95"
R=../results
OUT=$R/browser_$S.jsonl
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
C=".venv/bin/python ceiling.py --exe $EXE --point-size default --opacity default --port 8963 --cold-dir $DATA_ROOT/tahoe_scale/stores/_cold_rerun --cold --reps 1"
note() { echo "- $(date -u '+%F %TZ') $1" >> results/PROGRESS_rerun.md; }
snap() { (date -u '+%F %TZ'; uptime; sysctl -n kern.memorystatus_level; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | grep -v 'Google Chrome.app' | cut -c1-180) >> $R/ps_$S.txt; }
done_already() {  # store stem, colour, rep, tag, out
  [ -f "$5" ] && grep -q "\"store\": \"$1_$2_r$3.zarr\", \"n\": [0-9]*, \"color\": \"$2\", \"rep\": $3, .*\"event\": \"first_plot\".*\"tag\": \"$4\"" "$5"
}
run() {
  while [ -e $HOME/.scale-rerun.PAUSE ]; do sleep 30; done
  $L bash -c "$(declare -f snap); R=$R; S=$S; snap; $*" >> $R/browser_$S.log 2>&1
  sleep 30
}
note "$S queue started (queue_v031.sh $REV, $EXE)"
./queue_series.sh $EXE $S
for st in $REAL; do for c in gene cat; do for r in 0 1 2; do
  done_already $(basename $st .zarr) $c $r sub_$S $OUT && continue
  run $C $st --emb X_umap --cat cell_line_id --genes FN1,VIM,CD44 --subset absent --colors $c --recolour 2 --recolour-cat cell_line_id --part-steps 2 --balance cell_line_id --zoom 2 --limit 600 --rep-base $r --out $OUT --tag sub_$S
done; done; done
note "$S: subset series done"
for c in cat gene; do for r in 0 1 2; do
  done_already tahoe_panel_95.6M_plot $c $r conf95_$S $OUT && continue
  run .venv/bin/python ceiling.py $F95 --exe $EXE --emb X_umap --cat cell_line_id --genes FN1 --point-size 1 --opacity 0.2 --subset null --colors $c --recolour 0 --port 8963 --cold-dir $DATA_ROOT/tahoe_scale/stores/_cold_rerun --cold --reps 1 --rep-base $r --limit 900 --out $OUT --tag conf95_$S
done; done
note "$S: conf95 done"
# server per click (bench_http.py --client 0.3), one store and rep per lock; skipped when already in http_$S.csv
for st in $REAL; do for r in 0 1 2; do
  grep -q "^laptop,$(basename $st),[0-9]*,$r,server,startup_all" $R/http_$S.csv 2>/dev/null && continue
  run "cd .. && ceiling/.venv/bin/python bench_http.py $st --site laptop --client 0.3 --exe $EXE --emb X_umap --out results/http_$S.csv --scratch $DATA_ROOT/tahoe_scale/stores/_scratch_http_rerun --port 8964 --reps 1 --rep-base $r --slow 300"
done; done
note "$S: HTTP series done"
./shots_fig7ad.sh $EXE
note "$S queue finished (shots done)"
