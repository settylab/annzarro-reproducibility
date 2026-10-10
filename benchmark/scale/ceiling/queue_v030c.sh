#!/bin/bash
# v0.3.0 tag: (1) every cell at 95.6M with point size 1 / opacity 0.2, 3 cold reps per colour
# (tag conf95_v030, as confirm95 on d5be664); (2) re-shoot the Fig. 7a-d screenshots with
# figures/scale/commands.txt's 95.6M commands on the tag. One bench lock per run, ps inside it.
cd benchmark/scale/ceiling
F95=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
EXE=$ANNZARRO_SRC/.venv-bench/bin/annzarro
R=../results
FIG=figures/scale
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
note() { echo "- $(date -u '+%F %TZ') $1" >> results/PROGRESS_rerun.md; }
snap() { (date -u '+%F %TZ'; uptime; sysctl -n kern.memorystatus_level; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | grep -v 'Google Chrome.app' | cut -c1-180) >> $R/ps_v030.txt; }
done_already() {  # store stem, colour, rep, tag, out (a run already in the results is skipped)
  [ -f "$5" ] && grep -q "\"store\": \"$1_$2_r$3.zarr\", \"n\": [0-9]*, \"color\": \"$2\", \"rep\": $3, .*\"event\": \"first_plot\".*\"tag\": \"$4\"" "$5"
}
run() {
  while [ -e $HOME/.scale-rerun.PAUSE ]; do sleep 30; done
  $L bash -c "$(declare -f snap); R=$R; snap; $*" >> $R/browser_v030.log 2>&1
  sleep 30
}
PX='{"xaxisTitle":"UMAP 1","yaxisTitle":"UMAP 2"}'
note "v0.3.0: conf95 + Fig. 7a-d re-shoot started (queue_v030c.sh)"
for c in cat gene; do for r in 0 1 2; do
  done_already tahoe_panel_95.6M_plot $c $r conf95_v030 $R/browser_v030.jsonl && continue
  run .venv/bin/python ceiling.py $F95 --exe $EXE --emb X_umap --cat cell_line_id --genes FN1 --point-size 1 --opacity 0.2 --subset null --colors $c --recolour 0 --port 8963 --cold-dir $DATA_ROOT/tahoe_scale/stores/_cold_rerun --cold --reps 1 --rep-base $r --limit 900 --out $R/browser_v030.jsonl --tag conf95_v030
done; done
F=".venv/bin/python figures_tahoe.py $F95 --exe $EXE --out $FIG --emb X_umap --genes FN1"
run $F --prefix tahoe95M_umap --point-size 1 --opacity 0.2 --panel-extra "'$PX'" --shots all_cat,all_gene,sub_cat,sub_gene
run $F --prefix tahoe95M_umap_cmax30 --point-size 1 --opacity 0.2 --panel-extra "'{\"xaxisTitle\":\"UMAP 1\",\"yaxisTitle\":\"UMAP 2\",\"colorMin\":0,\"colorMax\":30}'" --shots all_gene,sub_gene
run $F --prefix tahoe95M_umap --point-size 1 --opacity 0.2 --zoom-box 14.0,14.33,7.8,8.15 --panel-extra "'$PX'" --shots all_zoom
run $F --prefix tahoe95M_umap_default --zoom-box 14.0,14.33,7.8,8.15 --panel-extra "'$PX'" --shots all_cat,all_zoom
run $F --prefix tahoe95M_umap_default --port 8977 --panel-extra "'$PX'" --shots sub_cat
note "v0.3.0: conf95 + Fig. 7a-d re-shoot finished"
