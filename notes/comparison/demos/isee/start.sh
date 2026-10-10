#!/bin/sh
# iSEE (Bioconductor) in its own micromamba R env. Open http://127.0.0.1:8902 (first load ~20 s).
# Stop: ./stop.sh (or Ctrl-C).
cd "$(dirname "$0")"
exec ../_mamba/envs/rtools/bin/Rscript app.R
