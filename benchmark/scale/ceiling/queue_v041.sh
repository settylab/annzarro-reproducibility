#!/bin/bash
# The Scale figure and the laptop browser series on v0.4.1 (notes/v041_remeasure_plan.md), one stage per call:
#   step1  endpoint check (must pass), every cell 1M-95.6M (all_v041), synthetic 95.6M/150M (ceil_v041),
#          175M guard outcome (guard175_v041), 95.6M confirmations (conf95_v041, conf95auto_v041)
#   name   first name search at 50M, prewarm on/off interleaved, 3 reps each (prewarm50M_v041) [plan step 3]
#   http   server per click, bench_http.py --client 0.3 (http_v041.csv)                      [plan step 5]
#   sub    default-subset browser series (sub_v041)                                         [plan step 6]
#   malat1 the 95.6M confirmations' gene arms on MALAT1, the gene of Fig. scale b and c (conf95malat1_v041,
#          conf95automalat1_v041; 3 cold reps each)
#   shots  Scale a-d screenshots (shots_fig7ad.sh)                                          [plan step 7]
# Runs from this checkout (never the shared tree). Every run is one timed measurement: one store, colour and
# rep per run-timed call (exclusive bench lock, <= 30 min), ps inside it, 5 s apart (30 s until 2026-10-07 21:17Z). Resumable: runs already
# in the results are skipped. Holds while $HOME/.scale-rerun.PAUSE exists.
# Usage: queue_v041.sh EXE STAGE   (EXE: the v0.4.1 tag's annzarro from setup_build.sh 78c9da6 v041-bench)
set -e
EXE=${1:?annzarro executable}; STAGE=${2:?step1|name|http|sub|shots|malat1}
cd "$(dirname "$0")"
S=v041
SP=$TMPDIR
RT=$SP/teamlead-bench/run-timed
PY=benchmark/scale/ceiling/.venv/bin/python   # the harness venv (read only)
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix
F95=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
D=$DATA_ROOT/tahoe_scale_ceiling
REAL="$P/tahoe95_first1000000.zarr $P/tahoe95_first2000000.zarr $P/tahoe95_first5000000.zarr $P/tahoe95_first10000000.zarr $P/tahoe95_first20000000.zarr $P/tahoe95_first50000000.zarr $F95"
R=../results
OUT=$R/browser_$S.jsonl
OUT_SYN=$R/browser_${S}_ceiling.jsonl
COLD=$DATA_ROOT/tahoe_scale/stores/_cold_rerun
C="$PY ceiling.py --exe $EXE --point-size default --opacity default --port 8963 --cold-dir $COLD --cold --reps 1"
note() { echo "- $(date -u '+%F %TZ') $1" >> results/PROGRESS_rerun.md; }
# ps inside the lock (from 2026-10-07 21:17Z no other AnnZarro server runs on the machine)
snap() { (date -u '+%F %TZ'; uptime; sysctl -n kern.memorystatus_level; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom|[g]unicorn' | grep -v 'Google Chrome.app' | cut -c1-180) >> $R/ps_$S.txt; }
done_already() {  # store stem, colour, rep, tag, out
  [ -f "$5" ] && grep -q "\"store\": \"$1_$2_r$3.zarr\", \"n\": [0-9]*, \"color\": \"$2\", \"rep\": $3, .*\"event\": \"first_plot\".*\"tag\": \"$4\"" "$5"
}
run() {
  while [ -e $HOME/.scale-rerun.PAUSE ]; do sleep 30; done
  $RT bash -c "$(declare -f snap); R=$R; S=$S; snap; $*" >> $R/browser_$S.log 2>&1
  sleep 5   # 30 s until 2026-10-07 21:17Z (operator: 5 s between timed holds)
}
case $STAGE in
step1)
  note "$S step1 started (queue_v041.sh, $EXE)"
  # endpoint check: a recolour ends at the draw that shows the new colours; the series runs only if it passes
  if ! grep -q '"tag": "endpoint_v041"' $OUT 2>/dev/null; then
    run $C $P/tahoe95_first1000000.zarr --emb X_umap --cat cell_line_id --genes FN1,VIM --subset null --colors gene --recolour 1 --limit 600 --rep-base 0 --out $OUT --tag endpoint_$S
    run $C $F95 --emb X_umap --cat cell_line_id --genes FN1,VIM --subset absent --colors gene --recolour 1 --limit 600 --rep-base 0 --out $OUT --tag endpoint_$S
  fi
  $PY - "$OUT" "endpoint_$S" <<'PY' || { note "$S: endpoint check FAILED, queue stopped"; exit 1; }
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if f'"tag": "{sys.argv[2]}"' in l]
rec = [r for r in rows if r["event"] == "recolour"]
ok = len(rec) == 2 and all(r["status"] == "ok" and r.get("seconds_drawn") and r["seconds"] >= r["seconds_data"] for r in rec)
for r in rec:
    print(r["store"], r["n"], "data", r.get("seconds_data"), "drawn", r.get("seconds_drawn"), "seconds", r["seconds"])
sys.exit(0 if ok else 1)
PY
  note "$S: endpoint check passed"
  for st in $REAL; do for c in gene cat; do for r in 0 1 2; do
    done_already $(basename $st .zarr) $c $r all_$S $OUT && continue
    run $C $st --emb X_umap --cat cell_line_id --genes FN1,VIM,CD44 --subset null --colors $c --recolour 2 --recolour-cat cell_line_id --zoom 4 --drag 3 --limit 900 --rep-base $r --out $OUT --tag all_$S
  done; done; done
  note "$S: real every-cell series done"
  for st in $D/syn_95624334.zarr $D/syn_150000000.zarr; do for c in gene cat; do for r in 0 1 2; do
    done_already $(basename $st .zarr) $c $r ceil_$S $OUT_SYN && continue
    run $C $st --emb X_umap --cat cell_type --genes GENE0,GENE1,GENE2 --subset null --colors $c --recolour 1 --recolour-cat cell_type --zoom 2 --drag 1 --limit 900 --min-free 15 --rep-base $r --out $OUT_SYN --tag ceil_$S
  done; done; done
  for c in gene cat; do
    done_already syn_175000000 $c 0 guard175_$S $OUT_SYN && continue
    run $C $D/syn_175000000.zarr --emb X_umap --cat cell_type --genes GENE0 --subset null --colors $c --recolour 0 --limit 300 --min-free 15 --rep-base 0 --out $OUT_SYN --tag guard175_$S
  done
  for c in cat gene; do for r in 0 1 2; do
    done_already tahoe_panel_95.6M_plot $c $r conf95_$S $OUT && continue
    run $PY ceiling.py $F95 --exe $EXE --emb X_umap --cat cell_line_id --genes FN1 --point-size 1 --opacity 0.2 --subset null --colors $c --recolour 0 --port 8963 --cold-dir $COLD --cold --reps 1 --rep-base $r --limit 900 --out $OUT --tag conf95_$S
  done; done
  for c in cat gene; do for r in 0 1 2; do
    done_already tahoe_panel_95.6M_plot $c $r conf95auto_$S $OUT && continue
    run $PY ceiling.py $F95 --exe $EXE --emb X_umap --cat cell_line_id --genes FN1 --point-size default --opacity default --subset null --colors $c --recolour 0 --port 8963 --cold-dir $COLD --cold --reps 1 --rep-base $r --limit 900 --out $OUT --tag conf95auto_$S
  done; done
  note "$S step1 done" ;;
malat1)
  note "$S malat1 started (queue_v041.sh, $EXE)"
  for r in 0 1 2; do
    done_already tahoe_panel_95.6M_plot gene $r conf95malat1_$S $OUT && continue
    run $PY ceiling.py $F95 --exe $EXE --emb X_umap --cat cell_line_id --genes MALAT1 --point-size 1 --opacity 0.2 --subset null --colors gene --recolour 0 --port 8963 --cold-dir $COLD --cold --reps 1 --rep-base $r --limit 900 --out $OUT --tag conf95malat1_$S
  done
  for r in 0 1 2; do
    done_already tahoe_panel_95.6M_plot gene $r conf95automalat1_$S $OUT && continue
    run $PY ceiling.py $F95 --exe $EXE --emb X_umap --cat cell_line_id --genes MALAT1 --point-size default --opacity default --subset null --colors gene --recolour 0 --port 8963 --cold-dir $COLD --cold --reps 1 --rep-base $r --limit 900 --out $OUT --tag conf95automalat1_$S
  done
  note "$S malat1 done" ;;
sub)
  for st in $REAL; do for c in gene cat; do for r in 0 1 2; do
    done_already $(basename $st .zarr) $c $r sub_$S $OUT && continue
    run $C $st --emb X_umap --cat cell_line_id --genes FN1,VIM,CD44 --subset absent --colors $c --recolour 2 --recolour-cat cell_line_id --part-steps 2 --balance cell_line_id --zoom 2 --limit 600 --rep-base $r --out $OUT --tag sub_$S
  done; done; done
  note "$S: subset series done" ;;
name)
  ST50=$DATA_ROOT/tahoe_scale/stores/n50M_plot/tahoe_50M_plot.zarr; OUTN=$R/prewarm50M_$S.jsonl
  for r in 0 1 2; do for mode in on off; do
    FLAG=""; [ $mode = off ] && FLAG="--no-prewarm"
    [ -f $OUTN ] && [ "$(grep -c '"prewarm": '$([ $mode = on ] && echo true || echo false) $OUTN)" -gt $r ] && continue
    while [ -e $HOME/.scale-rerun.PAUSE ]; do sleep 30; done
    $RT bash -c "(date -u '+%F %TZ'; uptime; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom|[g]unicorn' | grep -v 'Google Chrome.app' | cut -c1-180) >> $R/ps_prewarm50M_$S.txt; $PY -c \"import sys; sys.path.insert(0, '..'); import envcapture; envcapture.require_clean_bench(); envcapture.record('$OUTN', exe='$EXE', tag='prewarm50M_$S', prewarm='$mode', rep=$r, script='prewarm_check.py')\" && $PY prewarm_check.py $ST50 --exe $EXE $FLAG --out $OUTN" >> $R/prewarm50M_$S.log 2>&1
    sleep 20
  done; done
  note "$S: prewarm50M (ts.name_index) done" ;;
http)
  for st in $REAL; do for r in 0 1 2; do
    grep -q "^laptop,$(basename $st),[0-9]*,$r,server,startup_all" $R/http_$S.csv 2>/dev/null && continue
    run "cd .. && $PY bench_http.py $st --site laptop --client 0.3 --exe $EXE --emb X_umap --out results/http_$S.csv --scratch $DATA_ROOT/tahoe_scale/stores/_scratch_http_rerun --port 8964 --reps 1 --rep-base $r --slow 300"
  done; done
  note "$S: HTTP series done" ;;
shots)
  ./shots_fig7ad.sh $EXE
  note "$S: Scale a-d shots done" ;;
*) echo "stage: step1|name|http|sub|shots" >&2; exit 2 ;;
esac
