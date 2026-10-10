#!/usr/bin/env python
"""Corrected control (v2): kNN preservation (PC -> UMAP) versus pool size, with UNIFORM pools.

v1 (knn_preservation_by_pool.py) took the placed pool as the first `size` of 2*size sorted random cells,
i.e. the low-row-index half (early shards), not a uniform sample of placed cells. v2 draws every pool
uniformly:
- reference: rng.choice(ref_idx, size), without replacement;
- placed: rng.choice(all non-reference rows, size), without replacement;
- a separate generator per pool (seed 11 + pool index), so no pool depends on another's draws;
- nq = min(size, 20,000);
- umap_tahoe.knn_preservation: exact search within the pool, K=15.
Run from benchmark/scale/ with the panel venv.
"""
import json
import sys

import numpy as np

sys.path.insert(0, ".")
import umap_tahoe as ut  # noqa: E402

W = "$SCRATCH/annzarro-scale/work"
pcs = np.load(W + "/master_pcs.npy", mmap_mode="r")
U = np.load(W + "/umap/umap_all.f32.npy", mmap_mode="r")
ref = np.load(W + "/umap/ref_idx.npy")
N = pcs.shape[0]
nonref = np.setdiff1d(np.arange(N, dtype=np.int64), ref, assume_unique=True)
out, k = {}, 0
for size in (5000, 10000, 100000):
    for name, popn in (("reference", ref), ("placed", nonref)):
        rng = np.random.default_rng(11 + k)
        k += 1
        idx = np.sort(rng.choice(popn, size, replace=False))
        P = np.asarray(pcs[idx], dtype=np.float32)
        Uu = np.asarray(U[idx])
        v = ut.knn_preservation(P, Uu, min(size, 20000), rng)
        out[f"{name}_pool{size}"] = v
        out[f"{name}_pool{size}_median_row"] = int(np.median(idx))
        print(name, size, round(v, 4), "median row", int(np.median(idx)), flush=True)
json.dump(out, open(W + "/umap/knn_preservation_by_pool_v2.json", "w"), indent=1)
