#!/bin/sh
# One gap session for Cirrocumulus: bm_demo checks, then the lymph node spatial demo. Starts and stops both servers.
# Usage: notes/comparison/demos/scale_probe/gap_run.sh sh notes/comparison/demos/cirrocumulus/matrix_check.sh
DEMO_ROOT="${DEMO_ROOT:-$HOME/annzarro_compare}"  # local demos, apps and data
REPO="$(cd "$(dirname "$0")" && git rev-parse --show-toplevel)"  # repository root
cd $REPO/notes/comparison
PY=$DEMO_ROOT/_browser/.venv/bin/python
C=$DEMO_ROOT/cirrocumulus
$PY demos/_focus_run.py cirrocumulus 8901 demos/cirrocumulus/matrix_check.py
(cd $C/lymph && exec $C/.venv/bin/cirro launch --host 127.0.0.1 --port 8901 --no-open V1_Human_Lymph_Node.h5ad --spatial spatial > /tmp/cirro_lymph.log 2>&1) &
i=0; until curl -s -o /dev/null http://127.0.0.1:8901/ || [ $i -gt 120 ]; do sleep 1; i=$((i+1)); done; echo "lymph up after ${i}s"
$PY demos/_focus_run.py none 8901 demos/cirrocumulus/matrix_check_spatial.py
$C/stop.sh
