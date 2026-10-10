"""fig:cellgene: the cells x genes data, read from both sides.

    .venv/bin/python figures/fig4_cells_by_genes.py

(a) A gene's column of layers/kompot_de_Young_to_Old_fold_change on obsm/X_umap
    (Old minus Young smoothed log2 expression, per cell). Focus gene S100a9, the
    demo store's focus gene (examples.json): a near-zero mean LFC that hides a
    strong, cell-state-restricted loss.
(b, c) Its columns of kompot_de_Young_smoothed and kompot_de_Old_smoothed on one
    shared sequential scale.
(d) The same layer read by rows: every gene's fold change in the locked HSC (x)
    against the focused monocyte (y), the two example cells of examples.json.
    DE genes are coloured by sign agreement (sign of the product), with no
    magnitude cut; the strongest opposite-direction genes (by min(|x|, |y|)) are
    labelled.

Writes manuscript/figures/fig4_cells_by_genes.{pdf,png} and figures/numbers/fig4.json.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from adjustText import adjust_text  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from figures._load import EXAMPLES, HSC_CELL, KEYS, MONO_CELL, Store, highlight, ring, write_numbers  # noqa: E402
from figures.style import (CAT, DIV, INK, MUTED, NEUTRAL, SECONDARY, SEQ, TWO_COL, apply,  # noqa: E402
                           embedding_axes, panel_label, save)

GENE = EXAMPLES["genes"]["focus"]["name"]     # S100a9
C_SAME, C_OPP = CAT[6], CAT[3]                 # purple / amber: not the DIV blue-red of panel a
FC, (YK, OK) = KEYS["FC_KEY"], KEYS["SMOOTH_KEYS"]


def cbar(fig, ax, mappable, label, ticks=None):
    cb = fig.colorbar(mappable, ax=ax, orientation="horizontal", fraction=0.05, pad=0.03,
                      aspect=28 if not isinstance(ax, list) else 56)
    cb.set_label(label, fontsize=7, color=SECONDARY, labelpad=1.5)
    if ticks is not None:
        cb.set_ticks(ticks)
    cb.ax.tick_params(labelsize=7, width=0.5, length=2)
    cb.outline.set_linewidth(0.5)
    return cb


def mark_cells(ax, U, h, m, labels=True):
    ring(ax, U[h], size=26)
    ring(ax, U[m], size=26)
    if labels:
        kw = dict(fontsize=7, color=INK, ha="center",
                  arrowprops=dict(arrowstyle="-", lw=0.5, color=SECONDARY, shrinkB=3.5))
        ax.annotate("locked HSC", xy=U[h], xytext=U[h] + np.array([2.0, -5.5]), va="top", **kw)
        ax.annotate("focused\nmonocyte", xy=U[m], xytext=U[m] + np.array([-5.5, 5.0]), va="bottom", **kw)


def main():
    apply()
    s = Store()
    U = s.umap
    ct = s.celltype
    genes = s.var.index.to_numpy()
    h, m = s.ci(HSC_CELL), s.ci(MONO_CELL)
    fc = s.layer_col(FC, GENE)
    y = s.layer_col(YK, GENE)
    o = s.layer_col(OK, GENE)
    assert np.allclose(fc, o - y, atol=1e-5), "fold change should be Old - Young"
    by_ct = pd.DataFrame({"ct": ct, "fc": fc, "young": y, "old": o}).groupby("ct").median()
    nums = {"gene": GENE, "fold_change_key": FC, "smoothed_keys": [YK, OK],
            "mean_lfc": float(s.lfc[s.gi(GENE)]), "mahalanobis": float(s.mahal[s.gi(GENE)]),
            "mahalanobis_rank": int((s.mahal > s.mahal[s.gi(GENE)]).sum() + 1),
            "fc_range": [float(fc.min()), float(fc.max())],
            "fc_HSC_cell": float(fc[h]), "fc_monocyte_cell": float(fc[m]),
            "median_by_celltype": by_ct.round(3).to_dict(orient="index"),
            "frac_cells_fc_lt_-0.5": float((fc < -0.5).mean()),
            "celltypes_of_cells_fc_lt_-0.5": pd.Series(ct[fc < -0.5]).value_counts().head(5).to_dict()}

    fig = plt.figure(figsize=(TWO_COL, 5.25))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 0.95], hspace=0.22, wspace=0.04)

    # ---------------- (a) fold-change column
    ax = fig.add_subplot(gs[0, 0])
    lim = float(np.abs(fc).max())
    order = np.argsort(np.abs(fc))
    sc = ax.scatter(U[order, 0], U[order, 1], c=fc[order], cmap=DIV, norm=Normalize(-lim, lim), s=0.9,
                    linewidths=0, rasterized=True)
    mark_cells(ax, U, h, m)
    embedding_axes(ax)
    ax.set_title(f"{GENE} fold change\n(Old $-$ Young)", pad=2, fontsize=7)
    cbar(fig, ax, sc, "log2 fold change (fold-change layer)")
    panel_label(ax, "a", x=-0.04, y=1.0)

    # ---------------- (b, c) Young / Old smoothed, one shared scale
    vmax = float(max(y.max(), o.max()))
    norm = Normalize(0, vmax)
    axes_bc = []
    for j, (vals, name, key) in enumerate(((y, "Young", YK), (o, "Old", OK))):
        ax = fig.add_subplot(gs[0, 1 + j])
        axes_bc.append(ax)
        order = np.argsort(vals)
        sc = ax.scatter(U[order, 0], U[order, 1], c=vals[order], cmap=SEQ, norm=norm, s=0.9, linewidths=0,
                        rasterized=True)
        mark_cells(ax, U, h, m, labels=False)
        embedding_axes(ax)
        ax.set_title(f"{GENE} smoothed\n{name}", pad=2, fontsize=7)
        ax.text(0.02, 0.98, f"HSC median {by_ct.loc['HSC', name.lower()]:.2f}", transform=ax.transAxes,
                fontsize=7, color=SECONDARY, ha="left", va="top")
        panel_label(ax, "bc"[j], x=-0.04, y=1.0)
    cbar(fig, axes_bc, sc, "smoothed log2 expression, one scale for b and c (smoothed layers)")

    # ---------------- (d) locked HSC vs focused monocyte, rows of the FC layer
    a = s.layer_row(FC, HSC_CELL)
    b = s.layer_row(FC, MONO_CELL)
    de = s.is_de
    # Threshold-free encoding: DE genes split by the sign of a*b (no magnitude cut).
    opp = de & (a * b < 0)
    same = de & (a * b > 0)
    # Noise level: the fold-change z-score layer was not stored; Kompot's per-cell
    # posterior stds (obs) give a gene-shared fold-change sd = sqrt(sd_Y^2 + sd_O^2).
    sd = {c: float(np.hypot(*s.obs.loc[c, ["kompot_de_Young_std", "kompot_de_Old_std"]].astype(float)))
          for c in (HSC_CELL, MONO_CELL)}
    zh, zm = a / sd[HSC_CELL], b / sd[MONO_CELL]
    opp_z = opp & (np.abs(zh) > 1.96) & (np.abs(zm) > 1.96)
    strength = np.minimum(np.abs(a), np.abs(b))
    top_opp = np.where(opp)[0][np.argsort(-strength[opp])][:5]
    nums["panel_d"] = {
        "locked_cell": HSC_CELL, "focused_cell": MONO_CELL,
        "encoding": "DE genes coloured by sign(x*y); no magnitude threshold",
        "spearman_rows_all_genes": float(spearmanr(a, b)[0]),
        "spearman_rows_de_genes": float(spearmanr(a[de], b[de])[0]),
        "n_de": int(de.sum()), "n_de_same_direction": int(same.sum()), "n_de_opposite_direction": int(opp.sum()),
        "frac_de_opposite": float(opp.sum() / de.sum()),
        "frac_all_genes_opposite": float((a * b < 0).mean()),
        "top_opposite_by_min_abs": [(genes[i], round(float(a[i]), 3), round(float(b[i]), 3),
                                     round(float(strength[i]), 3)) for i in top_opp],
        "opposite_de_min_abs_median": float(np.median(strength[opp])),
        "same_de_min_abs_median": float(np.median(strength[same])),
        "noise_fc_sd_per_cell": sd,
        "noise_note": "kompot fold_change_zscores layer not stored; per-cell sd from obs kompot_de_{Young,Old}_std",
        "n_de_opposite_beyond_1.96sd_both": int(opp_z.sum()),
        "de_opposite_beyond_1.96sd_both": [genes[i] for i in np.where(opp_z)[0]],
        "n_de_same_beyond_1.96sd_both": int((same & (np.abs(zh) > 1.96) & (np.abs(zm) > 1.96)).sum()),
        "n_de_beyond_1.96sd_hsc": int((de & (np.abs(zh) > 1.96)).sum()),
        "n_de_beyond_1.96sd_mono": int((de & (np.abs(zm) > 1.96)).sum()),
        "hsc_fc_range": [float(a.min()), float(a.max())], "mono_fc_range": [float(b.min()), float(b.max())],
        "de_abs_fc_median_hsc": float(np.median(np.abs(a[de]))), "de_abs_fc_median_mono": float(np.median(np.abs(b[de]))),
    }
    ax = fig.add_subplot(gs[1, :])
    rest = ~de
    ax.scatter(a[rest], b[rest], s=1.0, c=NEUTRAL, linewidths=0, rasterized=True,
               label=f"not DE (n = {rest.sum():,})")
    highlight(ax, a[same], b[same], C_SAME, s=6, label=f"DE, same direction in both cells (n = {same.sum()})")
    highlight(ax, a[opp], b[opp], C_OPP, s=7, zorder=6,
              label=f"DE, opposite direction (n = {opp.sum()}, {100 * opp.sum() / de.sum():.0f}% of DE)")
    lo = min(a.min(), b.min()) - 0.05
    hi = max(a.max(), b.max()) + 0.05
    ax.plot([lo, hi], [lo, hi], color=SECONDARY, lw=0.5, ls=(0, (3, 2)), zorder=1)
    ax.axhline(0, color=MUTED, lw=0.5, zorder=0)
    ax.axvline(0, color=MUTED, lw=0.5, zorder=0)
    ax.set_xlim(a.min() - 0.08, a.max() + 0.08)
    ax.set_ylim(b.min() - 0.06, b.max() + 0.06)
    ax.set_aspect("equal")
    ax.set_xlabel(f"log2 fold change in the locked HSC  ({HSC_CELL})")
    ax.set_ylabel("log2 fold change in the\nfocused monocyte")
    ax.text(0.01, 0.97, f"Spearman $\\rho$ = {nums['panel_d']['spearman_rows_de_genes']:.2f} over DE genes, "
            f"{nums['panel_d']['spearman_rows_all_genes']:.2f} over all {len(genes):,} genes\n"
            f"opposite-direction DE genes beyond 1.96 Kompot s.d. in both cells: "
            f"{nums['panel_d']['n_de_opposite_beyond_1.96sd_both']} "
            f"({', '.join(nums['panel_d']['de_opposite_beyond_1.96sd_both'])})",
            transform=ax.transAxes, fontsize=7, color=INK, ha="left", va="top",
            bbox=dict(facecolor="white", edgecolor="none", pad=0.5), zorder=15)
    ax.text(hi - 1.0, min(hi - 1.0, b.max()), "identity", fontsize=7, color=SECONDARY, rotation=45,
            rotation_mode="anchor", va="bottom")
    gi = s.gi(GENE)
    ring(ax, (a[gi], b[gi]), size=22)
    labs = list(top_opp) + [gi]
    texts = [ax.text(a[i], b[i], genes[i], fontsize=7, color=INK, zorder=12,
                     fontweight="bold" if i == gi else "normal") for i in labs]
    adjust_text(texts, ax=ax, expand=(1.4, 1.8), force_text=(0.6, 0.9),
                arrowprops=dict(arrowstyle="-", lw=0.5, color=SECONDARY))
    ax.legend(loc="lower left", fontsize=7, markerscale=1.5, handletextpad=0.2, borderaxespad=0.2)
    panel_label(ax, "d", x=-0.03, y=1.02)

    save(fig, "fig4_cells_by_genes")
    write_numbers("fig4", nums)
    import json
    print(json.dumps({k: v for k, v in nums.items() if k != "median_by_celltype"}, indent=1, default=str))


if __name__ == "__main__":
    main()
