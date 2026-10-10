#!/usr/bin/env python
"""Rechunk a dense pairwise array (obsp/<key> or varp/<key>) to whole-row chunks of R rows.

The destination is a new minimal store: root metadata, obs/ and var/ copied verbatim, and the
one array rewritten with chunks (R, n_cols), the SOURCE's compressor, dtype and fill value.
Reads row blocks of lcm(source rows, R), so every source chunk is decompressed once. Verifies
5 seeded rows equal after the write.

Usage: rechunk_rows.py SRC_STORE ARRAY DST_STORE R      (ARRAY e.g. obsp/diffmap_distance)
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
    src, arr, dst, r = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    if os.path.exists(dst):
        raise SystemExit(f"refusing to overwrite existing {dst}")
    za = json.load(open(os.path.join(src, arr, ".zarray")))
    n, m = za["shape"]
    tmp = dst + ".partial"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(os.path.join(tmp, os.path.dirname(arr)))
    for f in (".zgroup", ".zattrs"):
        for d in ("", os.path.dirname(arr)):
            p = os.path.join(src, d, f)
            if os.path.exists(p):
                shutil.copy2(p, os.path.join(tmp, d, f))
    for g in ("obs", "var"):
        shutil.copytree(os.path.join(src, g), os.path.join(tmp, g))
    s = zarr.open_array(os.path.join(src, arr), mode="r")
    d = zarr.create_array(store=os.path.join(tmp, arr), shape=(n, m), chunks=(r, m), dtype=za["dtype"],
                          zarr_format=2, compressors=numcodecs.get_codec(za["compressor"]),
                          fill_value=za["fill_value"])
    if os.path.exists(os.path.join(src, arr, ".zattrs")):
        shutil.copy2(os.path.join(src, arr, ".zattrs"), os.path.join(tmp, arr, ".zattrs"))
    step = math.lcm(s.chunks[0], r)
    step *= max(1, 1024 // step)  # bigger blocks, still aligned to both chunkings
    t0 = time.time()
    for i in range(0, n, step):
        d[i:i + step] = s[i:i + step]
        if (i // step) % 20 == 0:
            print(f"rows {i}/{n} {time.time() - t0:.0f}s", flush=True)
    for i in np.random.default_rng(0).choice(n, 5, replace=False):
        assert np.array_equal(s[int(i)], d[int(i)], equal_nan=True), f"row {i} differs"
    os.rename(tmp, dst)
    print(f"done {dst} chunks=({r}, {m}) in {time.time() - t0:.0f}s; verified 5 rows")


if __name__ == "__main__":
    main()
