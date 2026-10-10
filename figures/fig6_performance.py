"""The performance figure (fig:performance; the Scale figure is fig:scale): what one AnnZarro interaction costs as data grow.

Usage:
    .venv/bin/python figures/fig6_performance.py

Every value is AnnZarro v0.4.1 (the tag, 78c9da6): the laptop series in
benchmark/results/scale_v041.csv and the 1M chunk sweep sweep_v041.csv, and the HPC series of the
HPC worker's $SCRATCH runs T and T2 (benchmark/scale/results/hpc/full/, hpc_v041_case_map.tsv): dense
pairwise rows up to 200,000 x 200,000 and a 1M x 5,000 dense Tahoe-100M layer in four chunk shapes.

Writes manuscript/figures/fig6_performance.{pdf,png} and the supplementary
figS_interactions and figS_chunk_sweep.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402

from figures.style import (CAT, GRID, INK, MUTED, NEUTRAL, ONE_COL, SECONDARY, SEQ,  # noqa: E402
                           TWO_COL, apply, panel_label, save)

REPO = Path(__file__).resolve().parents[1]
LAPTOP = REPO / "benchmark" / "results"
SCALE = LAPTOP / "scale_v041.csv"       # v0.4.1 (the tag), binary wire (benchmark/queue_perf.sh)
SWEEP = LAPTOP / "sweep_v041.csv"       # v0.4.1 chunk sweep at 1M
HPC = REPO / "benchmark" / "scale" / "results" / "hpc" / "full"
HPC_PAIR = [HPC / "t_v041_hpctemp_reduced/run_v041_hpctemp_reduced/pairwise_public/http.csv",   # T: corr 30k, dist 200k
            HPC / "t2_v041_hpctemp_extra/run_v041_hpctemp_extra/pairwise_public/http.csv"]     # T2: the rest
HPC_GRID = HPC / "t_v041_hpctemp_reduced/run_v041_hpctemp_reduced/grid/http.csv"           # 1M x 5,000, four shapes
HPC_WARM = "newidx"   # page cache warm, a new index: the laptop's warm_new

# Identity encodings shared by every panel.
C_GENE, C_CELL, C_PAIR = CAT[0], CAT[1], CAT[2]
M_LAPTOP, M_HPC = "o", "s"
LW = 1.2
MS = 3.5


# --------------------------------------------------------------------------- helpers
def q(x, p):
    return float(np.quantile(np.asarray(x, dtype=float), p))


def med_iqr(x):
    x = np.asarray(x, dtype=float)
    return float(np.median(x)), q(x, 0.25), q(x, 0.75)


def fmt_bytes(v, _pos=None):
    for unit, f in (("TB", 1e12), ("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if v >= f * 0.999:
            s = f"{v / f:g}"
            return f"{s} {unit}"
    return f"{v:g} B"


def fmt_mem(v, _pos=None):
    """Memory in binary units (the paper's convention)."""
    for unit, f in (("GiB", 2 ** 30), ("MiB", 2 ** 20)):
        if v >= f * 0.999:
            return f"{v / f:g} {unit}"
    return f"{v:g} B"


def fmt_count(v, _pos=None):
    if v >= 1e6:
        return f"{v / 1e6:g}M"
    if v >= 1e3:
        return f"{v / 1e3:g}k"
    return f"{v:g}"


def fmt_seconds(v, _pos=None):
    if v >= 1:
        return f"{v:g} s"
    return f"{v * 1e3:g} ms"


def log_axis(ax, which, formatter, numticks=12, minor=True):
    axis = ax.xaxis if which == "x" else ax.yaxis
    (ax.set_xscale if which == "x" else ax.set_yscale)("log")
    axis.set_major_locator(LogLocator(base=10, numticks=numticks))
    axis.set_major_formatter(FuncFormatter(formatter))
    if minor:
        axis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10) * 0.1, numticks=numticks))
    else:
        axis.set_minor_locator(plt.NullLocator())
    axis.set_minor_formatter(NullFormatter())


def grid(ax, axis="both"):
    ax.grid(True, which="major", axis=axis, color=GRID, lw=0.5, zorder=0)
    ax.set_axisbelow(True)


def title(ax, text):
    ax.set_title(text, loc="left", fontsize=7, fontweight="bold", color=INK, pad=4)


def errline(ax, x, m, lo, hi, color, marker, ls="-", filled=True, label=None, z=3):
    m, lo, hi = map(np.asarray, (m, lo, hi))
    ax.errorbar(x, m, yerr=[m - lo, hi - m], color=color, marker=marker, ls=ls, lw=LW,
                ms=MS, mfc=color if filled else "white", mec=color, mew=0.8,
                elinewidth=0.6, capsize=1.2, label=label, zorder=z)


# --------------------------------------------------------------------------- data
def load_laptop():
    scale = pd.read_csv(SCALE)
    assert (scale.status == 200).all()
    assert (scale[scale.interaction.str.startswith("layer_")].wire == "binary").all()
    sweep = None
    if SWEEP.exists():
        sweep = pd.read_csv(SWEEP)
        assert (sweep.status == 200).all()
    return scale, sweep


def load_hpc():
    """The $SCRATCH pairwise rows (matrix kind and n from the case id) and the chunk-shape grid."""
    pw = pd.concat([pd.read_csv(f) for f in HPC_PAIR], ignore_index=True)
    assert (pw.status == 200).all() and (pw.fs == "hpctemp").all()
    pw["matrix"] = pw.case_id.str.extract(r"^tahoe_(\w+?)_\d+:")[0]
    pw["n"] = pw.n_values
    grid_ = pd.read_csv(HPC_GRID)
    assert (grid_.status == 200).all() and (grid_.fs == "hpctemp").all()
    grid_["shape"] = grid_.case_id.str.extract(r"^tahoe_dense_1M_(\w+?):")[0]
    return pw, grid_


def by_size(df, key, val, cond_col, cond):
    d = df[df[cond_col] == cond]
    rows = []
    for k, g in d.groupby(key):
        m, lo, hi = med_iqr(g[val])
        rows.append((k, m, lo, hi, len(g)))
    return pd.DataFrame(rows, columns=[key, "m", "lo", "hi", "count"]).sort_values(key)


# --------------------------------------------------------------------------- panels
# Binary wire format (annzarro/core/array_response.py): a numeric slice is sent as little-endian
# float32 when that is exact, dense (4 B per value) unless its non-zeros plus their uint32
# positions (8 B per non-zero) are smaller. The benchmark's layers are float32 with noise, so
# every value is non-zero and a click sends exactly 4 B per value. A pairwise row of n cells
# carries n values, as a gene column does.
F32 = 4


def panel_payload(ax, scale):
    """(a) bytes per click vs n_cells (binary float32), with full-matrix reference lines."""
    title(ax, "Clicks move vectors, not matrices")
    n = np.array([1e4, 1.2e6])
    ax.plot(n, n * 5000 * F32, color=MUTED, lw=0.8, ls=":", zorder=1)
    ax.text(3e4, 3e4 * 5000 * F32 * 0.4, "whole n × 5,000 layer", color=SECONDARY,
            fontsize=7, ha="left", va="top")
    ax.plot(n, n ** 2 * F32, color=MUTED, lw=0.8, ls="--", dashes=(3, 2), zorder=1)
    ax.text(1.6e5, 1.6e5 ** 2 * F32 * 4, "whole n × n\npairwise matrix", color=SECONDARY,
            fontsize=7, ha="right", va="bottom")
    for it, col in (("layer_gene", C_GENE), ("layer_cell", C_CELL)):
        d = scale[scale.interaction == it].assign(binary=lambda x: x.n_values * F32)
        s = by_size(d, "n_cells", "binary", "condition", "cold")
        errline(ax, s.n_cells, s.m, s.lo, s.hi, col, M_LAPTOP)
    ax.text(8.5e5, 4e6 * 2.2, "gene column\n(= pairwise row, n values)", color=INK, fontsize=7,
            ha="right", va="bottom")
    ax.text(1e6, 2e4 * 1.7, "cell row (5,000 genes)", color=INK, fontsize=7,
            ha="right", va="bottom")
    ax.annotate("", xy=(1e6, 5e6), xytext=(1e6, 1.6e10),
                arrowprops=dict(arrowstyle="<->", color=SECONDARY, lw=0.6, shrinkA=1, shrinkB=1))
    ax.text(1.17e6, 2.5e8, "÷5,000", color=SECONDARY, fontsize=7, ha="left", va="center",
            rotation=90)
    log_axis(ax, "x", fmt_count)
    log_axis(ax, "y", fmt_bytes, minor=False)
    ax.set_xlim(7e3, 1.6e6)
    ax.set_ylim(5e3, 1e13)
    ax.set_yticks([1e4, 1e5, 1e6, 1e7, 1e8, 1e9, 1e10, 1e11, 1e12])
    ax.set_xlabel("Cells (n)")
    ax.set_ylabel("Bytes per click (binary)")
    grid(ax)


def panel_latency(ax, scale, pw, grid_):
    """(b) latency per interaction vs n_cells, cold and warm; laptop layers, HPC pairwise rows and gene column."""
    title(ax, "Latency follows payload size")
    ax.axhline(1.0, color=MUTED, lw=0.6, ls=":", zorder=1)
    ax.text(8e3, 1.08, "1 s", color=SECONDARY, fontsize=7, va="bottom", ha="left")
    for cond, ls, filled in (("cold", "-", True), ("warm_new", "--", False)):
        for it, col in (("layer_gene", C_GENE), ("layer_cell", C_CELL)):
            s = by_size(scale[scale.interaction == it], "n_cells", "latency_s", "condition", cond)
            errline(ax, s.n_cells, s.m, s.lo, s.hi, col, M_LAPTOP, ls=ls, filled=filled)
    for phase, ls, filled in (("cold", "-", True), (HPC_WARM, "--", False)):
        s = by_size(pw[pw.matrix == "dist"], "n", "latency_s", "phase", phase)
        errline(ax, s.n, s.m, s.lo, s.hi, C_PAIR, M_HPC, ls=ls, filled=filled)
        g = grid_[(grid_.kind == "dense_layer_gene_col") & (grid_["shape"] == "allx4")]
        s = by_size(g, "n_values", "latency_s", "phase", phase)
        errline(ax, s.n_values, s.m, s.lo, s.hi, C_GENE, M_HPC, ls=ls, filled=filled)
    ax.text(6e5, 0.13, "gene column", color=INK, fontsize=7, ha="right", va="bottom")
    ax.text(1e6, 0.02, "cell row", color=INK, fontsize=7, ha="right", va="top")
    ax.text(4.5e4, 0.45, "pairwise row (HPC)", color=INK, fontsize=7, ha="left", va="bottom")
    log_axis(ax, "x", fmt_count)
    log_axis(ax, "y", fmt_seconds)
    ax.set_xlim(7e3, 1.6e6)
    ax.set_ylim(4e-3, 4)
    ax.set_xlabel("Cells (n)")
    ax.set_ylabel("Time per click")
    grid(ax)


def panel_memory(ax, scale, pw):
    """(c) peak server RSS vs uncompressed matrix size: laptop layers, HPC pairwise matrices."""
    title(ax, "Peak RSS stays far below matrix size")
    xs = np.array([1e8, 3e11])
    ax.plot(xs, xs, color=MUTED, lw=0.8, ls=":", zorder=1)
    ax.text(1.5e9, 1.5e9 * 1.6, "matrix size", color=SECONDARY, fontsize=7,
            ha="right", va="bottom")
    idle_l = float(np.median(scale.rss_base_bytes))
    idle_h = float(np.median(pw[pw.phase == "cold"].server_baseline_rss_mb)) * 2 ** 20
    lo_, hi_ = min(idle_l, idle_h), max(idle_l, idle_h)
    ax.axhspan(lo_, hi_ * 1.02, color=NEUTRAL, lw=0, zorder=0.5)
    ax.text(3.5e11, lo_ * 0.93, f"idle {lo_ / 2 ** 20:.0f}" + (f"–{hi_ / 2 ** 20:.0f}" if round(hi_ / 2 ** 20) != round(lo_ / 2 ** 20) else "")
            + " MiB", color=SECONDARY, fontsize=7, ha="right", va="top")
    sc = scale[scale.condition.isin(["cold", "cold_new"])].copy()
    sc["full"] = sc.n_cells * sc.n_genes * 4.0
    for it, col in (("layer_gene", C_GENE), ("layer_cell", C_CELL)):
        s = by_size(sc[sc.interaction == it], "full", "rss_peak_bytes", "interaction", it)
        errline(ax, s.full, s.m, s.lo, s.hi, col, M_LAPTOP)
    p = pw[(pw.phase == "cold") & pw.matrix.isin(["dist", "corr"])].copy()
    p["full"] = p.n.astype(float) ** 2 * F32
    p["hwm"] = p.server_hwm_mb * 2 ** 20
    s = by_size(p, "full", "hwm", "phase", "cold")
    errline(ax, s.full, s.m, s.lo, s.hi, C_PAIR, M_HPC)
    ax.text(1.6e11, 1.45e8, "pairwise\nrow (HPC)", color=INK, fontsize=7, ha="center", va="bottom")
    log_axis(ax, "x", fmt_bytes)
    log_axis(ax, "y", fmt_mem, minor=False)
    ax.set_xlim(1e8, 4e11)
    ax.set_ylim(4.5e7, 4e11)
    ax.set_xticks([1e8, 1e9, 1e10, 1e11])
    ax.set_yticks([2 ** 27, 2 ** 30, 2 ** 33, 2 ** 36])
    ax.set_xlabel("Matrix size, uncompressed")
    ax.set_ylabel("Server peak RSS")
    grid(ax)


LAPTOP_LABELS = {   # label, text position (data coordinates), ha, va
    "1000000x64": ("whole-gene\n(n, 64)", (0.035, 2.2), "left", "center"),
    "15625x79": ("anndata default\n(15625, 79)", (0.019, 0.22), "left", "center"),
    "1024x1024": ("square\n(1024, 1024)", (0.2, 0.0065), "center", "bottom"),
    "256x4096": ("wide\n(256, 4096)", (1.3, 0.085), "center", "bottom"),
}
GOOD = "#ecebe6"


def chunk_points(sweep, n_cells=1_000_000):
    lap = sweep[(sweep.n_cells == n_cells) & (sweep.condition == "cold")]
    rows = []
    for ch, g in lap.groupby("chunks"):
        gc = med_iqr(g[g.interaction == "layer_gene"].latency_s)
        cr = med_iqr(g[g.interaction == "layer_cell"].latency_s)
        rows.append((ch, *gc, *cr))
    return pd.DataFrame(rows, columns=["chunks", "gm", "glo", "ghi", "cm", "clo", "chi"])


HPC_LABELS = {   # the HPC grid's named shapes: label, text position (data coordinates), ha, va
    "allx4": ("whole-gene (n, 4), HPC", (0.28, 8.0), "right", "center"),
    "8192x64": ("Step 10 (8192, 64)\nHPC", (0.75, 0.6), "left", "center"),
}


def hpc_chunk_points(grid_):
    g = grid_[grid_.phase == "cold"]
    rows = []
    for sh, d in g.groupby("shape"):
        gc = med_iqr(d[d.kind == "dense_layer_gene_col"].latency_s)
        cr = med_iqr(d[d.kind == "dense_layer_cell_row"].latency_s)
        rows.append((sh, *gc, *cr))
    return pd.DataFrame(rows, columns=["shape", "gm", "glo", "ghi", "cm", "clo", "chi"])


def panel_chunks(ax, sweep, grid_=None, labels=True):
    """(d) cold cell row vs cold gene column per chunk shape, 1M cells: laptop (1M x 5k sweep) and HPC grid."""
    title(ax, "Chunk shape trades rows against columns")
    xlim, ylim = (0.015, 6), (5e-3, 12)
    ax.fill_between([xlim[0], 1.0], ylim[0], 1.0, color=GOOD, lw=0, zorder=0)
    ax.text(0.018, 0.85, "both reads\nunder 1 s", color=SECONDARY, fontsize=7,
            ha="left", va="top", linespacing=0.95)
    if grid_ is not None:
        for _, r in hpc_chunk_points(grid_).iterrows():
            named = r["shape"] in HPC_LABELS
            col = INK if named else NEUTRAL
            ax.errorbar(r.gm, r.cm, xerr=[[r.gm - r.glo], [r.ghi - r.gm]],
                        yerr=[[r.cm - r.clo], [r.chi - r.cm]], fmt=M_HPC, ms=MS + 0.5,
                        mfc="white", mec=col, mew=0.9, ecolor=col, elinewidth=0.6, capsize=0,
                        zorder=3 if named else 2)
            if named and labels:
                text, xy, ha, va = HPC_LABELS[r["shape"]]
                ax.annotate(text, (r.gm, r.cm), xytext=xy, textcoords="data", fontsize=7,
                            color=INK, ha=ha, va=va, linespacing=0.95,
                            arrowprops=dict(arrowstyle="-", lw=0.5, color=SECONDARY,
                                            shrinkA=1.5, shrinkB=3))
    if sweep is not None:
        for _, r in chunk_points(sweep).iterrows():
            named = r.chunks in LAPTOP_LABELS
            col = INK if named else NEUTRAL
            ax.errorbar(r.gm, r.cm, xerr=[[r.gm - r.glo], [r.ghi - r.gm]],
                        yerr=[[r.cm - r.clo], [r.chi - r.cm]], fmt=M_LAPTOP, ms=MS + 0.5,
                        mfc=col, mec=col, mew=0.9, ecolor=col, elinewidth=0.6, capsize=0,
                        zorder=3 if named else 2)
            if named and labels:
                text, xy, ha, va = LAPTOP_LABELS[r.chunks]
                ax.annotate(text, (r.gm, r.cm), xytext=xy, textcoords="data", fontsize=7,
                            color=INK, ha=ha, va=va, linespacing=0.95,
                            arrowprops=dict(arrowstyle="-", lw=0.5, color=SECONDARY,
                                            shrinkA=1.5, shrinkB=3))
    log_axis(ax, "x", fmt_seconds, minor=False)
    log_axis(ax, "y", fmt_seconds, minor=False)
    ax.set_xticks([0.1, 1])
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xlabel("Gene column, cold")
    ax.set_ylabel("Cell row, cold")
    grid(ax)


def shared_legend(fig, y):
    h = [
        Line2D([], [], color=C_GENE, lw=LW, label="gene column (one gene, all cells)"),
        Line2D([], [], color=C_CELL, lw=LW, label="cell row (one cell, all genes)"),
        Line2D([], [], color=C_PAIR, lw=LW, label="pairwise row"),
        Line2D([], [], color=SECONDARY, marker=M_LAPTOP, ls="", ms=MS, label="laptop (NVMe)"),
        Line2D([], [], color=SECONDARY, marker=M_HPC, ls="", ms=MS, label="HPC (NFS scratch filer)"),
        Line2D([], [], color=SECONDARY, lw=LW, ls="-", marker="o", ms=MS, label="cold"),
        Line2D([], [], color=SECONDARY, lw=LW, ls="--", marker="o", mfc="white", ms=MS,
               label="warm"),
    ]
    fig.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, y), ncol=4, fontsize=7,
               handlelength=1.6, handletextpad=0.4, columnspacing=1.1, frameon=False)


# --------------------------------------------------------------------------- figures
def fig6(scale, sweep, pw, grid_):
    fig = plt.figure(figsize=(TWO_COL, 5.2))
    gs = fig.add_gridspec(2, 2, hspace=0.45, wspace=0.32, left=0.075, right=0.975,
                          top=0.865, bottom=0.095)
    axes = [fig.add_subplot(gs[i, j]) for i in range(2) for j in range(2)]
    panel_payload(axes[0], scale)
    panel_latency(axes[1], scale, pw, grid_)
    panel_memory(axes[2], scale, pw)
    panel_chunks(axes[3], sweep, grid_)
    for ax, l in zip(axes, "abcd"):
        panel_label(ax, l, x=-0.17, y=1.03)
    shared_legend(fig, 0.995)
    save(fig, "fig6_performance")


def figS_interactions(scale):
    """Supplementary: latency of every laptop interaction vs n_cells, cold and warm."""
    its = [("layer_gene", "gene column"), ("layer_cell", "cell row"),
           ("obsm_col", "obsm column"), ("obs_col", "obs column"),
           ("obsp_knn_row", "kNN graph row"), ("open_cells", "cell names")]
    fig, axes = plt.subplots(2, 3, figsize=(TWO_COL, 3.4), sharex=True, sharey=True)
    for ax, (it, lab) in zip(axes.flat, its):
        d = scale[scale.interaction == it]
        warm = "warm_new" if (d.condition == "warm_new").any() else "warm_repeat"
        for cond, ls, filled, col in (("cold", "-", True, INK), (warm, "--", False, INK)):
            s = by_size(d, "n_cells", "latency_s", "condition", cond)
            errline(ax, s.n_cells, s.m, s.lo, s.hi, col, M_LAPTOP, ls=ls, filled=filled,
                    label="cold" if cond == "cold" else
                    ("warm, new index" if cond == "warm_new" else "warm, same index"))
        ax.axhline(1.0, color=MUTED, lw=0.6, ls=":", zorder=1)
        title(ax, lab)
        log_axis(ax, "x", fmt_count)
        log_axis(ax, "y", fmt_seconds)
        ax.set_ylim(1e-3, 2)
        grid(ax)
        ax.legend(loc="lower right", handlelength=1.8)
    for ax in axes[1]:
        ax.set_xlabel("Cells (n)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Time per click")
    fig.tight_layout(w_pad=1.2, h_pad=1.0)
    save(fig, "figS_interactions")


def figS_chunk_sweep(sweep):
    """Supplementary: the 1M laptop chunk sweep with every shape labelled."""
    fig, ax = plt.subplots(figsize=(ONE_COL, ONE_COL * 0.95))
    panel_chunks(ax, sweep, labels=False)
    for _, r in chunk_points(sweep).iterrows():
        h, w = r.chunks.replace("1000000x", "nx").split("x")
        ax.annotate(f"({h}, {w})" + (" default" if r.chunks == "15625x79" else ""),
                    (r.gm, r.cm), xytext=(5, 0), textcoords="offset points", fontsize=7,
                    color=SECONDARY, ha="left", va="center")
    save(fig, "figS_chunk_sweep")


def main():
    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args()
    apply()
    scale, sweep = load_laptop()
    pw, grid_ = load_hpc()
    fig6(scale, sweep, pw, grid_)
    figS_interactions(scale)
    if sweep is not None:
        figS_chunk_sweep(sweep)


if __name__ == "__main__":
    main()
