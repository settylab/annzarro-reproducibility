#!/bin/bash
# AnnZarro v030-preview 12f93f8 at the edge, on scale-benchmarker's synthetic stores
# (build_stores.py, 300M master; obs cell_type with 50 categories, 4 dense genes):
# 150M, 175M, 182M, 200M. Colour: GENE0, then cell_type. Local server, measured apart.
cd "$(dirname "$0")"
PY=.venv/bin/python
EXE=$ENVS_ROOT/annzarro_v030p_12f93f8/.venv/bin/annzarro
SY=$DATA_ROOT/tahoe_scale_ceiling
for n in ${SIZES:-150000000 175000000 182000000 200000000}; do
  $PY run.py --web --tool annzarro --variant v030p_syn --n $n --note "AnnZarro v030-preview 12f93f8, local server; build_stores.py synthetic" -- \
    $PY annzarro_task.py default $SY/syn_$n.zarr {out} --exe $EXE --inprocess --version-label 12f93f8 --cat cell_type --gene GENE0
done
