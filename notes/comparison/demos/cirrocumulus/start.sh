#!/bin/sh
# Cirrocumulus (local mode) on the shared bone marrow demo. Open http://127.0.0.1:8901
# Stop: ./stop.sh (or Ctrl-C when run in the foreground).
cd "$(dirname "$0")"
exec .venv/bin/cirro launch --host 127.0.0.1 --port 8901 --no-open ../_data/bm_demo.h5ad
