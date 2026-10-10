"""AnnData remote-store check (the code path behind the Scanpy/Seurat row's remote-stores P).

Opens public, anonymous AnnData zarr stores on S3 and GCS lazily with anndata.experimental.read_lazy
and reads one gene column, timing each step. Run with $DEMO_ROOT/scanpy-seurat/.venv-remote.
"""
import time

import anndata as ad
import zarr
from zarr.storage import FsspecStore

STORES = ["s3://lamindata/.lamindb/CFcQxNjzSRzWZrVh.anndata.zarr",
          "gs://vitessce-demo-data/habib-2017/habib17.processed.h5ad.zarr"]
for url in STORES:
    t = time.time()
    store = FsspecStore.from_url(url, storage_options={"anon": True} if url.startswith("s3") else {"token": "anon"}, read_only=True)
    a = ad.experimental.read_lazy(zarr.open_group(store, mode="r"))
    t1 = time.time() - t
    g = a.var_names[0]
    col = a[:, g].X
    col = col.compute() if hasattr(col, "compute") else col
    print(f"{url}: {a.n_obs} x {a.n_vars}, lazy open {t1:.1f} s, one gene ({g}) {time.time() - t - t1:.1f} s, "
          f"obsm={list(a.obsm.keys())[:3]}, versions anndata {ad.__version__} zarr {zarr.__version__}")
