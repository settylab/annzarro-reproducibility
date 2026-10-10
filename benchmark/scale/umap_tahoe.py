#!/usr/bin/env python
"""A 2-D UMAP for every cell of Tahoe-100M, computed on a laptop.

Input: the 50 PCs of every cell (``build_tahoe.py``: PCA fitted on 203,220
cells, every cell projected exactly) and the per-cell obs, both in store order.

Method:

  sample    A reference set balanced over plate x cell_line_id: the same
            number of cells from every (plate, cell line) stratum, all of a
            stratum's cells when it has fewer (seeded).
  fit       umap-learn on the reference cells' 50 PCs (n_neighbors=15,
            min_dist=0.3, euclidean, random_state=0). Euclidean because the
            PCs are a linear map of centred log-normalised counts, where
            Euclidean distance is the usual metric, and because placement
            searches the same space with exact L2 distances.
  place     Every cell: its k=15 nearest reference cells in PC space (faiss
            IVF-Flat, recall measured against exact search), coordinates =
            the inverse-distance-weighted mean of their UMAP coordinates.
            Reference cells keep their own fitted coordinates. Chunked, so
            memory does not grow with N; output float32 [N, 2] (.npy).
  validate  kNN preservation (fraction of a cell's 15 PC-space neighbours
            among its 15 UMAP neighbours) for reference vs placed cells,
            cell-line purity and silhouette of the layout, preview plots.
  write     obsm/X_umap into an AnnZarro store: the first N rows, since the
            stores are nested prefixes of the full cell order.

  umap_tahoe.py sample   --obs OBS.parquet --work WORK [--per-stratum 1430]
  umap_tahoe.py fit      --pcs PCS --work WORK
  umap_tahoe.py place    --pcs PCS --work WORK
  umap_tahoe.py validate --pcs PCS --obs OBS.parquet --work WORK
  umap_tahoe.py write    --work WORK --store STORE.zarr

PCS is a .npy of shape [N, 50] (float32, read memory-mapped) or a zarr array.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 0
K = 15
N_NEIGHBORS = 15
MIN_DIST = 0.3
METRIC = "euclidean"
NLIST = 4096           # IVF lists over ~1M reference cells
NPROBE = 32            # chosen by measured recall, see `place`
CHUNK = 1 << 20        # cells per placement chunk


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def versions():
    from importlib.metadata import version
    v = {p: version(p) for p in ["umap-learn", "pynndescent", "faiss-cpu", "numpy", "numba",
                                 "scikit-learn", "zarr"]}
    v["python"] = platform.python_version()
    v["machine"] = f"{platform.machine()} {os.cpu_count()} cores"
    return v


def open_pcs(path, in_memory=False):
    if str(path).endswith(".npy"):
        return np.load(path, mmap_mode=None if in_memory else "r")
    import zarr
    return zarr.open_array(str(path), mode="r")


def rows(pcs, idx):
    """PCs of the sorted cells `idx`, read one block of CHUNK consecutive rows at a time
    (a zarr read of the span between far-apart indices would load the whole array)."""
    if isinstance(pcs, np.ndarray):
        return np.asarray(pcs[idx], dtype=np.float32)
    out = np.empty((len(idx), pcs.shape[1]), np.float32)
    blk = idx // CHUNK
    for b in np.unique(blk):
        sel = np.flatnonzero(blk == b)
        lo = int(b) * CHUNK
        out[sel] = pcs[lo:min(lo + CHUNK, pcs.shape[0])][idx[sel] - lo]
    return out


def save_json(path, d):
    Path(path).write_text(json.dumps(d, indent=1, default=float))


# ------------------------------------------------------------------- sample
def cmd_sample(a):
    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    obs = pd.read_parquet(a.obs, columns=["plate", "cell_line_id"])
    rng = np.random.default_rng(SEED)
    strata = obs.groupby(["plate", "cell_line_id"], observed=True).indices
    pick, table = [], []
    for (plate, line), ix in sorted(strata.items()):
        take = min(a.per_stratum, len(ix))
        pick.append(np.sort(rng.choice(ix, take, replace=False)))
        table.append((plate, line, len(ix), take))
    ref = np.sort(np.concatenate(pick)).astype(np.int64)
    np.save(work / "ref_idx.npy", ref)
    t = pd.DataFrame(table, columns=["plate", "cell_line_id", "n_cells", "n_ref"])
    t.to_csv(work / "ref_strata.csv", index=False)
    save_json(work / "sample.json", {
        "n_cells": len(obs), "n_ref": len(ref), "per_stratum": a.per_stratum,
        "n_strata": len(t), "strata_below_target": int((t.n_cells < a.per_stratum).sum()),
        "plates": int(t.plate.nunique()), "cell_lines": int(t.cell_line_id.nunique())})
    log(f"reference: {len(ref):,} cells from {len(t)} strata")


# ------------------------------------------------------------------- fit
def cmd_fit(a):
    import umap
    work = Path(a.work)
    pcs = open_pcs(a.pcs, a.in_memory)
    ref = np.load(work / "ref_idx.npy")
    ref = ref[ref < pcs.shape[0]]
    t0 = time.time()
    X = rows(pcs, ref)
    t_read = time.time() - t0
    t0 = time.time()
    model = umap.UMAP(n_neighbors=N_NEIGHBORS, min_dist=MIN_DIST, metric=METRIC,
                      random_state=SEED, low_memory=True, verbose=True)
    emb = model.fit_transform(X).astype(np.float32)
    t_fit = time.time() - t0
    np.save(work / "ref_umap.npy", emb)
    save_json(work / "fit.json", {"n_ref": len(ref), "n_neighbors": N_NEIGHBORS, "min_dist": MIN_DIST,
                                  "metric": METRIC, "random_state": SEED, "n_epochs": model.n_epochs,
                                  "read_s": t_read, "fit_s": t_fit, "versions": versions()})
    log(f"UMAP of {len(ref):,} reference cells: {t_fit:.0f} s")


# ------------------------------------------------------------------- place
def build_index(X, nlist=NLIST):
    import faiss
    q = faiss.IndexFlatL2(X.shape[1])
    ix = faiss.IndexIVFFlat(q, X.shape[1], nlist)
    rng = np.random.default_rng(SEED)
    ix.train(X[rng.choice(len(X), min(len(X), 100 * nlist), replace=False)])
    ix.add(X)
    ix.nprobe = NPROBE
    return ix


def place(ix, emb, q):
    D, I = ix.search(np.ascontiguousarray(q, dtype=np.float32), K)
    w = 1.0 / (np.sqrt(np.maximum(D, 0)) + 1e-3)
    w[I < 0] = 0
    I = np.maximum(I, 0)
    return ((w[..., None] * emb[I]).sum(1) / w.sum(1, keepdims=True)).astype(np.float32)


def cmd_place(a):
    import faiss
    faiss.omp_set_num_threads(a.threads)
    work = Path(a.work)
    pcs = open_pcs(a.pcs, a.in_memory)
    N = pcs.shape[0]
    ref = np.load(work / "ref_idx.npy")
    ref = ref[ref < N]                   # (only matters for a test master shorter than obs)
    emb = np.load(work / "ref_umap.npy")
    assert len(emb) == len(ref)
    X = rows(pcs, ref)
    t0 = time.time()
    ix = build_index(X, a.nlist)
    t_build = time.time() - t0
    # recall against exact search, on 100k random non-reference cells
    rng = np.random.default_rng(SEED + 1)
    probe = np.sort(rng.choice(np.setdiff1d(np.arange(N), ref, assume_unique=True), 100_000, replace=False))
    Q = rows(pcs, probe)
    ex = faiss.IndexFlatL2(X.shape[1]); ex.add(X)
    _, G = ex.search(Q, K)
    # nprobe: the smallest of the ladder whose recall@K reaches --target-recall
    by_nprobe = []
    for nprobe in [p for p in (NPROBE, 64, 128, 256, 512, 1024) if p <= a.nlist]:
        ix.nprobe = nprobe
        t0 = time.time(); _, I = ix.search(Q, K); t_q = time.time() - t0
        recall = float(np.mean([len(np.intersect1d(i, g)) / K for i, g in zip(I, G)]))
        by_nprobe.append({"nprobe": nprobe, "recall": recall, "s_per_100k": t_q})
        log(f"IVF{a.nlist} nprobe {nprobe}: recall@{K} {recall:.3f}, {t_q:.1f} s per 100k queries")
        if recall >= a.target_recall:
            break
    if recall < a.target_recall:
        log(f"WARNING: recall {recall:.3f} < {a.target_recall} at the largest nprobe tried")
    out_path = work / "umap_all.f32.npy"
    out = np.lib.format.open_memmap(out_path, mode="w+", dtype=np.float32, shape=(N, 2))
    t0 = time.time()
    for s in range(0, N, CHUNK):
        e = min(s + CHUNK, N)
        out[s:e] = place(ix, emb, pcs[s:e])
        if (s // CHUNK) % 10 == 0:
            el = time.time() - t0
            log(f"placed {e:,}/{N:,} ({el:.0f} s, eta {el / e * (N - e):.0f} s)")
    out[ref] = emb                       # reference cells keep their fitted coordinates
    out.flush()
    t_place = time.time() - t0
    save_json(work / "place.json", {"k": K, "weights": "1/(L2 distance + 1e-3)", "index": f"IVFFlat nlist={a.nlist}",
                                    "nprobe": int(ix.nprobe), "recall_at_k_vs_exact": recall,
                                    "recall_by_nprobe": by_nprobe, "target_recall": a.target_recall,
                                    "recall_queries": len(probe),
                                    "build_s": t_build, "place_s": t_place, "n_cells": N,
                                    "threads": a.threads, "versions": versions()})
    log(f"placed {N:,} cells in {t_place:.0f} s")


# ------------------------------------------------------------------- validate
def knn_preservation(P, U, nq, rng):
    """Mean fraction of the K PC-space neighbours that are among the K UMAP neighbours,
    neighbours searched (exactly) within the pool; for nq query cells of the pool."""
    import faiss
    q = rng.choice(len(P), min(nq, len(P)), replace=False)
    a = faiss.IndexFlatL2(P.shape[1]); a.add(P); _, Ip = a.search(P[q], K + 1)
    b = faiss.IndexFlatL2(2); b.add(np.ascontiguousarray(U)); _, Iu = b.search(U[q], K + 1)
    return float(np.mean([len(np.intersect1d(x[1:], y[1:])) / K for x, y in zip(Ip, Iu)]))


def purity(Z, lab, nq, rng):
    import faiss
    q = rng.choice(len(Z), min(nq, len(Z)), replace=False)
    ix = faiss.IndexFlatL2(Z.shape[1]); ix.add(np.ascontiguousarray(Z)); _, I = ix.search(Z[q], K + 1)
    return float((lab[I[:, 1:]] == lab[q, None]).mean())


def plate_entropy(Z, plate, perm, nq, rng):
    """Mean Shannon entropy (bits) of the plate labels among each query cell's K nearest
    neighbours, with the observed labels and with the within-cell-line permuted labels."""
    import faiss
    q = rng.choice(len(Z), min(nq, len(Z)), replace=False)
    ix = faiss.IndexFlatL2(Z.shape[1]); ix.add(np.ascontiguousarray(Z)); _, I = ix.search(Z[q], K + 1)

    def ent(lbl):
        L = lbl[I[:, 1:]]
        out = np.empty(len(L))
        for i, r in enumerate(L):
            c = np.bincount(r) / K
            c = c[c > 0]
            out[i] = -(c * np.log2(c)).sum()
        return float(out.mean())
    return ent(plate), ent(perm)


def cmd_validate(a):
    from sklearn.metrics import silhouette_score
    work = Path(a.work)
    pcs = open_pcs(a.pcs, a.in_memory)
    umap_all = np.load(work / "umap_all.f32.npy", mmap_mode="r")
    N = pcs.shape[0]
    ref = np.load(work / "ref_idx.npy")
    ref = ref[ref < N]
    obs = pd.read_parquet(a.obs, columns=["plate", "cell_line_id", "drug", "moa_fine"])
    rng = np.random.default_rng(SEED + 2)
    res = {}
    # pools of equal size: the reference cells, and as many random placed cells
    n_pool = len(ref)
    placed = np.sort(rng.choice(np.setdiff1d(np.arange(N), ref, assume_unique=True), n_pool, replace=False))
    for name, idx in [("reference", ref), ("placed", placed)]:
        P, U = rows(pcs, idx), np.asarray(umap_all[idx])
        res[f"knn_preservation_{name}"] = knn_preservation(P, U, 100_000, rng)
        log(name, res[f"knn_preservation_{name}"])
    # purity and silhouette by cell line over 100k random cells (any)
    s = np.sort(rng.choice(N, 100_000, replace=False))
    P, U = rows(pcs, s), np.asarray(umap_all[s])
    lab = obs.cell_line_id.cat.codes.to_numpy()[s]
    res["cell_line_purity_umap"] = purity(U, lab, 20_000, rng)
    res["cell_line_purity_pca"] = purity(P, lab, 20_000, rng)
    res["cell_line_silhouette_umap"] = float(silhouette_score(U, lab, sample_size=50_000, random_state=SEED))
    res["cell_line_silhouette_pca"] = float(silhouette_score(P, lab, sample_size=50_000, random_state=SEED))
    res["random_baseline_purity"] = float((np.bincount(lab) / len(lab)) @ (np.bincount(lab) / len(lab)))
    # plate mixing within cell lines: same-plate fraction of the 15-NN vs its expectation if
    # plates were fully mixed within each cell line (sum of squared plate shares, averaged)
    plate = obs.plate.cat.codes.to_numpy()[s]
    res["same_plate_fraction_umap"] = purity(U, plate, 20_000, rng)
    res["same_plate_fraction_pca"] = purity(P, plate, 20_000, rng)
    ct = pd.crosstab(lab, plate).to_numpy().astype(float)
    pp = ct / ct.sum(1, keepdims=True)
    res["same_plate_fraction_if_mixed"] = float((ct.sum(1) / ct.sum()) @ (pp ** 2).sum(1))
    # plate entropy of each cell's 15-NN neighbourhood, against the same neighbourhoods with the
    # plate labels permuted within each cell line (= plates fully mixed within cell lines)
    perm = plate.copy()
    for l in np.unique(lab):
        w = np.flatnonzero(lab == l)
        perm[w] = plate[rng.permutation(w)]
    for name, Z in [("umap", U), ("pca", P)]:
        e_obs, e_mix = plate_entropy(Z, plate, perm, 20_000, rng)
        res[f"plate_entropy_15nn_{name}"] = e_obs
        res[f"plate_entropy_15nn_{name}_if_mixed"] = e_mix
    res["plate_entropy_max_bits"] = float(np.log2(min(K, len(np.unique(plate)))))
    save_json(work / "validate.json", res)
    log(json.dumps(res, indent=1))
    preview(work, umap_all, obs, rng)


def preview(work, umap_all, obs, rng):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    N = len(umap_all)
    s = np.sort(rng.choice(N, min(N, 1_000_000), replace=False))
    U = np.asarray(umap_all[s]); o = obs.iloc[s]
    p = rng.permutation(len(s))
    for col, cmap in [("cell_line_id", "nipy_spectral"), ("moa_fine", "tab20"), ("plate", "tab20")]:
        c = o[col].cat.codes.to_numpy()
        fig, ax = plt.subplots(figsize=(12, 12))
        ax.scatter(U[p, 0], U[p, 1], c=c[p], cmap=cmap, s=0.05, lw=0, rasterized=True)
        ax.set_title(f"Tahoe-100M UMAP, 1M random of {N:,} cells, coloured by {col} "
                     f"({o[col].nunique()} values)")
        ax.set_aspect("equal"); ax.axis("off")
        fig.savefig(work / f"preview_1M_{col}.png", dpi=150, bbox_inches="tight")
        plt.close(fig)


# ------------------------------------------------------------------- write
def cmd_write(a):
    import zarr
    work = Path(a.work)
    umap_all = np.load(work / "umap_all.f32.npy", mmap_mode="r")
    root = zarr.open_group(a.store, mode="r+", zarr_format=2)
    other = next(iter(k for k in root["obsm"].array_keys()))
    n = root["obsm"][other].shape[0]          # the store holds the first n cells
    if n > len(umap_all):
        raise SystemExit(f"{a.store}: {n:,} cells, but the UMAP has {len(umap_all):,}")
    chunks = root["obsm"][other].chunks[0]
    if "X_umap" in root["obsm"]:
        raise SystemExit(f"{a.store}: obsm/X_umap exists")
    arr = root["obsm"].create_array("X_umap", shape=(n, 2), chunks=(chunks, 2), dtype="f4",
                                    compressors=root["obsm"][other].compressors)
    arr.attrs.update({"encoding-type": "array", "encoding-version": "0.2.0"})
    for s in range(0, n, chunks * 8):
        arr[s:min(n, s + chunks * 8)] = umap_all[s:min(n, s + chunks * 8)]
    zarr.consolidate_metadata(a.store, zarr_format=2)
    log(f"{a.store}: obsm/X_umap [{n:,}, 2] written")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample"); s.add_argument("--obs", required=True); s.add_argument("--work", required=True)
    s.add_argument("--per-stratum", type=int, default=1430)
    f = sub.add_parser("fit"); f.add_argument("--pcs", required=True); f.add_argument("--work", required=True)
    f.add_argument("--in-memory", action="store_true")
    p = sub.add_parser("place"); p.add_argument("--pcs", required=True); p.add_argument("--work", required=True)
    p.add_argument("--threads", type=int, default=os.cpu_count())
    p.add_argument("--nlist", type=int, default=NLIST); p.add_argument("--target-recall", type=float, default=0.9)
    p.add_argument("--in-memory", action="store_true", help="load a .npy PCS fully instead of memory-mapping it")
    v = sub.add_parser("validate"); v.add_argument("--pcs", required=True); v.add_argument("--obs", required=True)
    v.add_argument("--work", required=True); v.add_argument("--in-memory", action="store_true")
    w = sub.add_parser("write"); w.add_argument("--work", required=True); w.add_argument("--store", required=True)
    a = ap.parse_args()
    {"sample": cmd_sample, "fit": cmd_fit, "place": cmd_place, "validate": cmd_validate,
     "write": cmd_write}[a.cmd](a)


if __name__ == "__main__":
    main()
