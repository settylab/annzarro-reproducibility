#!/bin/bash
# UCSC 5M builds again (r1) into scratch dirs: the r0 builds overlapped a user session.
cd "$(dirname "$0")"
D=$DATA_ROOT/tool_ceiling_data C=$DEMO_ROOT PY=.venv/bin/python
i=$D/ucsc_r1/in_5000000 h=$D/ucsc_r1/html_5000000; rm -rf $i $h
$PY run.py --tool ucsc --variant cbImportScanpy --phase convert --n 5000000 --run 1 --timeout 7200 -- \
  $C/ucsc-cell-browser/.venv/bin/cbImportScanpy -i $D/h5ad/tahoe_first5000000.h5ad -o $i -n first5000000 --clusterField=cell_line_id --skipMarkers -f mtx
$PY run.py --tool ucsc --variant cbBuild --phase convert --n 5000000 --run 1 --timeout 7200 -- bash -c "cd $i && exec $C/ucsc-cell-browser/.venv/bin/cbBuild -o $h"
rm -rf $i $h
