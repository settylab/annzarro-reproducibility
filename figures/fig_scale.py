"""Scale: every cell of Tahoe-100M in one plot, and the subset path that keeps it interactive.

Usage:
    python figures/fig_scale.py            # needs scale-benchmarker's results; fails if any is missing
    python figures/fig_scale.py --draft    # draws missing panels as "awaiting data" (layout only)

Inputs
  figures/scale/tahoe95M_umap_*_panel.png      screenshots (figures/scale/README.md)
  benchmark/scale/results/browser_v041_events.csv  browser series on v0.4.1 (summarize_rerun.py)

Writes manuscript/figures/fig_scale.{pdf,png}.

Panels
  a  every cell (95,624,334) by cell line, large-plot mode, size 1, opacity 0.2
  b  every cell by MALAT1, colour scale 0 to 400 counts; the box marks c
  c  the operator's zoom (CVCL_0320's island edge) by MALAT1, every cell at the app's automatic
     size and opacity, opened zoomed from the view link
  d  part 1 of 957 (the default 100,000-cell subset), regular plot, app default size and opacity
  e  browser time per action on the default subset against dataset size (cold)
  f  time to first plot with every cell: regular plot until it fails, large-plot mode beyond
  g  browser tab memory (renderer RSS) and peak JS heap (maxima over runs), subset and every cell
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402
from PIL import Image  # noqa: E402

from figures.style import CAT, GRID, MUTED, SECONDARY, TWO_COL, apply, panel_label, save  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "figures" / "scale"
RES = REPO / "benchmark" / "scale" / "results"
BROWSER = RES / "browser_v041_events.csv"     # every cell and the default subset (all, ceil, sub _v041), tag v0.4.1 = 78c9da6
# What the memory guard allows at default settings (ceiling-benchmarker, AnnZarro v0.3.0 preview 120f322):
# every cell drawn up to max_n_16gb; the guard declines the first plot at first_fail_n.
GUARD = REPO / "benchmark" / "tool_ceiling" / "ceilings.csv"
GUARD_KEY = ("annzarro", "v041")
HEAPCAP = RES / "heapcap_v041.jsonl"          # the tab's V8 heap limit, default flags (Chromium 153; with the v0.4.1 series)
CLEAN_BEFORE = pd.Timestamp("2026-10-03 17:57", tz="UTC").timestamp()
N_TAHOE = 95_624_334
LARGE_PLOT_POINTS = 1_000_000      # v0.4.1 (DEFAULT_LARGE_PLOT_POINTS): plots of more than 1M points switch to large-plot mode

# Plot areas in the 3196-px-wide panel screenshots (x0, y0, x1, y1), found from the axis lines.
# The app's notice, tick labels and legend are 12 CSS px, unreadable at print size, so the panels
# keep only the plot area (and b its colour bar); the status bar below is restated in the caption.
PLOT_BOX = (152, 162, 2813, 1517)            # 1678-px-high every-cell shots (status bar below)
SUB_BOX = (152, 162, 2813, 1473)             # 1634-px-high subset shot
# b and c (MALAT1 shots with a colour bar): the plot area runs between the axis lines,
# x 151-2931 and y 162-1518 px; each shot's view.json records the axis ranges drawn there.
GENE_BOX, CBAR_BOX = (152, 162, 2935, 1517), (3009, 183, 3067, 1489)
AXES_PX = (151, 2931, 162, 1518)
B_SHOT, C_SHOT = "tahoe95M_malat1_all_gene", "tahoe95M_malat1_zoom_all_gene"
SHOT_PANELS = [
    ("a", "tahoe95M_umap_all_cat_panel.png", [PLOT_BOX], "Every cell (95.6M) by cell line"),
    ("b", f"{B_SHOT}_panel.png", [GENE_BOX, CBAR_BOX], "Every cell by MALAT1"),
    ("c", f"{C_SHOT}_panel.png", [GENE_BOX], "Zoom into the box in b"),
    ("d", "tahoe95M_umap_default_sub_cat_panel.png", [SUB_BOX], "Part 1 of 957: 100,000 cells"),
]
CBAR_TICKS = ("0", "400 counts")


def drawn_range(name):
    """Axis ranges (x0, x1, y0, y1) drawn in a shot, from its view.json."""
    return json.loads(need(SHOTS / f"{name}.view.json").read_text())["drawn"]["range_xy"]

PERF_TITLES = {"e": "Default subset (100,000 cells)", "f": "Every cell in one plot",
               "g": "V8 heap at the first plot"}


class Missing(Exception):
    pass


def need(path):
    if not path.exists():
        raise Missing(f"{path.relative_to(REPO)} is missing (waiting for scale-benchmarker)")
    return path


# ---------------------------------------------------------------- screenshots

def shot(name, boxes, gap=50):
    """Crop each box and set the crops side by side, top-aligned, on white."""
    im = Image.open(need(SHOTS / name)).convert("RGB")
    crops = [im.crop(b) for b in boxes]
    out = Image.new("RGB", (sum(c.width for c in crops) + gap * (len(crops) - 1),
                            max(c.height for c in crops)), "white")
    x = 0
    for c, b in zip(crops, boxes):
        out.paste(c, (x, b[1] - boxes[0][1]))
        x += c.width + gap
    return out


# ---------------------------------------------------------------- benchmark data
# The user live-tested on the 95.6M store from about 17:57Z on 2026-10-03, so a row after
# CLEAN_BEFORE (or a row without a time) is used only if scale-benchmarker marked it clean.
INCLUDE_UNCLEAN = False            # --include-unclean: layout previews only, never the manuscript


def clean_rows(d, name):
    keep = d.time < CLEAN_BEFORE if "time" in d else pd.Series(False, index=d.index)
    if "clean" in d:
        keep |= d.clean.astype(str).str.lower().isin(["1", "true"])
    if INCLUDE_UNCLEAN:
        keep[:] = True
    print(f"fig_scale: {name}: {int(keep.sum())} of {len(d)} rows used"
          + ("" if INCLUDE_UNCLEAN else " (rows after 17:57Z need clean=true)"))
    return d[keep].copy()


def load_browser():
    """scale-benchmarker's browser events (one row per event) and every-cell attempts beyond 95.6M."""
    d = clean_rows(pd.read_csv(need(BROWSER)), BROWSER.name)
    d["kind"] = np.select([d.tag == "sub_v041", d.tag == "all_v041", d.tag == "ceil_v041"],
                          ["sub", "all", "syn"], "other")
    # The reported ceiling is what the guard allows (user decision): every-cell points above
    # the guard's largest allowed size are not drawn; the guard's refusal is the rule.
    g = pd.read_csv(need(GUARD)).set_index(["tool", "variant"]).loc[GUARD_KEY]
    if "guard_refusal" not in str(g.first_fail):
        raise Missing(f"{GUARD.name} {GUARD_KEY}: first_fail is {g.first_fail!r}, not a guard refusal")
    c = {"allowed": int(g.max_n_16gb), "declined": int(g.first_fail_n)}
    return d, c


def heap_limit():
    """The tab's jsHeapSizeLimit under default flags, from heapcap.py's record."""
    for ln in need(HEAPCAP).read_text().splitlines():
        m = re.search(r"lim (\d+)", ln)
        if m:
            return int(m.group(1))
    raise Missing(f"no heap limit in {HEAPCAP.name}")


def stats(d, col="seconds"):
    """N -> (median, min, max) of `col` over ok events (memory: the maximum, three times),
    and the smallest N where any event failed."""
    ok = d[d.status == "ok"]
    if col == "seconds":
        s = ok.groupby("n_cells")[col].agg(["median", "min", "max"])
    else:
        m = ok.groupby("n_cells")[col].max() * 1e9
        s = pd.concat([m, m, m], axis=1, keys=["median", "min", "max"])
    bad = d[d.status != "ok"].n_cells
    return s.dropna(), (int(bad.min()) if len(bad) else None)


# ---------------------------------------------------------------- axes helpers

def fmt_count(v, _=None):
    return f"{v / 1e6:g}M" if v >= 1e6 else (f"{v / 1e3:g}k" if v >= 1e3 else f"{v:g}")


def fmt_s(v, _=None):
    return f"{v:g} s" if v >= 1 else f"{v * 1e3:g} ms"


def fmt_b(v, _=None):
    for u, f in (("GB", 1e9), ("MB", 1e6)):
        if v >= f * 0.999:
            return f"{v / f:g} {u}"
    return f"{v:g} B"


def fmt_mem(v, _=None):
    """Memory in binary units (the paper's convention): 64 MiB ... 8 GiB."""
    for u, f in (("GiB", 2 ** 30), ("MiB", 2 ** 20)):
        if v >= f * 0.999:
            return f"{v / f:g} {u}"
    return f"{v:g} B"


def logax_mem(ax):
    """Log y axis for memory with ticks at powers of two."""
    ax.set_yscale("log", base=2)
    ax.yaxis.set_major_locator(LogLocator(base=2, numticks=12))
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_mem))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.grid(True, which="major", axis="y", color=GRID, lw=0.5)


def logax(ax, which, fmt):
    axis = ax.xaxis if which == "x" else ax.yaxis
    (ax.set_xscale if which == "x" else ax.set_yscale)("log")
    axis.set_major_locator(LogLocator(base=10, subs=(1.0,) if which == "x" else (1.0, 2.0, 5.0),
                                      numticks=12))
    axis.set_major_formatter(FuncFormatter(fmt))
    axis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10) * 0.1, numticks=12))
    axis.set_minor_formatter(NullFormatter())
    ax.grid(True, which="major", axis="y", color=GRID, lw=0.5)


def line(ax, s, fail, color, ls="-", label=None):
    if len(s):
        ax.plot(s.index, s["median"], ls=ls, color=color, marker="o", ms=2.5, lw=1.1)
        ax.vlines(s.index, s["min"], s["max"], color=color, lw=0.6)
        if label:
            ax.annotate(label, (s.index[-1], s["median"].iloc[-1]), xytext=(3, 0),
                        textcoords="offset points", fontsize=7, color=SECONDARY, va="center")
    if fail is not None:
        y = s["median"].iloc[-1] if len(s) else 1
        ax.plot([fail], [y], marker="x", color=color, ms=5, mew=1.2)


def cells_axis(ax):
    logax(ax, "x", fmt_count)
    ax.set_xlim(7e5, 2.6e8)
    ax.set_xlabel("Cells in the dataset")


def awaiting(ax, err):
    ax.text(0.5, 0.5, "awaiting scale-benchmarker\n" + str(err).split(" (waiting")[0],
            transform=ax.transAxes, ha="center", va="center", fontsize=7, color="red", wrap=True)
    ax.set_xticks([]); ax.set_yticks([])


# ---------------------------------------------------------------- performance panels
# Keys sit in a legend row above each panel: direct labels collided at print size.

SUB_EVENTS = [("first_plot", "open, first plot", CAT[0]), ("balance", "balanced subset", CAT[3]),
              ("part_step", "next part", CAT[2]), ("recolour", "recolour by a gene", CAT[1])]


def key(ax, handles, ncol=2):
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=ncol,
              fontsize=7, frameon=False, handlelength=1.3, handletextpad=0.4,
              columnspacing=0.9, borderaxespad=0.15, labelspacing=0.3)


def swatch(colour, label, mfc=None):
    return Line2D([], [], color=colour, marker="o", ms=2.5, mfc=mfc or colour, lw=1.1, label=label)


def mode_rule(ax, y=0.02, va="bottom"):
    """The large-plot threshold: plots of more than LARGE_PLOT_POINTS switch (the point at it is regular)."""
    ax.axvline(LARGE_PLOT_POINTS, color=MUTED, lw=0.5, ls=":")
    ax.text(LARGE_PLOT_POINTS * 1.1, y, "large-plot\nmode above", transform=ax.get_xaxis_transform(),
            fontsize=7, color=SECONDARY, ha="left", va=va)


def guard_rule(ax, c, y=0.02, va="bottom"):
    """The size at which the memory guard declines the first plot (ceilings.csv)."""
    n = c["declined"]
    ax.axvline(n, color=MUTED, lw=0.5, ls=":")
    ax.text(n * 1.08, y, f"guard\ndeclines\n{fmt_count(n)}", transform=ax.get_xaxis_transform(),
            fontsize=7, color=SECONDARY, ha="left", va=va)


def panel_subset(ax, data):
    b, _ = data
    d = b[(b.kind == "sub") & (b.color == "gene")]
    for ev, lab, c in SUB_EVENTS:
        s, fail = stats(d[d.event == ev])
        if not len(s):
            raise Missing(f"no subset '{ev}' events in {BROWSER.name}")
        line(ax, s, fail, c)
    cells_axis(ax); logax(ax, "y", fmt_s)
    key(ax, [swatch(c, lab) for _, lab, c in SUB_EVENTS])
    ax.set_ylabel("Browser time (cold)")


def panel_every_cell(ax, data):
    b, c = data
    d = b[(b.kind == "all") & (b.event == "first_plot")]
    if not len(d):
        raise Missing(f"no every-cell first_plot events in {BROWSER.name}")
    # One ladder per colouring: Tahoe-100M up to its 95.6M cells, the larger stores above
    # (Supplementary Note 1 says which are synthetic; the figure does not split them).
    syn = b[(b.kind == "syn") & (b.event == "first_plot") & (b.n_cells > N_TAHOE)
            & (b.n_cells <= c["allowed"])]
    for col, colour in (("cat", CAT[0]), ("gene", CAT[1])):
        g = d[d.color == col]
        line(ax, stats(g[g.large_mode != 1])[0], None, colour)
        big = pd.concat([g[g.large_mode == 1], syn[syn.color == col]])
        line(ax, stats(big)[0], None, colour)
    mode_rule(ax, y=0.98, va="top")
    guard_rule(ax, c, y=0.98, va="top")
    cells_axis(ax); logax(ax, "y", fmt_s)
    ax.set_ylim(0.6, 120)
    key(ax, [swatch(CAT[0], "by cell line"), swatch(CAT[1], "by gene")])
    ax.set_ylabel("Time to first plot (cold)")


def panel_memory(ax, data):
    b, c = data
    d = b[b.event == "first_plot"]
    every = pd.concat([d[d.kind == "all"],
                       d[(d.kind == "syn") & (d.n_cells > N_TAHOE) & (d.n_cells <= c["allowed"])]])
    # every cell as two lines, as in f: the regular plot, then large-plot mode
    for rows, colour, lab in ((d[d.kind == "sub"], CAT[2], "subset"),
                              (every[every.large_mode != 1], CAT[0], "every cell, regular"),
                              (every[every.large_mode == 1], CAT[0], "every cell, large-plot")):
        s = stats(rows, "v8_used_peak_gb")[0]
        if not len(s):
            raise Missing(f"no {lab} heap records in {BROWSER.name}")
        line(ax, s, None, colour)
    lim = heap_limit()
    ax.axhline(lim, color=MUTED, lw=0.6, ls="--")
    ax.text(1.2e8, lim / 1.1, f"tab's heap limit {lim / 2 ** 30:.1f} GiB", fontsize=7,
            color=SECONDARY, va="top", ha="right")
    mode_rule(ax, y=0.66, va="top")      # below the heap-limit line and its label
    guard_rule(ax, c, y=0.66, va="top")
    cells_axis(ax); logax_mem(ax)
    ax.set_ylim(2 ** 23, 2 ** 33)      # v0.4.1: large-plot mode keeps tens of MiB on the V8 heap
    key(ax, [swatch(CAT[0], "every cell"), swatch(CAT[2], "default subset")], ncol=2)
    ax.set_ylabel("V8 heap, peak at first plot")


# ---------------------------------------------------------------- figure

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-unclean", action="store_true",
                    help="layout preview with rows not marked clean; needs --out outside manuscript/")
    ap.add_argument("--out", type=Path, default=None, help="output directory (default manuscript/figures)")
    ap.add_argument("--draft", action="store_true",
                    help="draw panels whose data are missing as 'awaiting scale-benchmarker'")
    a = ap.parse_args()
    global INCLUDE_UNCLEAN
    INCLUDE_UNCLEAN = a.include_unclean
    if INCLUDE_UNCLEAN and (a.out is None or "manuscript" in str(a.out.resolve())):
        raise SystemExit("fig_scale: --include-unclean writes previews only; pass --out outside manuscript/")
    apply()

    shots = {k: (shot(f, boxes), t) for k, f, boxes, t in SHOT_PANELS}
    # The figure takes a whole page (caption on the next): a and b full width, c and d half.
    # The page fits the text block (465 x 711 pt) at scale 1, so a and b are drawn a little
    # narrower than the full width.
    W, gap, title_h, cbar_room, ab = TWO_COL, 0.2, 0.2, 0.62, 0.86
    half = (W - gap) / 2
    widths = {"a": (W - cbar_room) * ab, "b": (W - cbar_room) * ab, "c": half - 0.05, "d": half - 0.05}
    # d is cropped like a (same UMAP extent), so they read as the same space; c is a zoom.
    heights = {k: widths[k] * shots[k][0].height / shots[k][0].width for k in shots}
    widths["b"] *= heights["a"] / heights["b"]          # b at a's height: same scale for both
    heights["b"] = heights["a"]
    perf_h, perf_bottom = 1.55, 0.38
    rows = [("a",), ("b",), ("c", "d")]
    row_h = [max(heights[k] for k in r) for r in rows]
    H = sum(row_h) + title_h * len(rows) + 0.75 + perf_h + perf_bottom
    fig = plt.figure(figsize=(W, H))

    axes, top = {}, H
    for r, rh in zip(rows, row_h):
        top -= title_h
        for c, k in enumerate(r):
            im, t = shots[k]
            w, h = widths[k], heights[k]
            ax = fig.add_axes([c * (half + gap) / W, (top - h) / H, w / W, h / H])
            # 300 px per figure inch (about 330 dpi once the page scales the figure to the text
            # width) keeps the PDF small; coordinates stay in the full screenshot's pixels.
            small = im.resize((round(w * 300), round(h * 300)), Image.LANCZOS)
            ax.imshow(small, interpolation="none", extent=(0, im.width, im.height, 0))
            ax.set_axis_off()
            ax.text(0.03 if len(r) == 1 else 0.05, 1.01, t, transform=ax.transAxes, fontsize=7,
                    fontweight="bold", va="bottom")
            panel_label(ax, k, x=0.0, y=1.01)
            axes[k] = (ax, im)
        top -= rh

    # c: its extent, so the dots read as cells and not as noise
    ax, _ = axes["c"]
    zx0, zx1, zy0, zy1 = drawn_range(C_SHOT)
    ax.text(0.985, 0.03, f"{zx1 - zx0:.2f} × {zy1 - zy0:.2f} UMAP units; each dot is one cell",
            transform=ax.transAxes, fontsize=7, va="bottom", ha="right",
            bbox=dict(boxstyle="square,pad=0.25", fc="white", ec="none"))

    # b: where c looks, from b's drawn ranges (pixels relative to the crop's corner)
    ax, _ = axes["b"]
    bx0, bx1, by0, by1 = drawn_range(B_SHOT)
    px0, px1, py0, py1 = AXES_PX
    to_x = lambda v: px0 + (v - bx0) / (bx1 - bx0) * (px1 - px0) - GENE_BOX[0]   # noqa: E731
    to_y = lambda v: py1 - (v - by0) / (by1 - by0) * (py1 - py0) - GENE_BOX[1]   # noqa: E731
    ax.add_patch(plt.Rectangle((to_x(zx0), to_y(zy1)), to_x(zx1) - to_x(zx0), to_y(zy0) - to_y(zy1),
                               fill=False, ec="black", lw=0.8))
    ax.annotate("c", (to_x(zx1), to_y(zy1)), xytext=(2, 2), textcoords="offset points",
                fontsize=7, fontweight="bold")
    # b: colour bar ends
    ax, im = axes["b"]
    cb_x = im.width + 6
    ax.text(cb_x, CBAR_BOX[3] - PLOT_BOX[1], CBAR_TICKS[0], fontsize=7, va="bottom",
            color=SECONDARY, clip_on=False)
    ax.text(cb_x, CBAR_BOX[1] - PLOT_BOX[1], CBAR_TICKS[1], fontsize=7, va="top",
            color=SECONDARY, clip_on=False)

    try:
        b, err = load_browser(), None
    except Missing as e:
        b, err = None, e
    left, sep = 0.5, 1.0
    gw = (W - left - 2 * sep - 0.75) / 3
    for j, (k, fn) in enumerate((("e", panel_subset), ("f", panel_every_cell), ("g", panel_memory))):
        ax = fig.add_axes([(left + j * (gw + sep)) / W, perf_bottom / H, gw / W, perf_h / H])
        panel_label(ax, k, x=-0.3, y=1.205)
        ax.set_title(PERF_TITLES[k], loc="left", pad=30)
        try:
            if err:
                raise err
            fn(ax, b)
        except Missing as e:
            if not a.draft:
                raise SystemExit(f"fig_scale: {e}. Use --draft for a layout check.")
            awaiting(ax, e)
    save(fig, "fig_scale", **({"outdir": a.out} if a.out else {}))


if __name__ == "__main__":
    main()
