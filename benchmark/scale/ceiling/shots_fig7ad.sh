#!/bin/bash
# Fig. 7a-d screenshots on a given AnnZarro build (to run on the v0.3.1 fix for the clipped x axis).
# Usage: shots_fig7ad.sh /path/to/annzarro   (the build's console script; its checkout should be clean
# and tagged; envcapture records both). Same commands as figures/scale/commands.txt, plus the panel c
# zoom at an explicit point size (5, opacity 1: d5be664's default, at which single cells showed) under
# its own prefix, so the view.json records the size and the caption can state it.
# One run-timed call per command (exclusive bench lock; headless, so no screen lock), ps inside it, 5 s apart.
# Runs from this checkout and writes into its figures/scale (never the shared tree).
set -e
EXE=${1:?usage: shots_fig7ad.sh /path/to/annzarro}
cd "$(dirname "$0")"
F95=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
FIG=$(cd ../../../figures/scale && pwd)
R=../results
RT=$TMPDIR/teamlead-bench/run-timed
PY=benchmark/scale/ceiling/.venv/bin/python   # the harness venv (read only)
snap() { (date -u '+%F %TZ'; uptime; sysctl -n kern.memorystatus_level; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | grep -v 'Google Chrome.app' | cut -c1-180) >> $R/ps_shots.txt; }
run() { $RT bash -c "$(declare -f snap); R=$R; snap; $*"; sleep 5; }
PX='{"xaxisTitle":"UMAP 1","yaxisTitle":"UMAP 2"}'
F="$PY figures_tahoe.py $F95 --exe $EXE --out $FIG --emb X_umap --genes FN1"
run $F --prefix tahoe95M_umap --point-size 1 --opacity 0.2 --panel-extra "'$PX'" --shots all_cat,all_gene,sub_cat,sub_gene
run $F --prefix tahoe95M_umap_cmax30 --point-size 1 --opacity 0.2 --panel-extra "'{\"xaxisTitle\":\"UMAP 1\",\"yaxisTitle\":\"UMAP 2\",\"colorMin\":0,\"colorMax\":30}'" --shots all_gene,sub_gene
run $F --prefix tahoe95M_umap --point-size 1 --opacity 0.2 --zoom-box 14.0,14.33,7.8,8.15 --panel-extra "'$PX'" --shots all_zoom
run $F --prefix tahoe95M_umap_default --zoom-box 14.0,14.33,7.8,8.15 --panel-extra "'$PX'" --shots all_cat,all_zoom
run $F --prefix tahoe95M_umap_default --port 8977 --panel-extra "'$PX'" --shots sub_cat
# panel c: zoom at an explicit point size, recorded in tahoe95M_umap_ps5_all_zoom.view.json (panel pointSize)
run $F --prefix tahoe95M_umap_ps5 --point-size 5 --opacity 1 --zoom-box 14.0,14.33,7.8,8.15 --panel-extra "'$PX'" --shots all_cat,all_zoom
