#!/bin/bash
# 50M every cell after the lazy names (remote-names.js), interleaved categories; merged tree 245ef82.
cd benchmark/scale/ceiling
ST=$DATA_ROOT/tahoe_scale/stores/n50M_plot/tahoe_50M_plot.zarr
C=".venv/bin/python ceiling.py $ST --exe .venv-test/bin/annzarro --emb X_pca_2d --cat cell_line_id --genes VIM,CD44,MALAT1 --point-size default --opacity default --limit 1200 --port 8959 --cold-dir $DATA_ROOT/tahoe_scale_ceiling/_cold --out results/tahoe50M_lazy.jsonl --subset null --colors cat,gene --recolour 2 --zoom 4 --drag 3"
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
others() { echo "$(date +%T) other jobs: $(ps aux | grep -E '[b]uild_tahoe|[b]ench_http|[b]ench_browser' | awk '{print $12, $13}' | tr '\n' ';')"; }
others; $L $C --cold --reps 3 --tag t50L_all_cold
others; $L $C --warm --reps 4 --tag t50L_all_warm
others; echo T50L DONE
