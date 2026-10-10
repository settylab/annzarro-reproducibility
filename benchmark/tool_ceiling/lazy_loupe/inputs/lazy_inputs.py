"""Two h5ad inputs for the Loupe lazy-read test, built from the SAME first N Tahoe-100M cells:
  g200:  the 200 panel genes of the ceiling ladder's input (the genes with stored values in tahoe_first<N>.h5ad)
  g2000: those 200 plus the most-detected other genes on these cells, 2,000 genes in all
Values are the raw counts from the laptop's 50M master CSR (benchmark/scale/NOTES.md); obs and obsm (X_umap) are
copied from the ladder's tahoe_first<N>.h5ad, so cells, order, cell lines and the UMAP are identical. Before writing,
the panel genes' values are checked equal to the ladder input's on the first 20,000 cells.
Both are then built into .cloupe by benchmark/tool_ceiling/loupe_build.R, unchanged (as the ladder did).
Usage: lazy_inputs.py N OUTDIR    (env DATA_ROOT, default ~/tahoe_scale; TC_DATA default ~/tool_ceiling_data)"""
import os, sys, time, json
from pathlib import Path
import numpy as np, h5py, zarr
N = int(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("DATA_ROOT", Path.home() / "tahoe_scale")); TC = Path(os.environ.get("TC_DATA", Path.home() / "tool_ceiling_data"))
SRC = TC / "h5ad" / f"tahoe_first{N}.h5ad"; M = zarr.open_group(str(DATA / "work50/master.zarr"), mode="r")
GENES = [l.rstrip("\n").split("\t") for l in open(OUT / "master_genes.tsv")][1:]   # gene_symbol, ensembl_id (master column order)
ens2col = {e: i for i, (_, e) in enumerate(GENES)}
CH = 100_000; t0 = time.time()
src = h5py.File(SRC, "r"); X = src["X"]
vidx = src["var"][src["var"].attrs["_index"]][:].astype(str); vens = src["var"]["ensembl_id"][:].astype(str) if "ensembl_id" in src["var"] else None
used = np.zeros(X.attrs["shape"][1], bool); used[np.unique(X["indices"][:])] = True
panel_ens = list(vens[used]); panel_cols = sorted(ens2col[e] for e in panel_ens)
print(f"panel genes with values: {len(panel_cols)}", flush=True)
ip = M["indptr"][: N + 1].astype(np.int64)
det = np.zeros(len(GENES), np.int64)
for a in range(0, N, CH):
    b = min(N, a + CH); det += np.bincount(M["indices"][ip[a]:ip[b]], minlength=len(GENES))
print(f"pass 1 (detection) {time.time() - t0:.0f} s", flush=True)
rest = [c for c in np.argsort(-det, kind="stable") if c not in set(panel_cols)]
g2000 = sorted(panel_cols + rest[: 2000 - len(panel_cols)])
sets = {"g200": panel_cols, "g2000": g2000}
# check: panel values equal the ladder input's on the first 20,000 cells
k = 20_000; si = X["indptr"][: k + 1]; sx = X["data"][: si[-1]]; sj = X["indices"][: si[-1]]
mi = M["indices"][ip[0]:ip[k]]; mx = M["data"][ip[0]:ip[k]]
col_of = {ens2col[e]: j for j, e in enumerate(vens)}
keep = np.isin(mi, panel_cols); rows = np.repeat(np.arange(k), np.diff(ip[: k + 1]))[keep]
a = sorted(zip(rows, [col_of[c] for c in mi[keep]], mx[keep])); b = sorted(zip(np.repeat(np.arange(k), np.diff(si)), sj, sx))
assert [(r, c, float(v)) for r, c, v in a] == [(r, c, float(v)) for r, c, v in b], "panel values differ from the ladder input"
print("check: panel values equal the ladder input on 20,000 cells", flush=True)
for name, cols in sets.items():
    remap = np.full(len(GENES), -1, np.int64); remap[cols] = np.arange(len(cols))
    path = OUT / f"tahoe_first{N}_{name}.h5ad"
    with h5py.File(path, "w") as f:
        f.attrs.update({"encoding-type": "anndata", "encoding-version": "0.1.0"})
        for g in ("obs", "obsm"): src.copy(src[g], f, g)
        if "uns" in src: src.copy(src["uns"], f, "uns")
        v = f.create_group("var"); v.attrs.update({"encoding-type": "dataframe", "encoding-version": "0.2.0", "_index": "_index", "column-order": np.array(["ensembl_id"], dtype=object)})
        sym = np.array([GENES[c][0] for c in cols], dtype=object); ens = np.array([GENES[c][1] for c in cols], dtype=object)
        for key, arr in (("_index", sym), ("ensembl_id", ens)):
            d = v.create_dataset(key, data=arr, dtype=h5py.string_dtype()); d.attrs.update({"encoding-type": "string-array", "encoding-version": "0.2.0"})
        x = f.create_group("X"); x.attrs.update({"encoding-type": "csr_matrix", "encoding-version": "0.1.0", "shape": np.array([N, len(cols)])})
        dd = x.create_dataset("data", (0,), np.float32, maxshape=(None,), chunks=(1 << 20,))
        di = x.create_dataset("indices", (0,), np.int32, maxshape=(None,), chunks=(1 << 20,))
        ptr = np.zeros(N + 1, np.int64); n = 0
        for a in range(0, N, CH):
            b = min(N, a + CH); mi = M["indices"][ip[a]:ip[b]]; mx = M["data"][ip[a]:ip[b]]
            nc = remap[mi]; keep = nc >= 0; r = np.repeat(np.arange(b - a), np.diff(ip[a:b + 1]))[keep]
            order = np.lexsort((nc[keep], r)); cj = nc[keep][order].astype(np.int32); cx = mx[keep][order].astype(np.float32)
            ptr[a + 1:b + 1] = n + np.cumsum(np.bincount(r, minlength=b - a))
            dd.resize((n + len(cx),)); di.resize((n + len(cj),)); dd[n:] = cx; di[n:] = cj; n += len(cx)
        x.create_dataset("indptr", data=ptr)
    meta = {"n_cells": N, "n_genes": len(cols), "nnz": int(n), "values_per_cell": round(n / N, 1), "source": "work50/master.zarr rows 0..N-1; obs/obsm from " + SRC.name,
            "panel_genes": len(panel_cols), "seconds": round(time.time() - t0)}
    (OUT / f"tahoe_first{N}_{name}.h5ad.build.json").write_text(json.dumps(meta, indent=1)); print(name, meta, flush=True)
