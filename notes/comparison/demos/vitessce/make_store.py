"""AnnData zarr (format 2) plus a Vitessce view config for the shared bone marrow demo.

Vitessce reads X per gene from a dense, column-chunked array, so X is written dense with
chunks (n_obs, 10), as vitessce-python's optimize_adata does. obsp is kept, to check whether
Vitessce offers it anywhere in the GUI.
"""
import json
from pathlib import Path

import anndata as ad
import numpy as np

HERE = Path(__file__).parent
URL = "http://127.0.0.1:8904"
a = ad.read_h5ad(HERE / "../_data/bm_demo.h5ad")
del a.layers["counts"]
a.X = np.asarray(a.X.todense(), dtype=np.float32)
ad.settings.zarr_write_format = 2
a.write_zarr(HERE / "store/bm_demo.zarr", chunks=(a.n_obs, 10))

files = [{"fileType": "anndata.zarr", "url": f"{URL}/bm_demo.zarr", "options": {
    "obsEmbedding": [{"path": "obsm/X_umap", "embeddingType": "UMAP", "dims": [0, 1]},
                     {"path": "obsm/X_draw_graph_fa", "embeddingType": "FA", "dims": [0, 1]}],
    "obsSets": [{"name": "Cell type", "path": "obs/highres_celltype"},
                {"name": "Age", "path": "obs/Age"}, {"name": "Sample", "path": "obs/Sample"}],
    "obsFeatureMatrix": {"path": "X"}}}]
config = {
    "version": "1.0.16", "name": "Vitessce: bone marrow demo (annzarro_compare)",
    "description": "8,090 cells x 16,285 genes; the AnnZarro paper's bone marrow demo.",
    "datasets": [{"uid": "bm", "name": "bone marrow", "files": files}],
    "coordinationSpace": {"embeddingType": {"A": "UMAP", "B": "FA"}},
    "layout": [
        {"component": "scatterplot", "coordinationScopes": {"embeddingType": "A"}, "x": 0, "y": 0, "w": 5, "h": 6},
        {"component": "scatterplot", "coordinationScopes": {"embeddingType": "B"}, "x": 5, "y": 0, "w": 4, "h": 6},
        {"component": "obsSets", "x": 9, "y": 0, "w": 3, "h": 3},
        {"component": "featureList", "x": 9, "y": 3, "w": 3, "h": 3},
        {"component": "heatmap", "x": 0, "y": 6, "w": 12, "h": 4},
    ],
    "initStrategy": "auto",
}
(HERE / "store/config.json").write_text(json.dumps(config, indent=1))
print(a)
