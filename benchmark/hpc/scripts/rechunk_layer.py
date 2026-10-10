#!/usr/bin/env python
"""Rechunk one dense layer of an AnnData zarr v2 store into a new, minimal store.

The destination holds the root group metadata, obs/ and var/ (copied verbatim, so
cell/gene names and the dataset-open path behave as in the source) and a single
layer, rewritten with the requested chunk shape and THE SOURCE'S compressor and
dtype, so chunk shape is the only variable. Values are verified equal on a
seeded sample of rows and columns after the write.

Usage: rechunk_layer.py SRC_STORE LAYER DST_STORE ROWS,COLS
       (ROWS may be 'all' for the full cell axis)
"""
import json
import math
import os
import shutil
import sys
import time

import numcodecs
import numpy as np
import zarr


def main():
    src, layer, dst, shape = sys.argv[1:5]
    za = json.load(open(os.path.join(src, "layers", layer, ".zarray")))
    n, m = za["shape"]
    r_s, c_s = shape.split(",")
    chunks = (n if r_s == "all" else int(r_s), m if c_s == "all" else int(c_s))
    if os.path.exists(dst):
        raise SystemExit(f"refusing to overwrite existing {dst}")
    tmp = dst + ".partial"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(os.path.join(tmp, "layers"))
    for f in (".zgroup", ".zattrs"):
        if os.path.exists(os.path.join(src, f)):
            shutil.copy2(os.path.join(src, f), os.path.join(tmp, f))
    for g in ("obs", "var"):
        shutil.copytree(os.path.join(src, g), os.path.join(tmp, g))
    shutil.copy2(os.path.join(src, "layers", ".zgroup"), os.path.join(tmp, "layers", ".zgroup"))
    with open(os.path.join(tmp, "layers", ".zattrs"), "w") as fh:
        json.dump({}, fh)
    comp = numcodecs.get_codec(za["compressor"])
    s = zarr.open_array(os.path.join(src, "layers", layer), mode="r")
    d = zarr.create_array(store=os.path.join(tmp, "layers", layer), shape=(n, m), chunks=chunks,
                          dtype=za["dtype"], zarr_format=2, compressors=comp,
                          fill_value=za["fill_value"])
    attrs = os.path.join(src, "layers", layer, ".zattrs")
    if os.path.exists(attrs):
        shutil.copy2(attrs, os.path.join(tmp, "layers", layer, ".zattrs"))
    # Column blocks aligned to BOTH the source and the destination column chunking,
    # so every source chunk is decompressed once and every destination chunk written once.
    step = math.lcm(s.chunks[1], chunks[1])
    t0 = time.time()
    for j in range(0, m, step):
        block = s[:, j:j + step]
        d[:, j:j + step] = block
        print(f"cols {j}-{min(m, j + step)} / {m}  {time.time() - t0:.0f}s", flush=True)
    rng = np.random.default_rng(0)
    for i in rng.choice(n, 3, replace=False):
        assert np.array_equal(s[int(i), :], d[int(i), :], equal_nan=True), f"row {i} differs"
    for j in rng.choice(m, 3, replace=False):
        assert np.array_equal(s[:, int(j)], d[:, int(j)], equal_nan=True), f"col {j} differs"
    os.rename(tmp, dst)
    print(f"done {dst} chunks={chunks} in {time.time() - t0:.0f}s; verified 3 rows + 3 cols")


if __name__ == "__main__":
    main()
