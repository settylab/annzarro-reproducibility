#!/usr/bin/env python
"""Figures for the AnnZarro benchmark (reads results/*.csv, writes plots/*.pdf|png).

Style: Nature-like, 7 pt text, single column 89 mm / double column 183 mm,
colour-blind-safe categorical palette (validated order: blue, orange, aqua,
yellow, magenta, ...), marker shape as a secondary encoding, log axes wherever
scaling is shown.  Points are medians, error bars span the IQR.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, LogLocator

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
OUT = HERE / "plots"
MANIFEST = HERE.parent / "data" / "bench" / "manifest.json"
MM = 1 / 25.4
SINGLE, DOUBLE = 89 * MM, 183 * MM

PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]

mpl.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 7, "axes.titlesize": 7, "axes.labelsize": 7, "xtick.labelsize": 6,
    "ytick.labelsize": 6, "legend.fontsize": 6, "axes.linewidth": 0.6,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.minor.width": 0.4,
    "ytick.minor.width": 0.4, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.4, "axes.axisbelow": True,
    "lines.linewidth": 1.2, "lines.markersize": 3.5, "legend.frameon": False,
    "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.dpi": 300, "figure.dpi": 150,
    "axes.titleweight": "bold", "axes.titlelocation": "left",
})


# ---------------------------------------------------------------- helpers
def q(x):
    return pd.Series({"med": np.median(x), "q1": np.percentile(x, 25), "q3": np.percentile(x, 75), "n": len(x)})


def summarise(df, by, col="latency_s"):
    """Median, IQR and n of ``col`` per group (empty frame if no rows)."""
    g = df.groupby(by)[col]
    return pd.DataFrame({"med": g.median(), "q1": g.quantile(0.25), "q3": g.quantile(0.75),
                         "n": g.size()}).reset_index()


def fmt_count(x, _=None):
    if x >= 1e6:
        return f"{x / 1e6:g}M"
    if x >= 1e3:
        return f"{x / 1e3:g}k"
    return f"{x:g}"


def fmt_bytes(x, _=None):
    for unit, s in [("TB", 1e12), ("GB", 1e9), ("MB", 1e6), ("kB", 1e3)]:
        if x >= s:
            return f"{x / s:.3g} {unit}"
    return f"{x:.3g} B"


def fmt_seconds(x, _=None):
    if x >= 1:
        return f"{x:.3g} s"
    return f"{x * 1e3:.3g} ms"


def errline(ax, x, s, color, marker, label, ls="-", ms=None, zorder=3):
    yerr = np.vstack([s["med"] - s["q1"], s["q3"] - s["med"]])
    ax.errorbar(x, s["med"], yerr=yerr, color=color, marker=marker, ls=ls, label=label, capsize=1.5,
                elinewidth=0.6, capthick=0.6, ms=ms or mpl.rcParams["lines.markersize"],
                mec="white", mew=0.4, zorder=zorder)


def logx_counts(ax):
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(fmt_count))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda *_: ""))


def logy(ax, fmt):
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(LogLocator(base=10))
    ax.yaxis.set_major_formatter(FuncFormatter(fmt))


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    for ext in ["pdf", "png"]:
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


def manifest():
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


LABELS = {
    "layer_gene": "Gene column, dense layer",
    "layer_cell": "Cell row, dense layer",
    "obsm_col": "obsm column (X_umap)",
    "obs_col": "obs float column",
    "obsp_knn_row": "Row of sparse kNN obsp",
    "open_cells": "Cell names (dataset open)",
    "open_structure": "Dataset structure (open)",
}
COND = {"cold": ("Cold (new process, uncached store)", PAL[1], "s", "-"),
        "warm_new": ("Warm, new index", PAL[0], "o", "-"),
        "warm_repeat": ("Warm, same index", PAL[2], "^", "--")}


# ---------------------------------------------------------------- Fig A, B: scale
def fig_scale():
    df = pd.read_csv(RES / "scale.csv")
    df = df[df.status == 200]
    man = manifest()
    inters = ["layer_gene", "layer_cell", "obsm_col", "obs_col", "obsp_knn_row", "open_cells"]

    # --- A: payload bytes vs n_cells
    fig, ax = plt.subplots(figsize=(SINGLE, 60 * MM))
    b = df[df.condition == "warm_repeat"].groupby(["interaction", "n_cells"]).bytes.median().reset_index()
    for k, it in enumerate(inters):
        s = b[b.interaction == it]
        ax.plot(s.n_cells, s.bytes, marker=MARKERS[k], color=PAL[k], label=LABELS[it], mec="white", mew=0.4)
    ns = np.array(sorted(df.n_cells.unique()))
    ax.plot(ns, ns * 5000 * 4, color=INK2, ls="--", lw=0.8, label="Full dense layer, float32 in memory")
    disk = {v["n_cells"]: v["layer"]["disk_bytes"] if "disk_bytes" in v.get("layer", {}) else v["disk_bytes"]
            for v in man.values() if v.get("family") == "scale"}
    if disk:
        xs = sorted(disk)
        ax.plot(xs, [disk[x] for x in xs], color=INK2, ls=":", lw=0.8, label="Whole store on disk")
    logx_counts(ax)
    logy(ax, fmt_bytes)
    ax.set_xlabel("Cells")
    ax.set_ylabel("Bytes per request (JSON)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=2, handlelength=2.2)
    save(fig, "figA_bytes_vs_cells")

    # --- B: latency small multiples
    inters_b = ["layer_gene", "layer_cell", "obsm_col", "obs_col", "obsp_knn_row", "open_cells"]
    fig, axes = plt.subplots(2, 3, figsize=(DOUBLE, 95 * MM), sharex=True, sharey=True)
    for ax, it in zip(axes.flat, inters_b):
        d = df[df.interaction == it]
        for cond, (lab, col, mk, ls) in COND.items():
            s = summarise(d[d.condition == cond], "n_cells")
            if len(s):
                errline(ax, s.n_cells, s, col, mk, lab, ls=ls)
        ax.set_title(LABELS[it])
        logx_counts(ax)
        logy(ax, fmt_seconds)
    for ax in axes[1]:
        ax.set_xlabel("Cells")
    for ax in axes[:, 0]:
        ax.set_ylabel("Latency per request")
    axes[0, 0].legend(loc="upper left")
    fig.tight_layout()
    save(fig, "figB_latency_vs_cells")


# ---------------------------------------------------------------- Fig C: chunk sweep
def chunk_order(df):
    """Sort chunk shapes by aspect (tall-narrow first), then size."""
    def key(c):
        h, w = map(int, c.split("x"))
        return (-h / w, h * w)
    return sorted(df.chunks.unique(), key=key)


def fig_sweep():
    df = pd.read_csv(RES / "sweep.csv")
    df = df[df.status == 200]
    sizes = sorted(df.n_cells.unique())
    conds = [("cold", "Cold", "s"), ("warm_new", "Warm, new index", "o")]
    fig, axes = plt.subplots(1, len(sizes), figsize=(DOUBLE, 80 * MM), sharey=False)
    axes = np.atleast_1d(axes)
    for ax, n in zip(axes, sizes):
        d = df[df.n_cells == n]
        order = chunk_order(d)
        y = np.arange(len(order))
        for j, (it, col) in enumerate([("layer_gene", PAL[0]), ("layer_cell", PAL[1])]):
            for k, (cond, clab, mk) in enumerate(conds):
                s = summarise(d[(d.interaction == it) & (d.condition == cond)], "chunks").set_index("chunks").reindex(order)
                off = (j * 2 + k - 1.5) * 0.17
                ax.errorbar(s.med, y + off, xerr=np.vstack([s.med - s.q1, s.q3 - s.med]), fmt=mk, color=col,
                            mfc=col if cond == "warm_new" else "white", mec=col, mew=0.8, ms=3.5,
                            elinewidth=0.6, capsize=1.2,
                            label=f"{'Gene column' if it == 'layer_gene' else 'Cell row'}, {clab.lower()}")
        tags = d.drop_duplicates("chunks").set_index("chunks").chunk_tag
        ylabels = [f"{c.replace('x', ' × ')}" + ("  (default)" if tags.get(c) == "default" else "") for c in order]
        ax.set_yticks(y, ylabels)
        ax.invert_yaxis()
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(FuncFormatter(fmt_seconds))
        ax.set_xlabel("Latency per request")
        ax.set_title(f"{fmt_count(n)} cells × 5,000 genes, float32")
        ax.grid(axis="y", visible=False)
    axes[0].set_ylabel("Chunk shape (cells × genes)")
    axes[-1].legend(loc="lower right", fontsize=5.5)
    fig.tight_layout()
    save(fig, "figC_chunk_sweep")

    # data volume each request must decompress (analytic; drives latency on slow storage)
    fig, axes = plt.subplots(1, len(sizes), figsize=(DOUBLE, 70 * MM))
    axes = np.atleast_1d(axes)
    rows = []
    for ax, n in zip(axes, sizes):
        d = df[df.n_cells == n]
        order = chunk_order(d)
        y = np.arange(len(order))
        g = 5000
        vol_gene, vol_cell = [], []
        for c in order:
            h, w = map(int, c.split("x"))
            vol_gene.append(np.ceil(n / h) * h * w * 4)
            vol_cell.append(np.ceil(g / w) * h * w * 4)
            rows.append(dict(n_cells=n, chunks=c, chunk_bytes=h * w * 4,
                             chunks_per_gene=int(np.ceil(n / h)), bytes_per_gene=vol_gene[-1],
                             chunks_per_cell=int(np.ceil(g / w)), bytes_per_cell=vol_cell[-1]))
        ax.scatter(vol_gene, y - 0.12, color=PAL[0], marker="o", s=14, label="Gene column", zorder=3)
        ax.scatter(vol_cell, y + 0.12, color=PAL[1], marker="s", s=14, label="Cell row", zorder=3)
        tags = d.drop_duplicates("chunks").set_index("chunks").chunk_tag
        ax.set_yticks(y, [c.replace("x", " × ") + ("  (default)" if tags.get(c) == "default" else "") for c in order])
        ax.invert_yaxis()
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(FuncFormatter(fmt_bytes))
        ax.set_xlabel("Uncompressed chunk data read per request")
        ax.set_title(f"{fmt_count(n)} cells × 5,000 genes")
        ax.grid(axis="y", visible=False)
    axes[0].set_ylabel("Chunk shape (cells × genes)")
    axes[-1].legend(loc="lower right")
    fig.tight_layout()
    save(fig, "figC2_chunk_read_volume")
    pd.DataFrame(rows).to_csv(RES / "chunk_read_volume.csv", index=False)


# ---------------------------------------------------------------- Fig D: memory
def fig_memory():
    rows = []
    man = manifest()
    for exp in ["scale", "sweep", "obsp", "varp", "sparse"]:
        p = RES / f"{exp}.csv"
        if not p.exists():
            continue
        d = pd.read_csv(p)
        # cold phases use one fresh server per interaction, so RSS is attributable
        d = d[(d.status == 200) & d.condition.isin(["cold", "cold_new"])]
        for (store, it, chunks), g in d.groupby(["store", "interaction", "chunks"]):
            m = g.iloc[0]
            if exp == "sparse":
                mi = man.get(store, {})
                full = mi.get("nnz", np.nan) * 8 + (m.n_cells + 1) * 8  # data f32 + indices i32 (+indptr)
                fam = f"sparse X ({m.chunk_tag.upper()})"
            elif exp in ("obsp", "varp"):
                nn = m.n_cells if exp == "obsp" else m.n_genes
                full = nn * nn * 4
                fam = "dense obsp/varp"
            else:
                if it not in ("layer_gene", "layer_cell"):
                    continue
                full = m.n_cells * m.n_genes * 4
                fam = "dense layer"
            rows.append(dict(exp=exp, store=store, interaction=it, chunks=chunks, family=fam, full=full,
                             peak=g.rss_peak_bytes.max(), base=g.rss_base_bytes.median(),
                             delta=(g.rss_peak_bytes - g.rss_base_bytes).max()))
    r = pd.DataFrame(rows)
    if r.empty:
        return
    r.to_csv(RES / "memory_summary.csv", index=False)
    fig, ax = plt.subplots(figsize=(SINGLE, 70 * MM))
    fams = ["dense layer", "dense obsp/varp", "sparse X (CSC)", "sparse X (CSR)"]
    for k, fam in enumerate(fams):
        s = r[r.family == fam]
        if s.empty:
            continue
        hollow = fam.endswith("(CSC)")
        ax.scatter(s.full, s.peak, s=22 if hollow else 12, marker=MARKERS[k], zorder=4 if hollow else 3,
                   facecolor="none" if hollow else PAL[k], edgecolor=PAL[k], lw=0.9 if hollow else 0.3,
                   label=fam)
    big_sparse = r[r.family.str.startswith("sparse") & (r.peak > 2e9)]
    if len(big_sparse):
        x0, y0 = big_sparse.full.max(), big_sparse.peak.max()
        ax.annotate("1M cells: CSR gene column,\nCSC cell row (whole matrix loaded)", (x0, y0), fontsize=5,
                    color=INK2, xytext=(8, -16), textcoords="offset points", ha="left", va="top",
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=0.4))
    big_dense = r[(r.family == "dense layer") & (r.peak > 2e9)]
    for _, row in big_dense.iterrows():
        ax.annotate(f"cell row, chunks\n{row.chunks.replace('x', ' × ')}", (row.full, row.peak), fontsize=5,
                    color=INK2, xytext=(-6, 10), textcoords="offset points", ha="right", va="bottom",
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=0.4))
    lim = np.array([r.full.min() / 2, r.full.max() * 2])
    ax.plot(lim, lim, color=INK2, ls="--", lw=0.8, label="Whole matrix in memory")
    ax.axhline(r.base.median(), color=INK2, ls=":", lw=0.8, label="Idle server")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(fmt_bytes))
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_bytes))
    ax.set_xlabel("Matrix size, uncompressed")
    ax.set_ylabel("Server peak RSS during request")
    ax.legend(loc="upper left")
    save(fig, "figD_server_memory")


# ---------------------------------------------------------------- Fig E: sparse
def fig_sparse():
    p = RES / "sparse.csv"
    if not p.exists():
        return
    df = pd.read_csv(p)
    df = df[df.status == 200]
    fig, axes = plt.subplots(1, 2, figsize=(SINGLE * 1.25, 55 * MM), sharey=True)
    for ax, it, title in zip(axes, ["X_gene", "X_cell"], ["Gene column of X", "Cell row of X"]):
        d = df[df.interaction == it]
        sizes = sorted(d.n_cells.unique())
        x = np.arange(len(sizes))
        for j, (lay, col, mk) in enumerate([("csr", PAL[1], "s"), ("csc", PAL[0], "o")]):
            for k, (cond, ls) in enumerate([("cold", 1), ("warm_new", 0)]):
                s = summarise(d[(d.chunk_tag == lay) & (d.condition == cond)], "n_cells").set_index("n_cells").reindex(sizes)
                off = (j * 2 + k - 1.5) * 0.12
                ax.errorbar(x + off, s.med, yerr=np.vstack([s.med - s.q1, s.q3 - s.med]), fmt=mk, color=col,
                            mfc=col if cond == "warm_new" else "white", mec=col, mew=0.8, ms=4, elinewidth=0.6,
                            capsize=1.2, label=f"{lay.upper()}, {'cold' if cond == 'cold' else 'warm'}")
        ax.set_xticks(x, [f"{fmt_count(n)} cells" for n in sizes])
        ax.set_xlim(-0.6, len(sizes) - 0.4)
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(FuncFormatter(fmt_seconds))
        ax.set_title(title)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Latency per request")
    axes[0].legend(loc="upper left", fontsize=5.5)
    fig.tight_layout()
    save(fig, "figE_sparse_csr_csc")


# ---------------------------------------------------------------- Fig G: breakdown
def fig_breakdown():
    p = RES / "breakdown.csv"
    if not p.exists():
        return
    df = pd.read_csv(p)
    df["t_other_s"] = (df.t_http_s - df.t_read_s - df.t_tolist_s - df.t_jsonify_s).clip(lower=0)
    comp = [("t_read_s", "zarr read (+ densify)", PAL[0]), ("t_tolist_s", "ndarray.tolist()", PAL[1]),
            ("t_jsonify_s", "Flask jsonify", PAL[2]), ("t_other_s", "HTTP, werkzeug, client parse", PAL[3])]
    m = df.groupby(["store", "interaction"]).median(numeric_only=True).reset_index()
    m = m[m.n_cells.isin([100_000, 1_000_000])]
    m["label"] = m.apply(lambda r: f"{LABELS.get(r.interaction, r.interaction.replace('_', ' '))} · {fmt_count(r.n_cells)}"
                         + (f" · {Path(r.store).stem.split('_')[-1].upper()}" if r.interaction.startswith('X_') else ""), axis=1)
    m = m.sort_values(["n_cells", "t_http_s"])
    fig, ax = plt.subplots(figsize=(DOUBLE * 0.75, (20 + 5 * len(m)) * MM))
    y = np.arange(len(m))
    left = np.zeros(len(m))
    for c, lab, col in comp:
        ax.barh(y, m[c], left=left, color=col, label=lab, height=0.7, edgecolor="white", lw=0.5)
        left += m[c].values
    for yi, (tot, b) in enumerate(zip(m.t_http_s, m.bytes)):
        ax.text(tot * 1.02, yi, f"{fmt_seconds(tot)}  ({fmt_bytes(b)})", va="center", fontsize=5.5, color=INK2)
    ax.set_yticks(y, m.label)
    ax.invert_yaxis()
    ax.set_xlabel("Median time per warm request (linear)")
    ax.set_xlim(0, left.max() * 1.35)
    ax.xaxis.set_major_formatter(FuncFormatter(fmt_seconds))
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.4, 1.0), ncol=4, fontsize=5.5)
    save(fig, "figG_time_breakdown")


if __name__ == "__main__":
    for f in [fig_sweep, fig_scale, fig_memory, fig_sparse, fig_breakdown]:
        try:
            f()
        except FileNotFoundError as e:
            print("skip", f.__name__, e)
