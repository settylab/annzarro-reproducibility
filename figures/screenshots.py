#!/usr/bin/env python
"""Reproducible screenshots of the AnnZarro web app for the protocol paper.

Starts an AnnZarro server on 127.0.0.1 (no auth, no browser), builds deep links for
the demo views against this machine's absolute path to ``data/bm_aging.zarr``, drives
headless Chromium with Playwright, writes PNGs to ``manuscript/figures/screens/`` and
stops the server.

Requirements (a separate venv; do not use the analysis env):

    uv venv venv && VIRTUAL_ENV=venv uv pip install -e <annzarro checkout> playwright zarr
    venv/bin/playwright install chromium
    venv/bin/python figures/screenshots.py

Options: ``--annzarro`` path to the ``annzarro`` CLI (default: next to this python),
``--port`` (default 8031), ``--url`` to reuse an already running server, ``--only`` to
capture a subset (overview, A..E, focus, share, filtercheck). ``filtercheck`` writes no
image: it applies view E's table filter in the page and fails the run if that fetches data.

Each capture waits until (i) no HTTP request is in flight, (ii) no loading screen,
overlay or spinner is visible, (iii) every Plotly graph has drawn its traces and
(iv) the state above held for 1.5 s. Toasts are recorded to the log and then hidden.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
import zarr
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "bm_aging.zarr"
VIEWS = ROOT / "data_prep" / "demo_panelsets"
OUT = ROOT / "manuscript" / "figures" / "screens"

HSC = "HSPC_Old_1#GAAGCCCGTGGCTCTG-1"
MONO = "Mature_Young_2#TCAATTCAGTGAGGCT-1"
FC_LAYER = "kompot_de_Young_to_Old_fold_change"
VIEWPORT = {"width": 1600, "height": 1000}
OVERVIEW_VIEWPORT = {"width": 1800, "height": 1000}
OVERVIEW_PANELS_PX = 1300   # height of the panel area in the overview
# Fig. 2b sets four walk tiles side by side: a narrower window keeps their axis labels
# and status lines legible at a quarter of the page width.
FOCUS_VIEWPORT = {"width": 1100, "height": 760}
# Fig. 2c: a shorter window keeps the table to a few rows, so the table and the masked
# UMAP share one row of the figure at a legible size.
E_VIEWPORT = {"width": 1600, "height": 760}
DSF = 2

HOLD_CONTROLS_JS = """
document.addEventListener('DOMContentLoaded', () => {
  const s = document.createElement('style');
  s.id = 'shot-hold-controls';
  s.textContent = '.tile-content .plot-controls, .tile-content .table-controls { display: none !important; }';
  document.head.appendChild(s);
});
"""

HOVER = [{"type": "obs", "key": "_index"}, {"type": "obs", "key": "highres_celltype"}]
UMAP_X = {"type": "obsm", "key": "X_umap", "column": "0"}
UMAP_Y = {"type": "obsm", "key": "X_umap", "column": "1"}

# Hides transient UI (toasts) and the hover label; injected before every capture.
CLEAN_CSS = """
#notification-container, .notification { display: none !important; }
.hoverlayer { display: none !important; }
"""
NO_MODEBAR_CSS = ".modebar-container, .modebar { display: none !important; }"


# --------------------------------------------------------------------------- links
def encode_view(view: dict) -> str:
    """Uncompressed base64url(JSON) payload; every AnnZarro build decodes it."""
    raw = json.dumps(view, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def deep_link(base: str, view: dict) -> str:
    return f"{base}/?dataset_path={DATASET}#view={encode_view(view)}"


def load_view(name: str) -> dict:
    return json.loads((VIEWS / f"{name}.view.json").read_text())


def tile(tid: str) -> dict:
    return {"type": "tile", "id": tid, "controlsVisible": False}


def split(direction: str, a: dict, b: dict, pa: int = 50) -> dict:
    return {
        "type": "split",
        "direction": direction,
        "panes": [{"percentage": pa, "controlsVisible": False},
                  {"percentage": 100 - pa, "controlsVisible": False}],
        "children": [a, b],
    }


def walk_umap(tid: str, title: str) -> dict:
    return {
        "id": tid, "title": title, "x": UMAP_X, "y": UMAP_Y, "z": None,
        "color": {"type": "obsp", "key": "diffusion_walk_t5", "column": HSC, "locked": False},
        # Reversed Blues instead of view A's reversed Hot: a zero-probability cell is
        # light grey, not white, so the UMAP outline stays visible around the walk.
        "pointSize": 3, "pointOpacity": 0.8, "colorScale": "Blues", "colorReversed": True,
        "highlightFocusedCell": True, "hoverInfo": HOVER,
    }


def overview_view() -> dict:
    """Four tiles: kernel walk, Kompot volcano, fold-change UMAP, filtered cell table."""
    cfg = {
        "cell-plot-O1": walk_umap("cell-plot-O1", "5-step diffusion walk from the focused cell"),
        "gene-plot-O2": {
            "id": "gene-plot-O2", "title": "Kompot volcano, color = Spearman (fold change) to focused gene",
            "x": {"type": "var", "key": "kompot_de_Young_to_Old_mean_lfc", "column": ""},
            "y": {"type": "var", "key": "kompot_de_Young_to_Old_mahalanobis", "column": ""},
            "z": None,
            "color": {"type": "varp", "key": "spearman_fold_change", "column": "H2-Q7", "locked": False},
            "pointSize": 5, "pointOpacity": 0.8, "colorScale": "RdBu",
            "colorMin": -1, "colorMax": 1, "lockColorRange": True,
            "hoverInfo": [{"type": "var", "key": "_index"}],
        },
        "cell-plot-O3": {
            "id": "cell-plot-O3", "title": "Fold change (Young to Old) of the focused gene",
            "x": UMAP_X, "y": UMAP_Y, "z": None,
            "color": {"type": "layer", "key": FC_LAYER, "column": "H2-Q7", "locked": False},
            "pointSize": 3, "pointOpacity": 0.8, "colorScale": "RdBu", "centeringActive": True,
            "highlightFocusedCell": True, "hoverInfo": HOVER,
        },
        "cell-table-O4": {
            "id": "cell-table-O4", "title": "Cells filtered by cell type (HSC)",
            "columns": [
                {"type": "obs", "key": "highres_celltype", "column": ""},
                {"type": "obs", "key": "Age", "column": ""},
                {"type": "obs", "key": "kompot_da_Young_to_Old_lfc_zscore", "column": ""},
            ],
            "searchBuilderConfig": {
                "criteria": [{"condition": "=", "data": "highres_celltype",
                              "origData": "obs_highres_celltype_main", "type": "string",
                              "value": ["HSC"]}],
                "logic": "AND",
            },
        },
    }
    hier = split("horizontal",
                 split("vertical", tile("cell-plot-O1"), tile("cell-plot-O3")),
                 split("vertical", tile("gene-plot-O2"), tile("cell-table-O4"), 58), 42)
    return {
        "v": 1,
        "constants": {"focusedCell": HSC, "focusedGene": "H2-Q7", "taxonomyId": "10090"},
        "layout": {"v": 1, "hierarchy": [hier],
                   "controlState": {k: False for k in cfg}, "panelConfigs": cfg},
    }


def focus_view() -> dict:
    """Walk UMAP (clicked) beside a cell-type UMAP that shows where each click lands."""
    cfg = {
        "cell-plot-F1": walk_umap("cell-plot-F1", "5-step diffusion walk from the focused cell"),
        "cell-plot-F2": {
            "id": "cell-plot-F2", "title": "Cell types (focused cell highlighted)",
            "x": UMAP_X, "y": UMAP_Y, "z": None,
            "color": {"type": "obs", "key": "highres_celltype", "column": ""},
            "pointSize": 3, "pointOpacity": 0.8, "colorScale": "Viridis",
            "highlightFocusedCell": True, "hoverInfo": HOVER,
        },
    }
    return {
        "v": 1,
        "constants": {"focusedCell": HSC, "focusedGene": "S100a9", "taxonomyId": "10090"},
        "layout": {"v": 1,
                   "hierarchy": [split("horizontal", tile("cell-plot-F1"), tile("cell-plot-F2"))],
                   "controlState": {k: False for k in cfg}, "panelConfigs": cfg},
    }


def trajectory_cells() -> list[tuple[str, list[str]]]:
    """HSC -> GMP -> cMoP -> Monocyte. The HSC and the monocyte are the protocol's
    example cells. Candidates (the example cell, then the 10 cells nearest the type's UMAP
    median) are tried in order until a click lands on that cell and not on a neighbour
    drawn above it."""
    z = zarr.open_group(str(DATASET), mode="r")
    cats = list(z["obs/highres_celltype/categories"][:])
    codes = z["obs/highres_celltype/codes"][:]
    names = z["obs/_index"][:]
    um = z["obsm/X_umap"][:]
    out = [("HSC", [HSC])]
    for ct, preferred in (("GMP", []), ("cMoP", []), ("Monocyte", [MONO])):
        m = np.where(codes == cats.index(ct))[0]
        d = ((um[m] - np.median(um[m], 0)) ** 2).sum(1)
        near = [str(names[i]) for i in m[np.argsort(d)[:10]]]
        out.append((ct, preferred + [c for c in near if c not in preferred]))
    return out


# --------------------------------------------------------------------------- server
def start_server(annzarro: str, port: int, log: Path) -> subprocess.Popen:
    cmd = [annzarro, "start", "--host", "127.0.0.1", "--port", str(port),
           "--data-dir", str(ROOT / "data"), "--no-browser", "--auth-disabled"]
    proc = subprocess.Popen(cmd, stdout=log.open("w"), stderr=subprocess.STDOUT,
                            start_new_session=True)
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            return proc
        except Exception:
            if proc.poll() is not None:
                sys.exit(f"server exited, see {log}")
            time.sleep(0.5)
    stop_server(proc)
    sys.exit("server did not come up")


def stop_server(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=15)
    except Exception:
        os.killpg(proc.pid, signal.SIGKILL)


# --------------------------------------------------------------------------- page
class Shooter:
    def __init__(self, browser, base: str, log: list[str]):
        self.browser, self.base, self.log = browser, base, log

    def open(self, view: dict, viewport=VIEWPORT, clipboard_denied=False) -> Page:
        ctx = self.browser.new_context(viewport=viewport, device_scale_factor=DSF,
                                       color_scheme="light")
        if clipboard_denied:
            # The plain-http cluster case: writeText rejects, the app shows the field.
            ctx.add_init_script("""
              Object.defineProperty(navigator, 'clipboard', {value: {
                writeText: () => Promise.reject(new DOMException('denied', 'NotAllowedError'))
              }});""")
        ctx.add_init_script(HOLD_CONTROLS_JS)
        page = ctx.new_page()
        page._inflight = set()
        page._urls = []
        page.on("request", lambda r: (page._inflight.add(r), page._urls.append(r.url)))
        page.on("requestfinished", lambda r: page._inflight.discard(r))
        page.on("requestfailed", lambda r: page._inflight.discard(r))
        page.on("console", lambda m: self.log.append(f"console.{m.type}: {m.text[:300]}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: self.log.append(f"pageerror: {e}"))
        # Deep links do not keep tile controls collapsed: controlState=false is
        # overridden when the dataset finishes loading (see SCREENSHOTS.md). With the
        # controls open, a half-height tile leaves the graph ~0 px tall and Plotly throws
        # "Something went wrong with axis scaling". Until that is fixed, a stylesheet
        # holds the controls closed while the view loads, then each tile's own toggle
        # button collapses them for real (as a user would) and the stylesheet is removed.
        page.goto(deep_link(self.base, view))
        self.ready(page)
        self.hide_controls(page)
        page.evaluate("document.getElementById('shot-hold-controls')?.remove()")
        self.ready(page)
        # The page grows with its content (body is min-height 100vh, not height), so a
        # tall tile such as a table with its SearchBuilder pushes the layout below the
        # fold. Grow the window to the document so the whole layout is in frame.
        for _ in range(4):
            h = page.evaluate("document.documentElement.scrollHeight")
            if h <= page.viewport_size["height"]:
                break
            page.set_viewport_size({"width": viewport["width"], "height": h})
            self.ready(page)
        return page

    def fit_panels(self, page: Page, height: int) -> None:
        """Give the panel area a fixed height and frame exactly the header and panels.

        The panel area keeps the height it was given, and the "Create New Panel"
        chooser fills whatever is left below it; neither belongs in a figure.
        """
        page.evaluate("""(h) => {
          document.querySelector('.tile-container > .panel-wrapper').style.height = h + 'px';
          const sel = document.querySelector('.tile-container > .tile-selector');
          if (sel) sel.style.display = 'none';
          window.dispatchEvent(new Event('resize'));
        }""", height)
        bottom = page.evaluate("""() => Math.ceil(document.querySelector(
          '.tile-container > .panel-wrapper').getBoundingClientRect().bottom)""")
        page.set_viewport_size({"width": page.viewport_size["width"], "height": bottom})
        self.ready(page)

    def ready(self, page: Page, timeout=90, settle=1.5) -> None:
        js = """() => {
          const vis = e => e.offsetParent !== null && getComputedStyle(e).visibility !== 'hidden';
          const busy = [...document.querySelectorAll(
              '.loading-screen, .loading-overlay, .spinner-border, .fa-spinner, .dataTables_processing, .dt-processing')]
              .filter(vis).length;
          const plots = [...document.querySelectorAll('.tile .js-plotly-plot')];
          const drawn = plots.every(g => g._fullData && g._fullData.length > 0 &&
                                         g._fullData[0].x && g._fullData[0].x.length > 0);
          const tiles = document.querySelectorAll('.tile').length;
          return {busy, drawn, plots: plots.length, tiles};
        }"""
        t0, stable_since = time.time(), None
        while time.time() - t0 < timeout:
            s = page.evaluate(js)
            ok = s["tiles"] > 0 and s["busy"] == 0 and s["drawn"] and not page._inflight
            if ok:
                stable_since = stable_since or time.time()
                if time.time() - stable_since >= settle:
                    page.evaluate("document.fonts.ready")
                    return
            else:
                stable_since = None
            time.sleep(0.25)
        urls = [r.url[:160] for r in page._inflight]
        self.log.append(f"WARNING: not ready after {timeout}s: {s}, inflight={urls}")

    def hide_controls(self, page: Page) -> None:
        """Deep-link controlState=false is overridden at panel init (see SCREENSHOTS.md),
        so collapse each tile's controls with its own toggle button, as a user would."""
        n = page.evaluate("""() => {
          let n = 0;
          for (const t of document.querySelectorAll('.tile')) {
            const c = t.querySelector('.tile-content .plot-controls, .tile-content .table-controls');
            if (c && c.style.display !== 'none') { t.querySelector('.tile-toggle-controls').click(); n++; }
          }
          return n; }""")
        if n:
            self.ready(page)
        return n

    def toasts(self, page: Page, tag: str) -> None:
        for t in page.evaluate("""() => [...document.querySelectorAll('.notification')]
                                   .map(n => n.className + ' | ' + n.textContent.trim())"""):
            self.log.append(f"{tag}: toast {t}")

    def shot(self, page: Page, name: str, tiles: dict[str, str] | None = None) -> None:
        self.toasts(page, name)
        page.mouse.move(2, VIEWPORT["height"] - 2)
        page.add_style_tag(content=CLEAN_CSS)
        time.sleep(0.3)
        page.screenshot(path=str(OUT / f"{name}.png"))
        if tiles:
            style = page.add_style_tag(content=NO_MODEBAR_CSS)
            for tid, tname in tiles.items():
                page.locator(f'.tile[data-tile-id="{tid}"] .tile-content').screenshot(
                    path=str(OUT / f"{tname}_tile.png"))
            style.evaluate("e => e.remove()")
        self.log.append(f"wrote {name}.png" + (f" + {len(tiles)} tile(s)" if tiles else ""))

    def table_info(self, page: Page) -> str:
        return page.evaluate("""() => [...document.querySelectorAll('.dataTables_info, .dt-info')]
                                 .map(e => e.textContent.trim()).join(' / ')""")


def in_table(page: Page, tid: str) -> int:
    """Points in the "In table" trace of a table-masked plot."""
    return page.evaluate("""(tid) => {
      const g = document.querySelector(`.tile[data-tile-id="${tid}"] .js-plotly-plot`);
      const t = g._fullData.find(t => t.name === 'In table');
      return t ? t.x.length : -1; }""", tid)


def click_cell(page: Page, tid: str, cell: str) -> str:
    """Click the point of `cell` in the Plotly graph of tile `tid`, like a user."""
    pos = page.evaluate("""([tid, cell]) => {
      const g = document.querySelector(`.tile[data-tile-id="${tid}"] .js-plotly-plot`);
      const tr = g._fullData[0], i = tr.customdata.indexOf(cell);
      if (i < 0) return null;
      const L = g._fullLayout, xa = L.xaxis, ya = L.yaxis, r = g.getBoundingClientRect();
      return {x: r.left + xa._offset + xa.l2p(tr.x[i]), y: r.top + ya._offset + ya.l2p(tr.y[i])};
    }""", [tid, cell])
    if pos is None:
        raise RuntimeError(f"{cell} not in plot {tid}")
    page.mouse.move(pos["x"], pos["y"])
    time.sleep(0.4)
    page.mouse.click(pos["x"], pos["y"])
    time.sleep(0.5)
    return page.evaluate("document.getElementById('focused-cell').value")


# --------------------------------------------------------------------------- main
class _Log(list):
    """A list that also echoes each entry as it is appended."""

    def append(self, item):
        print(item, flush=True)
        super().append(item)


def main() -> None:
    global OUT
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--annzarro", default=str(Path(sys.executable).parent / "annzarro"))
    ap.add_argument("--port", type=int, default=8031)
    ap.add_argument("--url", help="use a running server instead of starting one")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--out", type=Path, default=OUT, help="output directory (default: %(default)s)")
    args = ap.parse_args()
    OUT = args.out
    want = lambda k: args.only is None or k in args.only  # noqa: E731

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "focus_sequence").mkdir(exist_ok=True)
    log: list[str] = _Log()
    failed: list[str] = []
    proc = None
    if args.url:
        base = args.url.rstrip("/")
    else:
        proc = start_server(args.annzarro, args.port,
                            Path(tempfile.gettempdir()) / "annzarro_screenshots_server.log")
        base = f"http://127.0.0.1:{args.port}"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            s = Shooter(browser, base, log)

            if want("overview"):
                # Wider and taller than the other views: the volcano shows its controls,
                # and the table needs room for rows below its SearchBuilder.
                page = s.open(overview_view(), viewport=OVERVIEW_VIEWPORT)
                # Step 34 and the colour controls: the volcano's controls are open so
                # its colour row, with Strong on top pressed (the default), is in frame.
                page.click('.tile[data-tile-id="gene-plot-O2"] .tile-toggle-controls')
                s.ready(page)
                pressed = page.get_attribute("#sort-by-color-gene-plot-O2", "aria-pressed")
                log.append(f"overview: volcano Strong on top aria-pressed={pressed}")
                if pressed != "true":
                    sys.exit("Strong on top is not pressed on the overview volcano")
                s.fit_panels(page, OVERVIEW_PANELS_PX)
                log.append(f"overview table: {s.table_info(page)}")
                # Fig. 2a enlarges one status line in an inset, cropped from overview.png:
                # record where each plot's status line and its text sit (CSS px).
                rects = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll(
                    '.tile[data-tile-id] .plot-status')].map(st => {
                  const r = e => { const b = e.getBoundingClientRect();
                                   return [b.x, b.y, b.width, b.height].map(v => Math.round(v * 10) / 10); };
                  const t = st.querySelector('.ps-text') || st;
                  return [st.closest('.tile').dataset.tileId,
                          {strip: r(st), text: r(t), label: t.textContent.trim(),
                           class: st.className}]; }))""")
                (OUT / "overview_status.json").write_text(
                    json.dumps({"dsf": DSF, "status": rects}, indent=1) + "\n")
                log.append(f"overview status lines: { {k: v['label'] for k, v in rects.items()} }")
                s.shot(page, "overview", {"cell-plot-O1": "overview_walk",
                                          "gene-plot-O2": "overview_volcano",
                                          "cell-plot-O3": "overview_foldchange",
                                          "cell-table-O4": "overview_table"})
                page.context.close()

            views = {
                "A": ("A_kernel_walk", {"cell-plot-A1": "A_walk", "cell-plot-A2": "A_dm_kernel"}),
                "B": ("B_volcano_spearman", {"gene-plot-B1": "B_volcano_smoothed",
                                             "gene-plot-B2": "B_volcano_foldchange"}),
                "C": ("C_foldchange_umap", {"cell-plot-C1": "C_foldchange", "cell-plot-C2": "C_young",
                                            "cell-plot-C3": "C_old"}),
                "D": ("D_locked_vs_focused_cell", {"gene-plot-D1": "D_scatter",
                                                   "cell-plot-D2": "D_celltypes"}),
                "E": ("E_table_filter", {"cell-table-E1": "E_table", "cell-plot-E2": "E_umap"}),
            }
            for key, (name, tiles) in views.items():
                if not want(key):
                    continue
                view = load_view(name)
                if key == "E":
                    # The saved view gives the table 45%; at that width its row count and
                    # pager overlap, and below ~65% the SearchBuilder covers the "Search:"
                    # label. Fig. 2c needs both readable.
                    for pane, pct in zip(view["layout"]["hierarchy"][0]["panes"], (65, 35)):
                        pane["percentage"] = pct
                page = s.open(view, viewport=E_VIEWPORT if key == "E" else VIEWPORT)
                if key == "E":
                    info = s.table_info(page)
                    n = page.evaluate("""() => {
                      const g = document.querySelector('.tile[data-tile-id="cell-plot-E2"] .js-plotly-plot');
                      return g._fullData.map(t => (t.name || '') + ':' + t.x.length); }""")
                    log.append(f"E table: {info}; E plot traces: {n}")
                s.shot(page, name, tiles)
                page.context.close()

            if want("filtercheck"):
                # Fig. 2c's caption: the table filter masks the UMAP "without any new data
                # request". Open view E with only the first condition (319 HSCs), then
                # apply the full two-condition filter through the table's SearchBuilder and
                # count /api/v1/data/ requests from that moment until the page settles.
                view = load_view("E_table_filter")
                sb = view["layout"]["panelConfigs"]["cell-table-E1"]["searchBuilderConfig"]
                one = {**sb, "criteria": sb["criteria"][:1]}
                view["layout"]["panelConfigs"]["cell-table-E1"]["searchBuilderConfig"] = one
                page = s.open(view)
                before = in_table(page, "cell-plot-E2")
                # Control: loading the view does fetch through /api/v1/data/, so the
                # listener below would see such requests if the filter made any.
                on_load = sum("/api/v1/data/" in u for u in page._urls)
                data_reqs: list[str] = []
                page.on("request", lambda r: data_reqs.append(r.url)
                        if "/api/v1/data/" in r.url else None)
                page.evaluate("""(cfg) => {
                  const tile = document.querySelector('.tile[data-tile-id="cell-table-E1"]');
                  const el = $.fn.dataTable.tables().find(t => tile.contains(t));
                  $(el).DataTable().searchBuilder.rebuild(cfg); }""", sb)
                s.ready(page)
                after = in_table(page, "cell-plot-E2")
                log.append(f"filtercheck: {on_load} /api/v1/data/ requests while loading; "
                           f"In table {before} -> {after} after the second condition; "
                           f"/api/v1/data/ requests after the filter: {len(data_reqs)}"
                           + "".join(f"\n  {u[:160]}" for u in data_reqs))
                page.context.close()
                # v0.4.1 polls /data/fingerprint (the store's identity, no cell data) in the
                # background after opening a store; it is logged but is not a data fetch
                cell_reqs = [u for u in data_reqs if "/api/v1/data/fingerprint?" not in u]
                if after != 290 or cell_reqs or not on_load:
                    failed.append("filtercheck: the filter did not mask to 290 cells, or it "
                                  "fetched data (see the log); Fig. 2c's caption says it does not")

            if want("focus"):
                page = s.open(focus_view(), viewport=FOCUS_VIEWPORT)
                for k, (ct, cands) in enumerate(trajectory_cells(), 1):
                    if k == 1:  # the deep link's focus; clicks start from here
                        log.append(f"focus 1: deep-link focus {ct} {cands[0]}")
                    else:
                        for cell in cands:
                            n0 = len(page._urls)
                            got = click_cell(page, "cell-plot-F1", cell)
                            s.ready(page)
                            # Fig. 2b's caption: "each click fetched one row".
                            data = [u for u in page._urls[n0:] if "/api/v1/data/" in u]
                            log.append(f"focus {k}: clicked {ct} {cell} -> focused {got}; "
                                       f"{len(data)} /api/v1/data/ request(s)"
                                       + "".join(f"\n  {u[:200]}" for u in data))
                            rows = [u for u in data if "/api/v1/data/fingerprint?" not in u]   # identity polls, logged
                            if got == cell and (len(rows) != 1
                                                or "/obsp/diffusion_walk_t5?" not in rows[0]):
                                failed.append(f"focus {k}: expected one diffusion_walk_t5 row "
                                              f"request, got {len(rows)}; Fig. 2b's caption "
                                              "says each click fetched one row")
                            if got == cell:
                                break
                        else:
                            log.append(f"focus {k}: WARNING no {ct} candidate could be clicked")
                    tag = f"focus_sequence/{k}_{ct.replace(' ', '_')}"
                    s.shot(page, tag, None)
                    style = page.add_style_tag(content=NO_MODEBAR_CSS)
                    page.locator('.tile[data-tile-id="cell-plot-F1"] .tile-content').screenshot(
                        path=str(OUT / f"{tag}_tile.png"))
                    style.evaluate("e => e.remove()")
                page.context.close()

            if want("share"):
                page = s.open(focus_view(), clipboard_denied=True)
                page.click("#btn-share-link")
                page.wait_for_selector("#share-link-fallback:not([hidden])", timeout=10000)
                link = page.input_value("#share-link-field")
                log.append(f"share link ({len(link)} chars): {link[:120]}...")
                # The app selects the whole link, which scrolls the narrow field to its
                # tail; show the head (host and dataset_path) instead, selection kept.
                page.evaluate("document.getElementById('share-link-field').scrollLeft = 0")
                page.mouse.move(2, VIEWPORT["height"] - 2)
                page.add_style_tag(content=CLEAN_CSS)
                time.sleep(0.3)
                page.screenshot(path=str(OUT / "share_link.png"))
                page.locator("#app-header").screenshot(path=str(OUT / "share_link_header.png"))
                page.context.close()
            browser.close()
    finally:
        if proc:
            stop_server(proc)
        (OUT / ".screenshots.log").write_text("\n".join(log) + "\n")
    if failed:
        sys.exit("\n".join(failed))


if __name__ == "__main__":
    main()
