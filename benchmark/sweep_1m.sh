#!/bin/bash
# Chunk-shape sweep at 1,000,000 x 5,000 (each store ~18 GB): generate one
# shape, measure it, delete it, so the disk footprint stays at one store.
set -e
cd "$(dirname "$0")"
PY=../.venv/bin/python
for TAG in "$@"; do
  $PY generate_data.py sweep --sizes 1000000 --tags "$TAG"
  $PY run_benchmark.py sweep --sizes 1000000 $BENCH_ARGS   # BENCH_ARGS: e.g. --suffix _v031 --server-python ...
  rm -rf "../data/bench/sweep/n1000000/$TAG.zarr"
  $PY - "$TAG" <<'PY'
import json, sys
from pathlib import Path
p = Path("../data/bench/manifest.json"); m = json.loads(p.read_text())
m = {k: v for k, v in m.items() if k != f"sweep/n1000000/{sys.argv[1]}.zarr"}
p.write_text(json.dumps(m, indent=1, sort_keys=True))
PY
done
