#!/usr/bin/env python
"""Build realistic dense pairwise matrices as minimal AnnData zarr v2 stores.

kernel N  : dense float32 Gaussian kernel (obsp/gaussian_kernel, N x N) on the
            diffusion map of N cells subsampled (seeded) from the 1.17M-cell
            integrated atlas (obsm/X_diffmap, components 1..14; component 0 is the
            constant eigenvector). Bandwidth sigma = median distance to the 30th
            nearest neighbour, estimated on 2,000 seeded query cells. K = exp(-d^2 / 2 sigma^2).
dist  N   : the same N cells (same seed), dense float32 Euclidean diffusion-map distance
            (obsp/diffmap_distance): no exact zeros off the diagonal, so it is the
            worst case for compression and JSON payload (cf. the served spatial-A dist_diffmap).
corr  M   : dense float32 Pearson gene-gene correlation (varp/gene_corr_pearson, M x M)
            over ALL 460,337 cells of scPLM layers/logcounts, for the M genes
            detected in the most cells (deterministic; no sampling).

Chunking and compressor follow the existing dense pairwise arrays in the served
spatial-A store: obsp (16, n_obs), varp (64, n_vars), blosc-zstd clevel 5, shuffle.
Seeds are fixed (SEED below) and recorded in the store's uns-free root .zattrs.

Usage: build_pairwise.py kernel N DST   |   build_pairwise.py corr M DST
"""
import json
import os
import shutil
import sys
import time

import numcodecs
import numpy as np
import scipy.sparse as sp
import zarr

SEED = 20261001
LIVER = "$DATA_ROOT/lab-data/data/processed_zarr"
ATLAS = os.path.join(LIVER, "atlas-1.17M-scvi.zarr")
SCPLM = os.path.join(LIVER, "atlas-scPLM.zarr")
ZSTD = numcodecs.Blosc(cname="zstd", clevel=5, shuffle=numcodecs.Blosc.SHUFFLE)
LZ4 = numcodecs.Blosc(cname="lz4", clevel=5, shuffle=numcodecs.Blosc.SHUFFLE)


def attrs(path, d):
    with open(os.path.join(path, ".zattrs"), "w") as fh:
        json.dump(d, fh)


def group(path, enc="dict"):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, ".zgroup"), "w") as fh:
        json.dump({"zarr_format": 2}, fh)
    attrs(path, {"encoding-type": enc, "encoding-version": "0.1.0"})


def string_index(path, names):
    group(path, "dataframe")
    attrs(path, {"_index": "_index", "column-order": [], "encoding-type": "dataframe",
                 "encoding-version": "0.2.0"})
    a = zarr.create_array(store=os.path.join(path, "_index"), shape=(len(names),),
                          chunks=(min(len(names), 37500),), dtype=str, zarr_format=2,
                          compressors=LZ4)
    a[:] = np.asarray(names, dtype=object)
    attrs(os.path.join(path, "_index"), {"encoding-type": "string-array", "encoding-version": "0.2.0"})


def skeleton(tmp, obs_names, var_names, meta):
    group(tmp, "anndata")
    attrs(tmp, {"encoding-type": "anndata", "encoding-version": "0.1.0", "benchmark_build": meta})
    string_index(os.path.join(tmp, "obs"), obs_names)
    string_index(os.path.join(tmp, "var"), var_names)


def dense_rows(store, name, n_rows, n_cols, chunk_rows, rowfun, block=1024):
    a = zarr.create_array(store=store, shape=(n_rows, n_cols), chunks=(chunk_rows, n_cols),
                          dtype="<f4", zarr_format=2, compressors=ZSTD, fill_value=0.0)
    attrs(store, {"encoding-type": "array", "encoding-version": "0.2.0"})
    t0 = time.time()
    for i in range(0, n_rows, block):
        a[i:i + block] = rowfun(i, min(n_rows, i + block))
        if (i // block) % 20 == 0:
            print(f"{name}: rows {i}/{n_rows} {time.time() - t0:.0f}s", flush=True)
    return a


def build_kernel(n, dst, dist=False):
    rng = np.random.default_rng(SEED)
    dm = zarr.open_array(os.path.join(ATLAS, "obsm/X_diffmap"), mode="r")
    names = zarr.open_array(os.path.join(ATLAS, "obs/_index"), mode="r")
    idx = np.sort(rng.choice(dm.shape[0], n, replace=False))
    X = np.asarray(dm[:])[idx, 1:].astype(np.float64)
    obs_names = np.asarray(names[:])[idx]
    sq = (X ** 2).sum(1)
    q = rng.choice(n, 2000, replace=False)
    d2q = np.maximum(sq[q, None] + sq[None, :] - 2 * X[q] @ X.T, 0)
    sigma = float(np.median(np.sqrt(np.partition(d2q, 30, axis=1)[:, 30])))
    print(f"kernel n={n} sigma={sigma:.6g}", flush=True)
    kind = "diffmap_distance" if dist else "gaussian_kernel"
    meta = dict(kind=kind, n=n, seed=SEED, source=ATLAS + ":obsm/X_diffmap[:,1:]",
                sigma=None if dist else sigma,
                sigma_rule=None if dist else "median distance to 30th NN over 2000 seeded query cells")
    tmp = dst + ".partial"
    shutil.rmtree(tmp, ignore_errors=True)
    skeleton(tmp, obs_names, [f"DC{i}" for i in range(1, X.shape[1] + 1)], meta)
    group(os.path.join(tmp, "obsp"))
    Xf = X.astype(np.float32)
    sqf = sq.astype(np.float32)

    def rows(i, j):
        d2 = np.maximum(sqf[i:j, None] + sqf[None, :] - 2 * Xf[i:j] @ Xf.T, 0)
        if dist:
            return np.sqrt(d2).astype(np.float32)
        return np.exp(-d2 / np.float32(2 * sigma * sigma)).astype(np.float32)

    dense_rows(os.path.join(tmp, "obsp", kind), kind, n, n, 16, rows)
    os.rename(tmp, dst)


def build_corr(m, dst):
    """Exact Pearson over ALL cells: G = sum_blocks B^T B accumulated in float64 over
    20,000-cell row blocks, cov = G/n - mu mu^T, C = cov / (sd sd^T). No cell sampling."""
    g = zarr.open_group(os.path.join(SCPLM, "layers/logcounts"), mode="r")
    indptr = np.asarray(g["indptr"][:])
    n_obs = zarr.open_array(os.path.join(SCPLM, "obs/_index"), mode="r").shape[0]
    n_vars = len(indptr) - 1
    det = np.diff(indptr)
    genes = np.sort(np.argsort(-det, kind="stable")[:m])
    if det[genes].min() < 2:
        raise SystemExit(f"only {(det >= 2).sum()} genes detected in >=2 cells; m={m} too large")
    t0 = time.time()
    data = np.asarray(g["data"][:], dtype=np.float32)
    indices = np.asarray(g["indices"][:])
    print(f"read logcounts nnz={len(data)} {time.time() - t0:.0f}s", flush=True)
    sub = sp.csc_matrix((data, indices, indptr), shape=(n_obs, n_vars))[:, genes].tocsr()
    del data, indices
    s1 = np.asarray(sub.sum(0), dtype=np.float64).ravel()
    G = np.zeros((m, m), dtype=np.float64)
    for i in range(0, n_obs, 20000):
        B = sub[i:i + 20000].toarray()
        G += B.T @ B
        print(f"corr m={m}: cells {i}/{n_obs} {time.time() - t0:.0f}s", flush=True)
    mu = s1 / n_obs
    cov = G / n_obs - np.outer(mu, mu)
    del G
    sd = np.sqrt(np.clip(np.diag(cov), 0, None))
    if (sd == 0).any():
        raise SystemExit(f"{int((sd == 0).sum())} selected genes are constant")
    C = cov / np.outer(sd, sd)
    np.clip(C, -1, 1, out=C)
    print(f"corr m={m} computed {time.time() - t0:.0f}s; min detected={det[genes].min()}", flush=True)
    var_all = np.asarray(zarr.open_array(os.path.join(SCPLM, "var/_index"), mode="r")[:])
    obs_all = np.asarray(zarr.open_array(os.path.join(SCPLM, "obs/_index"), mode="r")[:])
    meta = dict(kind="gene_corr_pearson", m=m, n_cells=int(n_obs), source=SCPLM + ":layers/logcounts",
                gene_rule="top-m genes by number of cells detected (all cells)",
                min_cells_detected=int(det[genes].min()))
    tmp = dst + ".partial"
    shutil.rmtree(tmp, ignore_errors=True)
    skeleton(tmp, obs_all, var_all[genes], meta)
    group(os.path.join(tmp, "varp"))
    dense_rows(os.path.join(tmp, "varp", "gene_corr_pearson"), "corr", m, m, 64,
               lambda i, j: C[i:j].astype(np.float32))
    os.rename(tmp, dst)


if __name__ == "__main__":
    kind, size, dst = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    if os.path.exists(dst):
        raise SystemExit(f"refusing to overwrite {dst}")
    {"kernel": build_kernel, "corr": build_corr,
     "dist": lambda n, d: build_kernel(n, d, dist=True)}[kind](size, dst)
    print("done", dst)
