"""Fig. 1: the focus model, the AnnData slot map and the comparison with other tools.

Usage:
    .venv/bin/python figures/fig1_overview.py

a, what one click selects and what each panel receives; b, which stored array
drives which view; c, the feature matrix of figures/fig_comparison.py (its data
and sources live there and in figures/COMPARISON_NOTES.md).

Color carries one meaning across a and b: blue is what the focused cell
selects (a row), orange what the focused gene selects (a column).

Writes manuscript/figures/fig1_overview.{pdf,png}.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

from figures import fig_comparison  # noqa: E402
from figures.style import CAT, INK, MUTED, SECONDARY, TWO_COL, apply, save  # noqa: E402

apply()

CELL, GENE = CAT[0], CAT[1]
EDGE = MUTED
FILL = "#f4f3ef"          # layers behind X, server band
SUB = 7                   # secondary text size (7 pt, the print minimum)

W = TWO_COL
HC = fig_comparison.H     # panel c keeps its own size, so its 7 pt text stays 7 pt
GAP = 0.14                # between the top row and panel c
HTOP = 2.92
H = HC + GAP + HTOP
TOP = H

fig = plt.figure(figsize=(W, H))
ax = fig.add_axes([0, 0, 1, 1])      # one canvas in inches for a and b
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.canvas.draw()
renderer = fig.canvas.get_renderer()


def letter(x, y, s):
    """Panel letter, as figures.style.panel_label sets it, placed in inches."""
    ax.text(x, y, s, fontsize=9, fontweight="bold", color=INK, ha="left", va="top")


def width_in(s, **kw):
    t = ax.text(0, 0, s, **kw)
    w = t.get_window_extent(renderer).width / fig.dpi
    t.remove()
    return w


def wrap(s, width, **kw):
    """Greedy word wrap to a width in inches, measured with the real font."""
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and width_in(trial, **kw) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return "\n".join(lines + [cur])


def box(x0, y0, x1, y1, ec=EDGE, fc="white", lw=0.6, z=1):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, ec=ec, fc=fc, lw=lw, zorder=z,
                                boxstyle="round,pad=0,rounding_size=0.04"))


def arrow(p, q, color=EDGE, lw=0.7):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=6, lw=lw,
                                 color=color, shrinkA=0, shrinkB=0, zorder=2))


def titled(x, ytop, title, body, width, ha="center", title_lines=1):
    """Bold title line(s) over wrapped secondary text, top-aligned at ytop; returns the text's bottom."""
    if "\n" not in title:
        title = wrap(title, width, fontsize=7, fontweight="bold")
        title_lines = title.count("\n") + 1
    ax.text(x, ytop, title, fontsize=7, fontweight="bold", color=INK, ha=ha, va="top",
            linespacing=1.1, multialignment=ha)
    t = ax.text(x, ytop - 0.125 * title_lines, wrap(body, width, fontsize=SUB), fontsize=SUB, color=SECONDARY,
                ha=ha, va="top", linespacing=1.15, multialignment=ha)
    bb = t.get_window_extent(renderer).transformed(ax.transData.inverted())
    return bb.y0


# =========================================================================== a
letter(0.0, TOP, "a")

# focus
FY, FH, FW = TOP - 0.30, 0.26, 1.0
for x, name, col in [(1.0, "Focused cell", CELL), (2.4, "Focused gene", GENE)]:
    box(x - FW / 2, FY - FH / 2, x + FW / 2, FY + FH / 2, ec=col, fc=col + "1f", lw=1.0)
    ax.text(x, FY, name, fontsize=7, fontweight="bold", color=INK, ha="center", va="center")

# stored matrices
MY, MH, MW = TOP - 1.17, 0.46, 0.98
MATS = [(0.65, "cells × cells", "obsp: kernels, graphs, distances"),
        (1.70, "cells × genes", "X and layers: expression, LFC"),
        (2.75, "genes × genes", "varp: correlations")]
for x, name, sub in MATS:
    box(x - MW / 2, MY - MH / 2, x + MW / 2, MY + MH / 2)
    titled(x, MY + MH / 2 - 0.07, name, sub, MW - 0.1)

# panels
PY, PH = TOP - 2.13, 0.76
PANELS = [((0.16, 1.62), "Cell scatter", "embedding or spatial; color = similarity to the focused "
                                          "cell, or the focused gene in every cell"),
          ((1.78, 3.24), "Gene scatter", "e.g. a volcano; color = similarity to the focused "
                                          "gene, or the focused cell across genes")]
for (x0, x1), name, sub in PANELS:
    box(x0, PY - PH / 2, x1, PY + PH / 2)
    titled((x0 + x1) / 2, PY + PH / 2 - 0.07, name, sub, x1 - x0 - 0.12)

# server band
SY, SH = TOP - 2.74, 0.27
box(0.16, SY - SH / 2, 3.24, SY + SH / 2, fc=FILL)
ax.text(1.70, SY, wrap("Server reads only the chunks holding that row or column; "
                       "each panel receives one vector", 2.95, fontsize=SUB),
        fontsize=SUB, color=INK, ha="center", va="center", linespacing=1.15)

# focus -> matrices: the focused cell picks rows, the focused gene a column and a row
f_bot, m_top = FY - FH / 2, MY + MH / 2
for (x0, x1, col, lab, side, t) in [(0.85, 0.62, CELL, "its row", "left", 0.35),
                                    (1.15, 1.52, CELL, "its row", "right", 0.22),
                                    (2.25, 1.88, GENE, "its column", "left", 0.62),
                                    (2.55, 2.78, GENE, "its row", "right", 0.35)]:
    arrow((x0, f_bot), (x1, m_top), color=col)
    # the middle pair's labels sit at different heights so they cannot meet
    xm, ym = x0 + t * (x1 - x0), f_bot + t * (m_top - f_bot)
    dx = -0.05 if side == "left" else 0.05
    ax.text(xm + dx, ym, lab, fontsize=SUB, color=SECONDARY, va="center",
            ha="right" if side == "left" else "left")

# matrices -> panels, colored by the focus that chose the vector
m_bot, p_top = MY - MH / 2, PY + PH / 2
for x0, x1, col in [(0.62, 0.70, CELL), (1.52, 1.25, GENE), (1.88, 2.15, CELL), (2.78, 2.70, GENE)]:
    arrow((x0, m_bot), (x1, p_top), color=col)

# server -> panels
for x in (0.89, 2.51):
    arrow((x, SY + SH / 2), (x, PY - PH / 2))

# =========================================================================== b
BX0 = 3.42
letter(BX0, TOP, "b")

S = 0.165                       # inches per slot-map unit
UX0, UY1 = BX0 + 0.13, TOP - 0.06


def P(ux, uy):
    """Slot-map units (x right from obsp's left edge at -1, y up to varp's top at 6.2)."""
    return UX0 + (ux + 1.0) * S, UY1 + (uy - 6.2) * S


def rect(ux0, uy0, ux1, uy1, **kw):
    (x0, y0), (x1, y1) = P(ux0, uy0), P(ux1, uy1)
    kw = {"ec": EDGE, "fc": "white", "lw": 0.6, "zorder": 1} | kw
    ax.add_patch(Rectangle((min(x0, x1), min(y0, y1)), abs(x1 - x0), abs(y1 - y0), **kw))


# layers peek out behind X
rect(5.50, -0.30, 9.50, -4.30, fc=FILL)
rect(5.35, -0.15, 9.35, -4.15, fc=FILL)
# arrays
rect(5.2, 0, 9.2, -4)            # X
rect(4.2, 0, 5.0, -4)            # obs
rect(3.2, 0, 4.0, -4)            # obsm
rect(-1.0, 0, 3.0, -4)           # obsp
rect(5.2, 1.0, 9.2, 0.2)         # var
rect(5.2, 2.0, 9.2, 1.2)         # varm
rect(5.2, 6.2, 9.2, 2.2)         # varp

# focus bands: one row for the cell, one column for the gene, their crossing
rect(-1.0, -2.25, 9.2, -2.55, fc=CELL, ec="none", alpha=0.35, zorder=2)
rect(8.55, -4.0, 8.85, 6.2, fc=GENE, ec="none", alpha=0.35, zorder=2)
rect(8.55, -2.25, 8.85, -2.55, fc=INK, ec="none", zorder=3)


def name(ux, uy, s, dim=None):
    x, y = P(ux, uy)
    ax.text(x + 0.04, y - 0.04, s, fontsize=7, fontweight="bold", color=INK, ha="left", va="top")
    if dim:
        ax.text(x + 0.04, y - 0.16, dim, fontsize=SUB, color=SECONDARY, ha="left", va="top",
                linespacing=1.1)


name(5.2, 0, "X, layers", "cells ×\ngenes")
name(-1.0, 0, "obsp", "cells × cells")
name(5.2, 6.2, "varp", "genes ×\ngenes")
for uy, s in [(0.6, "var"), (1.6, "varm")]:
    x, y = P(5.2, uy)
    ax.text(x - 0.04, y, s, fontsize=7, fontweight="bold", color=INK, ha="right", va="center")
for ux, s in [(3.6, "obsm"), (4.6, "obs")]:
    x, y = P(ux, 0)
    ax.text(x, y - 0.04, s, fontsize=7, fontweight="bold", color=INK, rotation=90,
            ha="center", va="top")

# legend in the empty quadrant above obsp
# (two lines per entry: one line of 7 pt text is wider than the quadrant); uns goes with the notes
lx, ly = P(-1.0, 6.2)
ly -= 0.22
for i, (fc, alpha, s) in enumerate([(CELL, 0.35, "focused cell:\na row"),
                                    (GENE, 0.35, "focused gene:\na column"),
                                    (INK, 1.0, "crossing:\none value")]):
    y = ly - i * 0.27
    ax.add_patch(Rectangle((lx, y - 0.035), 0.10, 0.07, fc=fc, ec="none", alpha=alpha))
    ax.text(lx + 0.15, y + 0.05, s, fontsize=7, color=INK, ha="left", va="top", linespacing=1.1)

# what each array drives: notes to the right, stacked top-down from their arrays (a note moves
# down when the one above runs long), with a leader line from the array to the note's title
NX = P(9.5, 0)[0] + 0.12
NW = W - NX - 0.02
y_free = TOP
for uy, ux_from, title, body in [
        (4.6, 9.2, "Gene plot color",
         "the focused gene's row of a gene-by-gene matrix, e.g. correlation modules over a volcano"),
        (1.1, 9.2, "Gene plot axes, gene tables",
         "per-gene (var) and per-group (varm) statistics, e.g. a Kompot volcano"),
        (-2.4, 9.5, "Both directions",
         "the focused gene's column colors cells (expression, fold change); "
         "the focused cell's row colors genes"),
        (None, None, "uns", "category colors and run records")]:
    if uy is None:                 # uns has no array in the map: no leader, next in the stack
        ty = y_free - 0.04
    else:
        x, y = P(ux_from, uy)
        ty = min(y + 0.05, y_free)
        ax.plot([x, NX - 0.10, NX - 0.03], [y, ty - 0.05, ty - 0.05], color=EDGE, lw=0.5)
    y_free = titled(NX, ty, title, body, NW, ha="left") - 0.06

# notes below the cell-indexed arrays
_, by = P(0, -4.3)
by -= 0.06
x0, _ = P(-1.0, 0)
x1, _ = P(3.2, 0)
titled(x0, by, "Cell plot\ncolor", "the focused cell's row of a kernel, graph or distance",
       x1 - x0 - 0.08, ha="left", title_lines=2)
titled(x1, by, "Cell plot axes,\ncolors and masks",
       "embeddings and spatial positions (obsm), annotations and scores (obs), table filters",
       P(9.5, 0)[0] - x1, ha="left", title_lines=2)

# =========================================================================== c
cax = fig.add_axes([0, 0, 1, HC / H])
fig_comparison.draw(cax)
letter(0.0, HC + 0.02, "c")

save(fig, "fig1_overview")
print(f"figure {W:.2f} x {H:.2f} in")
