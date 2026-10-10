#!/usr/bin/env python
"""Choose (and justify from the data) the example gene and cells for the protocol figures.

Gene: among the top-ranked DE genes (Mahalanobis) pick the one whose Spearman
neighbourhood (varp) is largest AND mostly DE itself, i.e. a "clear correlated module".
Cells: for HSC and Monocyte, the cell closest to the cell-type median in diffusion
space whose 5-step diffusion walk keeps the most mass inside its own cell type.

Writes data_prep/demo_panelsets/examples.json.
"""
import argparse
import json
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import zarr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="data/bm_aging.zarr")
    ap.add_argument("--report", default="data/prepare_report.json")
    ap.add_argument("--out", default="data_prep/demo_panelsets/examples.json")
    ap.add_argument("--celltype", default="highres_celltype")
    args = ap.parse_args()

    keys = json.load(open(args.report))["discovered"]
    keys["WALK_KEY"] = json.load(open(args.report))["walk"]["key"]
    a = ad.read_zarr(args.store)  # small enough; obs/var/obsm are what we use
    z = zarr.open_group(args.store, mode="r")
    C = z["varp/spearman_smoothed"]
    fc = z[f"layers/{keys['FC_KEY']}"]
    W = z[f"obsp/{keys['WALK_KEY']}"]
    var, obs = a.var, a.obs
    isde = var[keys["IS_DE_KEY"]].values.astype(bool)

    # ---- gene
    # Criterion: among the 10 top-ranked DE genes (Mahalanobis), maximise the number
    # of DE genes among the 5 nearest Spearman neighbours, summed over BOTH varp
    # matrices (smoothed expression and fold change). A gene scoring high has a module
    # that is (i) co-expressed across cell states and (ii) co-regulated with age, so
    # the volcano view lights up a coherent block of DE genes. Ties -> better DE rank.
    C2 = z["varp/spearman_fold_change"]
    top = var.sort_values(keys["MAHAL_KEY"], ascending=False).index[:10]
    scored = []
    for rank, g in enumerate(top, 1):
        i = a.var_names.get_loc(g)
        sc = 0
        for M in (C, C2):
            r = M[i, :]
            nb5 = [j for j in np.argsort(-r) if j != i][:5]
            sc += int(isde[nb5].sum())
        scored.append((sc, -rank, g, i))
    scored.sort(reverse=True)
    print("gene scores (DE among 5 NN, smoothed+FC; -rank; gene):", [(s_, r_, g_) for s_, r_, g_, _ in scored])
    _, neg_rank, g, gi = scored[0]
    gene = dict(name=g, index=int(gi), mahalanobis_rank=-neg_rank,
                mahalanobis=float(var[keys["MAHAL_KEY"]].iloc[gi]),
                mean_lfc=float(var[keys["LFC_KEY"]].iloc[gi]), selection_score=scored[0][0])
    for lab, M in (("smoothed", C), ("fold_change", C2)):
        r = M[gi, :]
        nb = [j for j in np.argsort(-r) if j != gi][:8]
        gene[f"top_correlated_{lab}"] = [dict(gene=a.var_names[j], rho=round(float(r[j]), 3), is_de=bool(isde[j]))
                                         for j in nb]
    ct = obs[args.celltype].astype(str).values
    fc_by_ct = pd.Series(fc[:, gi]).groupby(ct).mean().sort_values()
    gene["fold_change_by_celltype_top"] = fc_by_ct.tail(3).round(3).to_dict()
    gene["fold_change_by_celltype_bottom"] = fc_by_ct.head(3).round(3).to_dict()
    alt_name = top[0] if top[0] != g else top[1]
    alt = dict(name=alt_name, index=int(a.var_names.get_loc(alt_name)), mahalanobis_rank=int(list(top).index(alt_name) + 1))

    # ---- cells
    DM = a.obsm["DM_EigenVectors"][:, 1:11]
    cells = {}
    for t in ("HSC", "Monocyte"):
        idx = np.where(ct == t)[0]
        d = np.linalg.norm(DM[idx] - np.median(DM[idx], 0), axis=1)
        best = None
        for c in idx[np.argsort(d)[:15]]:
            row = W[int(c), :]
            frac = float(row[idx].sum() / row.sum())
            if best is None or frac > best[1]:
                best = (int(c), frac)
        c, frac = best
        cells[t] = dict(name=str(obs.index[c]), index=c, celltype=t, age=str(obs["Age"].iloc[c]),
                        da_zscore=round(float(obs[keys["DA_Z_KEY"]].iloc[c]), 2),
                        celltype_median_da_zscore=round(float(np.median(obs[keys["DA_Z_KEY"]].values[idx])), 2),
                        walk_mass_in_own_celltype=round(frac, 3),
                        fold_change_of_gene=round(float(fc[c, gi]), 3))
    out = dict(keys=keys, genes=dict(focus=gene,
                                     alternative=alt),
               cells=cells, celltype_column=args.celltype)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
