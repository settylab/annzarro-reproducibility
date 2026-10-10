#!/usr/bin/env python
"""Direct-zarr read latency for one row / one column of the fold-change layer and
one row of varp under different chunk shapes (justifies Step 10's (1024, 1024))."""
import json, shutil, statistics, sys, time
from pathlib import Path
import numpy as np, zarr

src = zarr.open_group("data/bm_aging.zarr", mode="r")
FC = src["layers/kompot_de_Young_to_Old_fold_change"][:]
VP = src["varp/spearman_smoothed"][:]
tmp = Path("data/_chunkbench"); shutil.rmtree(tmp, ignore_errors=True)
rng = np.random.default_rng(0)
res = []
for ch in [(1024, 1024), (256, 256), (4096, 4096), (64, 16285), (8090, 64), (8090, 16285)]:
    out = {}
    for name, A in (("fc", FC), ("varp", VP)):
        c = (min(ch[0], A.shape[0]), min(ch[1], A.shape[1]))
        z = zarr.create_array(store=str(tmp / f"{name}_{c[0]}x{c[1]}"), shape=A.shape, chunks=c,
                              dtype="f4", zarr_format=2)
        z[:] = A
        size = sum(f.stat().st_size for f in (tmp / f"{name}_{c[0]}x{c[1]}").rglob("*") if f.is_file())
        def t(fn, n=15):
            xs = []
            for _ in range(n):
                t0 = time.perf_counter(); fn(); xs.append((time.perf_counter() - t0) * 1000)
            return round(statistics.median(xs), 2)
        z2 = zarr.open_array(str(tmp / f"{name}_{c[0]}x{c[1]}"), mode="r")
        if name == "fc":
            out["fc_col_ms"] = t(lambda: z2[:, int(rng.integers(A.shape[1]))])
            out["fc_row_ms"] = t(lambda: z2[int(rng.integers(A.shape[0])), :])
            out["fc_MB"] = round(size / 1e6, 1); out["fc_chunks"] = c
        else:
            out["varp_row_ms"] = t(lambda: z2[int(rng.integers(A.shape[0])), :])
            out["varp_MB"] = round(size / 1e6, 1)
    out["chunks"] = ch
    print(json.dumps(out), flush=True); res.append(out)
shutil.rmtree(tmp)
json.dump(res, open("data/chunk_benchmark.json", "w"), indent=1)
