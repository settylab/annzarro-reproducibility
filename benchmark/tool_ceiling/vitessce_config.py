#!/usr/bin/env python
"""A Vitessce input directory: store.zarr (a symlink to the AnnData zarr store,
X stored CSC, which Vitessce reads per gene) and config.json (one UMAP
scatterplot, the Cell Sets tree with obs/cell_line_id, the Gene List).
No conversion: Vitessce reads the same store AnnZarro reads.

Usage: vitessce_config.py STORE OUTDIR PORT
"""
import json
import sys
from pathlib import Path

store, out, port = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
link = out / "store.zarr"
if link.is_symlink():
    link.unlink()
link.symlink_to(store)
files = [{"fileType": "anndata.zarr", "url": f"http://127.0.0.1:{port}/store.zarr", "options": {
    "obsEmbedding": [{"path": "obsm/X_umap", "embeddingType": "UMAP", "dims": [0, 1]}],
    "obsSets": [{"name": "Cell line", "path": "obs/cell_line_id"}],
    "obsFeatureMatrix": {"path": "X"}}}]
config = {"version": "1.0.16", "name": "tool_ceiling", "initStrategy": "auto",
          "datasets": [{"uid": "d", "name": "tahoe", "files": files}],
          "coordinationSpace": {"embeddingType": {"A": "UMAP"}},
          "layout": [{"component": "scatterplot", "coordinationScopes": {"embeddingType": "A"}, "x": 0, "y": 0, "w": 8, "h": 12},
                     {"component": "obsSets", "x": 8, "y": 0, "w": 4, "h": 6},
                     {"component": "featureList", "x": 8, "y": 6, "w": 4, "h": 6}]}
(out / "config.json").write_text(json.dumps(config, indent=1))
