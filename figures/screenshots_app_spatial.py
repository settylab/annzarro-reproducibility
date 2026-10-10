#!/usr/bin/env python
"""Screenshots of the spatial demo for the app figure's spatial row (fig5_app.py, Fig. 2 panel d).

Uses the capture machinery of figures/screenshots.py (same readiness rule, same click,
same device scale factor) on data/spatial_demo.zarr: the public 10x Visium anterior
sagittal mouse-brain section built by AnnZarro v0.4.1's docs/_tools/make_spatial_demo.py,
plus obsp/expression_walk_t5 from figures/spatial/add_expression_walk.py. The capture is
taken after a click on a cortex spot, and the run fails unless the click focused that spot
and fetched one row of each matrix a panel follows.

Two layouts of the same view, both captured (the figure uses one, set by fig5_app.py):
  row4  tissue by Leiden cluster | tissue by the spot's expression_walk_t5 row |
        UMAP by Leiden cluster   | UMAP by the spot's spatial_kernel row
  row3  the same without the UMAP by Leiden cluster
Equal aspect on every plot; font size and margins from the app's plot options (FONT_SIZE,
MARGINS). Each plot is captured without the tile's status line, and crops.json records the box
fig5_app.py cuts (the drawn content; left of the Leiden legend on the cluster plots).

Run (any venv with playwright, zarr and numpy; the app from its own install):
    python figures/screenshots_app_spatial.py --annzarro <v0.4.1 venv>/bin/annzarro [--port 8841]
Writes manuscript/figures/screens/app_spatial/*, the views to figures/spatial_views/app_spatial_*
and the numbers to figures/numbers/app_spatial.json (the row was Fig. 1d before it moved to Fig. 2).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
import zarr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import figures.screenshots as S  # noqa: E402
from figures.screenshots import (NO_MODEBAR_CSS, Shooter, _Log, click_cell, split,  # noqa: E402
                                 start_server, stop_server, tile)

DATASET = ROOT / "data" / "spatial_demo.zarr"
OUT = ROOT / "manuscript" / "figures" / "screens" / "app_spatial"
VIEW_DIR = ROOT / "figures" / "spatial_views"
NUMBERS = ROOT / "figures" / "numbers" / "app_spatial.json"

# The medoid (PCA space) of the cortical Leiden cluster 18 (highest Slc17a7 among the upper
# bands, lowest Penk); the deep links start on the medoid of cluster 0, before the click.
CORTEX = "TGCAAGAATGACGTAA-1"
GENE = "Penk"
# 380 x 480 CSS px of window per tile: near the data's own aspect (section and UMAP are both
# about square, plus a colorbar), so equal aspect leaves little empty axis range at the sides
VIEWPORTS = {"row4": {"width": 1520, "height": 480}, "row3": {"width": 1140, "height": 480}}
# The app's own plot options (Plot Options: font size, margins) shrink the text and the white
# margins; v0.4.1 has no setting for the colorbar's thickness or length, so the colorbar shrinks
# only with the font (its ticks and title)
FONT_SIZE = 9
MARGINS = {"l": 46, "r": 4, "t": 6, "b": 34, "pad": 0}

TISSUE = ({"type": "obsm", "key": "spatial_upright", "column": "0"},
          {"type": "obsm", "key": "spatial_upright", "column": "1"})
UMAP = ({"type": "obsm", "key": "X_umap", "column": "0"}, {"type": "obsm", "key": "X_umap", "column": "1"})
LEIDEN = {"type": "obs", "key": "leiden", "column": ""}
HOVER = [{"type": "obs", "key": "_index"}, {"type": "obs", "key": "leiden"}]


def row(key: str, spot: str) -> dict:
    """A focused spot's obsp row; unlocked, so it follows every click."""
    return {"type": "obsp", "key": key, "column": spot, "locked": False}


def plot(tid, title, xy, color, scale=None):
    cfg = {"id": tid, "title": title, "x": xy[0], "y": xy[1], "z": None, "color": color,
           "pointSize": 3, "pointOpacity": 0.9, "highlightFocusedCell": True,
           "hoverInfo": HOVER, "equalAspect": True, "fontSize": FONT_SIZE, "margins": dict(MARGINS)}
    if scale:
        cfg.update(colorScale=scale, colorReversed=True)
    return cfg


def panels(focus: str) -> dict:
    return {
        "tissue_leiden": plot("cell-plot-P1", "Section: Leiden cluster", TISSUE, LEIDEN),
        "tissue_walk": plot("cell-plot-P2", "Diffusion walk in state space", TISSUE,
                            row("expression_walk_t5", focus), "Blues"),
        "umap_leiden": plot("cell-plot-P3", "UMAP: Leiden cluster", UMAP, LEIDEN),
        "umap_kernel": plot("cell-plot-P4", "UMAP: spatial_kernel row", UMAP,
                            row("spatial_kernel", focus), "Blues"),
    }


LAYOUTS = {"row4": ["tissue_leiden", "tissue_walk", "umap_leiden", "umap_kernel"],
           "row3": ["tissue_leiden", "tissue_walk", "umap_kernel"]}


def view(focus: str, layout: str) -> dict:
    p = panels(focus)
    names = LAYOUTS[layout]
    t = [tile(p[n]["id"]) for n in names]
    hier = (split("horizontal", split("horizontal", t[0], t[1]), split("horizontal", t[2], t[3]))
            if len(t) == 4 else split("horizontal", t[0], split("horizontal", t[1], t[2]), 33))
    cfgs = [p[n] for n in names]
    return {"v": 1, "constants": {"focusedCell": focus, "focusedGene": GENE, "taxonomyId": "10090"},
            "layout": {"v": 1, "hierarchy": [hier], "controlState": {c["id"]: False for c in cfgs},
                       "panelConfigs": {c["id"]: c for c in cfgs}}}


def store_numbers(spot: str) -> dict:
    """What a caption may quote, read from the store (the clicked spot's rows)."""
    g = zarr.open_group(str(DATASET), mode="r")
    names = [str(x) for x in g["obs/_index"][:]]
    cats = [str(x) for x in g["obs/leiden/categories"][:]]
    lei = np.array(cats)[g["obs/leiden/codes"][:]]
    W = np.asarray(g["obsp/expression_walk_t5"][:], dtype=np.float64)
    i = names.index(spot)
    k = np.asarray(g["obsp/spatial_kernel"][i], dtype=np.float64)
    return {
        "n_spots": len(names), "n_genes": int(g["var/_index"].shape[0]), "n_leiden": len(cats),
        "connectivities_nnz_per_row_median": float(np.median(np.diff(g["obsp/connectivities/indptr"][:]))),
        "walk_t": 5, "walk_n_eff_median": float(np.median(1 / (W ** 2).sum(1))),
        "spot": {"name": spot, "leiden": str(lei[i]),
                 "walk_n_eff": float(1 / (W[i] ** 2).sum()),
                 "walk_mass_own_leiden": float(W[i][lei == lei[i]].sum()),
                 "spatial_kernel_mass_own_leiden": float(k[lei == lei[i]].sum()),
                 "spatial_kernel_n_leiden_clusters_with_mass_gt_1pct": int(sum(k[lei == c].sum() > 0.01 for c in cats))},
    }


def medoid(cluster: str) -> str:
    g = zarr.open_group(str(DATASET), mode="r")
    cats = list(g["obs/leiden/categories"][:])
    codes = g["obs/leiden/codes"][:]
    names = g["obs/_index"][:]
    pc = g["obsm/X_pca"][:]
    m = np.where(codes == cats.index(cluster))[0]
    c = np.median(pc[m], 0)
    return str(names[m[np.argmin(((pc[m] - c) ** 2).sum(1))]])


def legend_left(page, tid):
    """Left edge of the plot's legend, in capture pixels from the plot's left edge."""
    return page.evaluate("""([tid, dsf]) => {
      const p = document.querySelector(`.tile[data-tile-id="${tid}"] .js-plotly-plot`).getBoundingClientRect();
      const l = document.querySelector(`.tile[data-tile-id="${tid}"] .legend`);
      return l ? Math.floor((l.getBoundingClientRect().left - p.left) * dsf) : null; }""", [tid, S.DSF])


def content_box(path, right=None, pad=6):
    """[left, top, right, bottom] of the drawn content in a capture (pixels darker than 235 in
    any channel), with `right` as the outer limit (the legend's left edge) and a small pad: the
    white the app's margins cannot remove (equal aspect, Plotly's own padding)."""
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB"))
    if right:
        a = a[:, :right]
    ink = (a < 235).any(axis=2)
    ink[:4] = False                     # the tile's top border line, not plot content
    ys, xs = np.where(ink.any(1))[0], np.where(ink.any(0))[0]
    return [max(0, int(xs[0]) - pad), max(0, int(ys[0]) - pad),
            min(a.shape[1], int(xs[-1]) + 1 + pad), min(a.shape[0], int(ys[-1]) + 1 + pad)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annzarro", required=True, help="the annzarro CLI of the release under test")
    ap.add_argument("--port", type=int, default=8841)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    S.OUT, S.DATASET = OUT, DATASET              # Shooter.shot / deep_link read these
    start = medoid("0")
    for layout in LAYOUTS:
        for tag, focus in (("", start), ("_cortex", CORTEX)):
            (VIEW_DIR / f"app_spatial_{layout}{tag}.view.json").write_text(
                json.dumps(view(focus, layout), indent=1) + "\n")

    os.environ["ANNZARRO_HOME"] = tempfile.mkdtemp(prefix="annzarro-home-app-spatial-")
    log, failed, clicks, crops = _Log(), [], [], {}
    proc = start_server(a.annzarro, a.port, OUT / ".server.log")
    log.append(f"server pid {proc.pid} on 127.0.0.1:{a.port}, ANNZARRO_HOME {os.environ['ANNZARRO_HOME']}")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            s = Shooter(browser, f"http://127.0.0.1:{a.port}", log)
            for layout, names in LAYOUTS.items():
                p = panels(start)
                page = s.open(view(start, layout), viewport=VIEWPORTS[layout])
                n0 = len(page._urls)
                got = click_cell(page, p["tissue_walk"]["id"], CORTEX)
                s.ready(page)
                data = [u for u in page._urls[n0:] if "/api/v1/data/" in u and "/data/fingerprint?" not in u]
                rows = {k: sum(f"/obsp/{k}?" in u for u in data) for k in ("expression_walk_t5", "spatial_kernel")}
                log.append(f"{layout}: clicked {CORTEX} -> focused {got}; rows {rows}; "
                           f"{len(data)} /api/v1/data/ request(s)" + "".join(f"\n  {u[:200]}" for u in data))
                clicks.append({"tag": layout, "spot": CORTEX, "focused": got, "data_requests": len(data),
                               "obsp_rows": rows})
                if got != CORTEX or any(n != 1 for n in rows.values()) or len(data) != 2:
                    failed.append(f"{layout}: click focused {got}; rows {rows}; {len(data)} data requests")
                s.shot(page, f"{layout}_cortex", None)
                style = page.add_style_tag(content=NO_MODEBAR_CSS)
                for n in names:
                    tid = p[n]["id"]
                    left = legend_left(page, tid) if n.endswith("leiden") else None
                    page.locator(f'.tile[data-tile-id="{tid}"] .js-plotly-plot').screenshot(
                        path=str(OUT / f"{layout}_{n}.png"))
                    crops[f"{layout}_{n}"] = {"legend_left": left,
                                              "box": content_box(OUT / f"{layout}_{n}.png", left and left - 4)}
                style.evaluate("e => e.remove()")
                page.context.close()

                # smoke test: the after-click view reopens headless with its focus and all spots drawn
                page = s.open(view(CORTEX, layout), viewport=VIEWPORTS[layout])
                got = page.evaluate("document.getElementById('focused-cell').value")
                drawn = page.evaluate("""() => [...document.querySelectorAll('.tile .js-plotly-plot')]
                    .map(g => (g._fullData || []).reduce((n, t) => n + ((t.x || []).length), 0))""")
                log.append(f"smoke {layout}_cortex: focus {got}, points per plot {drawn}")
                if got != CORTEX or len(drawn) != len(names) or min(drawn) < 2693:
                    failed.append(f"smoke {layout}_cortex: focus {got}, points {drawn}")
                page.context.close()
            browser.close()
    finally:
        stop_server(proc)
        (OUT / ".screenshots.log").write_text("\n".join(log) + "\n")
        (OUT / "crops.json").write_text(json.dumps(crops, indent=1) + "\n")
    nums = {**store_numbers(CORTEX), "clicks": clicks}
    NUMBERS.write_text(json.dumps(nums, indent=1) + "\n")
    if failed:
        sys.exit("\n".join(failed))


if __name__ == "__main__":
    main()
