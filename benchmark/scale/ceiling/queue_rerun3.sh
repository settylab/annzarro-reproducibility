#!/bin/bash
# Release-0.3 rerun, part 3: every-cell drawing ceiling on synthetic stores beyond 95.6M
# (build_stores.py: obs cell_type with 50 categories, X_umap 50 blobs, 4 float genes).
# syn_95624334 bridges to the real 95.6M store. A colour that fails is not tried at larger N.
cd benchmark/scale/ceiling
D=$DATA_ROOT/tahoe_scale_ceiling
EXE=$ANNZARRO_SRC/.venv-test/bin/annzarro
R=../results
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
snap() { (date '+%F %T'; uptime; sysctl -n kern.memorystatus_level; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | grep -v 'Google Chrome.app' | cut -c1-180) > $R/ps_rerun_$1.txt; }
note() { echo "- $(date '+%F %T') $1" >> results/PROGRESS_rerun.md; }
note "ceiling hunt (synthetic 95.6M-300M, default flags) started"
$L bash -c "R=$R; $(declare -f snap); snap ceiling; .venv/bin/python ceiling.py $D/syn_95624334.zarr $D/syn_150000000.zarr $D/syn_200000000.zarr $D/syn_250000000.zarr $D/syn_master_300000000.zarr --exe $EXE --emb X_umap --cat cell_type --genes GENE0,GENE1,GENE2 --point-size default --opacity default --subset null --colors gene,cat --recolour 1 --recolour-cat cell_type --zoom 2 --drag 1 --reps 3 --limit 900 --min-free 20 --port 8963 --out $R/browser_rerun_ceiling.jsonl --tag ceil_default" > $R/browser_rerun_ceiling.log 2>&1
note "ceiling hunt finished: $(grep -o '"status": "[a-z_:A-Za-z]*"' $R/browser_rerun_ceiling.log | sort | uniq -c | tr '\n' ' ')"
