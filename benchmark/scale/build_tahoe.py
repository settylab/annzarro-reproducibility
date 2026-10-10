#!/usr/bin/env python
"""Build nested AnnZarro-ready zarr stores from Tahoe-100M.

Source: the Hugging Face release of Tahoe-100M (``tahoebio/Tahoe-100M``,
licence CC0-1.0), 3,388 parquet shards of ~28,000 cells each. Each record is
one cell: ``genes`` (token ids, the first a CLS token = 1 with expression -2),
``expressions`` (raw UMI counts as float32) and per-cell metadata. Gene token
``t`` is column ``t - 3`` of the 62,710-gene vocabulary in
``metadata/gene_metadata.parquet`` (token ids 3..62712, contiguous).

Nested: the store with N cells holds the first N cells in shard order
(shard 0, 1, 2, ...), so every smaller store is a prefix of every larger one.

Layout, following the paper's Procedure (Steps 8-10):

  X                    CSC float32 counts (read by gene: one gene column is
                       one contiguous slice of data/indices)
  layers/counts_csr    the same counts as CSR (read by cell: one cell row is
                       one contiguous slice). Its data/indices chunk files are
                       hard links into the master CSR, so it costs no disk.
  obs                  sample, plate, cell_line_id, drug, moa_fine
                       (categorical, categories fixed over the whole master),
                       n_genes (int32), total_counts (float32); index =
                       BARCODE_SUB_LIB_ID
  var                  index = gene_symbol, column ensembl_id
  obsm/X_pca_2d        PCs 1-2 (float32), see `fit`
  zarr format v2, Blosc-zstd, consolidated metadata

Embedding (`fit`): Tahoe-100M ships no embedding. PCA is fitted on every 5th
cell of shards 0..35 (~200k cells): counts normalised to 10,000 per cell,
log1p, the 2,000 genes of highest variance, centred, 50 PCs by randomized SVD
(seed 0). Every cell is then projected exactly (the map is linear on the
sparse log-normalised row), and PCs 1-2 are stored. It is a cheap, documented
stand-in for a UMAP; it only provides coordinates to draw.

Steps (each resumable; WORK is a scratch directory):

  build_tahoe.py fit    --parquet DIR --work WORK
  build_tahoe.py master --parquet DIR --work WORK --max-cells 20000000
  build_tahoe.py store  --work WORK --n 1000000 --out STORES/tahoe_1M.zarr
  build_tahoe.py check  --work WORK --store STORES/tahoe_1M.zarr

`master` writes one CSR (WORK/master.zarr) of the first --max-cells cells
plus obs/embedding arrays; the parquet shards may be deleted afterwards.
`store` builds the CSC for N cells out of core: gene blocks of at most
--mem-entries stored values (default 1e9, ~26 GB peak RAM) per pass over the
master's CSR, so peak memory does not grow with N.

Gene-panel series (HPC hand-off; replaces `fit` by a refit on a sample
stratified over plate x cell line, and keeps a ~5,000-gene panel):

  build_tahoe.py obs          --parquet DIR --work WORK
  umap_tahoe.py  sample       --obs WORK/obs.parquet --work WORK/umap
  build_tahoe.py refit        --parquet DIR --work WORK --ref-idx WORK/umap/ref_idx.npy
  build_tahoe.py master       --parquet DIR --work WORK --max-cells 200000000 --n-pcs 50 \
                              --detect-at 1000000 2000000 ...
  build_tahoe.py panel        --work WORK --out genes_panel.txt
  build_tahoe.py panel-master --work WORK
  build_tahoe.py store        --work WORK --n N --out STORE.zarr --genes genes_panel.txt
  build_tahoe.py check        --work WORK --store STORE.zarr --genes genes_panel.txt

`obs` reads the per-cell metadata of every shard in shard order (store order).
`refit` fits the PCA (same recipe as `fit`: 1e4 normalisation, log1p, 2,000
genes of highest variance, centred, 50 PCs, randomized SVD seed 0) on the
cells of --ref-idx, and keeps every gene's variance on that sample. With
--n-pcs 50 `master` projects every cell onto all 50 PCs (WORK/master_pcs.npy)
and, with --detect-at, records per-gene detection counts of each prefix.
`panel` selects the genes (rule written into the panel file), `panel-master`
writes WORK/master_panel.zarr, the master CSR restricted to the panel, and
`store --genes` builds X (CSC) and layers/counts_csr (hard links into
master_panel) over the panel genes only, with obsm/X_pca (50 PCs) and
obsm/X_pca_2d (PCs 1-2 of the same basis).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numcodecs
import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq
import scipy.sparse as sp
import zarr

N_GENES = 62710
TOKEN_OFFSET = 3
CHUNK = 1 << 21                      # 1-D chunk of data/indices: 2M values, 8 MB raw
OBS_CAT = ["sample", "plate", "cell_line_id", "drug", "moa-fine"]
FIT_SHARDS = 36
FIT_EVERY = 5
N_HVG = 2000
N_PCS = 50
SEED = 0
BLOSC_F = numcodecs.Blosc(cname="zstd", clevel=3, shuffle=numcodecs.Blosc.SHUFFLE)
BLOSC_I = numcodecs.Blosc(cname="zstd", clevel=3, shuffle=numcodecs.Blosc.BITSHUFFLE)
ENC = {"encoding-version": "0.1.0"}

zarr.config.set({"threading.max_workers": os.cpu_count(), "async.concurrency": 64})


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def shards(parquet: Path) -> list[Path]:
    """The contiguous prefix 0, 1, 2, ... of downloaded shards (stops at the first gap)."""
    have = {int(p.name[6:11]): p for p in parquet.glob("train-*-of-03388.parquet")}
    out = []
    while len(out) in have:
        out.append(have[len(out)])
    return out


def read_shard(path: Path):
    """One shard -> (CSR parts without the CLS token, obs DataFrame)."""
    t = pq.read_table(path, columns=["genes", "expressions", "BARCODE_SUB_LIB_ID"] + OBS_CAT)
    g = t.column("genes").combine_chunks()
    e = t.column("expressions").combine_chunks()
    lens = pc.list_value_length(g).to_numpy(zero_copy_only=False).astype(np.int64)
    gv = pc.list_flatten(g).to_numpy()
    ev = pc.list_flatten(e).to_numpy()
    starts = np.concatenate([[0], np.cumsum(lens)[:-1]])
    if not (np.all(lens > 0) and np.all(gv[starts] == 1) and np.all(ev[starts] < 0)):
        raise ValueError(f"{path.name}: a cell does not start with the CLS token")
    keep = np.ones(gv.size, bool)
    keep[starts] = False
    cols = (gv[keep] - TOKEN_OFFSET).astype(np.int32)
    vals = ev[keep].astype(np.float32)
    n_genes = (lens - 1).astype(np.int64)
    indptr = np.concatenate([[0], np.cumsum(n_genes)])
    obs = t.select(["BARCODE_SUB_LIB_ID"] + OBS_CAT).to_pandas()
    for c in OBS_CAT:
        obs[c] = obs[c].astype("category")
    return cols, vals, indptr, obs


def lognorm(cols, vals, indptr, n):
    """Sparse CSR of log1p(counts normalised to 1e4 per cell)."""
    m = sp.csr_matrix((vals, cols, indptr), shape=(n, N_GENES))
    tot = np.asarray(m.sum(1)).ravel()
    m = sp.diags((1e4 / np.where(tot > 0, tot, 1)).astype(np.float32)) @ m
    m.data = np.log1p(m.data)
    return m.tocsr(), tot


# ------------------------------------------------------------------- fit
def cmd_fit(a):
    from sklearn.decomposition import PCA
    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    out = work / "pca_fit.npz"
    if out.exists():
        log("fit exists:", out); return
    parts = []
    for p in shards(Path(a.parquet))[:FIT_SHARDS]:
        cols, vals, indptr, _ = read_shard(p)
        n = len(indptr) - 1
        m, _ = lognorm(cols, vals, indptr, n)
        parts.append(m[::FIT_EVERY])
    m = sp.vstack(parts).tocsc()
    log("fit cells", m.shape[0])
    mean = np.asarray(m.mean(0)).ravel()
    var = np.asarray(m.multiply(m).mean(0)).ravel() - mean ** 2
    hvg = np.sort(np.argsort(-var)[:N_HVG])
    d = m[:, hvg].toarray().astype(np.float32)
    mu = d.mean(0)
    pca = PCA(n_components=N_PCS, svd_solver="randomized", random_state=SEED).fit(d - mu)
    np.savez(out, hvg=hvg, mean=mu, components=pca.components_.astype(np.float32),
             explained_variance_ratio=pca.explained_variance_ratio_, n_fit=m.shape[0])
    log("fit done; variance ratio PC1-2", pca.explained_variance_ratio_[:2])


def read_obs(path: Path) -> pd.DataFrame:
    obs = pq.read_table(path, columns=["BARCODE_SUB_LIB_ID"] + OBS_CAT).to_pandas()
    for c in OBS_CAT:
        obs[c] = obs[c].astype("category")
    return obs


def cmd_obs(a):
    """Per-cell metadata of every shard, in shard (= store) order, and the cells per shard."""
    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    out = work / "obs.parquet"
    if out.exists():
        log("obs exists:", out); return
    files = shards(Path(a.parquet))
    if len(files) < a.shards:
        sys.exit(f"only {len(files)} contiguous shards of {a.shards}")
    t0 = time.time()
    with ThreadPoolExecutor(a.threads) as ex:
        parts = list(ex.map(read_obs, files))
    np.save(work / "shard_rows.npy", np.array([len(p) for p in parts], np.int64))
    obs = pd.DataFrame({"BARCODE_SUB_LIB_ID": np.concatenate([p["BARCODE_SUB_LIB_ID"].to_numpy(object)
                                                               for p in parts])})
    for c in OBS_CAT:
        obs[c] = pd.api.types.union_categoricals([p[c] for p in parts], sort_categories=True)
    obs = obs.rename(columns={"moa-fine": "moa_fine"})
    obs.to_parquet(out)
    log(f"obs: {len(obs):,} cells from {len(files)} shards in {time.time() - t0:.0f} s")


def cmd_refit(a):
    """PCA (the `fit` recipe) on the reference cells --ref-idx (row numbers in shard order)."""
    from sklearn.decomposition import PCA
    work = Path(a.work)
    out = work / "pca_fit.npz"
    if out.exists():
        log("fit exists:", out); return
    ref = np.load(a.ref_idx).astype(np.int64)
    assert np.all(np.diff(ref) > 0), "ref_idx must be sorted and unique"
    nrow = np.load(work / "shard_rows.npy")
    off = np.concatenate([[0], np.cumsum(nrow)])
    files = shards(Path(a.parquet))
    assert len(files) == len(nrow)
    shard_of = np.searchsorted(off, ref, "right") - 1
    todo = np.unique(shard_of)
    t0 = time.time()

    def load(i):
        cols, vals, ip, _ = read_shard(files[i])
        assert len(ip) - 1 == nrow[i], files[i]
        loc = ref[shard_of == i] - off[i]
        return sp.csr_matrix((vals, cols, ip), shape=(nrow[i], N_GENES))[loc]
    parts = []
    with ThreadPoolExecutor(a.threads) as ex:
        for k, m in enumerate(_ordered(ex, load, todo, 2 * a.threads)):
            parts.append(m)
            if k % 200 == 0:
                log(f"refit read {k}/{len(todo)} shards, {time.time() - t0:.0f} s")
    counts = sp.vstack(parts).tocsr()
    del parts
    assert counts.shape[0] == len(ref)
    sp.save_npz(work / "ref_counts.npz", counts, compressed=False)
    t_read = time.time() - t0
    m, _ = lognorm(counts.indices, counts.data, counts.indptr, counts.shape[0])
    log(f"refit cells {m.shape[0]:,}, {m.nnz:,} values, read {t_read:.0f} s")
    mean = np.asarray(m.mean(0)).ravel()
    var = np.asarray(m.multiply(m).mean(0)).ravel() - mean ** 2
    hvg = np.sort(np.argsort(-var, kind="stable")[:N_HVG])
    d = m[:, hvg].toarray().astype(np.float32)
    del m
    mu = d.mean(0)
    pca = PCA(n_components=N_PCS, svd_solver="randomized", random_state=SEED).fit(d - mu)
    np.savez(out, hvg=hvg, mean=mu, components=pca.components_.astype(np.float32),
             explained_variance_ratio=pca.explained_variance_ratio_, n_fit=len(ref),
             gene_mean=mean.astype(np.float32), gene_var=var.astype(np.float32),
             basis=np.array("refit on --ref-idx (stratified plate x cell_line_id)"))
    (work / "refit.json").write_text(json.dumps({
        "n_fit": int(len(ref)), "n_hvg": N_HVG, "n_pcs": N_PCS, "seed": SEED, "read_s": t_read,
        "total_s": time.time() - t0, "shards_read": int(len(todo)),
        "explained_variance_ratio": [float(x) for x in pca.explained_variance_ratio_]}, indent=1))
    log("refit done; variance ratio PC1-5", pca.explained_variance_ratio_[:5])


def project(m, fit, k=2):
    w = fit["components"][:k].T                     # (n_hvg, k)
    return (np.asarray(m[:, fit["hvg"]] @ w) - fit["mean"] @ w).astype(np.float32)


def cmd_project(a):
    """Project every cell of WORK/master.zarr onto the first --n-pcs PCs of --fit (exactly as `master`
    does while building), writing a float32 [n, n_pcs] .npy. Lets a store series use a different
    basis than the one the master was built with."""
    work, out = Path(a.work), Path(a.out)
    if out.exists():
        log("projection exists:", out); return
    fit = dict(np.load(a.fit))
    master = zarr.open_group(str(work / "master.zarr"), mode="r")
    ip = master["indptr"][:]
    n = len(ip) - 1
    tmp = out.with_name(out.stem + ".partial.npy")
    emb = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.float32, shape=(n, a.n_pcs))
    cuts = np.unique(np.concatenate([np.searchsorted(ip, np.arange(0, int(ip[-1]), 16 * CHUNK), "left"), [n]]))
    jobs = list(zip(cuts[:-1], cuts[1:]))
    ind_z, dat_z = master["indices"], master["data"]

    def job(rr):
        r0, r1 = rr
        s, e = int(ip[r0]), int(ip[r1])
        m, _ = lognorm(ind_z[s:e], dat_z[s:e], ip[r0:r1 + 1] - s, r1 - r0)
        return r0, r1, project(m, fit, a.n_pcs)
    t0 = time.time()
    with ThreadPoolExecutor(a.threads) as ex:
        for j, (r0, r1, x) in enumerate(_ordered(ex, job, jobs, 2 * a.threads)):
            emb[r0:r1] = x
            if j % 200 == 0:
                log(f"project block {j}/{len(jobs)}, {time.time() - t0:.0f} s")
    emb.flush(); del emb
    tmp.rename(out)
    log(f"projected {n:,} cells onto {a.n_pcs} PCs of {a.fit} in {time.time() - t0:.0f} s")


# ------------------------------------------------------------------- master CSR
def _ordered(ex, fn, items, window):
    """ex.map with at most `window` results in flight (ex.map submits everything)."""
    from collections import deque
    q, it = deque(), iter(items)
    for x in it:
        q.append(ex.submit(fn, x))
        if len(q) >= window:
            break
    while q:
        yield q.popleft().result()
        for x in it:
            q.append(ex.submit(fn, x)); break


class Appender:
    """Append to a 1-D zarr array in whole chunks (the tail is written by close())."""

    def __init__(self, arr):
        self.arr, self.n, self.buf, self.nbuf = arr, arr.shape[0], [], 0

    def add(self, x):
        self.buf.append(x); self.nbuf += x.size
        if self.nbuf >= 32 * CHUNK:
            self.flush(False)

    def flush(self, final):
        cat = np.concatenate(self.buf) if len(self.buf) > 1 else self.buf[0]
        k = cat.size if final else (cat.size // CHUNK) * CHUNK
        if k:
            self.arr.resize((self.n + k,))
            self.arr[self.n:self.n + k] = cat[:k]
            self.n += k
        self.buf, self.nbuf = [cat[k:]], cat.size - k


def cmd_master(a):
    work = Path(a.work)
    fit = dict(np.load(work / "pca_fit.npz"))
    path = work / "master.zarr"
    if (work / "master_done.json").exists():
        log("master exists"); return
    g = zarr.open_group(str(path), mode="w", zarr_format=2)
    data = g.create_array("data", shape=(0,), chunks=(CHUNK,), dtype="f4", compressors=BLOSC_F)
    ind = g.create_array("indices", shape=(0,), chunks=(CHUNK,), dtype="i4", compressors=BLOSC_I)
    ad, ai = Appender(data), Appender(ind)
    indptr, obs_parts, emb_parts, tot_parts, ng_parts = [np.zeros(1, np.int64)], [], [], [], []
    n_done, nnz = 0, 0
    k_pcs = a.n_pcs
    assert fit["components"].shape[0] >= k_pcs
    detect_at = sorted(set(a.detect_at or []))
    colcount, detect = np.zeros(N_GENES, np.int64), {}
    files = shards(Path(a.parquet))
    t0 = time.time()
    with ThreadPoolExecutor(6) as ex:
        for i, (cols, vals, ip, obs) in enumerate(_ordered(ex, read_shard, files, 12)):
            n = len(ip) - 1
            take = min(n, a.max_cells - n_done)
            if take < n:
                ip = ip[:take + 1]; cols, vals = cols[:ip[-1]], vals[:ip[-1]]; obs = obs.iloc[:take]
            m, tot = lognorm(cols, vals, ip, take)
            emb_parts.append(project(m, fit, k_pcs))
            if detect_at:
                for s_ in detect_at:          # per-gene detection counts of the first s_ cells
                    if n_done < s_ <= n_done + take:
                        detect[str(s_)] = colcount + np.bincount(cols[:ip[s_ - n_done]], minlength=N_GENES)
                colcount += np.bincount(cols, minlength=N_GENES)
            tot_parts.append(tot.astype(np.float32)); ng_parts.append(np.diff(ip).astype(np.int32))
            ad.add(vals); ai.add(cols)
            indptr.append(ip[1:] + nnz)
            nnz += int(ip[-1]); n_done += take
            obs_parts.append(obs)
            if a.delete_consumed:
                files[i].unlink()
            if i % 20 == 0:
                log(f"shard {i}: {n_done:,} cells, {nnz:,} nnz, {time.time() - t0:.0f} s")
            if n_done >= a.max_cells:
                break
    ad.flush(True); ai.flush(True)
    if n_done < a.max_cells:
        log(f"WARNING: only {n_done:,} cells in the downloaded shards")
    indptr = np.concatenate(indptr)
    g.create_array("indptr", data=indptr, chunks=(1 << 22,), compressors=BLOSC_I)
    g.attrs.update({"encoding-type": "csr_matrix", **ENC, "shape": [n_done, N_GENES]})
    obs = pd.DataFrame({"BARCODE_SUB_LIB_ID": np.concatenate([o["BARCODE_SUB_LIB_ID"].to_numpy(object)
                                                               for o in obs_parts])})
    for c in OBS_CAT:
        obs[c] = pd.api.types.union_categoricals([o[c] for o in obs_parts], sort_categories=True)
    del obs_parts
    obs = obs.rename(columns={"moa-fine": "moa_fine"})
    obs["n_genes"] = np.concatenate(ng_parts)
    obs["total_counts"] = np.concatenate(tot_parts)
    dup = obs["BARCODE_SUB_LIB_ID"].duplicated()
    if dup.any():
        log(f"{dup.sum()} duplicate barcodes; suffixed with -<n>")
        obs.loc[dup, "BARCODE_SUB_LIB_ID"] += "-" + obs[dup].groupby("BARCODE_SUB_LIB_ID").cumcount().add(1).astype(str)
    obs.to_parquet(work / "master_obs.parquet")
    emb = np.concatenate(emb_parts)
    del emb_parts
    np.save(work / "master_emb.npy", np.ascontiguousarray(emb[:, :2]))
    if k_pcs > 2:
        np.save(work / "master_pcs.npy", emb)
    del emb
    if detect_at:
        detect["all"] = colcount
        np.savez(work / "detect_prefix.npz", **detect)
    (work / "master_done.json").write_text(json.dumps(
        {"n_cells": n_done, "nnz": nnz, "shards_read": i + 1, "seconds": time.time() - t0,
         "n_pcs": k_pcs, "fit_basis": str(fit.get("basis", "fit (shards 0-35, every 5th cell)")),
         "fit_n": int(fit["n_fit"])}))
    log(f"master done: {n_done:,} cells, {nnz:,} nnz in {time.time() - t0:.0f} s")


# ------------------------------------------------------------------- gene panel
def gene_table(work: Path, path=None) -> pd.DataFrame:
    gm = pd.read_parquet(Path(path) if path else work / "gene_metadata.parquet").sort_values("token_id")
    assert len(gm) == N_GENES and np.array_equal(gm["token_id"].to_numpy(), np.arange(N_GENES) + TOKEN_OFFSET)
    return gm.reset_index(drop=True)


def read_panel(path) -> np.ndarray:
    """Gene column indices (0-based, in the 62,710-gene vocabulary) from a panel file."""
    idx = [int(l.split("\t")[0]) for l in Path(path).read_text().splitlines() if l and not l.startswith("#")]
    idx = np.array(idx, np.int64)
    assert np.all(np.diff(idx) > 0) and idx[-1] < N_GENES
    return idx


def cmd_panel(a):
    """Select the gene panel: the --n-hvg genes of highest variance on the refit sample (the
    criterion `refit` uses for its 2,000 PCA genes), the --extra genes, and the --bench-top
    most-detected genes of every prefix in WORK/detect_prefix.npz (bench_http.py and
    bench_browser.py pick genes by detection rank up to 2,007, so their picks are unchanged)."""
    work = Path(a.work)
    fit = np.load(work / "pca_fit.npz")
    gm = gene_table(work, a.gene_metadata)
    sym = gm["gene_symbol"].astype(str).to_numpy()
    var = fit["gene_var"]
    hvg = np.argsort(-var, kind="stable")[:a.n_hvg]
    extra = []
    for g in a.extra:
        hit = np.flatnonzero(sym == g)
        if hit.size == 0:
            sys.exit(f"--extra gene {g} not in the vocabulary")
        extra += list(hit)
    det = np.load(work / "detect_prefix.npz")
    bench = {k: np.argsort(-det[k], kind="stable")[:a.bench_top] for k in det.files}
    panel = np.unique(np.concatenate([hvg, np.array(extra, np.int64)] + list(bench.values())))
    why = {}
    for g in hvg: why.setdefault(int(g), []).append("hvg")
    for g in extra: why.setdefault(int(g), []).append("extra")
    for g in np.unique(np.concatenate(list(bench.values()))): why.setdefault(int(g), []).append("detected")
    inp = np.zeros(N_GENES, bool); inp[panel] = True
    # stored values kept per cell, on the refit sample
    rc = sp.load_npz(work / "ref_counts.npz").tocsr()
    nz = np.diff(rc.indptr)
    row = np.repeat(np.arange(rc.shape[0]), nz)
    kept = np.bincount(row, weights=inp[rc.indices], minlength=rc.shape[0])
    umi = np.bincount(row, weights=rc.data * inp[rc.indices], minlength=rc.shape[0])
    tot = np.asarray(rc.sum(1)).ravel()
    ok = nz > 0
    frac, ufrac = kept[ok] / nz[ok], umi[ok] / tot[ok]
    allc = det["all"]
    info = {"n_genes": int(len(panel)), "n_hvg": a.n_hvg, "extra": a.extra, "bench_top": a.bench_top,
            "bench_prefixes": sorted(det.files, key=lambda k: (k == "all", int(k) if k != "all" else 0)),
            "n_hvg_only": int(sum(1 for v in why.values() if v == ["hvg"])),
            "n_detected_not_hvg": int(sum(1 for v in why.values() if "detected" in v and "hvg" not in v)),
            "ref_cells": int(rc.shape[0]),
            "kept_values_per_cell_ref": {"median": float(np.median(frac)), "mean": float(frac.mean()),
                                         "p05": float(np.quantile(frac, 0.05)), "p95": float(np.quantile(frac, 0.95))},
            "kept_umi_per_cell_ref": {"median": float(np.median(ufrac)), "mean": float(ufrac.mean())},
            "kept_values_all_cells_pooled": float(allc[panel].sum() / allc.sum())}
    (work / "panel.json").write_text(json.dumps(info, indent=1))
    np.save(work / "panel_idx.npy", panel)
    with open(a.out, "w") as f:
        sj = work / "umap" / "sample.json"
        per = json.loads(sj.read_text())["per_stratum"] if sj.exists() else "?"
        f.write(f"# Tahoe-100M gene panel: {len(panel)} genes (build_tahoe.py panel)\n"
                f"# rule: union of (a) the {a.n_hvg} genes of highest variance of log1p(counts normalised to 1e4)\n"
                f"#   on the {rc.shape[0]:,}-cell reference sample (stratified over plate x cell_line_id, <={per} per\n"
                f"#   stratum, seed 0; the sample and criterion of the PCA refit), (b) {', '.join(a.extra)},\n"
                f"#   (c) the {a.bench_top} most-detected genes (stored values) of each nested prefix\n"
                f"#   {', '.join(info['bench_prefixes'])} (bench_http.py / bench_browser.py pick genes by detection rank <= 2007)\n"
                f"# stored values kept per cell on the reference sample: median {info['kept_values_per_cell_ref']['median']:.4f},"
                f" mean {info['kept_values_per_cell_ref']['mean']:.4f}; pooled over all cells {info['kept_values_all_cells_pooled']:.4f}\n"
                f"# columns: index (0-based column of the 62,710-gene vocabulary = token_id - 3), gene_symbol, ensembl_id, reason\n")
        for g in panel:
            f.write(f"{g}\t{sym[g]}\t{gm['ensembl_id'].iloc[g]}\t{','.join(why[int(g)])}\n")
    log(json.dumps(info, indent=1))


def cmd_panel_master(a):
    """WORK/master_panel.zarr: the master CSR restricted to the panel genes (columns renumbered
    0..G-1 in vocabulary order), and the per-cell fraction of stored values kept over all cells."""
    work = Path(a.work)
    if (work / "panel_master_done.json").exists():
        log("panel master exists"); return
    panel = np.load(work / "panel_idx.npy")
    G = len(panel)
    remap = np.full(N_GENES, -1, np.int32); remap[panel] = np.arange(G, dtype=np.int32)
    master = zarr.open_group(str(work / "master.zarr"), mode="r")
    ip = master["indptr"][:]
    n, nnz = len(ip) - 1, int(ip[-1])
    ind_z, dat_z = master["indices"], master["data"]
    g = zarr.open_group(str(work / "master_panel.zarr"), mode="w", zarr_format=2)
    data = g.create_array("data", shape=(0,), chunks=(CHUNK,), dtype="f4", compressors=BLOSC_F)
    ind = g.create_array("indices", shape=(0,), chunks=(CHUNK,), dtype="i4", compressors=BLOSC_I)
    ad, ai = Appender(data), Appender(ind)
    cuts = np.unique(np.concatenate([np.searchsorted(ip, np.arange(0, nnz, 16 * CHUNK), "left"), [n]]))
    jobs = list(zip(cuts[:-1], cuts[1:]))

    def job(rr):
        r0, r1 = rr
        s, e = int(ip[r0]), int(ip[r1])
        ii = remap[ind_z[s:e]]
        k = ii >= 0
        kc = np.concatenate([[0], np.cumsum(k)])
        per_row = kc[ip[r0 + 1:r1 + 1] - s] - kc[ip[r0:r1] - s]
        return ii[k], dat_z[s:e][k], per_row
    kept_rows = []
    t0 = time.time()
    with ThreadPoolExecutor(a.threads) as ex:
        for j, (ii, dd, pr) in enumerate(_ordered(ex, job, jobs, 2 * a.threads)):
            ai.add(ii); ad.add(dd); kept_rows.append(pr)
            if j % 200 == 0:
                log(f"panel master block {j}/{len(jobs)}, {time.time() - t0:.0f} s")
    ad.flush(True); ai.flush(True)
    kept = np.concatenate(kept_rows).astype(np.int64)
    assert len(kept) == n
    pip = np.concatenate([[0], np.cumsum(kept)])
    g.create_array("indptr", data=pip, chunks=(1 << 22,), compressors=BLOSC_I)
    g.attrs.update({"encoding-type": "csr_matrix", **ENC, "shape": [n, G]})
    ng = np.diff(ip)
    frac = kept[ng > 0] / ng[ng > 0]
    info = {"n_cells": n, "n_genes": G, "nnz": int(pip[-1]), "nnz_master": nnz, "seconds": time.time() - t0,
            "kept_values_per_cell_all": {"median": float(np.median(frac)), "mean": float(frac.mean()),
                                         "p05": float(np.quantile(frac, 0.05)), "p95": float(np.quantile(frac, 0.95))},
            "kept_values_pooled": float(pip[-1] / nnz)}
    (work / "panel_master_done.json").write_text(json.dumps(info, indent=1))
    log(json.dumps(info, indent=1))


PLOT_RULE = ("X holds values only for the genes in gene_panel (indices into var; every other column is "
             "empty). gene_panel: the genes benchmark clicks use (ranks 0-2, 1000-1002, 2000-2007 by stored values "
             "in this store, i.e. gene_order_full, and MALAT1), then panel genes by decreasing variance of "
             "log1p(counts normalised to 1e4) on the stratified reference sample (WORK/pca_fit.npz gene_var), "
             "up to {size} genes. As build_tahoe.py store --panel at paper f5c01b7, except that the variance is "
             "taken on the reference sample instead of the first 200,000 cells.")


def cmd_plot_copy(a):
    """A slim copy of a finished panel store for plotting: obs, var, obsm/X_umap, obsm/X_pca_2d, and an X
    (CSC, same shape and chunking) whose values are kept for --n-genes genes only; no layers."""
    import shutil
    import hashlib
    work, src, out = Path(a.work), Path(a.src), Path(a.out)
    if out.exists():
        sys.exit(f"{out} exists")
    tmp = out.with_name(out.name + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    t0 = time.time()
    st = zarr.open_group(str(src), mode="r", use_consolidated=True)
    n, G = st["X"].attrs["shape"]
    assert "X_umap" in st["obsm"], f"{src} has no obsm/X_umap"
    cp = st["X/indptr"][:]
    nz = np.diff(cp)
    order = np.argsort(-nz, kind="stable")                       # local (panel) gene order by stored values
    vocab = np.load(work / "panel_idx.npy")
    assert len(vocab) == G
    names = np.array([str(x) for x in st["var/_index"][:]], dtype=object)
    var_all = np.load(work / "pca_fit.npz")["gene_var"][vocab]
    bench = [int(g) for g in order[[0, 1, 2, 1000, 1001, 1002]]] + [int(g) for g in order[2000:2008]]
    bench += [int(g) for g in np.flatnonzero(names == "MALAT1")]
    why = {g: "bench" for g in bench}
    vrank = np.argsort(-var_all, kind="stable")
    sel = []
    for g in bench + [int(x) for x in vrank]:
        if g not in sel:
            sel.append(g)
            why.setdefault(g, f"variance rank {int(np.flatnonzero(vrank == g)[0])}")
        if len(sel) >= a.n_genes:
            break
    sel = np.array(sorted(sel))
    tmp.mkdir(parents=True)
    for f in (".zattrs", ".zgroup"):
        shutil.copy2(src / f, tmp / f)
    for d in ("obs", "var", "varm", "obsp", "varp", "uns"):
        shutil.copytree(src / d, tmp / d)
    (tmp / "obsm").mkdir()
    for f in (".zattrs", ".zgroup"):
        shutil.copy2(src / "obsm" / f, tmp / "obsm" / f)
    for d in ("X_umap", "X_pca_2d"):
        shutil.copytree(src / "obsm" / d, tmp / "obsm" / d)
    log(f"obs/var/obsm copied ({time.time() - t0:.0f} s)")
    root = zarr.open_group(str(tmp), mode="r+", zarr_format=2)
    keep = np.zeros(G, bool); keep[sel] = True
    newcount = np.where(keep, nz, 0)
    newptr = np.concatenate([[0], np.cumsum(newcount)]).astype(np.int64)
    xg = root.create_group("X")
    data = xg.create_array("data", shape=(0,), chunks=(CHUNK,), dtype="f4", compressors=BLOSC_F)
    ind = xg.create_array("indices", shape=(0,), chunks=(CHUNK,), dtype="i4", compressors=BLOSC_I)
    ad_, ai_ = Appender(data), Appender(ind)
    for k, g in enumerate(sel):
        s0, e0 = int(cp[g]), int(cp[g + 1])
        for s1 in range(s0, e0, 16 * CHUNK):
            e1 = min(e0, s1 + 16 * CHUNK)
            ai_.add(st["X/indices"][s1:e1]); ad_.add(st["X/data"][s1:e1])
        if k % 20 == 0:
            log(f"  gene {k + 1}/{len(sel)} {names[g]}: {e0 - s0:,} values ({time.time() - t0:.0f} s)")
    ad_.flush(True); ai_.flush(True)
    assert data.shape[0] == newptr[-1]
    xg.create_array("indptr", data=newptr, chunks=(1 << 22,), compressors=BLOSC_I)
    xg.attrs.update({"encoding-type": "csc_matrix", **ENC, "shape": [n, G],
                     "gene_panel": [int(g) for g in sel], "gene_panel_symbols": [str(names[g]) for g in sel],
                     "gene_panel_vocab_index": [int(vocab[g]) for g in sel],
                     "gene_order_full": [int(g) for g in order[:2010]],
                     "gene_panel_rule": PLOT_RULE.format(size=a.n_genes), "source_store": str(src)})
    zarr.consolidate_metadata(str(tmp), zarr_format=2)
    # check: kept columns equal the source, every other column empty, X_umap identical
    rng = np.random.default_rng(3)
    for g in rng.choice(sel, min(5, len(sel)), replace=False):
        a0, b0 = int(cp[g]), int(cp[g] + min(nz[g], 1_000_000))
        a1 = int(newptr[g])
        assert np.array_equal(xg["indices"][a1:a1 + (b0 - a0)], st["X/indices"][a0:b0]), g
        assert np.array_equal(xg["data"][a1:a1 + (b0 - a0)], st["X/data"][a0:b0]), g
    assert np.all(np.diff(newptr)[~keep] == 0)
    h = hashlib.sha256()
    um = root["obsm/X_umap"]
    for s1 in range(0, n, 1 << 22):
        blk = np.ascontiguousarray(um[s1:min(n, s1 + (1 << 22))], dtype="<f4")
        assert np.array_equal(blk, st["obsm/X_umap"][s1:min(n, s1 + (1 << 22))])
        h.update(blk.tobytes())
    tmp.rename(out)
    with open(out.parent / (out.name + ".panel.tsv"), "w") as f:
        f.write("gene_index_var\tgene_index_vocab\tgene_symbol\tstored_values\treason\n")
        for g in sel:
            f.write(f"{g}\t{vocab[g]}\t{names[g]}\t{nz[g]}\t{why[g]}\n")
    info = {"n_cells": int(n), "n_genes_var": int(G), "n_genes_with_values": int(len(sel)),
            "nnz": int(newptr[-1]), "nnz_source": int(cp[-1]), "source": str(src), "seconds": time.time() - t0,
            "x_umap_sha256": h.hexdigest(),
            "x_umap_sha256_of": "raw little-endian float32 bytes of obsm/X_umap [n, 2], C order",
            "zarr": zarr.__version__}
    (out.parent / (out.name + ".build.json")).write_text(json.dumps(info, indent=1))
    log(json.dumps(info, indent=1))


# ------------------------------------------------------------------- store
def link_prefix(src, dst: Path, n: int):
    """A zarr v2 1-D array of the first n values of `src`, sharing its chunk files."""
    dst.mkdir(parents=True)
    meta = json.loads((src / ".zarray").read_text())
    meta["shape"] = [n]
    (dst / ".zarray").write_text(json.dumps(meta))
    for k in range(math.ceil(n / meta["chunks"][0])):
        os.link(src / str(k), dst / str(k))


def _version(pkg):
    from importlib.metadata import version
    return version(pkg)


def _ram_bytes() -> int:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError):
        return 32 << 30


def read_blocks(master, nnz, block):
    """Yield (start, indices, data, row-of-each-entry) blocks of the master's prefix."""
    indptr = master["indptr"][:]
    for s in range(0, nnz, block):
        e = min(s + block, nnz)
        r0 = int(np.searchsorted(indptr, s, "right") - 1)
        r1 = int(np.searchsorted(indptr, e, "left"))
        yield s, e, r0, r1, indptr


def column_counts(master, nnz, block=32 * CHUNK, n_genes=N_GENES):
    """Stored values per gene in the master's first nnz values (one pass over indices)."""
    ind_z = master["indices"]
    jobs = list(read_blocks(master, nnz, block))
    colcount = np.zeros(n_genes, np.int64)
    with ThreadPoolExecutor(6) as pool:
        for c in _ordered(pool, lambda job: np.bincount(ind_z[job[0]:job[1]], minlength=n_genes), jobs, 12):
            colcount += c
    return colcount


def build_csc(master, xg, n, nnz, budget, block=32 * CHUNK, n_genes=N_GENES, colcount=None, panel=None):
    """CSC of the master's first n rows, out of core.

    Gene blocks of at most `budget` stored values; for each block one pass over
    the CSR prefix in storage order (cells ascending) scatters every entry of
    the block straight to its final CSC position (per-gene write cursors), so
    the memory held is the block's output (8 bytes per value) plus a few read
    blocks in flight.
    """
    ind_z, dat_z = master["indices"], master["data"]
    jobs = list(read_blocks(master, nnz, block))
    pool = ThreadPoolExecutor(6)

    if colcount is None:
        colcount = column_counts(master, nnz, block, n_genes)
    inpanel = None
    if panel is not None:        # only these genes hold values in X; every other column is empty
        inpanel = np.zeros(n_genes, bool)
        inpanel[panel] = True
        colcount = np.where(inpanel, colcount, 0)
    colptr = np.concatenate([[0], np.cumsum(colcount)]).astype(np.int64)
    if panel is None:
        assert colptr[-1] == nnz
    nnz = int(colptr[-1])
    bounds, g0 = [], 0
    while g0 < n_genes:
        g1 = int(np.searchsorted(colptr, colptr[g0] + budget, "right") - 1)
        g1 = min(max(g1, g0 + 1), n_genes)
        bounds.append((g0, g1)); g0 = g1
    log(f"CSC: {nnz:,} values, {len(bounds)} passes of <= {budget:,.0f} values")
    data = xg.create_array("data", shape=(nnz,), chunks=(CHUNK,), dtype="f4", compressors=BLOSC_F)
    indices = xg.create_array("indices", shape=(nnz,), chunks=(CHUNK,), dtype="i4", compressors=BLOSC_I)
    xg.create_array("indptr", data=colptr, chunks=(1 << 22,), compressors=BLOSC_I)
    for p, (g0, g1) in enumerate(bounds):
        t0 = time.time()
        lo, hi = int(colptr[g0]), int(colptr[g1])
        out_cell = np.empty(hi - lo, np.int32)
        out_val = np.empty(hi - lo, np.float32)
        cursor = colptr[g0:g1] - lo

        def collect(job):
            s, e, r0, r1, indptr = job
            ind = ind_z[s:e]
            m = (ind >= g0) & (ind < g1)
            if inpanel is not None:
                m &= inpanel[ind]
            sel = np.flatnonzero(m)
            if sel.size == 0:
                return None
            rows = np.repeat(np.arange(r0, r1, dtype=np.int32),
                             np.diff(np.clip(indptr[r0:r1 + 1], s, e)))
            gene = (ind[sel] - g0).astype(np.uint16)
            order = np.argsort(gene, kind="stable")       # radix; cells stay ascending per gene
            gene = gene[order]
            cnt = np.bincount(gene, minlength=g1 - g0)
            rank = np.arange(gene.size) - (np.cumsum(cnt) - cnt)[gene]
            return gene, rank, rows[sel][order], dat_z[s:e][sel][order], cnt
        for res in _ordered(pool, collect, jobs, 8):
            if res is None:
                continue
            gene, rank, cell, val, cnt = res
            pos = cursor[gene] + rank
            out_cell[pos] = cell
            out_val[pos] = val
            cursor += cnt
        assert np.array_equal(cursor, colptr[g0 + 1:g1 + 1] - lo)
        indices[lo:hi] = out_cell
        data[lo:hi] = out_val
        del out_cell, out_val
        log(f"  pass {p + 1}/{len(bounds)} genes {g0}-{g1}: {hi - lo:,} values, {time.time() - t0:.0f} s")
    pool.shutdown()
    xg.attrs.update({"encoding-type": "csc_matrix", **ENC, "shape": [n, n_genes]})


PANEL_RULE = ("X holds values only for the genes in gene_panel (other columns are empty; every gene's "
              "values are in layers/counts_csr). Panel: the genes benchmark clicks use (ranks 0-2, "
              "1000-1002, 2000-2007 by stored values in this store, i.e. gene_order_full, and MALAT1), then genes by "
              "decreasing variance of log1p(counts normalised to 1e4) over the first 200,000 cells, "
              "while the panel's stored values fit one CSC pass.")


def select_panel(master, indptr_all, colcount, order, size, budget, names):
    """Benchmark genes first, then high-variance genes, within `budget` stored values."""
    why = {}
    bench = list(order[[0, 1, 2, 1000, 1001, 1002]]) + list(order[2000:2008])
    bench += [int(i) for i in np.flatnonzero(names == "MALAT1")]
    for g in bench:
        why[int(g)] = "bench"
    m = 200_000
    ip = indptr_all[:m + 1]
    sub, _ = lognorm(master["indices"][:ip[-1]], master["data"][:ip[-1]], ip, m)
    mean = np.asarray(sub.mean(0)).ravel()
    var = np.asarray(sub.multiply(sub).mean(0)).ravel() - mean ** 2
    panel, total = [], 0
    for g in bench + list(np.argsort(-var)):
        g = int(g)
        if g in panel:
            continue
        if len(panel) >= size or (total + colcount[g] > budget and why.get(g) != "bench"):
            if len(panel) >= size:
                break
            continue
        panel.append(g); total += int(colcount[g])
        why.setdefault(g, f"variance rank {int(np.flatnonzero(np.argsort(-var) == g)[0])}")
    return np.array(sorted(panel)), why


def cmd_store(a):
    work = Path(a.work)
    done = json.loads((work / "master_done.json").read_text())
    if a.n > done["n_cells"]:
        sys.exit(f"master has {done['n_cells']:,} cells, fewer than {a.n:,}")
    out = Path(a.out)
    if out.exists():
        sys.exit(f"{out} exists")
    tmp = out.with_name(out.name + ".partial")
    if tmp.exists():
        import shutil; shutil.rmtree(tmp)
    t_start = time.time()
    panel = None
    if a.genes:
        panel = read_panel(a.genes)
        assert np.array_equal(panel, np.load(work / "panel_idx.npy")), "--genes differs from WORK/panel_idx.npy"
    mname = "master_panel.zarr" if panel is not None else "master.zarr"
    master = zarr.open_group(str(work / mname), mode="r")
    n_genes = int(master.attrs["shape"][1])
    assert n_genes == (len(panel) if panel is not None else N_GENES)
    indptr_all = master["indptr"][:]
    n = a.n
    nnz = int(indptr_all[n])
    root = zarr.open_group(str(tmp), mode="w", zarr_format=2)
    root.attrs.update({"encoding-type": "anndata", **ENC})
    import anndata as ad
    # obs / var / obsm through anndata's own writers
    obs = pd.read_parquet(work / "master_obs.parquet")
    for c in ["sample", "plate", "cell_line_id", "drug", "moa_fine"]:
        obs[c] = obs[c].astype("category")
    obs = obs.iloc[:n].set_index("BARCODE_SUB_LIB_ID")
    obs.index.name = None
    obs.index = obs.index.astype(str)
    ad.settings.zarr_write_format = 2
    obs_chunks = min(n, 1 << 20)
    ad.io.write_elem(root, "obs", obs, dataset_kwargs={"chunks": (obs_chunks,)})
    gm = gene_table(work, a.gene_metadata)
    if panel is not None:
        gm = gm.iloc[panel]
    var = pd.DataFrame({"ensembl_id": gm["ensembl_id"].astype(str).values},
                       index=pd.Index(gm["gene_symbol"].astype(str).values))
    ad.io.write_elem(root, "var", var)
    emb = np.load(work / "master_emb.npy", mmap_mode="r")[:n]
    obsm = root.create_group("obsm")
    obsm.attrs.update({"encoding-type": "dict", **ENC})
    ad.io.write_elem(obsm, "X_pca_2d", np.ascontiguousarray(emb), dataset_kwargs={"chunks": (min(n, 1 << 19), 2)})
    if (work / "master_pcs.npy").exists():       # all PCs, rows of ~1M cells x 50
        pcs = np.load(work / "master_pcs.npy", mmap_mode="r")
        xp = obsm.create_array("X_pca", shape=(n, pcs.shape[1]), chunks=(min(n, 1 << 20), pcs.shape[1]),
                               dtype="f4", compressors=BLOSC_F)
        xp.attrs.update({"encoding-type": "array", "encoding-version": "0.2.0"})
        for s0 in range(0, n, 1 << 23):
            xp[s0:min(n, s0 + (1 << 23))] = pcs[s0:min(n, s0 + (1 << 23))]
    for empty in ("varm", "obsp", "varp", "uns"):
        ad.io.write_elem(root, empty, {})
    log(f"obs/var/obsm written ({time.time() - t_start:.0f} s)")
    # layers/counts_csr: hard-linked prefix of the master CSR
    layers = root.create_group("layers")
    layers.attrs.update({"encoding-type": "dict", **ENC})
    csr = layers.create_group("counts_csr")
    mpath = work / mname
    link_prefix(mpath / "data", tmp / "layers/counts_csr/data", nnz)
    link_prefix(mpath / "indices", tmp / "layers/counts_csr/indices", nnz)
    csr.create_array("indptr", data=indptr_all[:n + 1], chunks=(1 << 22,), compressors=BLOSC_I)
    csr.attrs.update({"encoding-type": "csr_matrix", **ENC, "shape": [n, n_genes]})
    # X: CSC
    xg = root.create_group("X")
    budget = a.mem_entries or 0.35 * _ram_bytes() / 8
    if a.panel:
        if a.genes:
            sys.exit("--panel and --genes cannot be combined")
        colcount = column_counts(master, nnz)
        log(f"gene counts ({time.time() - t_start:.0f} s)")
        order = np.argsort(-colcount, kind="stable")
        names = gm["gene_symbol"].astype(str).values
        panel, why = select_panel(master, indptr_all, colcount, order, a.panel, int(budget), names)
        xg.attrs.update({"gene_panel": [int(g) for g in panel],
                         "gene_order_full": [int(g) for g in order[:2010]],
                         "gene_panel_rule": PANEL_RULE})
        with open(out.parent / (out.name + ".panel.tsv"), "w") as f:
            f.write("gene_index\tgene_symbol\tstored_values\treason\n")
            for g in panel:
                f.write(f"{g}\t{names[g]}\t{colcount[g]}\t{why[g]}\n")
        log(f"panel: {len(panel)} genes, {colcount[panel].sum():,} of {nnz:,} values")
        build_csc(master, xg, n, nnz, int(budget), colcount=colcount, panel=panel)
    else:
        build_csc(master, xg, n, nnz, int(budget), n_genes=n_genes)
    zarr.consolidate_metadata(str(tmp), zarr_format=2)
    tmp.rename(out)
    info = {"n_cells": n, "n_genes": n_genes, "genes": str(a.genes) if a.genes else "all", "nnz": nnz,
            "obsm": sorted(obsm.array_keys()), "master": mname, "seconds": time.time() - t_start,
            "chunk": CHUNK, "compressor": "blosc zstd clevel 3",
            "zarr": zarr.__version__, "anndata": _version("anndata")}
    (out.parent / (out.name + ".build.json")).write_text(json.dumps(info, indent=1))
    log(f"store {out} done in {time.time() - t_start:.0f} s")


def cmd_check(a):
    """Compare a few gene columns (X, CSC) and cell rows (counts_csr) with the master."""
    import anndata as ad
    work = Path(a.work)
    mname = "master_panel.zarr" if a.genes else "master.zarr"
    master = zarr.open_group(str(work / mname), mode="r")
    G = int(master.attrs["shape"][1])
    st = zarr.open_group(a.store, mode="r", use_consolidated=True)
    assert st["X"].attrs["shape"][1] == G and st["layers/counts_csr"].attrs["shape"][1] == G
    if "X_pca" in st["obsm"]:   # a few rows of X_pca equal master_pcs.npy
        pcs = np.load(work / "master_pcs.npy", mmap_mode="r")
        n0 = st["obsm/X_pca"].shape[0]
        for r in np.random.default_rng(2).choice(n0, 5, replace=False):
            assert np.array_equal(st["obsm/X_pca"][r], pcs[r]), r
    n = st["X"].attrs["shape"][0]
    ip = master["indptr"][:n + 1]
    rng = np.random.default_rng(1)
    rows = np.sort(rng.choice(n, 5, replace=False))
    for r in rows:   # cell row from the CSR layer equals master
        s, e = ip[r], ip[r + 1]
        assert np.array_equal(st["layers/counts_csr/indices"][s:e], master["indices"][s:e])
    # gene columns from CSC vs a scan of the first 200k cells of the master
    m = min(n, 200_000)
    sub = sp.csr_matrix((master["data"][:ip[m]], master["indices"][:ip[m]], ip[:m + 1]), shape=(m, G)).tocsc()
    cp = st["X/indptr"][:]
    panel = st["X"].attrs.get("gene_panel")
    genes = rng.choice(panel if panel else G, min(20, len(panel) if panel else 20), replace=False)
    if panel:
        empty = np.setdiff1d(np.arange(G), panel)
        assert np.all(np.diff(cp)[empty] == 0), "a gene outside the panel holds values in X"
    for gidx in genes:
        s, e = cp[gidx], cp[gidx + 1]
        cells = st["X/indices"][s:e]; vals = st["X/data"][s:e]
        keep = cells < m
        col = sub[:, gidx]
        assert np.array_equal(cells[keep], col.indices) and np.allclose(vals[keep], col.data), gidx
    a2 = ad.read_zarr(a.store) if n <= 2_000_000 else None
    if a2 is not None:
        log("anndata read ok:", a2)
    log("check ok", a.store)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit"); f.add_argument("--parquet", required=True); f.add_argument("--work", required=True)
    m = sub.add_parser("master"); m.add_argument("--parquet", required=True); m.add_argument("--work", required=True)
    m.add_argument("--max-cells", type=int, required=True)
    m.add_argument("--delete-consumed", action="store_true",
                   help="delete each parquet shard once it is in the master (saves disk)")
    m.add_argument("--n-pcs", type=int, default=2,
                   help="PCs to project; >2 also writes WORK/master_pcs.npy [n, n_pcs]")
    m.add_argument("--detect-at", type=int, nargs="*", default=None,
                   help="prefix sizes whose per-gene detection counts go to WORK/detect_prefix.npz")
    s = sub.add_parser("store"); s.add_argument("--work", required=True); s.add_argument("--n", type=int, required=True)
    s.add_argument("--out", required=True); s.add_argument("--mem-entries", type=float, default=None,
                   help="values per CSC pass (8 bytes each); default: 35%% of RAM")
    s.add_argument("--gene-metadata", default=None)
    s.add_argument("--genes", default=None, help="panel file (build_tahoe.py panel): X and counts_csr over these genes only")
    s.add_argument("--panel", type=int, default=0,
                   help="X holds only this many genes (benchmark genes + top variance); 0 = all genes")
    c = sub.add_parser("check"); c.add_argument("--work", required=True); c.add_argument("--store", required=True)
    c.add_argument("--genes", default=None)
    o = sub.add_parser("obs"); o.add_argument("--parquet", required=True); o.add_argument("--work", required=True)
    o.add_argument("--shards", type=int, default=3388); o.add_argument("--threads", type=int, default=16)
    r = sub.add_parser("refit"); r.add_argument("--parquet", required=True); r.add_argument("--work", required=True)
    r.add_argument("--ref-idx", required=True); r.add_argument("--threads", type=int, default=16)
    pn = sub.add_parser("panel"); pn.add_argument("--work", required=True); pn.add_argument("--out", required=True)
    pn.add_argument("--n-hvg", type=int, default=5000); pn.add_argument("--extra", nargs="*", default=["MALAT1"])
    pn.add_argument("--bench-top", type=int, default=2008); pn.add_argument("--gene-metadata", default=None)
    pc_ = sub.add_parser("plot-copy"); pc_.add_argument("--work", required=True); pc_.add_argument("--src", required=True)
    pc_.add_argument("--out", required=True); pc_.add_argument("--n-genes", type=int, default=200)
    pj = sub.add_parser("project"); pj.add_argument("--work", required=True); pj.add_argument("--fit", required=True)
    pj.add_argument("--out", required=True); pj.add_argument("--n-pcs", type=int, default=2)
    pj.add_argument("--threads", type=int, default=8)
    pm = sub.add_parser("panel-master"); pm.add_argument("--work", required=True)
    pm.add_argument("--threads", type=int, default=8)
    a = ap.parse_args()
    {"fit": cmd_fit, "master": cmd_master, "store": cmd_store, "check": cmd_check, "obs": cmd_obs,
     "refit": cmd_refit, "panel": cmd_panel, "panel-master": cmd_panel_master,
     "plot-copy": cmd_plot_copy, "project": cmd_project}[a.cmd](a)


if __name__ == "__main__":
    main()
