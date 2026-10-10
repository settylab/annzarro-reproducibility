#!/bin/sh
# ShinyCell app built by build.R. Open http://127.0.0.1:8907
# Stop: ./stop.sh (or Ctrl-C).
cd "$(dirname "$0")"
exec ../_mamba/envs/rtools/bin/Rscript -e 'shiny::runApp("app", host = "127.0.0.1", port = 8907, launch.browser = FALSE)'
