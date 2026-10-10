#!/usr/bin/env python
"""Add obsp/expression_walk_t5 to the AnnZarro v0.4.1 spatial demo store.

Fig. 1d (fig:overview, panel d) colors the tissue section by a spot's row of
obsp/expression_walk_t5. AnnZarro v0.4.1's docs/_tools/make_spatial_demo.py, which builds
spatial_demo.zarr (10x Visium anterior sagittal mouse brain, CC BY 4.0), does not write
that key, so this script adds it to a store built by that release:

    W = T^5,  T = the row-normalized obsp/connectivities (the expression kNN graph)

computed in float64 and stored as float32, with whole-row chunks (as obsp/spatial_kernel),
then the metadata is consolidated again. It is the same computation, in the same order, as
the builder change that adds the key (annzarro branch dominik/spatial-expression-walk), and
the result matches that builder's array bit for bit.

Run (any env with anndata, zarr, numpy, scipy):
    python figures/spatial/add_expression_walk.py data/spatial_demo.zarr
"""
import argparse
import json

import anndata as ad
import numpy as np
import scipy.sparse as sp
import zarr

STEPS = 5
TARGET = 5e5            # values per chunk, as make_spatial_demo.py's row_chunks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("store", help="spatial_demo.zarr built by AnnZarro v0.4.1 (modified in place)")
    args = ap.parse_args()
    ad.settings.zarr_write_format = 2
    g = zarr.open_group(args.store, mode="r+", use_consolidated=False)
    G = sp.csr_matrix(ad.io.read_elem(g["obsp/connectivities"]), dtype=np.float64)
    T = (sp.diags(1.0 / np.asarray(G.sum(1)).ravel()) @ G).toarray()
    W = np.linalg.matrix_power(T, STEPS).astype(np.float32)
    n = W.shape[0]
    chunks = (max(1, min(n, int(round(TARGET / n)))), n)
    ad.io.write_elem(g["obsp"], f"expression_walk_t{STEPS}", W, dataset_kwargs={"chunks": chunks})
    zarr.consolidate_metadata(args.store)
    print(json.dumps({"key": f"obsp/expression_walk_t{STEPS}", "shape": list(W.shape), "chunks": list(chunks),
                      "n_eff_median": float(np.median(1 / (W.astype(np.float64) ** 2).sum(1)))}))


if __name__ == "__main__":
    main()
