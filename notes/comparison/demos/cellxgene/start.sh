#!/bin/sh
# CELLxGENE Annotate 1.3.0 on the shared bone marrow demo. Open http://127.0.0.1:8903
# Annotations you create are saved under ./annotations. Add --backed to read X lazily from disk.
# Stop: ./stop.sh (or Ctrl-C).
cd "$(dirname "$0")"
exec .venv/bin/cellxgene launch ../_data/bm_demo.h5ad --host 127.0.0.1 --port 8903 \
  --annotations-dir annotations --title "CELLxGENE Annotate: bone marrow demo" "$@"
