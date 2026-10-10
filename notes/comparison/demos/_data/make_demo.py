"""Shared demo dataset for the comparison tools: the paper's bone marrow store as h5ad.

Reads selected slots of data/bm_aging_showcase.zarr (8,090 cells x 16,285 genes) and writes
bm_demo.h5ad next to this script. Kept: X = layers/logged_counts (CSR; the store's own X is dense), counts, obs, var index, obsm (UMAP, PCA, diffusion,
force-directed), obsp kNN graph and the dense diffusion_distance matrix, so each tool can be
checked for whether it shows a stored cell x cell matrix. Also writes plain files for R tools
(X.mtx of log counts, obs.csv, var.csv, umap.csv, diffusion_distance_row_4236.csv).

Run: .venv/bin/python make_demo.py
"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scipy.io
import scipy.sparse as sp
import zarr
from anndata.io import read_elem

SRC = f"{_REPO}/data/bm_aging_showcase.zarr"
OUT = Path(__file__).parent

g = zarr.open_consolidated(SRC, mode="r")
# The store's X is MAGIC-like and fully dense; the tools expect sparse log-normalised data.
X = sp.csr_matrix(read_elem(g["layers"]["logged_counts"]), dtype=np.float32)
counts = sp.csr_matrix(read_elem(g["layers"]["raw_counts"]), dtype=np.float32)
obs = read_elem(g["obs"])
keep_obs = ["Age", "Sample", "Replicate", "Compartment", "highres_celltype", "midres_celltype",
            "leiden", "phase", "total_counts", "n_genes_by_counts", "pct_counts_mt",
            "kompot_da_Young_to_Old_lfc", "fig3_diffusion_dist_to_plasma"]
obs = obs[keep_obs]
var = pd.DataFrame(index=read_elem(g["var"]).index)
obsm = {k: np.asarray(read_elem(g["obsm"][k]), dtype=np.float32)
        for k in ["X_umap", "X_pca", "X_diffusion", "X_draw_graph_fa"]}
obsp = {k: read_elem(g["obsp"][k]) for k in ["connectivities", "distances", "diffusion_distance"]}
obsp["diffusion_distance"] = np.asarray(obsp["diffusion_distance"], dtype=np.float32)
uns = {k: read_elem(g["uns"][k]) for k in ["Age_colors", "Compartment_colors"] if k in g["uns"]}

a = ad.AnnData(X=X, obs=obs, var=var, obsm=obsm, obsp=obsp, uns=uns, layers={"counts": counts})
a.write_h5ad(OUT / "bm_demo.h5ad", compression="gzip")

# Plain files for R tools (iSEE, ShinyCell build an SCE / Seurat object from these).
scipy.io.mmwrite(OUT / "X.mtx", X.T.tocoo(), precision=4)  # genes x cells, as R expects
obs.to_csv(OUT / "obs.csv")
var.to_csv(OUT / "var.csv")
pd.DataFrame(obsm["X_umap"], index=obs.index, columns=["UMAP1", "UMAP2"]).to_csv(OUT / "umap.csv")
# One dense row of the stored cell x cell matrix: the focused monocyte (paper Fig. 3), for side-by-side checks.
pd.Series(obsp["diffusion_distance"][4236], index=obs.index,
          name="diffusion_distance_to_4236").to_csv(OUT / "diffusion_distance_row_4236.csv")
print(a)

# Sparse kNN graph as triplets (1-based, for SingleCellExperiment colPairs) and PCA for R tools.
knn = sp.coo_matrix(obsp["connectivities"])
pd.DataFrame({"i": knn.row + 1, "j": knn.col + 1, "x": knn.data}).to_csv(OUT / "knn_connectivities.csv", index=False)
pd.DataFrame(obsm["X_pca"][:, :20], index=obs.index).to_csv(OUT / "pca.csv")
