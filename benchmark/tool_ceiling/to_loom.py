#!/usr/bin/env python
"""The shared tahoe_first<N>.h5ad as a .loom for SCope 1.8.2, written in batches of cells.

loom stores the matrix dense (genes x cells, HDF5, chunked and gzip-compressed by loompy), so
the 5,000 x N panel is written column block by column block from the CSR X. SCope's
minimal attributes: ra Gene, ca CellID, ca Embedding (X_umap as _X/_Y), and cell_line_id as
a column attribute declared in the MetaData "annotations" (SCope's annotation colouring).
Input preparation, not measured (README, input rule).

Usage: to_loom.py IN.h5ad OUT.loom [--batch 100000]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import h5py
import loompy
import numpy as np
import scipy.sparse as sp


def strings(ds):
    g = ds
    if isinstance(g, h5py.Group):  # nullable-string-array
        g = g["values"]
    return np.array([x.decode() if isinstance(x, bytes) else str(x) for x in g[:]], dtype=object)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("h5ad")
    ap.add_argument("out")
    ap.add_argument("--batch", type=int, default=100_000)
    a = ap.parse_args()
    t0 = time.time()
    f = h5py.File(a.h5ad, "r")
    X = f["X"]
    assert X.attrs["encoding-type"] == "csr_matrix"
    n, g = (int(x) for x in X.attrs["shape"])
    genes = strings(f["var/_index"])
    cells = strings(f["obs/_index"])
    cl = f["obs/cell_line_id"]
    cats = strings(cl["categories"])
    lines = cats[cl["codes"][:]]
    umap = f["obsm/X_umap"][:]
    emb = np.zeros(n, dtype=[("_X", "<f4"), ("_Y", "<f4")])
    emb["_X"], emb["_Y"] = umap[:, 0], umap[:, 1]
    indptr = X["indptr"]
    meta = {"embeddings": [{"id": -1, "name": "X_umap"}],
            "annotations": [{"name": "cell_line_id", "values": sorted(set(cats.tolist()))}],
            "clusterings": [], "metrics": []}
    out = Path(a.out)
    out.unlink(missing_ok=True)
    with loompy.new(str(out)) as ds:
        for lo in range(0, n, a.batch):
            hi = min(lo + a.batch, n)
            p = indptr[lo:hi + 1]
            m = sp.csr_matrix((X["data"][p[0]:p[-1]], X["indices"][p[0]:p[-1]], p - p[0]), shape=(hi - lo, g))
            ds.add_columns(m.T.toarray().astype(np.float32),
                           col_attrs={"CellID": cells[lo:hi], "cell_line_id": lines[lo:hi], "Embedding": emb[lo:hi]},
                           row_attrs={"Gene": genes})
        ds.attrs["MetaData"] = json.dumps(meta)
    print(json.dumps({"out": str(out), "n": n, "genes": g, "bytes": out.stat().st_size,
                      "seconds": round(time.time() - t0, 1), "loompy": loompy.__version__}))


if __name__ == "__main__":
    main()
