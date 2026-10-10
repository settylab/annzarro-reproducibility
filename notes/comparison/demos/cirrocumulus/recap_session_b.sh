#!/bin/sh
# Gap session B: focus 01-04 on bm_demo, then m07/m11 on the lymph node example. Usage: notes/comparison/demos/scale_probe/gap_run.sh sh <this>
DEMO_ROOT="${DEMO_ROOT:-$HOME/annzarro_compare}"  # local demos, apps and data
REPO="$(cd "$(dirname "$0")" && git rev-parse --show-toplevel)"  # repository root
cd $REPO
PY=$DEMO_ROOT/_browser/.venv/bin/python
C=$DEMO_ROOT/cirrocumulus
$PY notes/comparison/demos/_focus_run.py cirrocumulus 8901 notes/comparison/demos/cirrocumulus/recap_focus.py
(cd $C/lymph && exec $C/.venv/bin/cirro launch --host 127.0.0.1 --port 8901 --no-open V1_Human_Lymph_Node.h5ad --spatial spatial > /tmp/cirro_lymph.log 2>&1) &
i=0; until curl -s -o /dev/null http://127.0.0.1:8901/ || [ $i -gt 90 ]; do sleep 1; i=$((i+1)); done; echo "lymph up after ${i}s"
$PY notes/comparison/demos/_focus_run.py none 8901 notes/comparison/demos/cirrocumulus/recap_spatial.py
$C/stop.sh
