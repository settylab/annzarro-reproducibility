#!/usr/bin/env python
"""Files for the Zenodo record of the Tahoe-100M UMAP (no upload; the user uploads).

Reads the full 95,624,334-cell AnnZarro store (obs/_index = BARCODE_SUB_LIB_ID,
obs/plate, obs/cell_line_id, obsm/X_umap, all in the Hugging Face release's
shard order) and writes to OUTDIR:

  tahoe100m_umap.parquet            cell_index (int64, row in shard order), BARCODE_SUB_LIB_ID,
                                    umap_1, umap_2 (float32), is_reference (bool)
  tahoe100m_umap_reference.parquet  the reference cells the UMAP was fitted on:
                                    cell_index, BARCODE_SUB_LIB_ID, plate, cell_line_id
  checks.json                       row counts, uniqueness of BARCODE_SUB_LIB_ID, the sha256 of the
                                    raw X_umap bytes (as in the store's .build.json), and whether the
                                    regenerated reference matches --ref-idx when given

The reference is regenerated exactly as `umap_tahoe.py sample` draws it (seed 0,
--per-stratum cells from every plate x cell_line_id stratum, all of a smaller
stratum), from the store's own plate and cell_line_id. With --ref-idx (the
ref_idx.npy of the UMAP run) it is checked against the run's file instead.

Usage: zenodo_umap.py STORE.zarr OUTDIR [--per-stratum 1430] [--ref-idx ref_idx.npy] [--ref-strata ref_strata.csv]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import zarr

SEED = 0          # umap_tahoe.py SEED
ROWS = 1 << 22    # rows per parquet row group


def categorical(g, name):
    codes = g[f"obs/{name}/codes"][:]
    cats = np.asarray(g[f"obs/{name}/categories"][:], dtype=object)
    return pd.Categorical.from_codes(codes, categories=cats)


def reference(plate, line, per_stratum):
    """umap_tahoe.py cmd_sample, on the same two columns."""
    obs = pd.DataFrame({"plate": plate, "cell_line_id": line})
    rng = np.random.default_rng(SEED)
    strata = obs.groupby(["plate", "cell_line_id"], observed=True).indices
    pick = []
    for _, ix in sorted(strata.items()):
        pick.append(np.sort(rng.choice(ix, min(per_stratum, len(ix)), replace=False)))
    return np.sort(np.concatenate(pick)).astype(np.int64)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("store")
    ap.add_argument("outdir")
    ap.add_argument("--per-stratum", type=int, default=1430)
    ap.add_argument("--ref-idx", default="")
    ap.add_argument("--ref-strata", default="", help="ref_strata.csv of the UMAP run: compare per-stratum counts")
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    g = zarr.open_group(a.store, mode="r")
    umap = g["obsm/X_umap"]
    n = umap.shape[0]
    names = np.asarray(g["obs/_index"][:], dtype=object)
    plate, line = categorical(g, "plate"), categorical(g, "cell_line_id")
    checks = {"n_cells": int(n), "store": a.store}
    checks["barcode_unique"] = bool(pd.Index(names).is_unique)

    ref = reference(plate, line, a.per_stratum)
    checks["n_reference"] = int(len(ref))
    checks["per_stratum"] = a.per_stratum
    if a.ref_idx:
        run = np.load(a.ref_idx)
        checks["reference_matches_run"] = bool(np.array_equal(np.sort(run), ref))
    if a.ref_strata:
        run = pd.read_csv(a.ref_strata).set_index(["plate", "cell_line_id"])["n_ref"].sort_index()
        mine = (pd.DataFrame({"plate": np.asarray(plate)[ref].astype(str), "cell_line_id": np.asarray(line)[ref].astype(str)})
                .value_counts().rename("n_ref").sort_index())
        mine.index = mine.index.set_names(["plate", "cell_line_id"])
        checks["strata_match_run"] = bool(run.astype(int).equals(mine.reindex(run.index).astype(int))
                                          and len(mine) == len(run))
        checks["n_strata"] = int(len(mine))
    is_ref = np.zeros(n, bool)
    is_ref[ref] = True

    sha = hashlib.sha256()
    schema = pa.schema([("cell_index", pa.int64()), ("BARCODE_SUB_LIB_ID", pa.string()),
                        ("umap_1", pa.float32()), ("umap_2", pa.float32()), ("is_reference", pa.bool_())])
    with pq.ParquetWriter(out / "tahoe100m_umap.parquet", schema, compression="zstd", compression_level=9) as w:
        for lo in range(0, n, ROWS):
            hi = min(lo + ROWS, n)
            xy = np.ascontiguousarray(umap[lo:hi], dtype="<f4")
            sha.update(xy.tobytes())
            w.write_table(pa.table({"cell_index": np.arange(lo, hi, dtype=np.int64),
                                    "BARCODE_SUB_LIB_ID": pa.array(names[lo:hi], pa.string()),
                                    "umap_1": xy[:, 0], "umap_2": xy[:, 1], "is_reference": is_ref[lo:hi]},
                                   schema=schema))
            print(f"{hi:,}/{n:,}", flush=True)
    checks["x_umap_sha256"] = sha.hexdigest()
    checks["x_umap_sha256_of"] = "raw little-endian float32 bytes of X_umap [n, 2], C order"
    pq.write_table(pa.table({"cell_index": ref, "BARCODE_SUB_LIB_ID": pa.array(names[ref], pa.string()),
                             "plate": pa.array(np.asarray(plate)[ref].astype(str)),
                             "cell_line_id": pa.array(np.asarray(line)[ref].astype(str))}),
                   out / "tahoe100m_umap_reference.parquet", compression="zstd", compression_level=9)
    (out / "checks.json").write_text(json.dumps(checks, indent=1))
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    main()
