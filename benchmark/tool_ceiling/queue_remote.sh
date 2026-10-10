#!/bin/bash
# AnnZarro client ladder against a remote server (HPC, through the SOCKS proxy):
# only Chromium is measured; RTT/throughput probed before each run.
# Usage: queue_remote.sh URL VERSION [REPS]
cd "$(dirname "$0")"
URL=$1 VER=$2 REPS=${3:-1} BASE=${4:-0}
R=$SCRATCH/annzarro-scale/stores_panel
PY=.venv/bin/python
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
for L in 1M:1000000 2M:2000000 5M:5000000 10M:10000000 20M:20000000 50M:50000000 95.6M:95624334; do
  lab=${L%%:*} n=${L#*:}
  for rep in $(seq $BASE $((BASE+REPS-1))); do
    $PY run.py --web --tool annzarro --variant remote_$VER --n $n --run $rep --note "server $URL annzarro $VER" -- \
      $PY annzarro_task.py default $R/n$lab/tahoe_panel_$lab.zarr {out} --server-url $URL --proxy socks5://127.0.0.1:8767 \
      --n $n --probe-store $R/n1M/tahoe_panel_1M.zarr --version-label $VER
  done
  last_ok || break
done
