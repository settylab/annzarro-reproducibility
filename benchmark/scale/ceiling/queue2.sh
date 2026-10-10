#!/bin/bash
# After queue1: Chrome/Chromium baselines with the watchdog, flag tests, large path runs, final timing.
cd benchmark/scale/ceiling
while pgrep -f queue1.sh >/dev/null; do sleep 20; done
S=$DATA_ROOT/tahoe_scale_ceiling
PY=.venv/bin/python
C="$PY ceiling.py --recolour 1 --zoom 2 --limit 900"
# 1-2. baselines (regular path, fast-transfer f5bd7d6)
$C $S/syn_7500000.zarr $S/syn_10000000.zarr $S/syn_15000000.zarr $S/syn_20000000.zarr --exe .venv-base/bin/annzarro --channel chrome --out results/baseline_chrome2.jsonl --tag base_chrome --port 8954 > results/baseline_chrome2.log 2>&1
$C $S/syn_7500000.zarr --colors gene --exe .venv-base/bin/annzarro --out results/baseline_chromium2.jsonl --tag base_chromium --port 8953 > results/baseline_chromium2.log 2>&1
$C $S/syn_15000000.zarr --colors cat --exe .venv-base/bin/annzarro --out results/baseline_chromium2.jsonl --tag base_chromium --port 8953 >> results/baseline_chromium2.log 2>&1
# 3. heap flag on the regular path
$C $S/syn_10000000.zarr --colors gene --exe .venv-base/bin/annzarro --args "--js-flags=--max-old-space-size=16384" --out results/flags.jsonl --tag base_maxold16g --port 8953 > results/flags.log 2>&1
$C $S/syn_20000000.zarr --colors cat --exe .venv-base/bin/annzarro --args "--js-flags=--max-old-space-size=16384" --out results/flags.jsonl --tag base_maxold16g --port 8953 >> results/flags.log 2>&1
# regular path below the threshold is unchanged on the branch
$C $S/syn_1000000.zarr --exe .venv-pc/bin/annzarro --out results/pc_regress.jsonl --tag pc_1M_regular --port 8959 > results/pc_regress.log 2>&1
# 4-5. large path at 95.6M: Chrome stable; GPU flags
$C $S/syn_95624334.zarr --exe .venv-pc/bin/annzarro --channel chrome --drag 3 --zoom 4 --out results/pc_browsers.jsonl --tag pc_chrome --port 8959 > results/pc_browsers.log 2>&1
$C $S/syn_95624334.zarr --exe .venv-pc/bin/annzarro --drag 3 --zoom 4 --args "--ignore-gpu-blocklist --force-gpu-mem-available-mb=16384 --use-angle=metal --enable-gpu-rasterization" --out results/pc_browsers.jsonl --tag pc_gpuflags --port 8959 >> results/pc_browsers.log 2>&1
echo QUEUE2 DONE
