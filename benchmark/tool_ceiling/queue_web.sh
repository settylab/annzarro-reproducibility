#!/bin/bash
# Web tools up the N ladder: each variant climbs until its first non-ok run.
# h5ad inputs come from queue_lib.sh (waited for here, never built twice);
# tool-specific conversions are measured runs of their own (phase convert).
cd "$(dirname "$0")"
M=$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix
D=$DATA_ROOT/tool_ceiling_data
C=$DEMO_ROOT
EXE=${EXE:-$ANNZARRO_SRC/.venv-test/bin/annzarro}
PY=.venv/bin/python
LADDER="${LADDER:-1000000 2000000 5000000 10000000 20000000 50000000 95624334}"

h5ad() { local f=$D/h5ad/tahoe_first$1.h5ad; until [ -f $f ]; do sleep 60; done; echo $f; }
zstore() { [ $1 = 95624334 ] && echo $M || echo $P/tahoe95_first$1.zarr; }
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
conv() {  # conv TOOL VARIANT N CMD...: a measured conversion, 2 h limit
  local t=$1 v=$2 n=$3; shift 3
  $PY run.py --tool $t --variant $v --phase convert --n $n --timeout 7200 -- "$@"
}
web() {  # web TOOL VARIANT N INPUT
  $PY run.py --web --tool $1 --variant $2 --n $3 -- $PY web_task.py $1 $2 $4 {out} --n $3 --port 8934
}

for v in ${VARIANTS:-annzarro:default annzarro:noprewarm cellxgene:default cellxgene:backed cirrocumulus:default cirrocumulus:prepared ucsc:default}; do
  tool=${v%%:*}; var=${v#*:}
  for n in $LADDER; do
    case $v in
      annzarro:*)
        $PY run.py --web --tool annzarro --variant $var --n $n -- $PY annzarro_task.py $var $(zstore $n) {out} --exe $EXE ;;
      cirrocumulus:prepared)
        out=$D/cirro/first$n.zarr
        if [ ! -d $out ]; then
          conv cirrocumulus prepare_data $n $C/cirrocumulus/.venv/bin/cirro prepare_data --format zarr --no-auto-groups --out $out $(h5ad $n)
          last_ok || break
        fi
        web cirrocumulus prepared $n $out ;;
      ucsc:default)
        in=$D/ucsc/in_$n html=$D/ucsc/html_$n
        if [ ! -f $html/index.html ]; then
          rm -rf $in $html
          conv ucsc cbImportScanpy $n $C/ucsc-cell-browser/.venv/bin/cbImportScanpy -i $(h5ad $n) -o $in -n first$n \
              --clusterField=cell_line_id --skipMarkers -f mtx
          last_ok || break
          conv ucsc cbBuild $n bash -c "cd $in && exec $C/ucsc-cell-browser/.venv/bin/cbBuild -o $html"
          last_ok || break
        fi
        web ucsc default $n $html ;;
      *) web $tool $var $n $(h5ad $n) ;;
    esac
    last_ok || break
  done
done
