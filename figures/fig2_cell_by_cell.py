"""fig:cellcell: a focused cell's row of a cell x cell matrix, and why the UMAP is no substitute.

    .venv/bin/python figures/fig2_cell_by_cell.py

(a) Rows of obsp/diffusion_walk_t5 (T^5, T = row-normalised DM_Kernel) for four
    cells on the HSC -> monocyte trajectory, painted on obsm/X_umap.
    Trajectory: shortest path from the example HSC to the example monocyte on the
    DM_Kernel graph, edges weighted by Palantir's multiscale diffusion distance
    (Euclidean in DM_EigenVectors[:, 1:] * lambda / (1 - lambda)). The two
    intermediates are the path cells closest to 1/3 and 2/3 of the path length,
    i.e. evenly spaced in diffusion pseudo-distance from the HSC.
(b) For one focused cell, UMAP Euclidean distance vs multiscale diffusion distance
    to every other cell. Discordant groups are defined on per-axis rank
    percentiles: "near" = among the focus's 5 % nearest cells by that metric,
    "far" = outside its 20 % nearest. The focus is chosen objectively (see
    choose_focus): the cell whose two discordant groups are jointly largest
    (max of min(|A|, |B|)) across the dataset.
(c) X_umap with the two groups marked.
(d) A connectome as a cell x cell matrix: C. elegans neuron classes (CeNGEN
    transcriptomes, UMAP of log TPM) coloured by the focused class's row of
    obsp/chemical_synapses (synapses it sends; Varshney et al. 2011), strongest on top. Store built by
    data_prep/neuro_demo.py into data/neuro_demo/.

Writes manuscript/figures/fig2_cell_by_cell.{pdf,png} and figures/numbers/fig2.json.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anndata as ad  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import scipy.sparse as sp  # noqa: E402
from matplotlib.colors import LogNorm  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402
from scipy.spatial.distance import cdist  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from figures._load import HSC_CELL, KEYS, MONO_CELL, Store, highlight, ring, write_numbers  # noqa: E402
from figures.style import (CAT, INK, MUTED, NEUTRAL, SECONDARY, SEQ, TWO_COL, apply,  # noqa: E402
                           embedding_axes, panel_label, save)

NEURO = Path(__file__).resolve().parent.parent / "data" / "neuro_demo" / "celegans_connectome_cengen.zarr"
NEURO_FOCUS = "AVA"             # command interneuron for backward locomotion
NEAR, FAR = 0.05, 0.20          # rank-percentile thresholds for the discordant groups
WALK_FLOOR = 1e-5               # walk probability below which a cell is drawn NEUTRAL
C_A, C_B = CAT[1], CAT[0]       # A: near in UMAP / far in diffusion; B: the reverse


def pow10(v, _pos=None):
    """A log colour bar's tick as plain decimal text (0.001, 100), not mathtext, whose exponent prints below 7 pt."""
    e = int(round(np.log10(v)))
    if not np.isclose(v, 10.0 ** e):
        return f"{v:g}"
    return f"{10 ** e:,}" if e >= 0 else f"{10.0 ** e:.{-e}f}"


def trajectory_cells(s, M):
    """HSC -> monocyte geodesic in multiscale diffusion space; return 4 cells."""
    K = ad.io.read_elem(s.g["obsp/DM_Kernel"]).tocoo()
    w = np.linalg.norm(M[K.row] - M[K.col], axis=1)
    G = sp.csr_matrix((w, (K.row, K.col)), shape=K.shape)
    h, m = s.ci(HSC_CELL), s.ci(MONO_CELL)
    dist, pred = dijkstra(G, directed=False, indices=h, return_predecessors=True)
    path = [m]
    while path[-1] != h:
        path.append(pred[path[-1]])
    path = np.array(path[::-1])
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(M[path], axis=0), axis=1))]
    frac = arc / arc[-1]
    picks = [path[0], path[np.argmin(abs(frac - 1 / 3))], path[np.argmin(abs(frac - 2 / 3))], path[-1]]
    return path, frac, picks


def rank_pct(D):
    """Row-wise rank percentiles (0 = the cell itself)."""
    return (np.argsort(np.argsort(D, axis=1), axis=1) / D.shape[1]).astype(np.float32)


def main():
    apply()
    s = Store()
    ct = s.celltype
    names = s.obs.index.to_numpy()
    U = s.umap
    M = s.multiscale_space()
    W = s.walk
    n = len(ct)
    nums = {"walk_key": KEYS["WALK_KEY"], "n_cells": n,
            "diffusion_space": "DM_EigenVectors[:,1:40] * l/(1-l) (Palantir multiscale, 39 comps)"}

    # ---------------- trajectory and panel (a) data
    path, frac, picks = trajectory_cells(s, M)
    nums["trajectory"] = [{"cell": names[i], "celltype": ct[i], "path_fraction": round(float(frac[list(path).index(i)]), 3)}
                          for i in picks]
    nums["trajectory_path_celltypes"] = [ct[i] for i in path]
    rows = [W[i].astype(np.float64) for i in picks]
    vmax = max(r.max() for r in rows)
    for i, r in zip(picks, rows):
        d = nums["trajectory"][picks.index(i)]
        d["walk_max"] = float(r.max())
        d["n_eff"] = float(1 / (r ** 2).sum())
        d["n_cells_above_floor"] = int((r >= WALK_FLOOR).sum())
        d["mass_below_floor"] = float(r[r < WALK_FLOOR].sum())
        d["mass_in_own_celltype"] = float(r[ct == ct[i]].sum())

    # ---------------- dataset-wide UMAP vs diffusion agreement
    DU = cdist(U, U).astype(np.float32)
    DM = cdist(M, M).astype(np.float32)
    RU, RM = rank_pct(DU), rank_pct(DM)
    # per-cell Spearman = Pearson of rank rows
    ru = RU - RU.mean(1, keepdims=True); rm = RM - RM.mean(1, keepdims=True)
    rho_all = (ru * rm).sum(1) / np.sqrt((ru ** 2).sum(1) * (rm ** 2).sum(1))
    del ru, rm
    k = 30
    nnU = np.argsort(DU, axis=1)[:, 1:k + 1]; nnM = np.argsort(DM, axis=1)[:, 1:k + 1]
    jac = np.array([len(set(a) & set(b)) / len(set(a) | set(b)) for a, b in zip(nnU, nnM)])
    Am = (RU < NEAR) & (RM > FAR)
    Bm = (RM < NEAR) & (RU > FAR)
    nA, nB = Am.sum(1), Bm.sum(1)
    nums["dataset"] = {
        "spearman_umap_vs_diffusion_per_cell_median": float(np.median(rho_all)),
        "spearman_per_cell_IQR": np.percentile(rho_all, [25, 75]).round(3).tolist(),
        "knn30_jaccard_median": float(np.median(jac)),
        "knn30_jaccard_IQR": np.percentile(jac, [25, 75]).round(3).tolist(),
        "knn30_shared_neighbours_median": float(np.median([len(set(a) & set(b)) for a, b in zip(nnU, nnM)])),
        "frac_cells_with_groupA": float((nA > 0).mean()),
        "frac_cells_with_groupB": float((nB > 0).mean()),
        "n_cells_both_groups_ge15": int(((nA >= 15) & (nB >= 15)).sum()),
        "both_groups_ge15_by_celltype": pd.Series(ct[(nA >= 15) & (nB >= 15)]).value_counts().to_dict(),
        "celltype_sizes": pd.Series(ct).value_counts().to_dict(),
    }
    wA, wB = (W * Am).sum(1), (W * Bm).sum(1)
    by_ct = pd.DataFrame({"ct": ct, "nA": nA, "nB": nB, "wA": wA, "wB": wB}).groupby("ct").median()
    nums["dataset"]["median_by_celltype"] = by_ct.round(4).to_dict(orient="index")
    for i in picks:
        nums["trajectory"][picks.index(i)].update(
            spearman_umap_vs_diffusion=float(rho_all[i]), knn30_jaccard=float(jac[i]),
            nA=int(nA[i]), nB=int(nB[i]))

    # ---------------- focus for (b, c)
    # Cell type whose cells most consistently have BOTH discordant groups (median
    # over its cells of min(|A|, |B|); types with >= 10 cells), then the cell of
    # that type whose min(|A|, |B|) is closest to the type median (a typical
    # member, not the extreme one).
    mn = np.minimum(nA, nB)
    sizes = pd.Series(ct).value_counts()
    type_score = pd.Series(mn).groupby(ct).median()[sizes[sizes >= 10].index].sort_values(ascending=False)
    best_type = type_score.index[0]
    members = np.where(ct == best_type)[0]
    f = int(members[np.argmin(np.abs(mn[members] - np.median(mn[members])))])
    nums["focus_selection"] = {"type_score_median_min_AB": type_score.head(6).to_dict(),
                               "chosen_type": best_type, "single_cell_argmax": names[int(np.argmax(mn))],
                               "single_cell_argmax_type": ct[int(np.argmax(mn))]}
    du, dm = DU[f].astype(float), DM[f].astype(float)
    A, B = Am[f], Bm[f]
    rho_f = spearmanr(du, dm)[0]
    nums["focus_bc"] = {
        "cell": names[f], "celltype": ct[f], "index": f,
        "spearman_umap_vs_diffusion": float(rho_f),
        "knn30_jaccard": float(jac[f]),
        "nA_near_umap_far_diffusion": int(A.sum()), "A_celltypes": pd.Series(ct[A]).value_counts().to_dict(),
        "nB_far_umap_near_diffusion": int(B.sum()), "B_celltypes": pd.Series(ct[B]).value_counts().to_dict(),
        "walk_mass_on_A": float(W[f][A].sum()), "walk_mass_on_B": float(W[f][B].sum()),
        "walk_mass_on_umap_near5pct": float(W[f][RU[f] < NEAR].sum()),
        "walk_mass_on_diffusion_near5pct": float(W[f][RM[f] < NEAR].sum()),
        "same_celltype_all_cells": {
            "n": int((ct == ct[f]).sum()),
            "n_with_both_groups_ge15": int(((nA >= 15) & (nB >= 15))[ct == ct[f]].sum()),
            "median_walk_mass_A": float(np.median(wA[ct == ct[f]])),
            "median_walk_mass_B": float(np.median(wB[ct == ct[f]])),
        },
        "umap_dist_thresholds": [float(np.quantile(du, NEAR)), float(np.quantile(du, FAR))],
        "diffusion_dist_thresholds": [float(np.quantile(dm, NEAR)), float(np.quantile(dm, FAR))],
    }
    # the HSC example, for the notes
    h = s.ci(HSC_CELL)
    nums["hsc_example"] = {"spearman": float(rho_all[h]), "knn30_jaccard": float(jac[h]),
                           "nA": int(nA[h]), "nB": int(nB[h]),
                           "A_celltypes": pd.Series(ct[Am[h]]).value_counts().to_dict()}
    del DU, DM, RU, RM

    # ================= layout
    fig = plt.figure(figsize=(TWO_COL, 4.55))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.42], hspace=0.28)
    gtop = gs[0].subgridspec(1, 5, width_ratios=[1, 1, 1, 1, 0.05], wspace=0.06)
    gbot = gs[1].subgridspec(1, 4, width_ratios=[1.0, 0.86, 0.62, 0.025], wspace=0.16)

    # ---------------- (a)
    norm = LogNorm(vmin=WALK_FLOOR, vmax=vmax)
    titles = ["HSC (start)", "LMPP (1/3 of path)", "GMP (2/3 of path)", "Monocyte (end)"]
    for j, (i, r) in enumerate(zip(picks, rows)):
        ax = fig.add_subplot(gtop[j])
        bg = r < WALK_FLOOR
        ax.scatter(U[bg, 0], U[bg, 1], s=0.6, c=NEUTRAL, linewidths=0, rasterized=True)
        o = np.where(~bg)[0]
        o = o[np.argsort(r[o])]
        sc = ax.scatter(U[o, 0], U[o, 1], s=0.9, c=r[o], cmap=SEQ, norm=norm, linewidths=0, rasterized=True)
        ax.plot(U[path, 0], U[path, 1], color=INK, lw=0.5, alpha=0.6, zorder=8)
        ring(ax, U[i], size=30)
        embedding_axes(ax)
        expected_title = titles[j].split(" ")[0]
        assert ct[i] == expected_title, (ct[i], expected_title)
        ax.set_title(titles[j], pad=2)
        d = nums["trajectory"][j]
        ax.text(0.02, 0.02, f"effective n = {d['n_eff']:.0f} cells", transform=ax.transAxes,
                fontsize=7, color=SECONDARY, va="bottom")
        if j == 0:
            panel_label(ax, "a", x=-0.06, y=1.02)
    cax = fig.add_subplot(gtop[4])
    cb = fig.colorbar(sc, cax=cax)
    cb.set_label("5-step walk probability\n(log scale)", fontsize=7, color=SECONDARY)
    cb.ax.tick_params(labelsize=7, width=0.5, length=2)
    cb.ax.yaxis.set_major_locator(LogLocator(base=10))
    cb.ax.yaxis.set_major_formatter(FuncFormatter(pow10))
    cb.ax.yaxis.set_minor_formatter(NullFormatter())
    cb.outline.set_linewidth(0.5)

    # ---------------- (b)
    ax = fig.add_subplot(gbot[0])
    other = ~(A | B)
    other[f] = False
    ax.scatter(du[other], dm[other], s=0.8, c=NEUTRAL, linewidths=0, rasterized=True)
    highlight(ax, du[B], dm[B], C_B, s=5, label=f"far in UMAP,\nnear in diffusion (n = {B.sum()})")
    highlight(ax, du[A], dm[A], C_A, s=5, label=f"near in UMAP,\nfar in diffusion (n = {A.sum()})")
    ux, mx = nums["focus_bc"]["umap_dist_thresholds"], nums["focus_bc"]["diffusion_dist_thresholds"]
    for v in ux:
        ax.axvline(v, color=MUTED, lw=0.5, ls=(0, (2, 2)), zorder=1)
    for v in mx:
        ax.axhline(v, color=MUTED, lw=0.5, ls=(0, (2, 2)), zorder=1)
    ax.set_xlabel("UMAP distance to focused cell")
    ax.set_ylabel("Diffusion distance to focused cell\n(multiscale, from DM_EigenVectors)")
    ax.set_xlim(0, None); ax.set_ylim(0, None)
    ax.text(0.98, 0.29, f"Spearman $\\rho$ = {rho_f:.2f}\n(all {n - 1:,} cells)", transform=ax.transAxes,
            ha="right", va="center", fontsize=7, color=INK)
    ax.text(ux[0], ax.get_ylim()[1], " 5%", fontsize=7, color=MUTED, va="top", ha="left")
    ax.text(ux[1], ax.get_ylim()[1], " 20%", fontsize=7, color=MUTED, va="top", ha="left")
    ax.text(ax.get_xlim()[1], mx[0], "5%", fontsize=7, color=MUTED, va="bottom", ha="right")
    ax.text(ax.get_xlim()[1], mx[1], "20%", fontsize=7, color=MUTED, va="bottom", ha="right")
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.56), handletextpad=0.2, borderaxespad=0.2,
              markerscale=1.6, fontsize=7)
    panel_label(ax, "b", x=-0.18, y=1.0)

    # ---------------- (c)
    ax = fig.add_subplot(gbot[1])
    ax.scatter(U[other, 0], U[other, 1], s=0.6, c=NEUTRAL, linewidths=0, rasterized=True)
    highlight(ax, U[B, 0], U[B, 1], C_B, s=4)
    highlight(ax, U[A, 0], U[A, 1], C_A, s=4)
    ring(ax, U[f], size=34)
    embedding_axes(ax)
    panel_label(ax, "c", x=-0.04, y=1.0)

    # Direct labels, ink-coloured. Text names the cell types (>= 20 cells) in each
    # group; leader lines go to each such type's median position within the group.
    short = {"Mature Naive B cell": "naive B", "Memory B cell": "memory B", "Immature B cell": "immature B",
             "Basophil": "basophil", "T cell": "T", "CD8 TEM": "CD8 TEM", "NK": "NK", "pDC": "pDC"}
    arrow = dict(arrowstyle="-", lw=0.5, color=SECONDARY, shrinkA=1, shrinkB=2)
    xr = np.ptp(U[:, 0]); yr = np.ptp(U[:, 1])
    for mask, key, offset in ((A, "A", (0.10, -0.22)), (B, "B", (0.28, 0.20))):
        vc = pd.Series(ct[mask]).value_counts()
        types = vc.index[vc >= 20].tolist()
        mw = W[f][mask].sum()
        txt = ", ".join(short.get(x, x) for x in types) + f"\nwalk mass {100 * mw:.1f}%"
        nums["focus_bc"][f"label_{key}"] = txt
        cen = np.median(U[mask], axis=0)
        # A: the empty space below the focus; B: above-right of the B-cell island
        xytext = (U[f, 0] + 0.06 * xr, U[:, 1].min() + 0.03 * yr) if key == "A" else \
            (cen[0] + offset[0] * xr, cen[1] + offset[1] * yr)
        # one leader line per spatial clump of the group (single-linkage, 1.5 UMAP units)
        from scipy.cluster.hierarchy import fcluster, linkage
        pts = U[mask]
        lab = fcluster(linkage(pts, "single"), 1.5, "distance")
        for c in np.unique(lab):
            if (lab == c).sum() < 10:
                continue
            ax.annotate(txt, xy=np.median(pts[lab == c], axis=0), xytext=xytext, color="none",
                        fontsize=7, ha="center", va="center",
                        bbox=dict(facecolor="none", edgecolor="none", pad=1.0), arrowprops=arrow)
        ax.text(*xytext, txt, fontsize=7, color=INK, ha="center", va="center", zorder=20)
    ax.annotate(f"focused {ct[f].lower()}", xy=U[f], xytext=(U[f, 0] + 0.10 * xr, U[f, 1] + 0.20 * yr),
                fontsize=7, color=INK, ha="center", va="bottom",
                arrowprops=dict(arrowstyle="-", lw=0.5, color=SECONDARY, shrinkB=4))

    # ---------------- (d)
    nums["neuro"] = connectome_panel(fig, gbot[2], gbot[3])

    save(fig, "fig2_cell_by_cell")
    write_numbers("fig2", nums)
    print({k: v for k, v in nums.items() if k != "dataset"})
    print(nums["dataset"]["spearman_umap_vs_diffusion_per_cell_median"], nums["dataset"]["knn30_jaccard_median"])


def connectome_panel(fig, spec, cspec):
    """(d) The focused neuron class's row of the chemical-synapse matrix on the transcriptome UMAP."""
    a = ad.read_zarr(NEURO)
    U = np.asarray(a.obsm["X_umap"])
    names = np.asarray(a.obs_names)
    f = int(np.where(names == NEURO_FOCUS)[0][0])
    r = a.obsp["chemical_synapses"][f]
    r = np.asarray(r.toarray() if hasattr(r, "toarray") else r).ravel().astype(float)
    ax = fig.add_subplot(spec)
    z = r == 0
    ax.scatter(U[z, 0], U[z, 1], s=4, c=NEUTRAL, linewidths=0)
    o = np.where(~z)[0]
    o = o[np.argsort(r[o])]                           # strongest drawn last, on top
    sc = ax.scatter(U[o, 0], U[o, 1], s=6, c=r[o], cmap=SEQ, norm=LogNorm(vmin=1, vmax=r.max()),
                    linewidths=0, zorder=5)
    ring(ax, U[f], size=26)
    embedding_axes(ax)
    xr, yr = np.ptp(U[:, 0]), np.ptp(U[:, 1])
    ax.set_xlim(U[:, 0].min() - 0.06 * xr, U[:, 0].max() + 0.06 * xr)
    ax.set_ylim(U[:, 1].min() - 0.30 * yr, U[:, 1].max() + 0.08 * yr)
    top = o[::-1][:4]
    mn = top[U[top, 0] > 0]                           # partners in the motor-neuron cluster
    lab = ", ".join(f"{names[i]} {r[i]:.0f}" for i in mn[np.argsort(-r[mn])])
    cen = U[U[:, 0] > 0].mean(axis=0)
    ax.annotate(f"ventral cord motor neurons\n{lab}", xy=(cen[0], U[U[:, 0] > 0, 1].min()),
                xytext=(cen[0] - 0.30 * xr, U[:, 1].min() - 0.22 * yr), fontsize=7, color=INK,
                ha="center", va="center", arrowprops=dict(arrowstyle="-", lw=0.5, color=SECONDARY, shrinkB=3))
    for i in top[U[top, 0] <= 0]:
        ax.annotate(f"{names[i]} {r[i]:.0f}", xy=U[i], xytext=(U[i, 0] + 0.10 * xr, U[i, 1] - 0.12 * yr),
                    fontsize=7, color=INK, ha="left", va="center",
                    arrowprops=dict(arrowstyle="-", lw=0.5, color=SECONDARY, shrinkB=2))
    ax.annotate(f"focused {NEURO_FOCUS}", xy=U[f], xytext=(U[f, 0] + 0.02 * xr, U[f, 1] + 0.30 * yr),
                fontsize=7, color=INK, ha="left", va="bottom",
                arrowprops=dict(arrowstyle="-", lw=0.5, color=SECONDARY, shrinkB=4))
    ax.set_title("$\\mathit{C.\\,elegans}$ connectome", pad=2)
    panel_label(ax, "d", x=-0.16, y=1.0)
    cax = fig.add_subplot(cspec)
    cb = fig.colorbar(sc, cax=cax)
    cb.set_label("chemical synapses from AVA\n(log scale)", fontsize=7, color=SECONDARY)
    cb.set_ticks([1, 3, 10, 30, 80], labels=["1", "3", "10", "30", "80"])
    cb.minorticks_off()
    cb.ax.tick_params(labelsize=7, width=0.5, length=2)
    cb.ax.yaxis.set_major_locator(LogLocator(base=10))
    cb.ax.yaxis.set_major_formatter(FuncFormatter(pow10))
    cb.ax.yaxis.set_minor_formatter(NullFormatter())
    cb.outline.set_linewidth(0.5)
    return {"n_classes": int(a.n_obs), "n_genes": int(a.n_vars), "focus": NEURO_FOCUS,
            "n_partners": int((~z).sum()), "total": float(r.sum()),
            "top": [[str(names[i]), float(r[i])] for i in top],
            "top3_share": float(np.sort(r)[::-1][:3].sum() / r.sum()),
            "self": float(r[f]),                      # AVAL/AVAR onto each other, kept as stored
            "total_to_other_classes": float(r.sum() - r[f]),
            "top3_share_of_other_classes": float(np.sort(r)[::-1][:3].sum() / (r.sum() - r[f])),
            "motor_cluster": [str(x) for x in names[U[:, 0] > 0]]}

if __name__ == "__main__":
    main()
