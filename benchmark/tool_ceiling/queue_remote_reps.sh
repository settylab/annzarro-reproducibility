#!/bin/bash
# Repeats r2, r3 at 1M and 95.6M of the remote AnnZarro client (noise check).
cd "$(dirname "$0")"
URL=$1 VER=$2
R=$SCRATCH/annzarro-scale/stores_panel
PY=.venv/bin/python
for L in 1M:1000000 95.6M:95624334; do lab=${L%%:*} n=${L#*:}
  for rep in 2 3; do
    $PY run.py --web --tool annzarro --variant remote_$VER --n $n --run $rep --note "server $URL annzarro $VER" -- \
      $PY annzarro_task.py default $R/n$lab/tahoe_panel_$lab.zarr {out} --server-url $URL --proxy socks5://127.0.0.1:8767 \
      --n $n --probe-store $R/n1M/tahoe_panel_1M.zarr --version-label $VER
  done
done
