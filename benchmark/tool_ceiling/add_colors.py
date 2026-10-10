#!/usr/bin/env python
"""Add uns/<obs>_colors to an h5ad, as scanpy writes them after sc.pl.umap(color=obs):
scanpy's palette for that many categories (godsnot_102 above 28). TissUUmaps
colours a categorical by these when present and draws every category in one
colour otherwise; a scanpy user's h5ad usually carries them.

Usage: add_colors.py H5AD [OBS ...]   (default cell_line_id)
"""
import sys

import h5py
import numpy as np
from scanpy.plotting import palettes

path, cols = sys.argv[1], sys.argv[2:] or ["cell_line_id"]
with h5py.File(path, "a") as f:
    uns = f.require_group("uns")
    if "encoding-type" not in uns.attrs:
        uns.attrs.update({"encoding-type": "dict", "encoding-version": "0.1.0"})
    for c in cols:
        k = len(f[f"obs/{c}/categories"])
        pal = palettes.default_20 if k <= 20 else palettes.default_28 if k <= 28 else palettes.godsnot_102
        name = f"{c}_colors"
        if name in uns:
            del uns[name]
        d = uns.create_dataset(name, data=np.array(pal[:k], dtype=object), dtype=h5py.string_dtype())
        d.attrs.update({"encoding-type": "string-array", "encoding-version": "0.2.0"})
        print(path, name, k)
