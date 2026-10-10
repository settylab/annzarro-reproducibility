#!/bin/bash
# Release-0.3 rerun, part 2: confirm the 95.6M real-UMAP first plots with the figure's settings
# (figures_tahoe.py: point size 1, opacity 0.2), store warm and cold; heap limits under the default flags.
cd benchmark/scale/ceiling
ST=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
EXE=$ANNZARRO_SRC/.venv-test/bin/annzarro
R=../results
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
C=".venv/bin/python ceiling.py $ST --exe $EXE --emb X_umap --cat cell_line_id --genes FN1 --point-size 1 --opacity 0.2 --subset null --colors cat,gene --recolour 0 --port 8963 --cold-dir $DATA_ROOT/tahoe_scale/stores/_cold_rerun --limit 900 --reps 3 --out $R/browser_rerun_confirm95.jsonl"
snap() { (date '+%F %T'; uptime; sysctl -n kern.memorystatus_level; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | grep -v 'Google Chrome.app' | cut -c1-180) > $R/ps_rerun_$1.txt; }
note() { echo "- $(date '+%F %T') $1" >> results/PROGRESS_rerun.md; }
note "confirm 95.6M (figure settings) started"
$L bash -c "R=$R; $(declare -f snap); snap confirm95; $C --tag confirm95_warm; $C --cold --tag confirm95_cold" > $R/browser_rerun_confirm95.log 2>&1
note "confirm 95.6M finished"
$L bash -c "R=$R; $(declare -f snap); snap heapcap; .venv/bin/python heapcap.py bundled > $R/heapcap_rerun.jsonl" 2>&1 | tail -2
note "heapcap (bundled chromium, default flags) finished: $(cut -c1-150 $R/heapcap_rerun.jsonl)"
