#!/bin/bash
cd benchmark/scale/ceiling
S=$DATA_ROOT/tahoe_scale_ceiling
T="perl -e 'alarm shift; exec @ARGV'"
C=".venv/bin/python ceiling.py --recolour 1 --zoom 2 --limit 900"
run() { perl -e 'alarm shift; exec @ARGV' "$@"; }
run 420 $C $S/syn_10000000.zarr --colors gene --exe .venv-base/bin/annzarro --args "--js-flags=--max-old-space-size=16384" --out results/flags.jsonl --tag base_maxold16g --port 8953 > results/flags.log 2>&1; echo "flags gene10M exit $?" >> results/queue4.log
pkill -f "port 8953"
run 420 $C $S/syn_20000000.zarr --colors cat --exe .venv-base/bin/annzarro --args "--js-flags=--max-old-space-size=16384" --out results/flags.jsonl --tag base_maxold16g --port 8953 >> results/flags.log 2>&1; echo "flags cat20M exit $?" >> results/queue4.log
pkill -f "port 8953"
run 900 $C $S/syn_1000000.zarr --exe .venv-pc/bin/annzarro --out results/pc_regress.jsonl --tag pc_1M_regular --port 8959 > results/pc_regress.log 2>&1; echo "regress exit $?" >> results/queue4.log
run 1500 $C $S/syn_95624334.zarr --exe .venv-pc/bin/annzarro --channel chrome --drag 3 --zoom 4 --out results/pc_browsers.jsonl --tag pc_chrome --port 8959 > results/pc_browsers.log 2>&1; echo "chrome exit $?" >> results/queue4.log
pkill -f "port 8959"
run 1500 $C $S/syn_95624334.zarr --exe .venv-pc/bin/annzarro --drag 3 --zoom 4 --args "--ignore-gpu-blocklist --force-gpu-mem-available-mb=16384 --use-angle=metal --enable-gpu-rasterization" --out results/pc_browsers.jsonl --tag pc_gpuflags --port 8959 >> results/pc_browsers.log 2>&1; echo "gpuflags exit $?" >> results/queue4.log
pkill -f "port 8959"
F=".venv/bin/python ceiling.py $S/syn_95624334.zarr --exe .venv-pc/bin/annzarro --recolour 3 --zoom 4 --drag 3 --limit 900 --port 8959"
run 3600 $F --cold --reps 3 --out results/final.jsonl --tag final_cold > results/final.log 2>&1; echo "final cold exit $?" >> results/queue4.log
pkill -f "port 8959"
run 3600 $F --warm --reps 4 --out results/final.jsonl --tag final_warm >> results/final.log 2>&1; echo "final warm exit $?" >> results/queue4.log
pkill -f "port 8959"
echo QUEUE4 DONE >> results/queue4.log
