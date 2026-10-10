"""The exact call cellxgene 1.3.0 makes for one gene when --backed (anndata_adaptor.get_X_array: X[slice(None), int array]),
on a CSR- and a CSC-encoded copy of the same matrix; peak traced allocation and time per gene (anndata 0.11.4)."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import json, os, time, tracemalloc
import anndata as ad, numpy as np
FILES = {"csr": os.path.expanduser(f"{_DEMO_ROOT}/_data/bm_demo.h5ad"),
         "csc": os.path.expanduser(f"{_DEMO_ROOT}/tissuumaps/data/bm_demo_csc.h5ad")}
out = {}
for enc, f in FILES.items():
    a = ad.read_h5ad(f, backed="r")
    X = a.X; nnz = X.group["data"].shape[0] if hasattr(X, "group") else None
    r = {"format": getattr(X, "format", type(X).__name__), "shape": list(a.shape), "nnz": nnz,
         "X_in_memory_MiB": round(nnz * (4 + 4) / 2**20 + a.shape[0 if enc == "csr" else 1] * 8 / 2**20, 1) if nnz else None}
    for g in ["Mpo", "Elane", "Cd74"]:
        j = np.array([a.var_names.get_loc(g)])
        tracemalloc.start(); t = time.time()
        col = X[slice(None), j]
        dt = time.time() - t; peak = tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
        r[g] = {"s": round(dt, 3), "peak_MiB": round(peak / 2**20, 1), "col_nnz": int(col.nnz)}
    out[enc] = r; a.file.close()
print(json.dumps(out, indent=1))
