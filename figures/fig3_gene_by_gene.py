"""fig:genegene: a focused gene's row of a gene x gene matrix, over a gene plot.

    .venv/bin/python figures/fig3_gene_by_gene.py

(a) Kompot volcano (var kompot_de_Young_to_Old_mean_lfc vs
    kompot_de_Young_to_Old_mahalanobis), every gene coloured by the focused
    gene's row of varp/spearman_fold_change. Focus H2-Q7 (MHC-I ageing module).
(b) The same volcano focused on H2-Aa (MHC-II).
(c) Continuous vs discrete. The 190 Kompot DE genes are clustered the
    conventional way: average-linkage hierarchical clustering on 1 - rho
    (spearman_fold_change restricted to DE genes), k chosen by the maximum mean
    silhouette over k = 2..12. For two focus genes (H2-Q7, S100a9) every other DE
    gene's rho to the focus is plotted in rank order and coloured by its module.
(d) spearman_smoothed vs spearman_fold_change rows of H2-Q7 across all genes.

Writes manuscript/figures/fig3_gene_by_gene.{pdf,png} and figures/numbers/fig3.json.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from adjustText import adjust_text  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from scipy.cluster.hierarchy import fcluster, linkage  # noqa: E402
from scipy.spatial.distance import squareform  # noqa: E402
from sklearn.metrics import silhouette_score  # noqa: E402

from figures._load import KEYS, Store, highlight, ring, write_numbers  # noqa: E402
from figures.style import (CAT, DIV, INK, MUTED, NEUTRAL, SECONDARY, TWO_COL, apply,  # noqa: E402
                           panel_label, save)

FOCUS_A, FOCUS_B, FOCUS_C2 = "H2-Q7", "H2-Aa", "S100a9"
N_LABEL = 5                     # top correlated genes labelled on each volcano
FC_KEY, SM_KEY = "spearman_fold_change", "spearman_smoothed"
# Module identity hues avoid the DIV blue/red that encode the sign of rho in a-b:
# purple, amber, dark green (green labelled directly).
MOD_COLORS = [CAT[6], CAT[5], CAT[3]]   # module 1, 2, 3 (fixed identity order)
C_AGE, C_LIN = CAT[6], CAT[3]           # panel d categories, same non-DIV hues


def volcano(ax, s, focus, nums, label_genes=None):
    genes = s.var.index.to_numpy()
    x, y = s.lfc, s.mahal
    r = s.varp_row(FC_KEY, focus)
    g = s.gi(focus)
    o = np.argsort(np.abs(r))           # strongest |rho| drawn last (on top)
    o = o[o != g]
    sc = ax.scatter(x[o], y[o], c=r[o], cmap=DIV, norm=Normalize(-1, 1), s=1.6, linewidths=0,
                    rasterized=True)
    thr = float(s.mahal[s.is_de].min())
    ax.axhline(thr, color=MUTED, lw=0.5, ls=(0, (2, 2)), zorder=0)
    ax.text(x.max(), thr - 0.15, "DE, FDR 5%", fontsize=7, color=MUTED, va="top", ha="right")
    ax.scatter(x[g], y[g], s=5, c=INK, linewidths=0, zorder=9)
    ring(ax, (x[g], y[g]), size=26)
    top = [i for i in np.argsort(-r) if i != g][:N_LABEL]
    if label_genes is not None:
        top = [s.gi(t) for t in label_genes]
    for i in top:
        ax.scatter(x[i], y[i], s=9, c=[DIV(Normalize(-1, 1)(r[i]))], edgecolors="white", linewidths=0.5, zorder=6)
    texts = [ax.text(x[i], y[i], f"{genes[i]} {r[i]:.2f}", fontsize=7, color=INK, zorder=12) for i in top]
    texts.append(ax.text(x[g], y[g], focus, fontsize=7, color=INK, fontweight="bold", zorder=12))
    ax.set_xlabel("Mean log2 fold change, Old vs Young (Kompot)")
    ax.set_ylabel("Mahalanobis distance (Kompot)")
    nums[focus] = {
        "top_fold_change_partners": [(genes[i], round(float(r[i]), 3), bool(s.is_de[i])) for i in
                                     [j for j in np.argsort(-r) if j != g][:10]],
        "n_rho_gt_0.7": int((r > 0.7).sum() - 1), "n_rho_gt_0.5": int((r > 0.5).sum() - 1),
        "n_rho_lt_-0.5": int((r < -0.5).sum()),
        "mean_lfc": float(x[g]), "mahalanobis": float(y[g]),
        "mahalanobis_rank": int((y > y[g]).sum() + 1),
    }
    return sc, texts, thr


def main():
    apply()
    s = Store()
    genes = s.var.index.to_numpy()
    nums = {"varp_fold_change": FC_KEY, "varp_smoothed": SM_KEY,
            "n_genes": len(genes), "n_de": int(s.is_de.sum())}

    fig = plt.figure(figsize=(TWO_COL, 6.25))
    gs = fig.add_gridspec(2, 3, width_ratios=[1, 1, 0.035], height_ratios=[1, 1.35],
                          hspace=0.36, wspace=0.30)

    # ---------------- (a), (b)
    axa = fig.add_subplot(gs[0, 0])
    sc, texts_a, thr = volcano(axa, s, FOCUS_A, nums)
    axb = fig.add_subplot(gs[0, 1], sharex=axa, sharey=axa)
    _, texts_b, _ = volcano(axb, s, FOCUS_B, nums)
    axb.set_ylabel("")
    nums["de_mahalanobis_threshold"] = thr
    rq = s.varp_row(FC_KEY, FOCUS_A)
    nums["rho_fc_H2-Q7_H2-Aa"] = float(rq[s.gi(FOCUS_B)])
    nums["rho_smoothed_H2-Q7_H2-Aa"] = float(s.varp_row(SM_KEY, FOCUS_A)[s.gi(FOCUS_B)])
    axa.set_title(f"Focus {FOCUS_A}:\ncolour = its row of {FC_KEY}", loc="left", fontweight="normal")
    axb.set_title(f"Focus {FOCUS_B}:\nsame plot, new row", loc="left", fontweight="normal")
    cax = fig.add_subplot(gs[0, 2])
    cb = fig.colorbar(sc, cax=cax)
    cb.set_label("Spearman $\\rho$ with focused gene\n(fold-change layer, across cells)", fontsize=7,
                 color=SECONDARY)
    cb.set_ticks([-1, -0.5, 0, 0.5, 1])
    cb.ax.tick_params(labelsize=7, width=0.5, length=2)
    cb.outline.set_linewidth(0.5)
    for ax, t in ((axa, texts_a), (axb, texts_b)):
        adjust_text(t, ax=ax, expand=(1.3, 1.6), force_text=(0.4, 0.8), force_static=(0.3, 0.6),
                    arrowprops=dict(arrowstyle="-", lw=0.5, color=SECONDARY), only_move={"text": "xy"})
    panel_label(axa, "a", x=-0.16, y=1.10)
    panel_label(axb, "b", x=-0.08, y=1.10)

    # ---------------- (c) clustering of DE genes
    de = np.where(s.is_de)[0]
    dg = genes[de]
    C = s.varp_block(FC_KEY, de)
    D = 1 - C
    np.fill_diagonal(D, 0)
    D = (D + D.T) / 2
    Z = linkage(squareform(D, checks=False), "average")
    sil = {k: float(silhouette_score(D, fcluster(Z, k, "maxclust"), metric="precomputed")) for k in range(2, 13)}
    k_best = max(sil, key=sil.get)
    lab = fcluster(Z, k_best, "maxclust")
    # relabel modules: 1 = module of FOCUS_A, then by size
    order = [lab[list(dg).index(FOCUS_A)]] + [m for m in np.argsort(-np.bincount(lab))
                                             if m != lab[list(dg).index(FOCUS_A)] and m > 0]
    remap = {m: i + 1 for i, m in enumerate(order)}
    lab = np.array([remap[m] for m in lab])
    sizes = {int(m): int((lab == m).sum()) for m in np.unique(lab)}
    nums["clustering"] = {"method": "average linkage on 1 - spearman_fold_change, DE genes only",
                          "silhouette_by_k": sil, "k": int(k_best), "module_sizes": sizes,
                          "module_top_genes_by_mahalanobis": {
                              int(m): list(dg[lab == m][np.argsort(-s.mahal[de][lab == m])][:12])
                              for m in np.unique(lab)}}
    assert k_best <= 3, "colour scheme assumes <= 3 modules"

    bot = gs[1, :].subgridspec(1, 2, width_ratios=[1.2, 1], wspace=0.3)   # c gets more room for its labels
    gsc = bot[0].subgridspec(2, 1, hspace=0.42)
    for row, focus in enumerate((FOCUS_A, FOCUS_C2)):
        ax = fig.add_subplot(gsc[row])
        j = list(dg).index(focus)
        r = C[j].copy()
        keep = np.arange(len(dg)) != j
        idx = np.where(keep)[0][np.argsort(-r[keep])]
        rank = np.arange(1, len(idx) + 1)
        fm = lab[j]
        for m in sorted(np.unique(lab)):
            sel = lab[idx] == m
            ax.scatter(rank[sel], r[idx][sel], s=5, c=MOD_COLORS[m - 1], linewidths=0,
                       zorder=3 if m == fm else 2,
                       label=f"module {m} ({sizes[m]})" if row == 0 else None)
        ax.axhline(0, color=MUTED, lw=0.5, zorder=0)
        ax.set_xlim(-3, len(idx) + 4)
        ax.set_ylim(-1.05, 1.05)        # room below the curve for the summary
        ax.set_yticks([-1, -0.5, 0, 0.5, 1])
        ax.set_ylabel(f"$\\rho$ with {focus}")
        mine = (lab == fm) & keep
        other = (lab != fm) & keep
        st = {"module": int(fm), "module_size": int(sizes[fm]),
              "in_module_median_rho": float(np.median(r[mine])),
              "in_module_n_rho_lt_0.2": int((r[mine] < 0.2).sum()),
              "in_module_n_rho_lt_0": int((r[mine] < 0).sum()),
              "out_module_n_rho_gt_0.7": int((r[other] > 0.7).sum()),
              "out_module_n_rho_gt_0.5": int((r[other] > 0.5).sum()),
              "out_module_n_rho_gt_0.4": int((r[other] > 0.4).sum()),
              "out_module_max": (dg[other][np.argmax(r[other])], float(r[other].max())),
              "out_module_top": [(dg[i], round(float(r[i]), 3), int(lab[i])) for i in
                                 np.where(other)[0][np.argsort(-r[other])][:5]],
              "top_rank_genes": [(dg[i], round(float(r[i]), 3), int(lab[i])) for i in idx[:8]]}
        # genome-wide view: strongest partners that are not DE (absent from every module)
        rr = s.varp_row(FC_KEY, focus)
        nd = np.where(~s.is_de)[0]
        st["non_de_n_rho_gt_0.5"] = int((rr[nd] > 0.5).sum())
        st["non_de_top"] = [(genes[i], round(float(rr[i]), 3)) for i in nd[np.argsort(-rr[nd])][:5]]
        nums.setdefault("rank_strips", {})[focus] = st
        # direct labels (ink); positions in data units, chosen to sit in empty space
        if focus == FOCUS_A:
            spots = {"H2-Q6": (14, 0.88), "Cd74": (38, 0.66), "H2-Aa": (38, 0.46)}
        else:
            o2 = [g for g, _, m in st["out_module_top"][:2]]
            spots = {"S100a8": (14, 1.0), o2[0]: (24, 0.80), o2[1]: (24, 0.60)}
        for gname, xy in spots.items():
            i = list(dg).index(gname)
            rk = int(np.where(idx == i)[0][0]) + 1
            ax.annotate(f"{gname} {r[i]:.2f}", xy=(rk, r[i]), xytext=xy, fontsize=7,
                        color=INK, va="center", ha="left",
                        arrowprops=dict(arrowstyle="-", lw=0.5, color=SECONDARY, shrinkA=0, shrinkB=1.5))
        if focus == FOCUS_A:  # the green module is labelled directly (low contrast hue)
            tail = idx[lab[idx] == 2][-12:]
            ax.annotate("module 2", xy=(np.where(idx == tail[0])[0][0] + 1, r[tail[0]]),
                        xytext=(175, 0.45), fontsize=7, color=INK, ha="right", va="center",
                        arrowprops=dict(arrowstyle="-", lw=0.5, color=SECONDARY, shrinkB=1.5))
        summary = (f"{focus}, module {fm}: median $\\rho$ = {st['in_module_median_rho']:.2f};\n"
                   f"{st['in_module_n_rho_lt_0.2']} of {int(mine.sum())} members $\\rho$ < 0.2, "
                   f"{st['out_module_n_rho_gt_0.5']} others $\\rho$ > 0.5")
        ax.text(0.01, 0.02, summary, transform=ax.transAxes, fontsize=7, color=SECONDARY, ha="left",
                va="bottom")   # bottom left: the ranked curve falls from top left to bottom right
        if row == 0:
            panel_label(ax, "c", x=-0.16, y=1.18)
            ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=3, fontsize=7, handletextpad=0.1,
                      borderaxespad=0.1, markerscale=1.3, columnspacing=0.8, title_fontsize=7)
        else:
            ax.set_xlabel(f"DE genes ranked by $\\rho$ with the focused gene (n = {len(idx)})")

    # ---------------- (d) smoothed vs fold-change rows for FOCUS_A
    ax = fig.add_subplot(bot[1])
    a = s.varp_row(SM_KEY, FOCUS_A)
    b = s.varp_row(FC_KEY, FOCUS_A)
    g = s.gi(FOCUS_A)
    keep = np.arange(len(genes)) != g
    lin = keep & (a > 0.7) & (b < 0.5)
    age = keep & (b > 0.5)
    rest = keep & ~lin & ~age
    ax.scatter(a[rest], b[rest], s=1.2, c=NEUTRAL, linewidths=0, rasterized=True)
    highlight(ax, a[lin], b[lin], C_LIN, s=4,
              label=f"smoothed $\\rho$ > 0.7, fold-change $\\rho$ < 0.5 (n = {lin.sum()})")
    highlight(ax, a[age], b[age], C_AGE, s=6, zorder=6,
              label=f"fold-change $\\rho$ > 0.5 (n = {age.sum()})")
    ax.axhline(0, color=MUTED, lw=0.5, zorder=0)
    ax.axvline(0, color=MUTED, lw=0.5, zorder=0)
    ax.set_xlim(-1, 1); ax.set_ylim(-1, 1)
    ax.set_xticks([-1, -0.5, 0, 0.5, 1]); ax.set_yticks([-1, -0.5, 0, 0.5, 1])
    ax.set_aspect("equal")
    ax.set_xlabel(f"$\\rho$ with {FOCUS_A}, smoothed expression\n({SM_KEY})")
    ax.set_ylabel(f"$\\rho$ with {FOCUS_A}, fold change\n({FC_KEY})")
    ax.text(-0.97, 0.97, "shares its\nage response", fontsize=7, color=SECONDARY, va="top")
    ax.text(0.98, -0.42, "shares its\ncell-state\npattern only", fontsize=7, color=SECONDARY, ha="right", va="top")
    lab_age = [genes[i] for i in np.where(age)[0][np.argsort(-b[age])]]
    lin_idx = np.where(lin)[0][np.argsort(-(a[lin] - b[lin]))]
    lab_lin = [genes[i] for i in np.where(lin)[0][np.argsort(-a[lin])][:2]]
    if lin[s.gi("H2-K1")] and "H2-K1" not in lab_lin:
        lab_lin.append("H2-K1")
    texts = []
    for gname in lab_age[:6] + lab_lin:
        i = s.gi(gname)
        texts.append(ax.text(a[i], b[i], gname, fontsize=7, color=INK, zorder=12,
                             bbox=dict(facecolor="white", edgecolor="none", pad=0.3, alpha=0.75)))
    adjust_text(texts, ax=ax, expand=(1.3, 1.6), force_text=(0.5, 0.9),
                arrowprops=dict(arrowstyle="-", lw=0.5, color=SECONDARY))
    ax.legend(loc="lower left", bbox_to_anchor=(-0.02, -0.02), fontsize=7, handletextpad=0.1,
              markerscale=1.4, borderaxespad=0.2)
    panel_label(ax, "d", x=-0.30, y=1.02)
    from scipy.stats import pearsonr, spearmanr
    nums["panel_d"] = {
        "focus": FOCUS_A,
        "n_smoothed_gt_0.7": int((keep & (a > 0.7)).sum()), "n_fc_gt_0.7": int((keep & (b > 0.7)).sum()),
        "n_both_gt_0.7": int((keep & (a > 0.7) & (b > 0.7)).sum()),
        "n_lineage_only": int(lin.sum()), "n_age_fc_gt_0.5": int(age.sum()),
        "age_genes": [(genes[i], round(float(a[i]), 3), round(float(b[i]), 3)) for i in np.where(age)[0][np.argsort(-b[age])]],
        "lineage_top": [(genes[i], round(float(a[i]), 3), round(float(b[i]), 3)) for i in np.where(lin)[0][np.argsort(-a[lin])][:10]],
        "pearson_between_rows": float(pearsonr(a[keep], b[keep])[0]),
        "spearman_between_rows": float(spearmanr(a[keep], b[keep])[0]),
        "lineage_only_frac_de": float(s.is_de[lin].mean()),
    }

    save(fig, "fig3_gene_by_gene")
    write_numbers("fig3", nums)
    import json
    print(json.dumps(nums, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
