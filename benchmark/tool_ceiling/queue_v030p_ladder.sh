#!/bin/bash
# AnnZarro v030-preview 12f93f8 on the real prefixes 1M-50M (the 95.6M run is in queue_synth.sh).
cd "$(dirname "$0")"
PY=.venv/bin/python
EXE=$ENVS_ROOT/annzarro_v030p_12f93f8/.venv/bin/annzarro
P=$DATA_ROOT/tahoe_scale/stores/rerun_prefix
for n in 1000000 2000000 5000000 10000000 20000000 50000000; do
  $PY run.py --web --tool annzarro --variant v030p --n $n --note "AnnZarro v030-preview 12f93f8, local server" -- \
    $PY annzarro_task.py default $P/tahoe95_first$n.zarr {out} --exe $EXE --inprocess --version-label 12f93f8
done
