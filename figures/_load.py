"""Shared loader for the analysis figures (fig2-fig4).

Reads only what a figure needs from the demo store, lazily and by key, the way
AnnZarro itself does: one row of an obsp/varp matrix, one column of a layer.
Keys and example cells/genes come from data_prep/demo_panelsets/examples.json so
the figures and the shipped panel sets cannot drift apart.

Usage:
    from figures._load import Store
    s = Store()
    s.obs, s.var, s.umap, s.walk_row("HSPC_Old_1#..."), s.varp_row("spearman_fold_change", "H2-Q7")
"""

import json
import os
import sys
from functools import cached_property
from pathlib import Path

import anndata as ad
import numpy as np
import zarr

ROOT = Path(__file__).resolve().parent.parent
# The demo store: the AnnZarro showcase store from Zenodo 10.5281/zenodo.23277103 (data_prep/fetch_demo_store.py
# puts it in data/). ANNZARRO_DEMO_STORE names another copy of it, for a host that keeps it elsewhere.
STORE = Path(os.environ.get("ANNZARRO_DEMO_STORE") or ROOT / "data" / "bm_aging_annzarro.zarr")
EXAMPLES = json.loads((ROOT / "data_prep" / "demo_panelsets" / "examples.json").read_text())
KEYS = EXAMPLES["keys"]
CELLTYPE = EXAMPLES["celltype_column"]          # highres_celltype
HSC_CELL = EXAMPLES["cells"]["HSC"]["name"]      # HSPC_Old_1#GAAGCCCGTGGCTCTG-1
MONO_CELL = EXAMPLES["cells"]["Monocyte"]["name"]  # Mature_Young_2#TCAATTCAGTGAGGCT-1

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class Store:
    def __init__(self, path=STORE):
        self.g = zarr.open_group(str(path), mode="r")

    # --- annotations -------------------------------------------------------
    @cached_property
    def obs(self):
        return ad.io.read_elem(self.g["obs"])

    @cached_property
    def var(self):
        return ad.io.read_elem(self.g["var"])

    @cached_property
    def cell_index(self):
        return {c: i for i, c in enumerate(self.obs.index)}

    @cached_property
    def gene_index(self):
        return {c: i for i, c in enumerate(self.var.index)}

    def ci(self, cell):
        return self.cell_index[cell]

    def gi(self, gene):
        return self.gene_index[gene]

    # --- embeddings --------------------------------------------------------
    @cached_property
    def umap(self):
        return np.asarray(self.g["obsm/X_umap"][:], dtype=np.float64)

    @cached_property
    def dm_eigvecs(self):
        return np.asarray(self.g["obsm/DM_EigenVectors"][:], dtype=np.float64)

    @cached_property
    def dm_eigvals(self):
        return np.asarray(self.g["uns/DM_EigenValues"][:], dtype=np.float64)

    def multiscale_space(self, n_components=None):
        """Palantir's multiscale diffusion space.

        Drops the trivial first eigenvector and scales component k by
        lambda_k / (1 - lambda_k), i.e. the sum of lambda_k**t over all walk
        lengths t >= 1. Euclidean distance here is Palantir's multiscale
        diffusion distance. Palantir by default keeps the components up to the
        eigen-gap; we keep all 39 non-trivial ones stored unless told otherwise.
        """
        lam = self.dm_eigvals[1:]
        V = self.dm_eigvecs[:, 1:]
        if n_components is not None:
            lam, V = lam[:n_components], V[:, :n_components]
        return V * (lam / (1 - lam))

    # --- matrices: one row/column at a time --------------------------------
    def walk_row(self, cell, key=None):
        key = key or KEYS["WALK_KEY"]
        return np.asarray(self.g[f"obsp/{key}"][self.ci(cell), :], dtype=np.float64)

    @cached_property
    def walk(self):
        """Full dense walk matrix (8,090^2 float32, 262 MB)."""
        return np.asarray(self.g[f"obsp/{KEYS['WALK_KEY']}"][:])

    def varp_row(self, key, gene):
        return np.asarray(self.g[f"varp/{key}"][self.gi(gene), :], dtype=np.float64)

    def varp_block(self, key, genes_idx):
        """Square sub-matrix varp[key][genes, genes] for a gene index list."""
        genes_idx = np.asarray(genes_idx)
        rows = np.asarray(self.g[f"varp/{key}"].get_orthogonal_selection((genes_idx, slice(None))))
        return rows[:, genes_idx].astype(np.float64)

    def layer_col(self, key, gene):
        return np.asarray(self.g[f"layers/{key}"][:, self.gi(gene)], dtype=np.float64)

    def layer_row(self, key, cell):
        return np.asarray(self.g[f"layers/{key}"][self.ci(cell), :], dtype=np.float64)

    # --- convenience -------------------------------------------------------
    @property
    def lfc(self):
        return self.var[KEYS["LFC_KEY"]].to_numpy(dtype=float)

    @property
    def mahal(self):
        return self.var[KEYS["MAHAL_KEY"]].to_numpy(dtype=float)

    @property
    def is_de(self):
        return self.var[KEYS["IS_DE_KEY"]].to_numpy(dtype=bool)

    @property
    def celltype(self):
        return self.obs[CELLTYPE].astype(str).to_numpy()


# --- shared plotting helpers ----------------------------------------------------
NUMBERS_DIR = ROOT / "figures" / "numbers"


def write_numbers(name, numbers):
    """Dump every number a caption may quote to figures/numbers/<name>.json."""
    NUMBERS_DIR.mkdir(exist_ok=True)

    def conv(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)

    (NUMBERS_DIR / f"{name}.json").write_text(json.dumps(numbers, indent=1, default=conv))


def ring(ax, xy, size=28, color="#0b0b0b", lw=0.9, zorder=10):
    """Hollow ring marking a focused point (drawn on top of everything)."""
    xy = np.atleast_2d(xy)
    ax.scatter(xy[:, 0], xy[:, 1], s=size, facecolors="none", edgecolors="white",
               linewidths=lw + 1.0, zorder=zorder)
    ax.scatter(xy[:, 0], xy[:, 1], s=size, facecolors="none", edgecolors=color,
               linewidths=lw, zorder=zorder + 1)


def highlight(ax, x, y, color, s=4, zorder=5, label=None):
    """Highlighted points on top of the background, each with a thin white ring."""
    return ax.scatter(x, y, s=s, c=color, edgecolors="white", linewidths=0.5,
                      zorder=zorder, rasterized=True, label=label)
