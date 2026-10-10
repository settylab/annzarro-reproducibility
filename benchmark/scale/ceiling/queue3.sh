#!/bin/bash
# Step 5: the full 95.6M plot on the branch, best settings (bundled Chromium, new headless, defaults).
cd benchmark/scale/ceiling
while pgrep -f queue2.sh >/dev/null; do sleep 20; done
S=$DATA_ROOT/tahoe_scale_ceiling
C=".venv/bin/python ceiling.py $S/syn_95624334.zarr --exe .venv-pc/bin/annzarro --recolour 3 --zoom 4 --drag 3 --limit 900 --port 8959"
$C --cold --reps 3 --out results/final.jsonl --tag final_cold > results/final.log 2>&1
$C --warm --reps 4 --out results/final.jsonl --tag final_warm >> results/final.log 2>&1
echo QUEUE3 DONE >> results/final.log
