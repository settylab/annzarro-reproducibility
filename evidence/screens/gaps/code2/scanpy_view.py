# view.py: the whole "view state" of a Scanpy figure is this script
import os, sys, matplotlib; matplotlib.use("Agg")
import scanpy as sc, matplotlib.pyplot as plt
adata = sc.read_h5ad(os.path.join(os.environ["DEMO_DATA"], "bm_demo.h5ad"))
fig, ax = plt.subplots(figsize=(5, 4))
sc.pl.umap(adata, color="Mpo", ax=ax, show=False)
fig.savefig(sys.argv[1], metadata={"Software": None})
