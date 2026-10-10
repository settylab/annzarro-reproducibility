#!/bin/bash
# Release-0.3 rerun, part 6 (after the coordinator's resume at 21:24:58Z): redo every timing that overlapped
# the user's live sessions or unlocked tests, one bench-lock acquisition per run (one N, one colour, one rep)
# with a pause between runs so other queued tests can take the lock. Then: 95.6M every-cell with the
# cell-name prewarm blocked (and a control), CPU profiles of the 1M/2M regular path, ceiling timings.
cd benchmark/scale/ceiling
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix
F95=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
D=$DATA_ROOT/tahoe_scale_ceiling
REAL="$P/tahoe95_first1000000.zarr $P/tahoe95_first2000000.zarr $P/tahoe95_first5000000.zarr $P/tahoe95_first10000000.zarr $P/tahoe95_first20000000.zarr $P/tahoe95_first50000000.zarr"
EXE=$ANNZARRO_SRC/.venv-test/bin/annzarro
R=../results
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
C=".venv/bin/python ceiling.py --exe $EXE --point-size default --opacity default --port 8963 --cold-dir $DATA_ROOT/tahoe_scale/stores/_cold_rerun --cold --reps 1"
REAL_V="--emb X_umap --cat cell_line_id --genes FN1,VIM,CD44"
SYN_V="--emb X_umap --cat cell_type --genes GENE0,GENE1,GENE2"
note() { echo "- $(date -u '+%F %TZ') $1" >> results/PROGRESS_rerun.md; }
snap() { (date -u '+%F %TZ'; uptime; sysctl -n kern.memorystatus_level; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | grep -v 'Google Chrome.app' | cut -c1-180) >> $R/ps_rerun6.txt; }
run() {   # one locked run; the ps snapshot is taken inside the lock, at the start of the timed run
  $L bash -c "$(declare -f snap); R=$R; snap; $*" >> $R/browser_rerun6.log 2>&1
  sleep 20
}
note "part 6 started (per-run lock): subset sweep, every-cell 1M-50M, prewarm test, profiles, ceiling timings"
for st in $REAL $F95; do for c in gene cat; do for r in 0 1 2; do
  # done at 21:28Z before this queue was restarted under nohup
  [ "$st$c$r" = "$P/tahoe95_first1000000.zarrgene0" ] && continue
  run $C $st $REAL_V --subset absent --colors $c --recolour 2 --recolour-cat cell_line_id --part-steps 2 --balance cell_line_id --zoom 2 --limit 600 --rep-base $r --out $R/browser_rerun.jsonl --tag sub_cold
done; done; done
note "part 6: subset sweep done"
for st in $REAL; do for c in gene cat; do for r in 0 1 2; do
  run $C $st $REAL_V --subset null --colors $c --recolour 2 --recolour-cat cell_line_id --zoom 4 --drag 3 --limit 900 --rep-base $r --out $R/browser_rerun.jsonl --tag all_cold
done; done; done
note "part 6: every-cell 1M-50M done"
for c in cat gene; do for r in 0 1 2; do
  run $C $F95 $REAL_V --subset null --colors $c --recolour 0 --limit 900 --rep-base $r --out $R/browser_rerun.jsonl --tag all95_prewarm_ctrl
  run $C $F95 $REAL_V --subset null --colors $c --recolour 0 --limit 900 --rep-base $r --block-prewarm --out $R/browser_rerun.jsonl --tag all95_noprewarm
done; done
note "part 6: 95.6M prewarm test done"
for st in $P/tahoe95_first1000000.zarr $P/tahoe95_first2000000.zarr; do for c in gene cat; do
  n=$(basename $st .zarr)
  run $C $st $REAL_V --subset null --colors $c --recolour 0 --limit 900 --cpu-profile $R/profiles/regular_${n}_$c.cpuprofile --out $R/browser_rerun_profile.jsonl --tag profile_regular
done; done
note "part 6: regular-path profiles done"
for st in $D/syn_95624334.zarr $D/syn_150000000.zarr $D/syn_175000000.zarr; do for c in gene cat; do for r in 0 1 2; do
  run $C $st $SYN_V --subset null --colors $c --recolour 1 --recolour-cat cell_type --zoom 2 --drag 1 --limit 900 --min-free 15 --rep-base $r --out $R/browser_rerun_ceiling.jsonl --tag ceil_rerun
done; done; done
note "part 6 finished"
