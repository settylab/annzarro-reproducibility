#!/bin/sh
# Vitessce: the hosted app at vitessce.io reads the local AnnData zarr and config served here.
# Data and config are served on 127.0.0.1:8904; no data leave the machine.
# Open: https://vitessce.io/?url=http://127.0.0.1:8904/config.json
# Stop: ./stop.sh (or Ctrl-C).
cd "$(dirname "$0")"
exec ../ucsc-cell-browser/.venv/bin/python ../_bin/serve.py store 8904
