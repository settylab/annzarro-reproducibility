#!/bin/bash
# Release-0.3 rerun, part 5: bisect the every-cell ceiling (175M, default flags, full interactions) and
# test whether a larger V8 heap (--js-flags=--max-old-space-size) moves the 200M failure.
cd benchmark/scale/ceiling
D=$DATA_ROOT/tahoe_scale_ceiling
EXE=$ANNZARRO_SRC/.venv-test/bin/annzarro
R=../results
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
snap() { (date '+%F %T'; uptime; sysctl -n kern.memorystatus_level; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | grep -v 'Google Chrome.app' | cut -c1-180) > $R/ps_rerun_$1.txt; }
note() { echo "- $(date '+%F %T') $1" >> results/PROGRESS_rerun.md; }
note "part 5: 175M default flags (ceiling.py) and 200M probes with --max-old-space-size started"
$L bash -c "R=$R; $(declare -f snap); snap ceiling175; .venv/bin/python ceiling.py $D/syn_175000000.zarr --exe $EXE --emb X_umap --cat cell_type --genes GENE0,GENE1,GENE2 --point-size default --opacity default --subset null --colors gene,cat --recolour 1 --recolour-cat cell_type --zoom 2 --drag 1 --reps 3 --limit 900 --min-free 15 --port 8963 --out $R/browser_rerun_ceiling.jsonl --tag ceil_default_175" > $R/browser_rerun_ceiling175.log 2>&1
note "175M: $(grep -o '"event": "first_plot", "status": "[a-z_:A-Za-z]*"' $R/browser_rerun_ceiling175.log | sort | uniq -c | tr '\n' ' ')"
for MB in 8192 16384; do
  $L bash -c "R=$R; $(declare -f snap); snap probe200_heap$MB; for c in gene cat; do for r in 0 1 2; do .venv/bin/python probe.py $D/syn_200000000.zarr --exe $EXE --color \$c --args '--js-flags=--max-old-space-size=$MB' --out $R/browser_rerun_probe.jsonl --tag probe_heap${MB}_r\$r; done; done" >> $R/browser_rerun_probe.log 2>&1
done
note "200M probes with --max-old-space-size 8192/16384: $(grep -c '"status": "ok"' $R/browser_rerun_probe.log) ok of $(grep -c '"status"' $R/browser_rerun_probe.log)"
