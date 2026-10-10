"""Scanpy matrix marks shown by code (no GUI). Run with .venv/bin/python.
Each block writes screens/scanpy-seurat/mNN_*.jpg and prints what it observed. Seurat is not installed
on this laptop (requireNamespace("Seurat") is FALSE in both R installs), so nothing here runs Seurat.
Remote read needs fsspec/aiohttp/xarray/dask, which are not in the paper venv; they were put in a scratch
--target dir (EXTRA below) and appended to sys.path so the venv's own numpy/pandas keep precedence."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import sys, os, io, time, json, hashlib, resource, warnings
EXTRA = f"{_SCRATCH}/pyextra"
S = f"{_SCRATCH}/scanpy_matrix"
OUT = f"{_REPO}/notes/comparison/screens/scanpy-seurat/"
os.makedirs(S, exist_ok=True)
sys.path.append(EXTRA)  # before anndata is imported, so its optional xarray/dask backends register
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import scanpy as sc, anndata as ad
from PIL import Image
BM = f"{_DEMO_ROOT}/_data/bm_demo.h5ad"
SPD = f"{_REPO}/data/spatial_demo.zarr"
LYMPH = f"{_DEMO_ROOT}/cirrocumulus/lymph/"
def rss(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20  # MB on macOS
def save(fig, name):
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=90, bbox_inches="tight"); plt.close(fig)
    Image.open(buf).convert("RGB").save(OUT + name, quality=70); print("saved", name)
step = sys.argv[1] if len(sys.argv) > 1 else "all"
print("scanpy", sc.__version__, "anndata", ad.__version__)

# ---- column 5: lazy (backed) read first, before anything is in memory ----
r0 = rss(); t = time.time()
ab = sc.read_h5ad(BM, backed="r")
print(f"m05 backed: X is {type(ab.X).__name__}, shape {ab.shape}, open {time.time()-t:.2f}s, maxrss {r0:.0f}->{rss():.0f} MB")
g = ab[:, "Mpo"].X; print("m05 one gene from backed X:", type(g).__name__, g.shape, f"maxrss {rss():.0f} MB")
ab.file.close()

# ---- full load for the rest ----
a = sc.read_h5ad(BM); print("loaded in memory, maxrss", round(rss()), "MB")

# m00 plots render
fig, ax = plt.subplots(figsize=(7, 5.5)); sc.pl.umap(a, color="highres_celltype", ax=ax, show=False, legend_fontsize=6); save(fig, "m00_plots_render_umap.jpg")

# m04 all slots: obsm, layers, obsp in one figure, all through code
fig, axs = plt.subplots(1, 3, figsize=(16, 4.6))
sc.pl.embedding(a, basis="X_draw_graph_fa", color="Compartment", ax=axs[0], show=False, title="obsm['X_draw_graph_fa']")
sc.pl.umap(a, color="Mpo", layer="counts", ax=axs[1], show=False, title="layers['counts'], gene Mpo")
row = a.obsp["connectivities"][4236]; a.obs["knn_4236"] = np.asarray(row.todense()).ravel() if hasattr(row, "todense") else np.asarray(row).ravel()
sc.pl.umap(a, color="knn_4236", ax=axs[2], show=False, title="obsp['connectivities'] row 4236", cmap="viridis")
save(fig, "m04_slots_obsm_layers_obsp_by_code.jpg")
print("m04 slots:", {k: list(getattr(a, k).keys()) for k in ["obsm", "layers", "obsp", "varm", "varp", "uns"]})

# m02 gene x gene (varp) as an axis: spatial_demo has varp['spearman_hvg']
s = ad.read_zarr(SPD); gi = list(s.var_names).index("Mbp") if "Mbp" in s.var_names else 0
rowg = pd.Series(np.asarray(s.varp["spearman_hvg"][gi]).ravel(), index=s.var_names).drop(s.var_names[gi]).sort_values()
top = pd.concat([rowg.head(8), rowg.tail(12)])
fig, ax = plt.subplots(figsize=(6, 5.5)); ax.barh(top.index, top.values, color=["#b2182b" if v > 0 else "#2166ac" for v in top.values])
ax.set_xlabel(f"Spearman to {s.var_names[gi]} (varp['spearman_hvg'] row {gi})"); ax.set_title("gene x gene row as an axis, by code")
save(fig, "m02_varp_row_as_axis.jpg"); print("m02 focus gene", s.var_names[gi], "top +:", list(rowg.tail(3).index))

# m08 filter by code: subset, then plot
mask = a.obs["highres_celltype"].astype(str).str.contains("Neutrophil")
fig, axs = plt.subplots(1, 2, figsize=(12, 4.8))
sc.pl.umap(a, color="highres_celltype", ax=axs[0], show=False, legend_loc=None, title=f"all {a.n_obs} cells")
sc.pl.umap(a[mask], color="highres_celltype", ax=axs[1], show=False, legend_loc=None, title=f"adata[obs.highres_celltype == 'Neutrophil'] ({int(mask.sum())} cells)")
for ax in axs: ax.set_xlim(axs[0].get_xlim()); ax.set_ylim(axs[0].get_ylim())
save(fig, "m08_filter_by_code.jpg")

# m09 annotation by code: label a UMAP rectangle, write, read back
u = a.obsm["X_umap"]; x0, x1 = np.percentile(u[:, 0], [5, 35]); y0, y1 = np.percentile(u[:, 1], [40, 90])
inside = (u[:, 0] > x0) & (u[:, 0] < x1) & (u[:, 1] > y0) & (u[:, 1] < y1)
a.obs["my_label"] = pd.Categorical(np.where(inside, "my_region", "other"))
small = ad.AnnData(obs=a.obs[["my_label"]].copy()); f = f"{S}/labels_only.h5ad"; small.write_h5ad(f)
back = ad.read_h5ad(f).obs["my_label"].value_counts().to_dict(); print("m09 written+read back:", back, os.path.getsize(f), "bytes")
fig, ax = plt.subplots(figsize=(6.5, 5)); sc.pl.umap(a, color="my_label", ax=ax, show=False, title="obs['my_label'] set by code, saved, re-read")
save(fig, "m09_annotation_by_code.jpg")

# m10 DE on the labelled set vs rest
t = time.time(); sc.tl.rank_genes_groups(a, "my_label", groups=["my_region"], reference="other", method="wilcoxon")
print(f"m10 rank_genes_groups wilcoxon {time.time()-t:.1f}s top:", list(pd.DataFrame(a.uns["rank_genes_groups"]["names"])["my_region"][:5]))
sc.pl.rank_genes_groups(a, n_genes=15, show=False); save(plt.gcf(), "m10_rank_genes_groups_by_code.jpg")

# m07 + m11 spatial coordinates and image underlay (V1_Human_Lymph_Node + its 10x spatial folder)
L = sc.read_h5ad(LYMPH + "V1_Human_Lymph_Node.h5ad")
pos = pd.read_csv(LYMPH + "spatial/tissue_positions_list.csv", header=None, index_col=0)
L.obsm["spatial"] = pos.loc[L.obs_names, [5, 4]].to_numpy().astype(float)  # pxl_col, pxl_row (full res)
sf = json.load(open(LYMPH + "spatial/scalefactors_json.json"))
L.uns["spatial"] = {"V1_Human_Lymph_Node": {"images": {"hires": plt.imread(LYMPH + "spatial/tissue_hires_image.png")}, "scalefactors": sf}}
fig, axs = plt.subplots(1, 2, figsize=(13, 6))
sc.pl.spatial(L, color="clusters", img_key=None, ax=axs[0], show=False, title="spatial coordinates only (img_key=None)", spot_size=sf["spot_diameter_fullres"])
sc.pl.spatial(L, color="clusters", img_key="hires", ax=axs[1], show=False, title="img_key='hires': H&E underlay", alpha_img=1.0)
save(fig, "m07_m11_spatial_and_image_underlay.jpg")

# m13 export: savefig to PDF and PNG; scanpy's own save= is deprecated
fig, ax = plt.subplots(figsize=(6, 5)); sc.pl.umap(a, color="Compartment", ax=ax, show=False)
for ext in ["pdf", "png"]:
    p = f"{S}/umap_compartment.{ext}"; fig.savefig(p, bbox_inches="tight"); print("m13 export:", os.path.basename(p), os.path.getsize(p), "bytes")
plt.close(fig)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always"); sc.settings.figdir = S
    sc.pl.umap(a, color="Compartment", save="_compartment.png", show=False)
    print("m13 save= warnings:", [str(x.message)[:120] for x in w if "save" in str(x.message).lower()][:1], "| file:", sorted(f for f in os.listdir(S) if "compartment" in f))
plt.close("all")

# m12 shareable state = the script: two runs of the same plotting code give byte-identical PNGs
def draw():
    fig, ax = plt.subplots(figsize=(5, 4)); sc.pl.umap(a, color="Compartment", ax=ax, show=False)
    b = io.BytesIO(); fig.savefig(b, format="png", metadata={"Software": None}); plt.close(fig); return hashlib.md5(b.getvalue()).hexdigest()
print("m12 same code twice -> same PNG md5:", draw() == draw())

# m06 remote: anndata read_lazy over HTTP (the anndata tutorial's public GCS Zarr)
try:
    import zarr, fsspec, aiohttp
    from zarr.storage import FsspecStore
    url = "https://vitessce-demo-data.storage.googleapis.com/anndata-demos/BALF_VIB-UGent_processed_cleaned.zarr/"
    t = time.time(); store = FsspecStore.from_url(url, read_only=True)
    lz = ad.experimental.read_lazy(store)
    print(f"m06 read_lazy remote: {lz.n_obs} x {lz.n_vars} in {time.time()-t:.1f}s, X is {type(lz.X).__name__}")
    t = time.time(); col = lz[:, lz.var_names[0]].X
    col = col.compute() if hasattr(col, "compute") else col
    print(f"m06 one gene fetched over HTTP in {time.time()-t:.1f}s, shape {col.shape}")
except Exception as e:
    print("m06 remote failed:", type(e).__name__, str(e)[:200])
print("done, maxrss", round(rss()), "MB")
