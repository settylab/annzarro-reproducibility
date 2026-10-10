#!/usr/bin/env python
"""Control for umap_tahoe.py validate: kNN preservation (PC -> UMAP) versus pool size.

Exactly the code run on 2026-10-03 ~00:40 PDT on the sandbox host (4 OMP threads, nice 10), from
benchmark/scale/ with WORK=$SCRATCH/annzarro-scale/work; output
umap/knn_preservation_by_pool.json. Uses umap_tahoe.knn_preservation, the same function as validate:
exact faiss IndexFlatL2 search within the pool, K=15, the query cell itself excluded.

Pools, drawn with ONE generator, default_rng(7), in this order:
  for size in 5,000, 10,000, 100,000:
    reference: a random subset (no replacement) of the 999,073 reference cells (ref_idx.npy);
    placed:    2*size random cells of all 95,624,334, minus reference cells, the first `size` of them.
  nq (query cells) = min(size, 20,000), drawn inside knn_preservation from the same generator.
"""
import json, numpy as np, sys
sys.path.insert(0, ".")
import umap_tahoe as ut
W="$SCRATCH/annzarro-scale/work"
pcs=np.load(W+"/master_pcs.npy", mmap_mode="r"); U=np.load(W+"/umap/umap_all.f32.npy", mmap_mode="r")
ref=np.load(W+"/umap/ref_idx.npy"); N=pcs.shape[0]
rng=np.random.default_rng(7)
placed_all=None
out={}
for size in (5000, 10000, 100000):
    for name in ("reference","placed"):
        if name=="reference":
            idx=np.sort(rng.choice(ref, size, replace=False))
        else:
            c=np.sort(rng.choice(N, size*2, replace=False)); c=np.setdiff1d(c, ref)[:size]; idx=np.sort(c)
        P=np.asarray(pcs[idx], dtype=np.float32); Uu=np.asarray(U[idx])
        v=ut.knn_preservation(P, Uu, min(size, 20000), rng)
        out[f"{name}_pool{size}"]=v; print(name, size, round(v,4), flush=True)
json.dump(out, open(W+"/umap/knn_preservation_by_pool.json","w"), indent=1)
