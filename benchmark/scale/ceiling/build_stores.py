#!/usr/bin/env python
"""Synthetic AnnData zarr stores for the Cell Plot point ceiling.

One master store with 95,624,334 cells (the size of Tahoe-100M) is written
chunk by chunk with numcodecs; every smaller store is a prefix of it whose
chunk files are hard links into the master (zarr format 2 keeps edge chunks at
full chunk size, so a prefix store can reuse the master's chunk files as they
are). Layout (AnnData on-disk spec, zarr format 2, consolidated metadata):

  obs/_index           vlen-utf8, Tahoe-like barcodes ("01_002_345-lib_0678", 19 chars)
  obs/cell_type        categorical, 50 categories ("type_00".."type_49"), int8 codes
  var/_index           4 genes: GENE0..GENE3
  X                    dense float32 N x 4, chunks (2^21, 1): one gene column is cheap
  obsm/X_umap          float32 N x 2, 50 Gaussian blobs (one per category)

Usage: build_stores.py OUTDIR [--sizes 1000000,5000000,...] [--master-n N]

--master-n builds (and cuts from) a master of N cells instead, named
syn_master_N.zarr. A chunk's values depend only on its index, so the two
masters agree on every cell before the default master's edge chunk.
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from numcodecs import Blosc, VLenUTF8

N_MASTER = 95_624_334
C = 2 ** 21
N_CAT = 50
N_GENE = 4
COMP = Blosc(cname="zstd", clevel=3, shuffle=Blosc.SHUFFLE)
COMP_CFG = COMP.get_config()
VLEN = VLenUTF8()
SIZES = [1_000_000, 5_000_000, 10_000_000, 20_000_000, 35_000_000, 50_000_000, 75_000_000]


def zarray(shape, chunks, dtype, fill, filters=None):
    return {"shape": list(shape), "chunks": list(chunks), "dtype": dtype, "fill_value": fill, "order": "C",
            "filters": filters, "dimension_separator": ".", "compressor": COMP_CFG, "zarr_format": 2}


def layout(n: int) -> dict:
    """Every .zarray/.zattrs/.zgroup of a store with n cells: {relative path: json}."""
    arr_attrs = {"encoding-type": "array", "encoding-version": "0.2.0"}
    str_attrs = {"encoding-type": "string-array", "encoding-version": "0.2.0"}
    dict_attrs = {"encoding-type": "dict", "encoding-version": "0.1.0"}
    vl = [{"id": "vlen-utf8"}]
    m = {
        ".zgroup": {"zarr_format": 2},
        ".zattrs": {"encoding-type": "anndata", "encoding-version": "0.1.0"},
        "obs/.zgroup": {"zarr_format": 2},
        "obs/.zattrs": {"_index": "_index", "column-order": ["cell_type"], "encoding-type": "dataframe",
                        "encoding-version": "0.2.0"},
        "obs/_index/.zarray": zarray([n], [C], "|O", "", vl),
        "obs/_index/.zattrs": str_attrs,
        "obs/cell_type/.zgroup": {"zarr_format": 2},
        "obs/cell_type/.zattrs": {"ordered": False, "encoding-type": "categorical", "encoding-version": "0.2.0"},
        "obs/cell_type/codes/.zarray": zarray([n], [C], "|i1", 0),
        "obs/cell_type/codes/.zattrs": arr_attrs,
        "obs/cell_type/categories/.zarray": zarray([N_CAT], [N_CAT], "|O", "", vl),
        "obs/cell_type/categories/.zattrs": str_attrs,
        "var/.zgroup": {"zarr_format": 2},
        "var/.zattrs": {"_index": "_index", "column-order": [], "encoding-type": "dataframe",
                        "encoding-version": "0.2.0"},
        "var/_index/.zarray": zarray([N_GENE], [N_GENE], "|O", "", vl),
        "var/_index/.zattrs": str_attrs,
        "X/.zarray": zarray([n, N_GENE], [C, 1], "<f4", 0.0),
        "X/.zattrs": arr_attrs,
        "obsm/.zgroup": {"zarr_format": 2},
        "obsm/.zattrs": dict_attrs,
        "obsm/X_umap/.zarray": zarray([n, 2], [C, 2], "<f4", 0.0),
        "obsm/X_umap/.zattrs": arr_attrs,
    }
    for g in ("layers", "obsp", "varm", "varp", "uns"):
        m[f"{g}/.zgroup"] = {"zarr_format": 2}
        m[f"{g}/.zattrs"] = dict_attrs
    return m


def write_meta(root: Path, n: int):
    meta = layout(n)
    for rel, obj in meta.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=1))
    (root / ".zmetadata").write_text(json.dumps({"metadata": meta, "zarr_consolidated_format": 1}, indent=1))


def centres():
    rng = np.random.default_rng(12345)
    ang = rng.uniform(0, 2 * np.pi, N_CAT)
    rad = rng.uniform(2, 12, N_CAT)
    return np.stack([rad * np.cos(ang), rad * np.sin(ang)], 1), rng.uniform(0.3, 1.2, N_CAT)


def write_chunk(args):
    root, k, n_master = args
    root = Path(root)
    lo, hi = k * C, min((k + 1) * C, n_master)
    m = hi - lo
    rng = np.random.default_rng(1000 + k)
    cen, sd = centres()
    w = 1.0 / np.arange(1, N_CAT + 1) ** 0.7
    codes = rng.choice(N_CAT, size=C, p=w / w.sum()).astype(np.int8)
    xy = (cen[codes] + rng.standard_normal((C, 2)) * sd[codes, None]).astype(np.float32)
    idx = np.arange(lo, lo + C)
    names = [f"{i // 1_000_000:02d}_{(i // 1000) % 1000:03d}_{i % 1000:03d}-lib_{(i * 7919) % 10000:04d}"
             if i < n_master else "" for i in idx]
    if m < C:   # pad the edge chunk past the end (never read)
        codes[m:] = 0
        xy[m:] = 0
    (root / "obs/_index" / str(k)).write_bytes(COMP.encode(VLEN.encode(np.array(names, dtype=object))))
    (root / "obs/cell_type/codes" / str(k)).write_bytes(COMP.encode(codes))
    (root / "obsm/X_umap" / f"{k}.0").write_bytes(COMP.encode(np.ascontiguousarray(xy)))
    for g in range(N_GENE):
        lam = np.exp(0.15 * (xy[:, 0] * np.cos(g) + xy[:, 1] * np.sin(g)) - 0.5)
        val = rng.poisson(np.clip(lam, 0, 50)).astype(np.float32)
        (root / "X" / f"{k}.{g}").write_bytes(COMP.encode(val))
    return k


def build_master(root: Path, n_master: int = N_MASTER):
    write_meta(root, n_master)
    cats = np.array([f"type_{i:02d}" for i in range(N_CAT)], dtype=object)
    (root / "obs/cell_type/categories/0").write_bytes(COMP.encode(VLEN.encode(cats)))
    genes = np.array([f"GENE{i}" for i in range(N_GENE)], dtype=object)
    (root / "var/_index/0").write_bytes(COMP.encode(VLEN.encode(genes)))
    nchunks = -(-n_master // C)
    with ProcessPoolExecutor(12) as ex:
        for k in ex.map(write_chunk, [(str(root), k, n_master) for k in range(nchunks)]):
            print(f"chunk {k + 1}/{nchunks}", flush=True)
    (root / ".built").write_text("ok")


def build_prefix(master: Path, root: Path, n: int):
    write_meta(root, n)
    nchunks = -(-n // C)
    for d in ("obs/cell_type/categories", "var/_index"):
        os.link(master / d / "0", root / d / "0")
    for k in range(nchunks):
        os.link(master / "obs/_index" / str(k), root / "obs/_index" / str(k))
        os.link(master / "obs/cell_type/codes" / str(k), root / "obs/cell_type/codes" / str(k))
        os.link(master / "obsm/X_umap" / f"{k}.0", root / "obsm/X_umap" / f"{k}.0")
        for g in range(N_GENE):
            os.link(master / "X" / f"{k}.{g}", root / "X" / f"{k}.{g}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outdir")
    ap.add_argument("--sizes", default=",".join(map(str, SIZES)))
    ap.add_argument("--master-n", type=int, default=N_MASTER)
    a = ap.parse_args()
    out = Path(a.outdir)
    master = out / (f"syn_{N_MASTER}.zarr" if a.master_n == N_MASTER else f"syn_master_{a.master_n}.zarr")
    if not (master / ".built").exists():
        build_master(master, a.master_n)
    for n in map(int, a.sizes.split(",")):
        dst = out / f"syn_{n}.zarr"
        if not dst.exists():
            build_prefix(master, dst, n)
            print("prefix", dst, flush=True)


if __name__ == "__main__":
    main()
