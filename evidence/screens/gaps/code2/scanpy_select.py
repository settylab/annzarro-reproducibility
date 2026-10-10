# select.py: in Scanpy a "selection" is a boolean mask typed in code; every other plot has to be redrawn by hand to show it
import os, sys, numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg")
import scanpy as sc, matplotlib.pyplot as plt
adata = sc.read_h5ad(os.path.join(os.environ["DEMO_DATA"], "bm_demo.h5ad"))
u = adata.obsm["X_umap"]
cut = np.quantile(u[:, 0], 0.85)
mask = u[:, 0] > cut                      # the "lasso": a gate on UMAP_1, written as code
adata.obs["selection"] = pd.Categorical(np.where(mask, "selected", "other"))
print(f"selected {mask.sum():,} of {adata.n_obs:,} cells (UMAP_1 > {cut:.2f})")
print("selected cells by midres_celltype:")
print(adata.obs.loc[mask, "midres_celltype"].value_counts().head(4).to_string())
fig, axs = plt.subplots(1, 2, figsize=(9, 4))
for ax, basis in zip(axs, ["umap", "draw_graph_fa"]):  # re-plot each view with the mask
    sc.pl.embedding(adata, basis=basis, color="selection", groups=["selected"],
                    palette={"selected": "#d62728", "other": "#bbbbbb"}, ax=ax, show=False, title=f"X_{basis}")
fig.savefig(sys.argv[1], metadata={"Software": None}, bbox_inches="tight")
print("the same cells highlighted in X_umap and X_draw_graph_fa ->", sys.argv[1])
