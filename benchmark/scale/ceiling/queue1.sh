#!/bin/bash
# Chrome baseline, then the Plotly-only harness matrix.
cd benchmark/scale/ceiling
S=$DATA_ROOT/tahoe_scale_ceiling
PY=.venv/bin/python
$PY ceiling.py $S/syn_5000000.zarr $S/syn_7500000.zarr $S/syn_10000000.zarr $S/syn_15000000.zarr $S/syn_20000000.zarr --exe .venv-base/bin/annzarro --channel chrome --out results/baseline_chrome.jsonl --tag base_chrome --recolour 1 --zoom 2 --port 8954 > results/baseline_chrome.log 2>&1
$PY ceiling.py $S/syn_7500000.zarr $S/syn_15000000.zarr --exe .venv-base/bin/annzarro --out results/baseline_chromium.jsonl --tag base_chromium --recolour 1 --zoom 2 --port 8953 >> results/baseline_chromium.log 2>&1
SZ="$S/syn_10000000.zarr $S/syn_35000000.zarr $S/syn_60000000.zarr $S/syn_95624334.zarr"
H="$PY harness.py --out results/harness.jsonl"
$H $SZ --mode cat --chunk 99999 --typed --tag cat_c1e5_typed
$H $SZ --mode cat --chunk 0 --typed --tag cat_nochunk_typed
$H $SZ --mode one --chunk 0 --typed --tag one_nochunk_typed
$H $SZ --mode one --chunk 99999 --typed --tag one_c1e5_typed
$H $SZ --mode num --chunk 0 --typed --tag num_nochunk_typed
$H $SZ --mode bins --chunk 99999 --typed --tag bins64_c1e5_typed
$H $SZ --mode cat --chunk 99999 --tag cat_c1e5_array
$H $SZ --mode cat --chunk 99999 --typed --hover --tag cat_c1e5_typed_hover
$H $SZ --mode cat --chunk 99999 --typed --channel chrome --tag cat_c1e5_typed_chrome
echo QUEUE1 DONE
