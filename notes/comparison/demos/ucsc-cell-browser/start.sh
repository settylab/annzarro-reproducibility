#!/bin/sh
# UCSC Cell Browser: static site built by cbImportScanpy + cbBuild (see ../_local_demos notes).
# Served by a Range-capable static server on 127.0.0.1. Open http://127.0.0.1:8906/?ds=bm_demo
# Stop: ./stop.sh (or Ctrl-C).
cd "$(dirname "$0")"
exec .venv/bin/python ../_bin/serve.py html 8906
