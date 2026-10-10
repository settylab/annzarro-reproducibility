"""Fig. 2: the AnnZarro interface on the demonstration data.

Assembles headless screenshots made by figures/screenshots.py:
  a  overview with four linked panels (walk, volcano, fold change, table)
  b  the same UMAP after four clicks along HSC -> monocyte
  c  a two-condition table filter masking a linked UMAP
and, by figures/screenshots_app_spatial.py (AnnZarro v0.4.1 on the public Visium demo):
  d  after a click on a cortex spot: the section and the expression UMAP by Leiden cluster,
     the section by the spot's expression_walk_t5 row, the UMAP by its spatial_kernel row

Panel a carries an enlarged inset of one plot's status line, cropped from the same
capture (overview_status.json, written by screenshots.py, says where it is): at the
panel's own scale the status line prints at about 2.5 pt.

Run: .venv/bin/python figures/fig5_app.py   [--screens DIR --outdir DIR] for a dry run
"""
import argparse
import os
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from matplotlib.patches import ConnectionPatch, Rectangle  # noqa: E402

from figures.style import apply, save, INK, MUTED, SECONDARY, TWO_COL  # noqa: E402

SCREENS = ROOT / "manuscript" / "figures" / "screens"
OUTDIR = ROOT / "manuscript" / "figures"
# d: four plots of the spatial demo (screens/app_spatial), one scale for all
SPATIAL_ROW = [("row4_tissue_leiden", "section, by cluster"), ("row4_tissue_walk", "diffusion walk\nin state space"),
               ("row4_umap_leiden", "UMAP, by cluster"), ("row4_umap_kernel", "its tissue neighbors")]

D_GAP_IN = 0.05               # between d's plots
# d's width as a share of a-c's; it sets d's height. 0.8 lets Fig. 2 and its caption, with a
# 3-line d caption, share one page at >= 7 pt (manuscript-edits' choice). Row d at row b's
# height (1.22 in) would need 1.17, so the 0.8 row (0.84 in) is the smaller of the two.
D_WIDTH = float(os.environ.get("FIG2_D_WIDTH", 0.8))
D_TITLE_IN = 0.30             # above d's plots: the gap to c and d's titles
INSET_TILE = "cell-plot-O3"   # bottom-left plot: its status line borders the free margin
INSET_PT = 6.0                # status-line text size in print
PRINT_SCALE = 165 / 183       # the 183 mm figure is set at the 165 mm text width


def img(path, crop_top=0, crop=None):
    im = Image.open(path).convert("RGB")
    if crop is not None:
        im = im.crop(crop)
    elif crop_top:
        im = im.crop((0, crop_top, im.width, im.height))
    return im


def spatial_tile(name):
    """A plot capture cut to the box the capture recorded (crops.json): the drawn content,
    left of the 20-entry Leiden legend on the cluster plots (it scrolls in the tile). The app's
    own font size and margins already remove most of the white (screenshots_app_spatial.py)."""
    d = SCREENS / "app_spatial"
    box = json.loads((d / "crops.json").read_text())[name]["box"]
    return Image.open(d / f"{name}.png").convert("RGB").crop(tuple(box))


def show(ax, im):
    ax.imshow(im, interpolation="lanczos")
    ax.set_axis_off()
    for side in ax.spines.values():
        side.set_visible(False)


def status_inset(fig, ax, overview):
    """Crop one status line from the overview capture and show it enlarged, as a callout."""
    src = SCREENS / "overview_status.json"
    if not src.exists():                          # captures made before screenshots.py wrote it
        print(f"no {src.name}: panel a without the status-line inset")
        return
    fig.canvas.draw()                             # apply panel a's anchor before measuring
    meta = json.loads(src.read_text())
    dsf, st = meta["dsf"], meta["status"][INSET_TILE]
    sx, sy, _, sh = st["strip"]
    tx, _, tw, _ = st["text"]
    pad = 6                                       # CSS px of strip kept right of the text
    box = (sx, sy, tx + tw + pad, sy + sh)        # CSS px in the page = the capture / dsf
    crop = overview.crop(tuple(round(v * dsf) for v in box))

    # Size: 12 px status text set at INSET_PT in print.
    css_in = INSET_PT / PRINT_SCALE / 72 / 12     # figure inches per CSS px in the inset
    w_in, h_in = (box[2] - box[0]) * css_in, (box[3] - box[1]) * css_in
    fw, fh = fig.get_size_inches()

    # Source position in figure coordinates (imshow data coords are capture pixels).
    to_fig = lambda x, y: fig.transFigure.inverted().transform(ax.transData.transform((x, y)))  # noqa: E731
    (x0, y1), (x1, y0) = to_fig(box[0] * dsf, box[1] * dsf), to_fig(box[2] * dsf, box[3] * dsf)
    a_left = ax.get_position().x0
    if w_in / fw > a_left - 0.02:
        sys.exit(f"status inset ({w_in * 25.4:.0f} mm) does not fit the margin "
                 f"({(a_left - 0.02) * fw * 25.4:.0f} mm)")
    ix = (a_left - 0.012) - w_in / fw                       # right edge just left of panel a
    iy = (y0 + y1) / 2 - h_in / fh / 2 + 0.035              # a little above the source
    iax = fig.add_axes([ix, iy, w_in / fw, h_in / fh])
    iax.imshow(crop, interpolation="lanczos")
    iax.set_xticks([]); iax.set_yticks([])
    for side in iax.spines.values():
        side.set_visible(True); side.set_color(INK); side.set_linewidth(0.6)
    fig.text(ix, iy + h_in / fh + 0.004, "status line\n(enlarged)", fontsize=7,
             color=SECONDARY, ha="left", va="bottom", linespacing=1.1)
    # Mark the source on the screenshot and join it to the inset.
    fig.add_artist(Rectangle((x0, y0), x1 - x0, y1 - y0, transform=fig.transFigure,
                             fill=False, ec=INK, lw=0.6))
    fig.add_artist(ConnectionPatch((ix + w_in / fw, iy), (x0, (y0 + y1) / 2),
                                   coordsA="figure fraction", coordsB="figure fraction",
                                   color=MUTED, lw=0.5))
    print(f"inset: {st['label']!r} from {INSET_TILE}, {w_in * 25.4:.1f} x {h_in * 25.4:.1f} mm, "
          f"text {INSET_PT} pt in print (x{(css_in * 1800) / ax.get_position().width / fw:.1f} "
          f"of panel a)")


def main():
    global SCREENS, OUTDIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--screens", type=Path, default=SCREENS)
    ap.add_argument("--outdir", type=Path, default=OUTDIR)
    args = ap.parse_args()
    SCREENS, OUTDIR = args.screens, args.outdir
    apply()
    # a-c keep their old layout (a TWO_COL x 1.235 TWO_COL figure with matplotlib's default
    # subplot box); d is added below at the width of that box, its height set by the plots
    ims = [spatial_tile(n) for n, _ in SPATIAL_ROW]
    sp = plt.rcParams
    left, right = sp["figure.subplot.left"], sp["figure.subplot.right"]
    top, bottom = sp["figure.subplot.top"], sp["figure.subplot.bottom"]
    h_abc = TWO_COL * 1.235
    w_row = (right - left) * TWO_COL * D_WIDTH
    h_d = (w_row - D_GAP_IN * (len(ims) - 1)) / sum(im.width / im.height for im in ims)
    H = h_abc + h_d + D_TITLE_IN
    fig = plt.figure(figsize=(TWO_COL, H))
    gs = fig.add_gridspec(3, 4, height_ratios=[3.0, 1.1, 1.0], hspace=0.12, wspace=0.04,
                          top=1 - (1 - top) * h_abc / H, bottom=(bottom * h_abc + h_d + D_TITLE_IN) / H)

    # a: overview, pushed right to leave the left margin for the status-line inset
    ax = fig.add_subplot(gs[0, :])
    overview = img(SCREENS / "overview.png")
    show(ax, overview)
    ax.set_anchor("E")
    rows = {"a": ax}
    ax_a = ax

    # b: focus sequence
    steps = [("1_HSC", "click 1: HSC"), ("2_GMP", "click 2: GMP"),
             ("3_cMoP", "click 3: cMoP"), ("4_Monocyte", "click 4: monocyte")]
    for i, (stem, title) in enumerate(steps):
        ax = fig.add_subplot(gs[1, i])
        tile = img(SCREENS / "focus_sequence" / f"{stem}_tile.png")
        show(ax, tile)
        ax.set_title(title, fontsize=7, fontweight="normal", color=SECONDARY, pad=2)
        if i == 0:
            rows["b"] = ax

    # c: table filter masking a UMAP, at the tiles' own width ratio (65:35)
    gc = gs[2, :].subgridspec(1, 2, width_ratios=[65, 35], wspace=0.04)
    ax = fig.add_subplot(gc[0])
    show(ax, img(SCREENS / "E_table_tile.png"))
    ax.set_title("cell table: cell type = HSC AND DA z-score > 2 (290 cells)", fontsize=7,
                 fontweight="normal", color=SECONDARY, pad=2)
    rows["c"] = ax
    ax = fig.add_subplot(gc[1])
    show(ax, img(SCREENS / "E_umap_tile.png"))
    ax.set_title("linked UMAP: cells outside the table in gray", fontsize=7,
                 fontweight="normal", color=SECONDARY, pad=2)

    # d: the spatial demo, four plots at one scale side by side, filling the width of a-c
    x, y0 = left + (right - left) * (1 - D_WIDTH) / 2, bottom * h_abc / H   # centered
    for j, (im, (_, title)) in enumerate(zip(ims, SPATIAL_ROW)):
        w = im.width / im.height * h_d
        ax = fig.add_axes([x, y0, w / TWO_COL, h_d / H])
        show(ax, im)
        ax.set_title(title, fontsize=7, fontweight="normal", color=SECONDARY, pad=2)
        if j == 0:
            rows["d"] = ax
        x += (w + D_GAP_IN) / TWO_COL

    status_inset(fig, ax_a, overview)

    # Panel letters at the figure's left edge, level with each row's top, so
    # they do not float with the centered, aspect-locked screenshot axes.
    fig.canvas.draw()
    for letter, row_ax in rows.items():
        top = row_ax.get_position().y1
        fig.text(0.0, top + 0.012, letter, fontsize=9, fontweight="bold", va="bottom", ha="left")

    save(fig, "fig5_app", outdir=OUTDIR)


if __name__ == "__main__":
    main()
