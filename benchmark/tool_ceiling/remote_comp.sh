#!/bin/bash
# One client run against a competitor server hosted on the HPC (through the SOCKS proxy):
# only Chromium is measured; the HPC worker records the server's peak.
# Usage: remote_comp.sh TOOL VARIANT N URL [RUN]   e.g. remote_comp.sh cellxgene default 20000000 http://hpc-node-23:8791 0
cd "$(dirname "$0")"
TOOL=$1 VAR=$2 N=$3 URL=$4 RUN=${5:-0} PROXY=${PROXY:-socks5://localhost:1080} NOTE=${NOTE:-}
PY=.venv/bin/python
$PY run.py --web --tool $TOOL --variant remote_$VAR --n $N --run $RUN --note "server on HPC: $URL; $NOTE" -- \
  $PY web_task.py $TOOL $VAR none {out} --n $N --server-url $URL --proxy $PROXY
tail -1 results.csv | cut -d, -f1,8,9,11,12,15
