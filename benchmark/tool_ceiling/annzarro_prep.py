#!/usr/bin/env python
"""AnnZarro's documented preparation path (docs/data/preparing-a-store.md,
"General recipe", v0.3.0), run on the ladder's h5ad: read_h5ad, float32 for
float arrays (already float32 here), X as CSC (the matrix cells are coloured by,
gene columns), write zarr format 2 with consolidated metadata. The optional
rechunk step does not apply: the store has no large dense layer. Measured as a
conversion run charged to AnnZarro.

Usage: annzarro_prep.py IN.h5ad OUT.zarr
"""
import sys
import time
from importlib.metadata import version

import anndata as ad
import numpy as np
import scipy.sparse as sp

t0 = time.time()
adata = ad.read_h5ad(sys.argv[1])
print(f"read {time.time() - t0:.0f}s", flush=True)
for slot in ("layers", "obsp", "varp", "obsm"):
    for key, arr in getattr(adata, slot).items():
        if getattr(arr, "dtype", None) == np.float64:
            getattr(adata, slot)[key] = arr.astype(np.float32)
adata.X = sp.csc_matrix(adata.X, dtype=np.float32)
print(f"csc {time.time() - t0:.0f}s", flush=True)
ad.settings.zarr_write_format = 2
adata.write_zarr(sys.argv[2])
print(f"written {time.time() - t0:.0f}s anndata {version('anndata')} zarr {version('zarr')} scipy {version('scipy')}",
      flush=True)
