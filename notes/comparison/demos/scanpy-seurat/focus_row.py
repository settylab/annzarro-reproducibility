import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import scanpy as sc, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
OUT = f"{_REPO}/notes/comparison/screens/scanpy-seurat/"
adata = sc.read_h5ad(f"{_DEMO_ROOT}/_data/bm_demo.h5ad")
i = 4236                                     # the focused cell: change this and re-run
print(adata.obs_names[i], type(adata.obsp["diffusion_distance"]))
row = adata.obsp["diffusion_distance"][i]
row = np.asarray(row.todense()).ravel() if hasattr(row, "todense") else np.asarray(row).ravel()
adata.obs["d"] = row                         # copy ONE relation row into obs
fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
sc.pl.umap(adata, color="d", ax=axes[0], show=False, title=f"diffusion distance to cell {i}")
sc.pl.embedding(adata, basis="X_draw_graph_fa", color="d", ax=axes[1], show=False, title="same row, force-directed")
for ax in axes:
    xy = adata.obsm["X_umap" if ax is axes[0] else "X_draw_graph_fa"][i]
    ax.scatter(*xy, s=120, facecolors="none", edgecolors="red", linewidths=2)
fig.tight_layout(); fig.savefig(OUT + "01_obsp_row_by_code.jpg", dpi=110, pil_kwargs={"quality": 80})
# Feature colouring, for contrast: a column of X
fig, ax = plt.subplots(figsize=(5.5, 4.6))
sc.pl.umap(adata, color="Mpo", ax=ax, show=False, title="Mpo expression (feature colouring)")
fig.tight_layout(); fig.savefig(OUT + "02_feature_colouring_Mpo.jpg", dpi=110, pil_kwargs={"quality": 80})
print("obsm", list(adata.obsm), "obsp", list(adata.obsp))
