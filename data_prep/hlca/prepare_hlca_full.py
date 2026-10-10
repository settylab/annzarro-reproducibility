#!/usr/bin/env python
"""Convert the HLCA full release (CELLxGENE h5ad) into an AnnZarro store.

Source: Sikkema et al. 2023, HLCA full, CELLxGENE dataset 9f222629-9e39-47d0-b83f-e08d610c7479
(collection 6f6d381a-7701-4781-935c-db10d30de293), CC BY 4.0, file
5f863718-02a6-46cb-83e7-52be988b915b.h5ad. Plan: notes/fig2_large_dataset_scout.md
("Preparation plan: HLCA full"), with these differences from its draft:
- X is never loaded whole. layers/normalized_csr is written from the h5ad CSR in row blocks, and X
  (CSC) is then built out of core from it by benchmark/scale/build_tahoe.py's build_csc, the same
  code that built the Tahoe stores. So peak memory is set by --mem-entries, not by the matrix.
- Index arrays are int32 (cell or gene ids fit); indptr stays int64 (4.03e9 stored values).
- var index = gene symbols (feature_name made unique as anndata does); the Ensembl id is kept as
  the column `ensembl_id`, so AnnZarro's gene search finds SFTPC, AGER etc. by name.

Layout: zarr format 2, Blosc-zstd 3 (shuffle for values, bitshuffle for indices), 1-D chunks of
2^21 values, consolidated metadata:
  X                       CSC float32, the shipped log-normalised values
  layers/normalized_csr   the same values, CSR float32
  obs                     all columns, categoricals kept
  var                     index = unique symbols; ensembl_id plus the shipped columns
  obsm/X_umap, obsm/X_scanvi_emb   float32 as shipped
  obsp/connectivities     CSR float32 as shipped; obsp/distances CSR cast to float32
  uns                     only the *_colors palettes
  raw and layers/soupX are dropped.

  prepare_hlca_full.py --src HLCA.h5ad --out hlca_full.zarr [--max-cells N] [--mem-entries 2e10]

--max-cells N writes the first N cells only (obsp restricted to those cells), for a test run.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import anndata as ad
import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp
import zarr

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmark" / "scale"))
import build_tahoe as bt  # noqa: E402  (Appender, build_csc, CHUNK, BLOSC_F, BLOSC_I, ENC, log)

log = bt.log


def peak_rss_gb() -> float:
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 ** 2


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-cells", type=int, default=0)
    ap.add_argument("--mem-entries", type=float, default=2e10, help="values per CSC pass (8 bytes each)")
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        sys.exit(f"{out} exists")
    tmp = out.with_name(out.name + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    t_all = time.time()
    timings = {}
    ad.settings.zarr_write_format = 2
    root = zarr.open_group(str(tmp), mode="w", zarr_format=2)
    root.attrs.update({"encoding-type": "anndata", **bt.ENC})
    with h5py.File(a.src, "r") as f:
        n_all, G = (int(x) for x in f["X"].attrs["shape"])
        assert f["X"].attrs["encoding-type"] == "csr_matrix", f["X"].attrs["encoding-type"]
        n = min(a.max_cells, n_all) if a.max_cells else n_all
        chunk_rows = min(n, 1 << 20)

        t0 = time.time()
        obs = ad.io.read_elem(f["obs"]).iloc[:n]
        ad.io.write_elem(root, "obs", obs, dataset_kwargs={"chunks": (chunk_rows,)})
        var = ad.io.read_elem(f["var"])
        var.insert(0, "ensembl_id", var.index.astype(str))
        var.index = ad.utils.make_index_unique(pd.Index(var["feature_name"].astype(str).values))
        var.index.name = None
        ad.io.write_elem(root, "var", var)
        timings["obs_var_s"] = time.time() - t0
        log(f"obs {obs.shape}, var {var.shape} ({timings['obs_var_s']:.0f} s)")

        t0 = time.time()
        obsm = root.create_group("obsm")
        obsm.attrs.update({"encoding-type": "dict", **bt.ENC})
        for k in ("X_umap", "X_scanvi_emb"):
            arr = np.asarray(f[f"obsm/{k}"][:n], dtype=np.float32)
            ad.io.write_elem(obsm, k, arr, dataset_kwargs={"chunks": (chunk_rows, arr.shape[1])})
        obsp = root.create_group("obsp")
        obsp.attrs.update({"encoding-type": "dict", **bt.ENC})
        for k in ("connectivities", "distances"):
            m = ad.io.read_elem(f[f"obsp/{k}"])
            if n < n_all:
                m = m[:n][:, :n]
            m = sp.csr_matrix((m.data.astype(np.float32), m.indices.astype(np.int32), m.indptr.astype(np.int64)),
                              shape=m.shape)
            ad.io.write_elem(obsp, k, m, dataset_kwargs={"chunks": (bt.CHUNK,)})
        colors = {k: ad.io.read_elem(f[f"uns/{k}"]) for k in f.get("uns", {}).keys() if k.endswith("_colors")}
        ad.io.write_elem(root, "uns", colors)
        for empty in ("varm", "varp"):
            ad.io.write_elem(root, empty, {})
        timings["obsm_obsp_uns_s"] = time.time() - t0
        log(f"obsm, obsp, uns ({len(colors)} palettes) written ({timings['obsm_obsp_uns_s']:.0f} s)")

        # layers/normalized_csr from the shipped CSR, in row blocks
        t0 = time.time()
        layers = root.create_group("layers")
        layers.attrs.update({"encoding-type": "dict", **bt.ENC})
        csr = layers.create_group("normalized_csr")
        data = csr.create_array("data", shape=(0,), chunks=(bt.CHUNK,), dtype="f4", compressors=bt.BLOSC_F)
        ind = csr.create_array("indices", shape=(0,), chunks=(bt.CHUNK,), dtype="i4", compressors=bt.BLOSC_I)
        ad_, ai_ = bt.Appender(data), bt.Appender(ind)
        ip = f["X/indptr"][:n + 1].astype(np.int64)
        nnz = int(ip[-1])
        step = 16 * bt.CHUNK
        for s in range(0, nnz, step):
            e = min(nnz, s + step)
            ai_.add(f["X/indices"][s:e].astype(np.int32))
            ad_.add(f["X/data"][s:e].astype(np.float32))
            if (s // step) % 50 == 0:
                log(f"  csr {e:,}/{nnz:,} values ({time.time() - t0:.0f} s)")
        ad_.flush(True); ai_.flush(True)
        assert data.shape[0] == nnz and ind.shape[0] == nnz
        csr.create_array("indptr", data=ip, chunks=(1 << 22,), compressors=bt.BLOSC_I)
        csr.attrs.update({"encoding-type": "csr_matrix", **bt.ENC, "shape": [n, G]})
        timings["csr_s"] = time.time() - t0
        log(f"layers/normalized_csr: {nnz:,} values ({timings['csr_s']:.0f} s)")

    # X: CSC out of core from the CSR just written
    t0 = time.time()
    xg = root.create_group("X")
    bt.build_csc(csr, xg, n, nnz, int(a.mem_entries), n_genes=G)
    timings["csc_s"] = time.time() - t0
    zarr.consolidate_metadata(str(tmp), zarr_format=2)
    tmp.rename(out)
    info = {"n_cells": n, "n_genes": G, "nnz": nnz, "source": str(a.src), "timings_s": timings,
            "total_s": time.time() - t_all, "peak_rss_gb_self": peak_rss_gb(), "chunk": bt.CHUNK,
            "compressor": "blosc zstd clevel 3", "zarr": zarr.__version__, "anndata": ad.__version__,
            "obs_columns": list(obs.columns), "var_index": "feature_name (make_unique)", "var_columns": list(var.columns)}
    (out.parent / (out.name + ".build.json")).write_text(json.dumps(info, indent=1))
    log(json.dumps({k: v for k, v in info.items() if k not in ("obs_columns", "var_columns")}, indent=1))


if __name__ == "__main__":
    main()
