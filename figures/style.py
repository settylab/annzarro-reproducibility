"""Shared figure style for the AnnZarro manuscript.

Every figure script imports this module so the paper reads as one system:

    from figures.style import apply, CAT, SEQ, DIV, NEUTRAL, INK, MUTED, save, panel_label
    apply()

Rules (from the dataviz method used for this paper):
- Colour comes last and by job: categorical = identity (fixed order, never
  cycled, at most three hues in a scatter), sequential = magnitude (one hue,
  light to dark), diverging = sign (blue <-> red, grey midpoint).
- Never a rainbow or viridis-style multi-hue map; never two y-axes.
- Thin marks, recessive grid and spines, text in ink colours, never in series
  colours. A legend whenever there are two or more series.
- Sizes are final print sizes: figures are drawn at the text width (164 mm, 464.9 pt), the
  width main.tex prints them at; lettering at least 7 pt, lines at least 0.5 pt, panel
  letters 9 pt bold lowercase (manuscript/tools/check_figures.py checks the PDFs).
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

MM = 1 / 25.4
ONE_COL = 89 * MM
TWO_COL = 163 * MM      # just inside the text width (A4, 2.3 cm margins: 464.9 pt), so figures print at scale >= 1

# Categorical slots, fixed order (validated: first three are CVD-safe all-pairs).
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

INK = "#0b0b0b"
SECONDARY = "#52514e"
MUTED = "#8a8984"
GRID = "#e6e5e0"
NEUTRAL = "#d9d8d3"       # background points (cells outside a mask, NaN)
SURFACE = "#ffffff"

_SEQ_STEPS = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
_SEQ2_STEPS = ["#fde1d3", "#f8b89b", "#f19066", "#eb6834", "#c4521f", "#9a3d12", "#6f2a08"]
_DIV_STEPS = ["#0d366b", "#256abf", "#6da7ec", "#f0efec", "#f19a95", "#e34948", "#9e1f22"]

SEQ = LinearSegmentedColormap.from_list("annz_seq", _SEQ_STEPS)
SEQ2 = LinearSegmentedColormap.from_list("annz_seq2", _SEQ2_STEPS)
DIV = LinearSegmentedColormap.from_list("annz_div", _DIV_STEPS)
for cmap in (SEQ, SEQ2, DIV):
    cmap.set_bad(NEUTRAL)


def apply():
    """Set matplotlib defaults for print figures."""
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 7,
        "axes.titlesize": 7,
        "axes.titleweight": "bold",
        "axes.labelsize": 7,
        "axes.labelcolor": SECONDARY,
        "axes.edgecolor": MUTED,
        "axes.linewidth": 0.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "grid.color": GRID,
        "grid.linewidth": 0.5,
        "xtick.color": SECONDARY,
        "ytick.color": SECONDARY,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "legend.fontsize": 7,
        "legend.frameon": False,
        "lines.linewidth": 1.2,
        "lines.markersize": 3,
        "text.color": INK,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "savefig.dpi": 600,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.prop_cycle": mpl.cycler(color=CAT),
    })


def panel_label(ax, letter, x=-0.12, y=1.04):
    """Bold lowercase panel letter at the axes' top left."""
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=9, fontweight="bold",
            va="bottom", ha="left", color=INK)


def embedding_axes(ax):
    """Embeddings carry no meaningful scale: hide ticks and spines."""
    ax.set_xticks([]); ax.set_yticks([])
    for side in ("left", "bottom", "top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_aspect("equal", adjustable="datalim")


def save(fig, name, outdir=Path(__file__).resolve().parent.parent / "manuscript" / "figures"):
    """Write PDF (for LaTeX) and PNG (for review) side by side."""
    outdir.mkdir(parents=True, exist_ok=True)
    fig.savefig(outdir / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(outdir / f"{name}.png", bbox_inches="tight", pad_inches=0.02, dpi=300)
    plt.close(fig)
