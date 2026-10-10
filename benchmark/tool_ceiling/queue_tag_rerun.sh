#!/bin/bash
# E6: AnnZarro at the v0.3.0 tag, server footprint and local-app total: real 95.6M
# plus the edge sizes. Usage: queue_tag_rerun.sh EXE TAG_SHA "N:STORE N:STORE ..."
cd "$(dirname "$0")"
PY=.venv/bin/python EXE=$1 VER=$2
for ns in $3; do n=${ns%%:*} store=${ns#*:}
  $PY run.py --web --tool annzarro --variant v030_tag --n $n --note "AnnZarro v0.3.0 $VER, local server" -- \
    $PY annzarro_task.py default $store {out} --exe $EXE --inprocess --version-label $VER
done
