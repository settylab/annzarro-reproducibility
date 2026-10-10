#!/bin/bash
# Real Tahoe 50M (scale-benchmarker's n50M_plot store), merged tree (plot-ceiling + scale-fixes, local 1d58157).
# Every timed run holds the shared bench lock; before each, whether a store build or other bench runs.
cd benchmark/scale/ceiling
ST=$DATA_ROOT/tahoe_scale/stores/n50M_plot/tahoe_50M_plot.zarr
C=".venv/bin/python ceiling.py $ST --exe .venv-test/bin/annzarro --emb X_pca_2d --cat cell_line_id --genes VIM,CD44,MALAT1 --point-size default --opacity default --limit 1200 --port 8959 --cold-dir $DATA_ROOT/tahoe_scale_ceiling/_cold --out results/tahoe50M.jsonl"
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
note() { echo "$(date +%T) $1 | other jobs: $(ps aux | grep -E '[b]uild_tahoe|[b]ench_(http|browser)|[c]eiling.py.*--tag (?!t50)' | awk '{print $12, $13}' | tr '\n' ';')" >> results/tahoe50M_queue.log; }
note "1a subset default cold"; $L $C --subset absent --colors gene,cat --recolour 2 --zoom 2 --cold --reps 3 --tag t50_sub_cold
note "1a subset default warm"; $L $C --subset absent --colors gene,cat --recolour 2 --zoom 2 --warm --reps 4 --tag t50_sub_warm
note "1b balanced subset cold"; $L $C --subset '{"n":100000,"seed":0,"balance":"cell_line_id"}' --colors cat --cold --reps 3 --tag t50_bal_cold
note "2 every cell cold"; $L $C --subset null --colors cat,gene --recolour 2 --zoom 4 --drag 3 --cold --reps 3 --tag t50_all_cold
note "2 every cell warm"; $L $C --subset null --colors cat,gene --recolour 2 --zoom 4 --drag 3 --warm --reps 4 --tag t50_all_warm
note "done"; echo T50 DONE >> results/tahoe50M_queue.log
