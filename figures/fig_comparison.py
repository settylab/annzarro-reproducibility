"""Feature matrix: AnnZarro against other single-cell viewers.

Usage:
    .venv/bin/python figures/fig_comparison.py

Panel c of Fig. 1: figures/fig1_overview.py calls draw(); run this script alone
to review the matrix by itself. Every cell value
and its source are listed in figures/COMPARISON_NOTES.md; keep the two in sync.

Marks (shape and fill, never colour alone):
    Y  filled circle   documented
    P  half-filled     partial, or reachable only by writing code
    N  open circle     searched docs and/or source, not found
    ?  grey dash       not verified

Writes manuscript/figures/fig_comparison.{pdf,png}.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import re  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from figures.style import (CAT, GRID, INK, MUTED, NEUTRAL, SECONDARY,  # noqa: E402
                           TWO_COL, apply, save)

apply()

ACCENT = CAT[0]
# The Cells strip has its own colour (reviewer, 2026-10-08), CAT[1]: distinct from the matrix marks under all three
# simulated colour-vision deficiencies (figures/cvd_check.py; min. ΔE2000 48.5 against ACCENT, >= 20 against the greys).
STRIP_COLOR = CAT[1]
BAND = "#eaf1fb"          # faint tint of CAT[0] for the highlight bands

# --------------------------------------------------------------------------- data
GROUPS = [
    ("Relationships", [
        "cell × cell matrix as color or axis",
        "gene × gene matrix as color or axis",
        "focused cell/gene drives linked panels",
    ]),
    ("Data", [
        "all AnnData slots incl. obsp/varp/varm",
        "remote stores (S3, GCS, HTTP)",
        "spatial coordinates",
    ]),
    ("Work", [
        "selection or filter restricts linked views",
        "annotation editing",
        "on-the-fly DE",
        "tissue image underlay",
    ]),
    ("Sharing", [
        "shareable view state",
        "plot export",
    ]),
    ("Deploy", [
        "desktop app",
        "hosted multi-user",
        "static site, no server",
    ]),
    ("Scale", [
        "lazy chunked reads",
        "every cell drawn",
        "user picks a subset of cells",
        "automatic subset for large data",
    ]),
]

# One string per tool, one character per capability column in GROUPS order:
#   R R R | D D D | W W W W | S S | P P P | Sc Sc Sc
# Marks as accepted by the user on 2026-10-04 (the authors' ledger): strict focus column,
# column 8 "selection or filter restricts linked views", the audit's mark changes, CELLxGENE as
# two programs, Single Cell Portal added, ShinyCell2, extensions do not count, and "only by
# writing code" = P (the Scanpy / Seurat row is the code baseline). Lazy reads and every cell
# drawn are scored by default behaviour (reading A). Evidence: notes/comparison/<tool>.md and
# _summary.md. These strings must agree with evidence/matrix/tools/*.yaml;
# until the figure reads the YAML, keep the two in sync by hand.
# Largest dataset the project documents or hosts (not a limit): S1 of each notes file;
# AnnZarro: figures/scale/README.md.
TOOLS = [
    ("AnnZarro",              "YYY YYY YNNN YY YYN YPYY", "200M, every cell\ndrawn at 17.4 GiB\n(1.5B with a subset)"),
    ("CELLxGENE Explorer",    "NNN NPY YPYY NY NYN YYPN", "11.4M (served, drawn;\ndocs state 4.3M)"),
    ("CELLxGENE Annotate",    "NNN NNN YYYN NN NPN PYPN", "1M (README claim)"),
    ("Vitessce",              "NNN PYY YPNY YP NPY YYNN", "1.28M"),
    ("Cirrocumulus",          "NNN PPY YYYY YY NYY PYPN", "1.3M"),
    ("iSEE",                  "NNN PNN YNNN PY NYN PYPN", ">170k (cytometry)"),
    ("UCSC Cell Browser",     "NNN PPY YYNY YY NYY YYPN", "21.8M (PanSci)"),
    ("Single Cell Portal",    "NNN PNY YYPN YY NYN YPYY", "3.18M (SCP2805)"),
    ("ShinyCell2",            "NNN PNY NNNY NY NYN YYPN", "162k"),
    ("Kana",                  "NNN NPP PPYN PY NPY NYPN", "174k (paper)"),
    ("SCope",                 "NNN PNN YYNN YN NYN YYPN", "568k (Fly Cell Atlas)"),
    ("Loupe Browser",         "NNN NNY PYYY PY YNN YYPN", ">1M (release notes)"),
    ("ManiVault Studio",      "PNN PNP YYNN YP YNN NYPN", "15M (cytometry)"),
    ("VizIt",                 "NNN NNY NNNY YY NYN YNPP", "310k"),
    ("Scanpy / Seurat code",  "PPP PPP PPPP PP NNN PYPN", "1.3M"),
]

# Footnote letters on single marks: (row, column index) -> letter, explained in the legend.
MARK_NOTES = {}

# Scoring of "lazy chunked reads" and "every cell drawn" is a choice of reading: reading "A" scores
# default behaviour (the TOOLS strings above), reading "B" scores what the
# GUI can do at all, after a user choice or a preparation step. Switch here; nothing else changes.
SCALE_READING = "B"                # user decision X1 (2026-10-04): what the GUI can do
READING_B = {                      # tool -> {Scale column: mark under reading B}
    "AnnZarro": {"every": "Y"},              # every cell one dialog away (large-plot mode)
    "Cirrocumulus": {"lazy": "Y"},           # prepared zarr/parquet/jsonl read lazily
    "Single Cell Portal": {"every": "Y"},    # "All Cells" in the subsampling menu
}
_SCALE_POS = {"lazy": -4, "every": -3}


def scored(name, marks):
    """The tool's mark string under SCALE_READING."""
    if SCALE_READING == "A":
        return marks
    assert SCALE_READING == "B", SCALE_READING
    vals = list(marks)
    pos = [i for i, c in enumerate(vals) if c != " "]
    for col, v in READING_B.get(name, {}).items():
        vals[pos[_SCALE_POS[col]]] = v
    return "".join(vals)


# Measured column: benchmark/tool_ceiling/ceilings.csv (ceiling-benchmarker), read at render time.
# The largest N whose CLIENT peak stays within 16 GiB: every browser process for a web tool,
# whose server runs on another machine; the whole process for Scanpy and Seurat (no server).
# Server-rendered tools (iSEE, ShinyCell2) are limited by the server, so the server is reported.
# ">=" marks a lower bound (largest N tested, or the server or input build failed first).
CEILINGS = Path(__file__).resolve().parents[1] / "benchmark" / "tool_ceiling" / "ceilings.csv"
MEASURED_ROWS = {                  # figure row -> [(tool, variant)] in ceilings.csv
    "AnnZarro": [("annzarro", "v041")],
    "CELLxGENE Annotate": [("cellxgene", "default")],
    "Vitessce": [("vitessce", "default")],
    "Cirrocumulus": [("cirrocumulus", "default")],
    "UCSC Cell Browser": [("ucsc", "default")],
    "iSEE": [("isee", "hdf5")],
    "ShinyCell2": [("shinycell", "default")],
    "Kana": [("kana", "default")],
    "SCope": [("scope", "default")],
    "ManiVault Studio": [("manivault", "default")],
    "Loupe Browser": [("loupe", "default")],
    "Scanpy / Seurat code": [("scanpy", "default"), ("seurat", "default")],
}


def _cells(n):
    n = float(n)
    return f"{n / 1e6:.3g}M" if n >= 1e6 else f"{n / 1e3:.3g}k"


def measured(name):
    """Fig. 1c's measured cell: 'not measured' for tools ceiling-benchmarker did not run."""
    rows = MEASURED_ROWS.get(name)
    if not rows:
        return "not measured"
    c = pd.read_csv(CEILINGS).set_index(["tool", "variant"])
    out = []
    for key in rows:
        r = c.loc[key]
        if r["rendering"] == "server":
            lower = "lower bound" in str(r["kind_16gb"])
            out.append(f"server-rendered:\n{'≥' if lower else ''}{_cells(r['max_n_server_budget'])} (server)")
        else:
            v = str(r["figure_value"])
            out.append(v.replace(">=", "≥"))
    return " / ".join(out)


# --------------------------------------------------------------------------- layout (inches)
W = TWO_COL
NAME_W = 0.98            # tool-name column
MEAS_W = 0.86            # measured-ceiling column
DOC_W = 1.02             # largest-dataset column
SCALE_W = MEAS_W + DOC_W
# The cells strip (X8) replaces the two text columns; COMPARISON_STRIP=0 draws the old columns.
STRIP = os.environ.get("COMPARISON_STRIP", "1") == "1"
STRIP_W, STRIP_LO, STRIP_HI = 1.40, 5, 10         # inches; log10 cells 1e5..1e10 (AnnZarro's subset reaches 1.5B)
if STRIP:
    SCALE_W = STRIP_W
GAP_GROUP = 0.07         # gap between capability groups
GAP_SCALE = 0.10         # gap between grid and scale column
ROW_H = 0.215
HEAD_H = 1.88            # rotated column headers, one line each (7 pt needs a wider pitch for two)
GROUP_H = 0.17           # group header strip
LEGEND_H = 0.96 if STRIP else 0.26

n_cols = sum(len(c) for _, c in GROUPS)
PITCH = (W - NAME_W - SCALE_W - GAP_SCALE - GAP_GROUP * (len(GROUPS) - 1)) / n_cols
n_rows = len(TOOLS)
GRID_H = ROW_H * n_rows
H = LEGEND_H + GRID_H + HEAD_H + GROUP_H

# x centre of every capability column, grouped
col_x, group_span = [], []
x = NAME_W
for _, caps in GROUPS:
    x0 = x
    for _ in caps:
        col_x.append(x + PITCH / 2)
        x += PITCH
    group_span.append((x0, x))
    x += GAP_GROUP
grid_right = x - GAP_GROUP
scale_x = grid_right + GAP_SCALE
meas_x, doc_x = scale_x, scale_x + MEAS_W

grid_top = LEGEND_H + GRID_H
row_y = [grid_top - ROW_H * (i + 0.5) for i in range(n_rows)]

R_MARK = 0.052           # circle radius in inches
LW_MARK = 0.6


def mark(ax, x, y, v):
    if v == "?":
        ax.plot([x - 0.035, x + 0.035], [y, y], color=MUTED, lw=0.9,
                solid_capstyle="butt", zorder=3)
        return
    ms = R_MARK * 2 * 72          # diameter in points
    kw = dict(marker="o", ms=ms, mec=INK, mew=LW_MARK, ls="none", zorder=3)
    if v == "Y":
        ax.plot([x], [y], mfc=ACCENT, **kw)
    elif v == "N":
        ax.plot([x], [y], mfc="white", **kw)
    elif v == "P":
        ax.plot([x], [y], mfc=ACCENT, mfcalt="white", fillstyle="left", **kw)
    else:
        raise ValueError(v)


# --------------------------------------------------------------------------- draw
_NUM = re.compile(r"(>=|>|≥)?\s*([\d.]+)\s*([kMB])")


def _parse_cells(text):
    """'>170k (cytometry)' -> (170000.0, lower=True); None when no number."""
    m = _NUM.search(text or "")
    if not m:
        return None
    n = float(m.group(2)) * {"k": 1e3, "M": 1e6, "B": 1e9}[m.group(3)]
    return n, bool(m.group(1))


def stop_limit(r):
    """Which limit stopped a tool in ceilings.csv: (client | server | input, lower bound?).

    client: the browser or process ran out of the 16 GiB budget, timed out, hung or refused (the
    tool's own limit). server: the tool's server passed the 32 GiB server budget. input: the tool
    failed at this size, by crashing below the budget or by not reading its input (drawn as one
    glyph, the triangle). Preparing inputs is not measured for any tool. A lower bound means the
    ladder ended before the tool stopped.
    """
    kind, fail = str(r["kind_16gb"]), str(r["first_fail"])
    if kind.startswith("lower bound"):   # nothing stopped the tool yet; its wording may name a pending check
        return "client", True
    if "input path limit" in kind or fail.startswith("input_limit"):
        return "input", kind.startswith("lower bound")
    if "server" in kind or "server" in fail:
        return "server", kind.startswith("lower bound")
    return "client", kind.startswith("lower bound")


def strip_points(name, doc_text):
    """Glyphs for one row: [(kind, n, lower, label)], kind client | server | input | documented."""
    pts = []
    rows = MEASURED_ROWS.get(name)
    if rows:
        c = pd.read_csv(CEILINGS).set_index(["tool", "variant"])
        for key in rows:
            r = c.loc[key]
            kind, lower = stop_limit(r)
            if row_crashed(r):
                kind = "input"           # a crash below the budget is a failure (Supp. Note 1; drawn as the strip's one glyph)
            n = r["max_n_server_budget"] if r["rendering"] == "server" else r["max_n_16gb"]
            label = {"scanpy": "Sc", "seurat": "Se"}.get(key[0], "") if len(rows) > 1 else ""
            pts.append((kind, float(n), lower, label))
    d = _parse_cells(doc_text)
    if d:
        pts.append(("documented", d[0], d[1], ""))
    return pts


# Tools that draw plots on the server (dagger): iSEE (Shiny, R graphics) and ShinyCell2.
SERVER_RENDERED = {"iSEE", "ShinyCell2"}


def server_rendered(name):
    return name in SERVER_RENDERED


def server_budget():
    """The flat server budget (GiB), from ceilings.csv."""
    b = pd.read_csv(CEILINGS)["server_budget_gib"].dropna().unique()
    assert len(b) == 1, b
    return float(b[0])


def row_crashed(r):
    """Whether a ceilings.csv row's next size crashed (process or module exit) below the budget."""
    if str(r["kind_16gb"]).startswith("lower bound"):
        return False
    fail = str(r["first_fail"])
    return "crash" in fail or "exited" in fail



# Subset reach: the largest dataset a tool opened and drew with its default or user-picked
# subset within the same 16 GiB client budget, for tools whose subset reduces what is loaded
# (strict subset Y or auto_subset Y/P). Source: ceilings.csv, column max_n_subset_16gb.
SUBSET_ROWS = {"AnnZarro": ("annzarro", "v041")}


def subset_eligible(name, marks):
    vals = scored(name, marks).replace(" ", "")
    return vals[-2] == "Y" or vals[-1] in "YP"


def subset_reach(name, marks):
    """Largest N opened with a subset, or None (not eligible, hosted only, or not measured)."""
    if not subset_eligible(name, marks) or name in HOSTED_ONLY:
        return None
    key = SUBSET_ROWS.get(name)
    if key is None:
        return None
    c = pd.read_csv(CEILINGS).set_index(["tool", "variant"])
    if "max_n_subset_16gb" not in c.columns:
        raise SystemExit("ceilings.csv has no max_n_subset_16gb yet (ceiling-benchmarker)")
    if key not in c.index or pd.isna(c.loc[key]["max_n_subset_16gb"]):
        return None
    return float(c.loc[key]["max_n_subset_16gb"])


def subset_lower_bound(name):
    """Whether the tool's subset reach is a lower bound (the largest size tested), from ceilings.csv."""
    key = SUBSET_ROWS.get(name)
    if key is None:
        return False
    c = pd.read_csv(CEILINGS).set_index(["tool", "variant"])
    return key in c.index and str(c.loc[key].get("subset_kind_16gb", "")).startswith("lower bound")



# Hosted-only services: they run on the project's servers and cannot load our data, so they
# cannot be measured (distinct from "not measured yet").
HOSTED_ONLY = {"CELLxGENE Explorer", "Single Cell Portal"}
# Why a row has no measured glyph (Supp. Note 1 gives one sentence each); no glyph for a prediction.
NM_REASON = {"VizIt": "fixed 50,000-cell sample"}


def draw_strip(ax, x0, w, y, pts, measured_any, footnote, hosted=False, reach=None, name=""):
    """One row's cells strip: measured above the row centre, documented below."""
    def X(n):
        return x0 + (np.log10(n) - STRIP_LO) / (STRIP_HI - STRIP_LO) * w
    ms = R_MARK * 1.5 * 72
    for kind, n, lower, label in pts:
        yy = y - 0.045 if kind == "documented" else y + 0.035
        if kind == "documented":
            ax.plot([X(n)], [yy], marker="D", ms=ms * 0.85, mfc="white", mec=INK, mew=LW_MARK,
                    ls="none", zorder=4)
        else:
            # one glyph whatever stopped the tool at the next size (client, server, crash or input);
            # the cause is classified by stop_limit/row_crashed and stated in Supplementary Note 1
            ax.plot([X(n)], [yy], marker="o", ms=ms, mfc=STRIP_COLOR, mec=INK, mew=LW_MARK, ls="none", zorder=4)
        if lower and kind != "documented":   # documented sizes never carry an arrow (operator)
            ax.annotate("", xy=(X(n) + 0.13, yy), xytext=(X(n) + 0.035, yy),
                        arrowprops=dict(arrowstyle="-|>", lw=0.6, color=INK,
                                        mutation_scale=5, shrinkA=0, shrinkB=0), zorder=4)
        if label:
            ax.text(X(n), yy + 0.045, label, fontsize=7, color=SECONDARY, ha="center",
                    va="bottom")
        if kind == "documented" and footnote:
            ax.text(X(n) + 0.05, yy + 0.02, footnote, fontsize=7, color=SECONDARY,
                    ha="left", va="bottom")
    start = max((n for k, n, _, _ in pts if k != "documented"), default=None)
    if reach and start is not None and reach <= start:
        reach = None                     # the subset opens no more than every cell: no ring
    if reach:
        yy = y + 0.035
        if start is not None:
            ax.plot([X(start), X(reach)], [yy, yy], color=STRIP_COLOR, lw=0.8, zorder=3)
        ax.plot([X(reach)], [yy], marker="o", ms=ms * 0.75, mfc="white", mec=STRIP_COLOR, mew=1.0,
                ls="none", zorder=4)
        if subset_lower_bound(name):     # nothing stopped the subset yet: an arrow, as for glyphs
            ax.annotate("", xy=(X(reach) + 0.095, yy), xytext=(X(reach) + 0.03, yy),
                        arrowprops=dict(arrowstyle="-|>", lw=0.6, color=STRIP_COLOR,
                                        mutation_scale=5, shrinkA=0, shrinkB=0), zorder=4,
                        annotation_clip=False)
    if not measured_any:
        ax.text(x0 + w, y + 0.035, NM_REASON.get(name, "hosted" if hosted else "not measured"),
                fontsize=7, color=MUTED, ha="right", va="center", style="italic")


def draw(ax):
    """Draw the matrix into ax, whose data coordinates are inches (0..W, 0..H).

    Fig. 1c (figures/fig1_overview.py) places such an axes in the combined figure.
    """
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    # highlight bands: AnnZarro row, Relationships group (header strip through grid)
    ax.add_patch(Rectangle((0, grid_top - ROW_H), grid_right + GAP_SCALE + SCALE_W, ROW_H,
                           fc=BAND, ec="none", zorder=0))
    rx0, rx1 = group_span[0]
    ax.add_patch(Rectangle((rx0, LEGEND_H), rx1 - rx0, GRID_H + HEAD_H + GROUP_H,
                           fc=BAND, ec="none", zorder=0))
    # overlap of the two bands: keep a single tint (draw once more would darken)

    # row separators
    for i in range(1, n_rows):
        y = grid_top - ROW_H * i
        ax.plot([0, scale_x + SCALE_W], [y, y], color=GRID, lw=0.5, zorder=1)
    ax.plot([0, scale_x + SCALE_W], [grid_top, grid_top], color=MUTED, lw=0.5, zorder=1)
    ax.plot([0, scale_x + SCALE_W], [LEGEND_H, LEGEND_H], color=MUTED, lw=0.5, zorder=1)

    # group headers with a thin rule under each
    gy = H - GROUP_H / 2
    for (name, _), (gx0, gx1) in zip(GROUPS, group_span):
        ax.text((gx0 + gx1) / 2, gy + 0.01, name, ha="center", va="center",
                fontsize=7, fontweight="bold", color=INK)
        ax.plot([gx0 + 0.02, gx1 - 0.02], [H - GROUP_H, H - GROUP_H], color=SECONDARY, lw=0.6)

    # rotated column headers, bottom-aligned just above the grid
    caps = [c for _, cs in GROUPS for c in cs]
    for cx, label in zip(col_x, caps):
        ax.text(cx, grid_top + 0.05, label, rotation=90, ha="center", va="bottom",
                fontsize=7, color=SECONDARY, linespacing=1.05, multialignment="left")

    # left and right headers
    ax.text(0.02, grid_top + 0.05, "Tool", ha="left", va="bottom", fontsize=7,
            fontweight="bold", color=INK)
    if STRIP:
        sx0, sw = scale_x + 0.05, STRIP_W - 0.22
        ax.text(scale_x, grid_top + 0.30, "Cells drawn within a\n16 GiB client memory budget\n(ring: opens with a subset)",
                ha="left", va="bottom", fontsize=7, fontweight="bold", color=INK, linespacing=1.05)
        for e, lab in zip(range(STRIP_LO, STRIP_HI + 1), ["100k", "1M", "10M", "100M", "1B", "10B"]):
            xx = sx0 + (e - STRIP_LO) / (STRIP_HI - STRIP_LO) * sw
            ax.text(xx, grid_top + 0.06, lab, ha="center", va="bottom", fontsize=7, color=SECONDARY)
            ax.plot([xx, xx], [LEGEND_H, grid_top + 0.04], color=GRID, lw=0.5, zorder=1)
    else:
        ax.text(meas_x, grid_top + 0.05, "Cells drawn in\n16 GiB (client;\nmeasured)", ha="left",
                va="bottom", fontsize=7, fontweight="bold", color=INK, linespacing=1.05)
        ax.text(doc_x, grid_top + 0.05, "Largest dataset\ndocumented or\nobserved (cells;\nnot a limit)", ha="left",
                va="bottom", fontsize=7, fontweight="bold", color=INK, linespacing=1.05)

    # rows
    for (name, marks, scale), y in zip(TOOLS, row_y):
        vals = scored(name, marks).replace(" ", "")
        assert len(vals) == n_cols, (name, len(vals))
        first = name == "AnnZarro"
        tname = ax.text(0.02, y, name, ha="left", va="center", fontsize=7,
                        fontweight="bold" if first else "normal", color=INK)
        for k, (cx, v) in enumerate(zip(col_x, vals)):
            mark(ax, cx, y, v)
            if (name, k) in MARK_NOTES:
                ax.text(cx + R_MARK * 0.9, y + R_MARK * 0.6, MARK_NOTES[(name, k)], fontsize=7,
                        color=SECONDARY, ha="left", va="bottom")
        if STRIP:
            pts = strip_points(name, scale)
            if server_rendered(name):
                ax.figure.canvas.draw()
                bb = tname.get_window_extent().transformed(ax.transData.inverted())
                ax.text(bb.x1 + 0.01, y + 0.03, "†", fontsize=7, color=INK,
                        ha="left", va="center")
            draw_strip(ax, sx0, sw, y, pts, any(p[0] != "documented" for p in pts),
                       "‡" if "cytometry" in scale else "", hosted=name in HOSTED_ONLY,
                       reach=subset_reach(name, marks), name=name)
            continue
        meas = measured(name)
        ax.text(meas_x, y, meas, ha="left", va="center", fontsize=7 if "\n" in meas else 7,
                color=INK if first else SECONDARY, linespacing=1.0)
        ax.text(doc_x, y, scale, ha="left", va="center", fontsize=7 if "\n" in scale else 7,
                color=INK if first else SECONDARY, linespacing=1.0)

    # legend: one line below the grid (two in the strip draft)
    ly = (LEGEND_H - 0.12 if STRIP else LEGEND_H / 2) - 0.02
    lx = 0.02
    entries = [("Y", "documented"), ("P", "partial, or only by writing code (the Scanpy / Seurat row)"),
               ("N", "searched, not found"), ("?", "not verified")]
    if not any("?" in marks for _, marks, _ in TOOLS):   # every mark verified: no dash, no legend entry
        entries = [e for e in entries if e[0] != "?"]
    for v, text in entries:
        mark(ax, lx + R_MARK, ly, v)
        t = ax.text(lx + 2 * R_MARK + 0.05, ly, text, ha="left", va="center", fontsize=7,
                    color=SECONDARY)
        ax.figure.canvas.draw()
        bb = t.get_window_extent().transformed(ax.transData.inverted())
        lx = bb.x1 + 0.22
    if STRIP:
        ly2, lx = ly - 0.2, 0.02
        ms = R_MARK * 1.5 * 72
        items = [("o", STRIP_COLOR, "every cell drawn within 16 GiB (largest N)"),
                 ("arrow", None, "lower bound: largest size tested"),
                 ("ring", None, "opens with a subset (loads and draws part)"),
                 ("D", "white", "largest dataset documented or observed"),
                 ("nm", None, "† server-rendered;  hosted: cannot load our data;  ‡ cytometry events")]
        for k, (m, fc, text) in enumerate(items):
            if k == 2 or m == "nm":          # next line of the cells legend
                ly2, lx = ly2 - 0.17, 0.02
            if m == "arrow":
                ax.annotate("", xy=(lx + 0.12, ly2), xytext=(lx, ly2),
                            arrowprops=dict(arrowstyle="-|>", lw=0.6, color=INK, mutation_scale=5,
                                            shrinkA=0, shrinkB=0))
            elif m == "ring":
                ax.plot([lx - 0.02, lx + 0.05], [ly2, ly2], color=STRIP_COLOR, lw=0.8)
                ax.plot([lx + 0.08], [ly2], marker="o", ms=ms * 0.75, mfc="white", mec=STRIP_COLOR,
                        mew=1.0, ls="none")
            elif m != "nm":
                ax.plot([lx + 0.05], [ly2], marker=m, ms=ms * {"D": 0.85}.get(m, 1), mfc=fc,
                        mec=INK, mew=LW_MARK, ls="none")
            t = ax.text(lx + {"nm": 0}.get(m, 0.17), ly2, text, ha="left", va="center",
                        fontsize=7, color=SECONDARY)
            ax.figure.canvas.draw()
            bb = t.get_window_extent().transformed(ax.transData.inverted())
            lx = bb.x1 + 0.16


if __name__ == "__main__":
    fig = plt.figure(figsize=(W, H))
    draw(fig.add_axes([0, 0, 1, 1]))
    save(fig, "fig_comparison")
    print(f"PITCH={PITCH:.3f} in, figure {W:.2f} x {H:.2f} in")
