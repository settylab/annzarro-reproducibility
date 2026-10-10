#!/bin/sh
# Gap session A: bm_demo matrix shots. Usage: notes/comparison/demos/scale_probe/gap_run.sh sh <this>
DEMO_ROOT="${DEMO_ROOT:-$HOME/annzarro_compare}"  # local demos, apps and data
REPO="$(cd "$(dirname "$0")" && git rev-parse --show-toplevel)"  # repository root
cd $REPO
PY=$DEMO_ROOT/_browser/.venv/bin/python
$PY notes/comparison/demos/_focus_run.py cirrocumulus 8901 notes/comparison/demos/cirrocumulus/recap_matrix.py
rm -f $DEMO_ROOT/_data/bm_demo.json; rm -rf $DEMO_ROOT/_data/results/*
