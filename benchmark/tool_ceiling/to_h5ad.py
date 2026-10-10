#!/usr/bin/env python
"""The first N cells of the Tahoe panel zarr store as a plain h5ad, the input a
Scanpy user would have: X as CSR float32 (int32 indices, int64 indptr), no
compression (anndata's write_h5ad default), obs/var/obsm as anndata writes them.

The source X is CSC. Within a gene column the row indices ascend, so a block of
rows [a, b) is one contiguous run of every column. Each of the 200 non-empty
columns is streamed once, chunk by chunk, and every block of rows is assembled
into CSR and appended. Memory: one decoded chunk per column plus one block.

This is input preparation, shared by every h5ad-based tool, and not charged to
any tool (README, "Conversion cost").

With --csc, X is written CSC instead (TissUUmaps reads gene columns).

Usage: to_h5ad.py SRC.zarr N OUT.h5ad [--block 2000000] [--csc]
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anndata as ad
import h5py
import numcodecs
import numpy as np
import pandas as pd
import zarr


class Flat:
    """A 1-D zarr v2 array read by raw chunk files."""

    def __init__(self, p: Path):
        m = json.loads((p / ".zarray").read_text())
        self.p, self.c, self.dt = p, m["chunks"][0], np.dtype(m["dtype"])
        self.codec = numcodecs.get_codec(m["compressor"])

    def get(self, a: int, b: int) -> np.ndarray:
        if b <= a:
            return np.empty(0, self.dt)
        k0, k1 = a // self.c, (b - 1) // self.c
        parts = [np.frombuffer(self.codec.decode((self.p / str(k)).read_bytes()), self.dt) for k in range(k0, k1 + 1)]
        return np.concatenate(parts)[a - k0 * self.c: b - k0 * self.c]


class Column:
    """One CSC column, consumed in ascending row order."""

    STEP = 2 ** 21

    def __init__(self, j, start, end, ind: Flat, dat: Flat):
        self.j, self.pos, self.end, self.ind, self.dat = j, start, end, ind, dat
        self.bi = np.empty(0, np.int32)
        self.bd = np.empty(0, np.float32)

    def take(self, b: int):
        """Rows < b not yet taken: (rows, values)."""
        while self.pos < self.end and (len(self.bi) == 0 or self.bi[-1] < b):
            e = min(self.pos + self.STEP, self.end)
            self.bi = np.concatenate([self.bi, self.ind.get(self.pos, e)])
            self.bd = np.concatenate([self.bd, self.dat.get(self.pos, e)])
            self.pos = e
        k = int(np.searchsorted(self.bi, b))
        r, v = self.bi[:k], self.bd[:k]
        self.bi, self.bd = self.bi[k:], self.bd[k:]
        return r, v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("n", type=int)
    ap.add_argument("out")
    ap.add_argument("--block", type=int, default=2_000_000)
    ap.add_argument("--csc", action="store_true", help="X as CSC (TissUUmaps reads columns): each column cut to rows < N")
    a = ap.parse_args()
    t0 = time.time()
    src, n, out = Path(a.src), a.n, Path(a.out)
    g = zarr.open_group(src, mode="r")
    nmax = g["obsm/X_umap"].shape[0]
    assert n <= nmax, (n, nmax)

    obs = {}
    for k in g["obs"].attrs["column-order"]:
        e = g["obs"][k]
        if e.attrs.get("encoding-type") == "categorical":
            obs[k] = pd.Categorical.from_codes(e["codes"][:n], e["categories"][:], ordered=bool(e.attrs["ordered"]))
        else:
            obs[k] = e[:n]
    obs = pd.DataFrame(obs, index=pd.Index(np.asarray(g["obs/_index"][:n], dtype=object), name=None))
    var = ad.io.read_elem(g["var"])
    obsm = {k: np.asarray(g["obsm"][k][:n]) for k in g["obsm"].keys()}
    n_vars = var.shape[0]
    adata = ad.AnnData(obs=obs, var=var, obsm=obsm)
    tmp = out.with_suffix(".h5ad.part")
    adata.write_h5ad(tmp)
    del adata, obs, obsm
    t_meta = time.time() - t0

    ip = g["X/indptr"][:]
    ind, dat = Flat(src / "X/indices"), Flat(src / "X/data")
    cols = [Column(j, int(ip[j]), int(ip[j + 1]), ind, dat) for j in range(n_vars) if ip[j + 1] > ip[j]]
    nnz = 0
    with h5py.File(tmp, "a") as f:
        X = f.create_group("X")
        X.attrs.update({"encoding-type": "csc_matrix" if a.csc else "csr_matrix", "encoding-version": "0.1.0",
                        "shape": np.array([n, n_vars])})
        dd = X.create_dataset("data", (0,), np.float32, maxshape=(None,), chunks=(2 ** 20,))
        di = X.create_dataset("indices", (0,), np.int32, maxshape=(None,), chunks=(2 ** 20,))
        if a.csc:  # each source column cut to its rows < n (row indices ascend within a column)
            new_ip = np.zeros(n_vars + 1, np.int64)
            for j in range(n_vars):
                a0, b0 = int(ip[j]), int(ip[j + 1])
                if b0 > a0:
                    idx = ind.get(a0, b0)
                    k = int(np.searchsorted(idx, n))
                    dd.resize((nnz + k,))
                    di.resize((nnz + k,))
                    dd[nnz:] = dat.get(a0, a0 + k)
                    di[nnz:] = idx[:k]
                    nnz += k
                new_ip[j + 1] = nnz
            # int32 when it fits, as scipy/anndata write it (TissUUmaps' h5wasm reader cannot use int64)
            X.create_dataset("indptr", data=new_ip.astype(np.int32) if nnz < 2 ** 31 else new_ip)
        else:
            pool = ThreadPoolExecutor(12)
            dp = X.create_dataset("indptr", (n + 1,), np.int64)
            dp[0] = 0
            for a0 in range(0, n, a.block):
                b = min(a0 + a.block, n)
                parts = list(pool.map(lambda c: c.take(b), cols))
                rows = np.concatenate([p[0] for p in parts]) - a0
                vals = np.concatenate([p[1] for p in parts])
                cj = np.concatenate([np.full(len(p[0]), c.j, np.int32) for c, p in zip(cols, parts)])
                order = np.argsort(rows, kind="stable")  # columns arrive in ascending order
                counts = np.bincount(rows, minlength=b - a0)
                m = len(vals)
                dd.resize((nnz + m,))
                di.resize((nnz + m,))
                dd[nnz:] = vals[order]
                di[nnz:] = cj[order]
                dp[a0 + 1: b + 1] = nnz + np.cumsum(counts)
                nnz += m
                print(f"{b:,} rows, {nnz:,} nnz, {time.time() - t0:.0f}s", flush=True)
    tmp.rename(out)
    rec = {"src": str(src), "n": n, "out": str(out), "nnz": nnz, "nnz_per_cell": nnz / n, "bytes": out.stat().st_size,
           "seconds": round(time.time() - t0, 1), "seconds_meta": round(t_meta, 1),
           "anndata": ad.__version__, "h5py": h5py.__version__}
    Path(str(out) + ".build.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
