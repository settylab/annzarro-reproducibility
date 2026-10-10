#!/bin/bash
# 120f322 rungs whose first plot was refused before the guard text was recorded: r1.
cd "$(dirname "$0")"
PY=.venv/bin/python EXE=$ENVS_ROOT/annzarro_v030p_120f322/.venv/bin/annzarro OLD=$DATA_ROOT/tahoe_scale_ceiling
while pgrep -f queue_fixed.sh >/dev/null; do sleep 30; done
for n in 160000000 167000000 175000000; do
  $PY run.py --web --tool annzarro --variant v030_syn --n $n --run 1 --note "AnnZarro v030-preview 120f322, local server" -- \
    $PY annzarro_task.py default $OLD/syn_$n.zarr {out} --exe $EXE --inprocess --version-label 120f322 --cat cell_type --gene GENE0
done
$PY run.py --web --tool annzarro --variant v030_synth --n 200000000 --run 1 --note "AnnZarro v030-preview 120f322, local server" -- \
  $PY annzarro_task.py default $DATA_ROOT/tool_ceiling_data/synth/synth_tahoe_200000000.zarr {out} --exe $EXE --inprocess --version-label 120f322
