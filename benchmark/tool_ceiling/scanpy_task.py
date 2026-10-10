#!/usr/bin/env python
"""The Scanpy task: open the dataset, draw the UMAP coloured by cell line, then
by one gene, each to a PNG. Run inside memmon.py, which measures the process.

Variants (each is a workflow the anndata/scanpy docs describe):
  default     sc.read_h5ad(path)                       everything in memory
  backed      sc.read_h5ad(path, backed="r")           X stays on disk
  lazy_h5ad   anndata.experimental.read_lazy(path), keep one gene, .to_memory()
  lazy_zarr   the same on the AnnData zarr store (X stored CSC)

Scanpy 1.12 cannot plot a lazy AnnData directly (TypeError: unhashable type
'DataArray'), so the lazy variants subset to the one gene first and load
obs/obsm/that gene with .to_memory(), as anndata's lazy-loading tutorial does.

Every cell drawn: the scatter's PathCollection must hold n_obs offsets.
Writes a JSON with phase times and checks to OUT.json; PNGs next to it.

Usage: scanpy_task.py VARIANT PATH OUTPREFIX [--gene MALAT1] [--color cell_line_id]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from importlib.metadata import version

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def n_colours(png: str) -> int:
    im = plt.imread(png)[..., :3]
    q = (im * 255).astype(np.uint8).reshape(-1, 3)
    return len(np.unique(q, axis=0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variant", choices=["default", "backed", "lazy_h5ad", "lazy_zarr"])
    ap.add_argument("path")
    ap.add_argument("out")
    ap.add_argument("--gene", default="MALAT1")
    ap.add_argument("--color", default="cell_line_id")
    a = ap.parse_args()
    rec = {"variant": a.variant, "path": a.path, "versions": {p: version(p) for p in
                                                              ("scanpy", "anndata", "matplotlib", "numpy", "h5py", "zarr")},
           "phases": {}, "checks": {}}
    t0 = time.time()

    def mark(k):
        rec["phases"][k] = round(time.time() - t0, 2)
        print(f"[{rec['phases'][k]:8.1f}s] {k}", file=sys.stderr, flush=True)
        json.dump(rec, open(a.out + ".json", "w"), indent=1)

    import anndata as ad
    import scanpy as sc
    mark("import")
    if a.variant == "default":
        adata = sc.read_h5ad(a.path)
    elif a.variant == "backed":
        adata = sc.read_h5ad(a.path, backed="r")
    else:
        lazy = ad.experimental.read_lazy(a.path)
        adata = lazy[:, [a.gene]].to_memory()
        del lazy
    rec["n_obs"] = int(adata.n_obs)
    mark("load")
    for key, tag in ((a.color, "cat"), (a.gene, "gene")):
        ax = sc.pl.umap(adata, color=key, show=False)
        n_drawn = sum(len(c.get_offsets()) for c in ax.collections)
        png = f"{a.out}_{tag}.png"
        ax.figure.savefig(png, dpi=150, bbox_inches="tight")
        plt.close(ax.figure)
        rec["checks"][tag] = {"n_drawn": n_drawn, "all_cells": n_drawn == adata.n_obs, "n_colours": n_colours(png),
                              "png": png}
        mark(f"plot_{tag}")
    ok = all(c["all_cells"] for c in rec["checks"].values()) and rec["checks"]["cat"]["n_colours"] >= 20
    rec["ok"] = bool(ok)
    mark("done")
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()
