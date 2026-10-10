#!/usr/bin/env python
"""Visual proof for AnnZarro's row of Fig. 1c: one DOM-recorded shot per mark.

Runs a local AnnZarro (installed from a given commit) on the 8,090-cell bone-marrow
showcase store, drives it with headless Chromium (1400x900, deviceScaleFactor 1), and writes
evidence/screens/annzarro/<NN>_<what>.png with a sidecar <stem>.annot.yaml from
evidence/tools/annotate.record() (boxes from element bounding boxes, source: dom).

Viewport 1400 x 900 at deviceScaleFactor 1; shots whose proof is a panel's open controls use a
taller window (1400 x 1400-1800, set per shot) so the plot below the controls stays in frame.

Re-run at another version (e.g. the v0.3.0 tag) by installing that commit and passing its
version and sha:

    git -C <annzarro checkout> archive <ref> | tar -x -C $SCRATCH/annzarro_src
    uv venv $SCRATCH/.venv && uv pip install -p $SCRATCH/.venv/bin/python "$SCRATCH/annzarro_src[remote]"
    <playwright python> evidence/screens/annzarro/capture.py \
        --annzarro $SCRATCH/.venv/bin/annzarro --version 0.3.0 --sha <40-hex> \
        --scratch $SCRATCH [--phase main|hosted|web|all]

Phases: main (local server: 01-17), hosted (a second server with login on, 18-19),
web (docs and GitHub pages, 20-22; no server), auto (s01: a Tahoe store given
with --tahoe opens on its default part; port 8924; not part of all). Servers bind 127.0.0.1 on ports 8920-8922;
a python http.server on 8923 serves the store over HTTP for the remote-store shot. On a shared
benchmark machine wrap the call in the gap script (notes/comparison/demos/scale_probe/gap_run.sh) so timed
runs are not disturbed. Data: --data <dir> holding bm_aging_showcase.zarr and
spatial_demo.zarr (default: the repo's data/).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from evidence.tools.annotate import check, record  # noqa: E402

OUT = Path(__file__).resolve().parent
DRIVER = "evidence/screens/annzarro/capture.py"
BY = "evidence-curator"
VIEWPORT = {"width": 1400, "height": 900}
SHOWCASE = "bm_aging_showcase.zarr"
SPATIAL = "spatial_demo.zarr"
DATA_LABEL = "bm_aging_showcase.zarr (8,090 cells x 16,285 genes; data/bm_aging_showcase.FIELDS.md)"
SPATIAL_LABEL = "spatial_demo.zarr (10x Visium mouse brain, 2,693 spots; annzarro docs/_tools/make_spatial_demo.py)"
FOCUS_CELL = "Mature_Young_2#TCAATTCAGTGAGGCT-1"   # the focused monocyte of the paper
PLASMA = "Mature_Mid_1#GCCATGGAGTATGATG-1"         # the Fig 3 plasma cell
HSC = "HSPC_Old_1#GAAGCCCGTGGCTCTG-1"               # the locked HSC of the paper
GENE = "H2-Q7"
CLEAN_CSS = "#notification-container, .notification { display: none !important; } .hoverlayer { display: none !important; }"

A = None          # parsed args
LOG: list[str] = []


# --------------------------------------------------------------------------- views
def ax(t, key, col=""):
    return {"type": t, "key": key, "column": col, **({"locked": False} if t in ("obsp", "varp", "layer") else {})}


def tile(tid, controls=False):
    return {"type": "tile", "id": tid, "controlsVisible": controls}


def split(direction, a, b, pa=50):
    return {"type": "split", "direction": direction,
            "panes": [{"percentage": pa, "controlsVisible": False}, {"percentage": 100 - pa, "controlsVisible": False}],
            "children": [a, b]}


def view(hierarchy, configs, cell=FOCUS_CELL, gene=GENE):
    controls = {}

    def walk(n):
        if n["type"] == "tile":
            controls[n["id"]] = n["controlsVisible"]
        for c in n.get("children", []):
            walk(c)
    walk(hierarchy)
    for k, v in configs.items():
        v.setdefault("id", k)
    return {"v": 1, "constants": {"focusedCell": cell, "focusedGene": gene, "taxonomyId": "10090"},
            "layout": {"v": 1, "hierarchy": [hierarchy], "controlState": controls, "panelConfigs": configs}}


def cplot(title, x, y, color, **kw):
    return {"title": title, "x": x, "y": y, "z": kw.pop("z", None), "color": color, "pointSize": kw.pop("pointSize", 4),
            "pointOpacity": kw.pop("pointOpacity", 0.9), **kw}


def encode(v):
    return base64.urlsafe_b64encode(json.dumps(v, separators=(",", ":")).encode()).decode().rstrip("=")


def link(port, dataset, v=None):
    target = dataset if "://" in str(dataset) else str(A.datadir / dataset)
    url = f"http://127.0.0.1:{port}/?dataset_path={urllib.parse.quote(target, safe='/:')}"
    return url + (f"#view={encode(v)}" if v else "")


def public_url(url):
    """The URL as recorded in a sidecar: no local paths."""
    for enc in (urllib.parse.quote(str(A.datadir), safe="/:"), urllib.parse.quote(str(A.datadir), safe=""), str(A.datadir)):
        url = url.replace(enc, "$DATA_DIR")
    return re.sub(r"#view=.{60,}", lambda m: m.group(0)[:60] + "...", url)


# --------------------------------------------------------------------------- servers
def wait_http(url, proc, what, tries=160):
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            if proc.poll() is not None:
                sys.exit(f"{what} exited; see its log in {A.scratch}")
            time.sleep(0.5)
    sys.exit(f"{what} did not come up")


def start(cmd, log, env=None):
    # A server left on the port (e.g. an earlier, interrupted capture) would answer instead of this one,
    # and every shot would show that server's version: refuse to start rather than shoot it.
    if "--port" in cmd:
        port = int(cmd[cmd.index("--port") + 1])
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                sys.exit(f"port {port} is already in use (lsof -nP -iTCP:{port} -sTCP:LISTEN); stop that server first")
    return subprocess.Popen(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT, start_new_session=True,
                            env={**os.environ, **(env or {})}, cwd=A.scratch)


def stop(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=15)
    except Exception:
        os.killpg(proc.pid, signal.SIGKILL)


def annzarro_env():
    return {"ANNZARRO_HOME": str(A.scratch / "home"), "ANNZARRO_HEADLESS": "1"}


# --------------------------------------------------------------------------- page helpers
def ready(page, timeout=90, settle=1.2):
    js = """() => {
      const vis = e => e.offsetParent !== null && getComputedStyle(e).visibility !== 'hidden';
      const busy = [...document.querySelectorAll('.loading-screen, .loading-overlay, .spinner-border, .fa-spinner, .dataTables_processing, .dt-processing')].filter(vis).length;
      const plots = [...document.querySelectorAll('.tile .js-plotly-plot')];
      const drawn = plots.every(g => g._fullData && g._fullData.length > 0);
      return {busy, drawn, tiles: document.querySelectorAll('.tile').length};
    }"""
    t0, since = time.time(), None
    while time.time() - t0 < timeout:
        s = page.evaluate(js)
        if s["busy"] == 0 and s["drawn"] and not page._inflight:
            since = since or time.time()
            if time.time() - since >= settle:
                return
        else:
            since = None
        time.sleep(0.25)
    LOG.append(f"WARNING not ready after {timeout}s: {s} {[r.url[:120] for r in page._inflight]}")


def new_page(browser, **ctx):
    c = browser.new_context(viewport=VIEWPORT, device_scale_factor=1, color_scheme="light", **ctx)
    page = c.new_page()
    page._inflight = set()
    page._requests = []
    page.on("request", lambda r: (page._inflight.add(r), page._requests.append(r.url)))
    page.on("requestfinished", lambda r: page._inflight.discard(r))
    page.on("requestfailed", lambda r: page._inflight.discard(r))
    page.on("pageerror", lambda e: LOG.append(f"pageerror: {e}"))
    page.on("console", lambda m: LOG.append(f"console.{m.type}: {m.text[:200]}") if m.type == "error" else None)
    return page


def goto(page, url, grow=True, height=None):
    if height:
        page.set_viewport_size({"width": VIEWPORT["width"], "height": height})
    page.goto(url)
    ready(page)
    # a layout with open controls is taller than 900 px: grow the window to the
    # document (as the docs' shot helper does) so plots are in frame; width stays 1400
    for _ in range(3):
        h = page.evaluate("document.documentElement.scrollHeight")
        if not grow or h <= page.viewport_size["height"]:
            break
        page.set_viewport_size({"width": VIEWPORT["width"], "height": min(h, 2000)})
        ready(page)


def shoot(page, name):
    page.add_style_tag(content=CLEAN_CSS)
    time.sleep(0.3)
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path))
    return path


def rec(page, shot, proves, callouts, data=DATA_LABEL, url=None):
    side = record(page, shot, tool="annzarro", proves=[{"column": c, "mark": m, "caption": t} for c, m, t in proves],
                  callouts=callouts, software=A.software, by=BY, driver=DRIVER, data=data,
                  url=public_url(url or page.url))
    errs = check(side)
    LOG.append(f"wrote {side.name}" + (f"  CHECK FAILED: {errs}" if errs else ""))


def tsel(tid, inner=""):
    return f'.tile[data-tile-id="{tid}"] {inner}'.strip()


def row(tid, axis):
    """The selector row (type, key, column) of one axis in a plot's controls."""
    return tsel(tid, f'.axis-type-select[data-axis="{axis}"] >> xpath=..')


def selected(page, tid, axis):
    return page.evaluate("""([t, a]) => [...document.querySelectorAll(`.tile[data-tile-id="${t}"] select[data-axis="${a}"]`)]
                            .map(s => s.selectedOptions[0] ? s.selectedOptions[0].text.trim() : '').filter(Boolean).join(' / ')""", [tid, axis])


def options(page, sel):
    return page.evaluate("s => [...document.querySelector(s).options].map(o => o.text.trim())", sel)


def npoints(page, tid):
    return page.evaluate("""t => { const g = document.querySelector(`.tile[data-tile-id="${t}"] .js-plotly-plot`);
        const names = new Set(); for (const d of g._fullData) for (const c of (d.customdata || [])) names.add(c);
        return names.size; }""", tid)


def click_entity(page, tid, name):
    """Click the point of `name` in a 2D plot, at the pixel Plotly maps it to."""
    pt = page.evaluate("""([t, name]) => {
        const g = document.querySelector(`.tile[data-tile-id="${t}"] .js-plotly-plot`);
        const L = g._fullLayout, r = g.getBoundingClientRect();
        for (const d of g._fullData) {
          const i = (d.customdata || []).indexOf(name);
          if (i < 0) continue;
          const xa = L[(d.xaxis || 'x').replace('x', 'xaxis')], ya = L[(d.yaxis || 'y').replace('y', 'yaxis')];
          return [r.left + xa._offset + xa.l2p(d.x[i]), r.top + ya._offset + ya.l2p(d.y[i])];
        }
        return null; }""", [tid, name])
    if pt is None:
        raise RuntimeError(f"{name} not in {tid}")
    page.mouse.move(pt[0] - 3, pt[1] - 3)
    time.sleep(0.2)
    page.mouse.move(pt[0], pt[1])
    time.sleep(0.4)
    page.mouse.click(pt[0], pt[1])
    time.sleep(0.5)
    sel = "#focused-gene" if "gene-plot" in tid else "#focused-cell"
    got = page.input_value(sel)
    if got != name:
        LOG.append(f"WARNING click on {name} in {tid} focused {got!r}")
    return pt


def api_requests(page, since):
    out = []
    for u in page._requests[since:]:
        if "/api/v1/data/" in u:
            p = urllib.parse.urlparse(u)
            q = urllib.parse.parse_qs(p.query)
            keep = {k: v[0][:40] for k, v in q.items() if k in ("rows", "cols", "row", "col", "name")}
            out.append(p.path.replace("/api/v1/data/", "") + (" " + json.dumps(keep) if keep else ""))
    return out


# --------------------------------------------------------------------------- main-server shots
def views():
    um0, um1 = ax("obsm", "X_umap", "0"), ax("obsm", "X_umap", "1")
    v = {}
    v["cells"] = view(split("horizontal", tile("cell-plot-L", True), tile("cell-plot-R", True)), {
        "cell-plot-L": cplot("UMAP, colour = obsp diffusion_distance row of the focused cell", um0, um1,
                      ax("obsp", "diffusion_distance", PLASMA), colorScale="Viridis", colorReversed=True),
        "cell-plot-R": cplot("x, y = obsp rows of the focused cell (UMAP vs diffusion distance)",
                      ax("obsp", "umap_distance", PLASMA), ax("obsp", "diffusion_distance", PLASMA),
                      ax("obs", "fig3_plasma_groups"))}, cell=PLASMA)
    v["genes"] = view(split("horizontal", tile("gene-plot-L", True), tile("gene-plot-R", True)), {
        "gene-plot-L": cplot("Volcano, colour = varp spearman_fold_change row of the focused gene",
                      ax("var", "kompot_de_Young_to_Old_mean_lfc"), ax("var", "kompot_de_Young_to_Old_mahalanobis"),
                      ax("varp", "spearman_fold_change", GENE), colorScale="RdBu", colorMin=-1, colorMax=1,
                      lockColorRange=True, pointSize=5),
        "gene-plot-R": cplot("x, y = varp rows of the focused gene", ax("varp", "spearman_smoothed", GENE),
                      ax("varp", "spearman_fold_change", GENE), ax("var", "fig4d_class"), pointSize=5)})
    v["focus"] = view(split("horizontal", tile("cell-plot-A"), split("vertical", tile("cell-plot-B"), tile("gene-plot-C")), 50), {
        "cell-plot-A": cplot("A: UMAP, colour = obsp diffusion_walk_t5 row of the focused cell", um0, um1,
                     ax("obsp", "diffusion_walk_t5", FOCUS_CELL), colorScale="Viridis", **{"sortByColor": True}),
        "cell-plot-B": cplot("B: diffusion components, colour = obsp diffusion_distance row", ax("obsm", "X_diffusion", "0"),
                     ax("obsm", "X_diffusion", "1"), ax("obsp", "diffusion_distance", FOCUS_CELL),
                     colorScale="Viridis", colorReversed=True),
        "gene-plot-C": cplot("C: genes, colour = the focused cell's row of the fold-change layer",
                     ax("var", "kompot_de_Young_to_Old_mean_lfc"), ax("var", "kompot_de_Young_to_Old_mahalanobis"),
                     ax("layer", "kompot_de_Young_to_Old_fold_change", FOCUS_CELL), colorScale="RdBu",
                     colorMin=-2, colorMax=2, lockColorRange=True, pointSize=5)})
    v["slots"] = view(split("horizontal", split("vertical", tile("cell-plot-s1", True), tile("cell-plot-s2", True)),
                            split("vertical", tile("gene-plot-s3", True), tile("gene-plot-s4", True))), {
        "cell-plot-s1": cplot("obsm axes, colour = X (focused gene)", um0, um1, ax("layer", "X", GENE)),
        "cell-plot-s2": cplot("obs axes, colour = obsp row", ax("obs", "n_genes_by_counts"), ax("obs", "pct_counts_mt"),
                     ax("obsp", "connectivities", FOCUS_CELL)),
        "gene-plot-s3": cplot("varm axes, colour = varp row", ax("varm", "PCs", "0"), ax("varm", "PCs", "1"),
                     ax("varp", "spearman_fold_change", GENE), colorScale="RdBu", colorMin=-1, colorMax=1, lockColorRange=True),
        "gene-plot-s4": cplot("var axes, colour = a layer row of the focused cell", ax("var", "kompot_de_Young_to_Old_mean_lfc"),
                     ax("var", "kompot_de_Young_to_Old_mahalanobis"),
                     ax("layer", "kompot_de_Young_to_Old_fold_change", FOCUS_CELL), colorScale="RdBu")})
    sb = {"criteria": [
        {"condition": "=", "data": "highres_celltype", "origData": "obs_highres_celltype_main", "type": "string", "value": ["HSC"]},
        {"criteria": [
            {"condition": ">", "data": "kompot_da_Young_to_Old_lfc_zscore", "origData": "obs_kompot_da_Young_to_Old_lfc_zscore_main", "type": "num", "value": ["2"]},
            {"condition": "=", "data": "Age", "origData": "obs_Age_main", "type": "string", "value": ["Old"]}],
         "logic": "OR"}], "logic": "AND"}
    v["filters"] = view(split("vertical", tile("cell-table-T"), split("horizontal", tile("cell-plot-P1"), tile("cell-plot-P2")), 55), {
        "cell-table-T": {"title": "Cell table: HSC AND (DA z-score > 2 OR Age = Old)",
                "columns": [ax("obs", "highres_celltype"), ax("obs", "kompot_da_Young_to_Old_lfc_zscore"), ax("obs", "Age")],
                "searchBuilderConfig": sb},
        "cell-plot-P1": cplot("UMAP masked by the table", um0, um1, ax("obs", "kompot_da_Young_to_Old_lfc_zscore"),
                      tableFilter="cell-table-T", colorScale="RdBu"),
        "cell-plot-P2": cplot("Diffusion components masked by the same table", ax("obsm", "X_diffusion", "0"),
                      ax("obsm", "X_diffusion", "1"), ax("obs", "Age"), tableFilter="cell-table-T")})
    v["table"] = view(tile("cell-table-tb", True), {
        "cell-table-tb": {"title": "Cell table", "columns": [ax("obs", "highres_celltype"), ax("obs", "Age"), ax("obs", "leiden")]}})
    v["spatial"] = view(tile("cell-plot-sp", True), {
        "cell-plot-sp": cplot("Visium spots in tissue coordinates (obsm spatial_upright)", ax("obsm", "spatial_upright", "0"),
                    ax("obsm", "spatial_upright", "1"), ax("obs", "leiden"), equalAspect=True, pointSize=6)},
        cell="AAACAAGTATCTCCCA-1", gene="Ttr")
    v["one"] = view(tile("cell-plot-e1"), {"cell-plot-e1": cplot("UMAP, every cell", um0, um1, ax("obs", "highres_celltype"), pointSize=3)})
    v["share"] = view(split("horizontal", tile("cell-plot-sh1"), tile("gene-plot-sh2"), 40), {
        "cell-plot-sh1": cplot("UMAP, colour = obsp diffusion_distance row", um0, um1, ax("obsp", "diffusion_distance", PLASMA),
                      colorScale="Viridis", colorReversed=True),
        "gene-plot-sh2": cplot("Volcano, colour = varp row of H2-Q7", ax("var", "kompot_de_Young_to_Old_mean_lfc"),
                      ax("var", "kompot_de_Young_to_Old_mahalanobis"), ax("varp", "spearman_fold_change", GENE),
                      colorScale="RdBu", colorMin=-1, colorMax=1, lockColorRange=True, pointSize=5)}, cell=PLASMA)
    v["remote"] = view(tile("cell-plot-r1", True), {
        "cell-plot-r1": cplot("UMAP, colour = fold-change layer of H2-Q7, read over HTTP", um0, um1,
                     ax("layer", "kompot_de_Young_to_Old_fold_change", GENE), colorScale="RdBu")})
    return v


def main_phase(browser):
    port = A.port
    V = views()
    data = A.scratch / "data"
    srv = start([A.annzarro, "start", "--host", "127.0.0.1", "--port", str(port), "--data-dir", str(data), "--no-browser"],
                A.scratch / "server_main.log", annzarro_env())
    httpd = None
    try:
        wait_http(f"http://127.0.0.1:{port}/", srv, "annzarro")
        run = lambda name, fn: _safe(name, fn, browser, port, V)  # noqa: E731
        for name, fn in [("cells", s_cells), ("genes", s_genes), ("focus", s_focus), ("slots", s_slots),
                         ("filters", s_filters), ("table", s_table), ("de", s_de), ("spatial", s_spatial),
                         ("every", s_every), ("subset", s_subset), ("share", s_share)]:
            run(name, fn)
        hd = A.scratch / "httpdata"
        httpd = start([sys.executable, "-m", "http.server", str(port + 3), "--bind", "127.0.0.1", "--directory", str(hd)],
                      A.scratch / "httpd.log")
        wait_http(f"http://127.0.0.1:{port + 3}/{SHOWCASE}/.zgroup", httpd, "http.server")
        run("remote", s_remote)
    finally:
        stop(httpd)
        stop(srv)


def _safe(name, fn, *args):
    try:
        fn(*args)
    except Exception:
        LOG.append(f"FAILED {name}:\n{traceback.format_exc()}")


def s_cells(browser, port, V):
    page = new_page(browser)
    goto(page, link(port, SHOWCASE, V["cells"]), height=1400)
    shot = shoot(page, "01_obsp_row_as_colour_and_axes")
    rec(page, shot, [
        ("cells", "Y", "A stored cells x cells matrix (obsp) is the colour of one plot and both axes of another, chosen from the GUI menus."),
        ("every_cell", "Y", f"The UMAP draws all {npoints(page, 'cell-plot-L'):,} cells of the dataset (statistics bar: All cells); no downsampling.")],
        [(1, row("cell-plot-L", "color"), f"Color = {selected(page, 'cell-plot-L', 'color')}"),
         (2, row("cell-plot-R", "x"), f"X-Axis = {selected(page, 'cell-plot-R', 'x')}"),
         (3, row("cell-plot-R", "y"), f"Y-Axis = {selected(page, 'cell-plot-R', 'y')}"),
         (4, "#focused-cell", f"Focused Cell = {page.input_value('#focused-cell')}: the obsp row shown"),
         (5, "#dataset-stats", f"Cells: {page.inner_text('#cell-count')}, badge '{page.inner_text('#subset-button').strip()}'; "
                               f"the UMAP trace holds {npoints(page, 'cell-plot-L'):,} distinct cells")])
    page.context.close()


def s_genes(browser, port, V):
    page = new_page(browser)
    goto(page, link(port, SHOWCASE, V["genes"]), height=1400)
    shot = shoot(page, "02_varp_row_as_colour_and_axes")
    rec(page, shot, [
        ("genes", "Y", "A stored genes x genes matrix (varp) is the colour of one gene plot and both axes of another, chosen from the GUI menus.")],
        [(1, row("gene-plot-L", "color"), f"Color = {selected(page, 'gene-plot-L', 'color')}"),
         (2, row("gene-plot-R", "x"), f"X-Axis = {selected(page, 'gene-plot-R', 'x')}"),
         (3, row("gene-plot-R", "y"), f"Y-Axis = {selected(page, 'gene-plot-R', 'y')}"),
         (4, "#focused-gene", f"Focused Gene = {page.input_value('#focused-gene')}: the varp row shown")])
    # click another gene in the volcano: both varp panels follow it
    n0 = len(page._requests)
    how = "a click on its point in the volcano"
    click_entity(page, "gene-plot-L", "Apoe")
    ready(page)
    if page.input_value("#focused-gene") != "Apoe":
        # fall back to the header's gene picker (type, Enter): the same focus change
        how = "the header's Focused Gene picker (type Apoe, Enter)"
        page.click("#focused-gene")
        page.fill("#focused-gene", "Apoe")
        time.sleep(1.5)
        page.keyboard.press("Enter")
        time.sleep(0.5)
        ready(page)
    shot = shoot(page, "03_gene_click_redrives_varp_panels")
    reqs = api_requests(page, n0)
    rec(page, shot, [
        ("focus", "Y", f"Focusing another gene ({how}) makes both panels re-read that gene's varp rows and redraw.")],
        [(1, "#focused-gene", f"Focused Gene after the change: {page.input_value('#focused-gene')}"),
         (2, row("gene-plot-L", "color"), f"Color now {selected(page, 'gene-plot-L', 'color')}"),
         (3, row("gene-plot-R", "x"), f"X-Axis now {selected(page, 'gene-plot-R', 'x')}"),
         (4, tsel("gene-plot-R", ".js-plotly-plot"), "data requests after the focus change: " + ("; ".join(r for r in reqs if not r.startswith("names")) or "none (cached)"))])
    page.context.close()


def s_focus(browser, port, V):
    page = new_page(browser)
    goto(page, link(port, SHOWCASE, V["focus"]))
    shot = shoot(page, "04_focus_before_cell_click")
    rec(page, shot, [
        ("focus", "Y", "Before: three panels, each showing a stored row of the focused cell (two obsp matrices, one layer row over genes).")],
        [(1, "#focused-cell", f"Focused Cell = {page.input_value('#focused-cell')}"),
         (2, tsel("cell-plot-A", ".js-plotly-plot"), "A: obsp diffusion_walk_t5 row of that cell"),
         (3, tsel("cell-plot-B", ".js-plotly-plot"), "B: obsp diffusion_distance row of that cell"),
         (4, tsel("gene-plot-C", ".js-plotly-plot"), "C: genes coloured by that cell's row of the fold-change layer")])
    n0 = len(page._requests)
    click_entity(page, "cell-plot-A", HSC)
    ready(page)
    shot = shoot(page, "05_focus_after_cell_click")
    reqs = api_requests(page, n0)
    rec(page, shot, [
        ("focus", "Y", "One click on a cell in plot A re-drives every linked panel through that cell's stored rows: A and B redraw from its obsp rows, C from its layer row."),
        ("lazy", "Y", "The click fetches only the new cell's rows (one per matrix), not the matrices: see callout 5 for the requests the browser made.")],
        [(1, "#focused-cell", f"Focused Cell after the click: {page.input_value('#focused-cell')}"),
         (2, tsel("cell-plot-A", ".js-plotly-plot"), "A redrawn from the new cell's diffusion_walk_t5 row"),
         (3, tsel("cell-plot-B", ".js-plotly-plot"), "B redrawn from its diffusion_distance row"),
         (4, tsel("gene-plot-C", ".js-plotly-plot"), "C redrawn from its fold-change row over genes"),
         (5, "#dataset-stats", "data requests after the click: " + ("; ".join(reqs) or "none"))])
    page.context.close()


def s_slots(browser, port, V):
    page = new_page(browser)
    goto(page, link(port, SHOWCASE, V["slots"]), height=1800)
    cell_types = options(page, tsel("cell-plot-s1", '.axis-type-select[data-axis="color"]'))
    gene_types = options(page, tsel("gene-plot-s3", '.axis-type-select[data-axis="color"]'))
    layer_keys = options(page, tsel("cell-plot-s1", '.axis-key-select[data-axis="color"]'))
    shot = shoot(page, "06_every_slot_in_the_source_menus")
    rec(page, shot, [
        ("slots", "Y", "X, layers, obs, var, obsm, varm, obsp and varp each drive an axis or a colour in this one layout, all chosen from the GUI menus.")],
        [(1, row("cell-plot-s1", "x"), f"obsm: X-Axis = {selected(page, 'cell-plot-s1', 'x')}"),
         (2, row("cell-plot-s1", "color"), f"X: Color = {selected(page, 'cell-plot-s1', 'color')}; the layer menu lists {', '.join(layer_keys[:4])}, ... ({len(layer_keys)} entries, X first)"),
         (3, row("cell-plot-s2", "x"), f"obs: X-Axis = {selected(page, 'cell-plot-s2', 'x')}"),
         (4, row("cell-plot-s2", "color"), f"obsp: Color = {selected(page, 'cell-plot-s2', 'color')}"),
         (5, row("gene-plot-s3", "x"), f"varm: X-Axis = {selected(page, 'gene-plot-s3', 'x')}"),
         (6, row("gene-plot-s3", "color"), f"varp: Color = {selected(page, 'gene-plot-s3', 'color')}"),
         (7, row("gene-plot-s4", "x"), f"var: X-Axis = {selected(page, 'gene-plot-s4', 'x')}"),
         (8, row("gene-plot-s4", "color"), f"layers: Color = {selected(page, 'gene-plot-s4', 'color')}. Source menus: cell plot {cell_types}, gene plot {gene_types}")])
    page.context.close()


def s_filters(browser, port, V):
    page = new_page(browser)
    goto(page, link(port, SHOWCASE, V["filters"]), height=1500)
    page.locator(tsel("cell-plot-P1", ".js-plotly-plot")).hover()
    time.sleep(0.5)
    modebar = page.evaluate("""t => [...document.querySelectorAll(`.tile[data-tile-id="${t}"] .modebar-btn`)]
                               .map(b => b.getAttribute('data-title')).filter(Boolean)""", "cell-plot-P1")
    info = page.evaluate("""() => { const i = document.querySelector('.tile[data-tile-id="cell-table-T"] .dataTables_info, .tile[data-tile-id="cell-table-T"] .dt-info'); return i ? i.textContent.trim() : ''; }""")
    page.evaluate("() => document.querySelectorAll('.tile .tile-content').forEach(e => e.scrollTop = 0)")
    time.sleep(0.3)
    shot = shoot(page, "07_table_filter_masks_linked_plots")
    rec(page, shot, [
        ("filters", "Y", "A nested AND/OR filter on the cell table masks the same cells in both linked plots (cells outside the filter in grey)."),
        ("selection", "Y", "The table filter is the selection mechanism: it restricts every plot linked to it; the plot toolbar has no lasso or box select.")],
        [(1, tsel("cell-table-T", ".dtsb-searchBuilder"), "SearchBuilder: highres_celltype = HSC AND (DA z-score > 2 OR Age = Old)"),
         (2, tsel("cell-table-T", ".dataTables_info, .dt-info"), f"table: {info}"),
         (3, tsel("cell-plot-P1", ".js-plotly-plot"), f"plot 1 (controls hidden) Filter by Table = {selected_text(page, '#table-filter-cell-plot-P1')}"),
         (4, tsel("cell-plot-P2", ".js-plotly-plot"), f"plot 2 (controls hidden) Filter by Table = {selected_text(page, '#table-filter-cell-plot-P2')}"),
         (5, tsel("cell-plot-P1", ".modebar"), f"plot toolbar: {', '.join(modebar)}; no lasso or box select")])
    page.context.close()


def selected_text(page, sel):
    return page.evaluate("s => { const e = document.querySelector(s); return e && e.selectedOptions[0] ? e.selectedOptions[0].text.trim() : ''; }", sel)


def s_table(browser, port, V):
    page = new_page(browser)
    goto(page, link(port, SHOWCASE, V["table"]))
    stats = page.evaluate("""() => { const b = document.querySelector('.tile[data-tile-id="cell-table-tb"] table tbody');
        return {inputs: b.querySelectorAll('input, select, textarea, [contenteditable="true"]').length,
                rows: b.querySelectorAll('tr').length}; }""")
    buttons = page.evaluate("""() => [...document.querySelectorAll('.tile[data-tile-id="cell-table-tb"] .table-controls button')]
                               .map(b => b.textContent.trim()).filter(Boolean)""")
    shot = shoot(page, "08_cell_table_has_no_edit_control")
    rec(page, shot, [
        ("annot", "N", "The cell table, where a label editor would sit, offers column choice, filters and CSV export only; its cells are read-only text.")],
        [(1, tsel("cell-table-tb", ".table-controls"), f"table controls: buttons {buttons}; no add, rename or label action"),
         (2, tsel("cell-table-tb", "table tbody"), f"{stats['rows']} rows shown, {stats['inputs']} editable fields in the table body"),
         (3, "#btn-save-session >> xpath=..", "the only things a user can save: panel sets and share links (views, not labels)")])
    page.context.close()


def s_de(browser, port, V):
    page = new_page(browser)
    goto(page, f"http://127.0.0.1:{port}/?dataset_path={urllib.parse.quote(str(A.datadir / SHOWCASE), safe='/:')}")
    page.wait_for_selector(".tile-type-label", timeout=60000)
    ready(page)
    types = page.evaluate("() => [...document.querySelectorAll('.tile-type-label')].map(e => e.textContent.trim())")
    shot = shoot(page, "09_panel_types_no_de")
    grid = page.evaluate("() => { const g = document.querySelector('.tile-selection-grid'); return g ? '#' + g.id : null; }")
    gs = " Gene Set Analysis sends the selected genes to external enrichment services and shows their results; it tests nothing between cell groups." if "Gene Set Analysis" in types else ""
    rec(page, shot, [
        ("de", "N", "The Create New Panel menu, where a differential-expression or marker panel would be offered, lists plots and tables of stored slots and no DE or marker panel." + gs)],
        [(1, grid or ".tile-selection-grid", f"panel types offered: {', '.join(types)}; no DE, marker or statistics panel"),
         (2, "#dataset-selector >> xpath=..", "the server only reads stored arrays (see the slot menus in shot 06); nothing is computed")])
    page.context.close()


def s_spatial(browser, port, V):
    page = new_page(browser)
    goto(page, link(port, SPATIAL, V["spatial"]), height=1400)
    shot = shoot(page, "10_spatial_coordinates_as_axes")
    rec(page, shot, [
        ("spatial", "Y", "Visium spot positions (obsm spatial_upright) are the plot's x and y, at equal aspect, coloured by cluster.")],
        [(1, row("cell-plot-sp", "x"), f"X-Axis = {selected(page, 'cell-plot-sp', 'x')}"),
         (2, row("cell-plot-sp", "y"), f"Y-Axis = {selected(page, 'cell-plot-sp', 'y')}"),
         (3, "#equal-aspect-cell-plot-sp", "Equal aspect on: one unit of x as long as one of y")], data=SPATIAL_LABEL)
    # Plot Options: what the plot's appearance can be set to, and the export buttons
    page.click("#aesthetics-menu-btn-cell-plot-sp")
    page.wait_for_selector(".aesthetics-menu-content", timeout=10000)
    time.sleep(0.6)
    sections = page.evaluate("() => [...document.querySelectorAll('.aesthetics-menu-content h6')].map(h => h.textContent.trim())")
    bg = page.evaluate("() => [...document.querySelectorAll('.aesthetics-menu-content .aesthetics-section')][0].innerText.replace(/\\s+/g, ' ').slice(0, 160)")
    downloads = []
    for fmt in ("png", "svg"):
        with page.expect_download(timeout=30000) as d:
            if not page.evaluate("() => !!document.querySelector('.aesthetics-menu-content .export-btn')"):
                page.click("#aesthetics-menu-btn-cell-plot-sp")   # an export closes the menu; reopen it
                page.wait_for_selector(".aesthetics-menu-content .export-btn", timeout=10000)
                time.sleep(0.5)
            page.evaluate("f => document.querySelector(`.aesthetics-menu-content .export-btn[data-format='${f}']`).click()", fmt)
        dl = d.value
        p = A.scratch / f"export.{fmt}"
        dl.save_as(p)
        downloads.append(f"{dl.suggested_filename} ({p.stat().st_size:,} bytes)")
        time.sleep(0.5)
    if not page.evaluate("() => !!document.querySelector('.aesthetics-menu-content')"):
        page.click("#aesthetics-menu-btn-cell-plot-sp")
        page.wait_for_selector(".aesthetics-menu-content", timeout=10000)
        time.sleep(0.6)
    page.evaluate("() => document.querySelector('.aesthetics-menu-content').scrollTop = 0")
    time.sleep(0.3)
    shot = shoot(page, "11_plot_options_no_image_layer")
    rec(page, shot, [
        ("image", "N", "The spatial plot's Plot Options, where an image underlay would be set, offer background colour, theme, axes, margins, legend and export only; no image layer.")],
        [(1, ".aesthetics-menu-content .aesthetics-section:first-child", f"Appearance: {bg}"),
         (2, tsel("cell-plot-sp", ".js-plotly-plot"), f"menu sections: {', '.join(sections)}; none loads an image")], data=SPATIAL_LABEL)
    page.evaluate("() => document.querySelector('.aesthetics-menu-content .aesthetics-section:last-child').scrollIntoView({block: 'end'})")
    time.sleep(0.4)
    shot = shoot(page, "11b_plot_options_export")
    rec(page, shot, [
        ("export", "Y", f"Plot Options exports the plot as JPEG, SVG, WEBP or PNG at a chosen size; clicking PNG and SVG downloaded {' and '.join(downloads)}.")],
        [(1, ".aesthetics-menu-content .aesthetics-section:last-child", f"Export section; downloads: {'; '.join(downloads)}")], data=SPATIAL_LABEL)
    page.context.close()


def s_every(browser, port, V):
    pass  # every_cell is proved in shot 01 (stats bar + trace length)


def s_subset(browser, port, V):
    page = new_page(browser)
    goto(page, link(port, SHOWCASE, V["one"]))
    page.click("#subset-button")
    page.wait_for_selector("#subset-fields", state="attached", timeout=10000)
    if not page.is_checked("#subset-enabled"):
        page.click("#subset-enabled")
    page.fill("#subset-n", "2000")
    time.sleep(1.5)
    shot = shoot(page, "12_subset_dialog")
    modal = page.evaluate("() => { const m = document.querySelector('.subset-dialog'); return m ? m.closest('.modal-content') ? '.subset-dialog' : null : null; }")
    rec(page, shot, [
        ("subset", "Y", "The statistics-bar badge opens a dialog to pick a reproducible subset: size, seed, balanced across an obs column, and conditions on obs columns."),
        ("every_cell", "Y", "The default for this 8,090-cell dataset is All cells; only datasets above 200,000 cells open on a 100,000-cell subset (the threshold the dialog notes).")],
        [(1, "#subset-button", f"badge: {page.inner_text('#subset-button').strip()}"),
         (2, "#subset-fields", "number of cells, seed, Balanced across, Only cells where (AND conditions)"),
         (3, ".subset-dialog", "Cell subset dialog")])
    page.context.close()


def s_share(browser, port, V):
    page = new_page(browser, permissions=["clipboard-read", "clipboard-write"])
    goto(page, link(port, SHOWCASE, V["share"]))
    click_entity(page, "cell-plot-sh1", FOCUS_CELL)   # change the focus, so the link carries a state the deep link did not
    ready(page)
    click_entity(page, "gene-plot-sh2", "Apoe")
    ready(page)
    focus = (page.input_value("#focused-cell"), page.input_value("#focused-gene"))
    page.click("#btn-share-link")
    time.sleep(1.0)
    url = page.evaluate("navigator.clipboard.readText()")
    shot = shoot(page, "13_share_link_copied")
    rec(page, shot, [
        ("share", "Y", f"Share Link copies a {len(url):,}-character URL holding the dataset, layout, panel settings and focus.")],
        [(1, "#btn-share-link", f"Share Link: copied {public_url(url)[:90]}"),
         (2, "#focused-cell", f"focus at copy time: cell {focus[0]}"),
         (3, "#focused-gene", f"gene {focus[1]}")])
    # open the copied link in a fresh browser context (no shared storage)
    p2 = new_page(browser)
    goto(p2, url)
    restored = (p2.input_value("#focused-cell"), p2.input_value("#focused-gene"))
    titles = p2.evaluate("() => [...document.querySelectorAll('.tile .tile-title')].map(t => t.value)")
    shot = shoot(p2, "14_share_link_reopened")
    rec(p2, shot, [
        ("share", "Y", "The copied link, opened in a fresh browser context, restores the layout, both panels' settings and the focused cell and gene.")],
        [(1, "#focused-cell", f"restored cell {restored[0]} (copied: {focus[0]})"),
         (2, "#focused-gene", f"restored gene {restored[1]} (copied: {focus[1]})"),
         (3, "#tile-container", f"restored tiles: {titles}")], url=url)
    p2.context.close()
    # panel set: save on the server, then list it
    page.click("#btn-save-session")
    page.wait_for_selector("#session-name", state="visible", timeout=10000)
    page.fill("#session-name", "audit: plasma cell distances")
    page.click("#btn-confirm-session")
    time.sleep(1.5)
    page.keyboard.press("Escape")
    time.sleep(0.8)
    page.click("#btn-load-session")
    page.wait_for_selector("#session-grid", state="visible", timeout=10000)
    time.sleep(1.2)
    sets = page.evaluate("() => [...document.querySelectorAll('#session-grid .session-card, #session-grid > *')].map(e => e.innerText.replace(/\\s+/g, ' ').trim()).filter(Boolean)")
    files = sorted(p.name for p in (A.scratch / "data" / "sessions").glob("*"))
    shot = shoot(page, "15_panel_set_saved_on_server")
    rec(page, shot, [
        ("share", "Y", "Save Panel Set stores the view on the server; Load Panel Set lists it for every user of this instance.")],
        [(1, "#session-grid", f"listed: {sets[:3]}"),
         (2, "#session-modal .modal-footer", f"server data_dir/sessions/: {files}")])
    page.context.close()


def s_remote(browser, port, V):
    page = new_page(browser)
    log = A.scratch / "httpd.log"
    n0 = len(log.read_text().splitlines()) if log.exists() else 0
    url = f"http://127.0.0.1:{port + 3}/{SHOWCASE}"
    goto(page, link(port, url, V["remote"]), height=1400)
    lines = log.read_text().splitlines()[n0:]
    gets = [re.search(r'"GET (\S+)', ln).group(1) for ln in lines if '"GET ' in ln]
    layer = [g for g in gets if "/layers/kompot_de_Young_to_Old_fold_change/" in g and not g.endswith((".zarray", ".zattrs"))]
    zarray = json.loads((A.datadir / SHOWCASE / "layers/kompot_de_Young_to_Old_fold_change/.zarray").read_text())
    import math
    nchunks = math.prod(math.ceil(s / c) for s, c in zip(zarray["shape"], zarray["chunks"]))
    shot = shoot(page, "16_remote_http_store")
    rec(page, shot, [
        ("remote", "Y", "The store is opened from an http:// URL (a web server on 127.0.0.1), and the plot is read from it; s3:// and gs:// go through the same fsspec path."),
        ("lazy", "Y", f"Colouring by one gene fetched {len(layer)} of the layer's {nchunks} chunks over HTTP (shape {zarray['shape']}, chunks {zarray['chunks']}): a gene column, not the matrix.")],
        [(1, "#dataset-stats", f"Dataset: {page.inner_text('#dataset-path')}; Cells {page.inner_text('#cell-count')}, Genes {page.inner_text('#gene-count')}"),
         (2, row("cell-plot-r1", "color"), f"Color = {selected(page, 'cell-plot-r1', 'color')}"),
         (3, tsel("cell-plot-r1", ".js-plotly-plot"), f"web-server log: {len(gets)} GETs, of which {len(layer)} chunk files of the layer, e.g. {layer[:2]}")],
        url=public_url(page.url))
    page.context.close()


# --------------------------------------------------------------------------- hosted
def hosted_phase(browser):
    port = A.port + 1
    data = A.scratch / "data_hosted"
    cfg = A.scratch / "hosted.yaml"
    users = A.scratch / "home" / "hosted_users.json"
    cfg.write_text(f"server:\n  data_dir: {data}\n  allowed_dirs: [{A.realdata.resolve()}]\nauth:\n  enabled: true\n  user_file: {users}\n")
    for u in ("alice", "bob"):
        subprocess.run([A.annzarro, "user", "--config", str(cfg), "add", "--username", u, "--password", f"{u}-audit-pw"],
                       check=False, env={**os.environ, **annzarro_env()}, capture_output=True)
    srv = start([A.annzarro, "start", "--config", str(cfg), "--host", "127.0.0.1", "--port", str(port), "--no-browser"],
                A.scratch / "server_hosted.log", annzarro_env())
    try:
        wait_http(f"http://127.0.0.1:{port}/login", srv, "annzarro (hosted)")
        V = views()
        A.datadir = data          # links name the store under the hosted data dir
        pa = new_page(browser)
        pa.goto(link(port, SHOWCASE, V["share"]))
        pa.wait_for_selector("input[name=username], #username", timeout=30000)
        shot = shoot(pa, "17_hosted_login")
        rec(pa, shot, [
            ("hosted", "Y", "With login on, the server asks every visitor to sign in: one deployment, many user accounts (here alice and bob, made with `annzarro user add`).")],
            [(1, "form", "login form of the hosted server; the share link survives sign-in")])
        login(pa, "alice")
        goto(pa, link(port, SHOWCASE, V["share"]))
        pa.click("#btn-save-session")
        pa.wait_for_selector("#session-name", state="visible", timeout=10000)
        pa.fill("#session-name", "saved by alice")
        pa.click("#btn-confirm-session")
        time.sleep(1.5)
        pb = new_page(browser)
        pb.goto(link(port, SHOWCASE, V["one"]))   # a layout, so no Welcome tile (it prints the server-side path)
        pb.wait_for_selector("input[name=username], #username", timeout=30000)
        login(pb, "bob")
        ready(pb)
        pb.click("#btn-load-session")
        pb.wait_for_selector("#session-grid", state="visible", timeout=10000)
        time.sleep(1.2)
        who = pb.inner_text("#auth-indicator") if pb.is_visible("#auth-indicator") else ""
        sets = pb.evaluate("() => [...document.querySelectorAll('#session-grid > *')].map(e => e.innerText.replace(/\\s+/g, ' ').trim()).filter(Boolean)")
        shot = shoot(pb, "18_hosted_second_user_sees_panel_set")
        rec(pb, shot, [
            ("hosted", "Y", "A second user (bob), signed in to the same server in a separate browser session, sees the panel set alice saved: one deployment serves many users.")],
            [(1, "#auth-indicator", f"signed in: {who.strip()}"),
             (2, "#session-grid", f"panel sets on this server: {sets[:3]}")])
        pa.context.close()
        pb.context.close()
    finally:
        stop(srv)


def login(page, user):
    page.fill("input[name=username], #username", user)
    page.fill("input[name=password], #password", f"{user}-audit-pw")
    page.click("button[type=submit], input[type=submit]")
    page.wait_for_load_state("networkidle")


# --------------------------------------------------------------------------- web pages (docs, GitHub)
def auto_phase(browser):
    """s01: a dataset above subset_threshold opens on its default part, with no subset in the link."""
    if not A.tahoe:
        sys.exit("--phase auto needs --tahoe <store>")
    port = A.port + 4
    data = A.scratch / "data_tahoe"
    data.mkdir(exist_ok=True)
    store = data / A.tahoe.name
    if not store.exists():
        store.symlink_to(A.tahoe)
    srv = start([A.annzarro, "start", "--host", "127.0.0.1", "--port", str(port), "--data-dir", str(data), "--no-browser"],
                A.scratch / "server_auto.log", annzarro_env())
    try:
        wait_http(f"http://127.0.0.1:{port}/", srv, "annzarro (auto)", tries=600)
        A.datadir = data
        umap = {"cell-plot-A": cplot("UMAP, opened with no subset chosen", ax("obsm", "X_umap", "0"), ax("obsm", "X_umap", "1"),
                                     ax("obs", "cell_line_id"))}
        v = {"v": 1, "constants": {"focusedGene": "FN1"},
             "layout": {"v": 1, "hierarchy": [tile("cell-plot-A")], "controlState": {"cell-plot-A": False}, "panelConfigs": umap}}
        page = new_page(browser)
        page.goto(link(port, store.name, v))
        page.wait_for_selector(".ps-chip", timeout=300000)
        ready(page, timeout=300)
        # the plot's status strip sits under the plot: grow the window until it is in frame
        for _ in range(4):
            bottom = page.evaluate("() => { const r = document.querySelector('.ps-chip').closest('.tile').getBoundingClientRect(); return Math.ceil(r.bottom); }")
            if bottom + 8 <= page.viewport_size["height"]:
                break
            page.set_viewport_size({"width": VIEWPORT["width"], "height": min(bottom + 40, 2000)})
            ready(page, timeout=300)
        chip = page.inner_text(".ps-chip").strip()
        cells = page.evaluate("() => document.getElementById('subset-button').parentElement.innerText.trim()")
        shot = shoot(page, "s01_auto_subset_default_part_95M")
        rec(page, shot, [
            ("auto_subset", "Y", "Opened from a link that names no subset, the 95.6M-cell dataset shows its default part: "
             "100,000 cells, part 1 of 957, with the cells left out stated under the plot.")],
            [(1, "#subset-button >> xpath=..", f"statistics bar: {' '.join(cells.split('‹')[0].split())}"),
             (2, "text=/of 957/ >> xpath=..", "part navigator: Part 1 of 957"),
             (3, ".ps-chip", f"plot status: {chip}")],
            data=A.tahoe_label)
        page.context.close()
    finally:
        stop(srv)


def web_phase(browser):
    docs = A.docs_base
    page = new_page(browser)
    page.goto(f"{docs}/deployment/modes.html")
    page.wait_for_load_state("networkidle")
    tbl = page.locator("article table").first
    tbl.scroll_into_view_if_needed()
    shot = shoot(page, "19_docs_every_mode_runs_a_server")
    rec(page, shot, [
        ("static", "N", "Docs screenshot (a GUI shot cannot show an absent mode): all three deployment modes run an AnnZarro server process; none serves static files without a backend."),
        ("desktop", "Y", "The deployment table lists the desktop app as its own mode: open the app, its server runs inside, no login, no setup.")],
        [(1, "article table tr:has-text('Where the server runs')", "Where the server runs: your laptop | a workstation or HPC node | an institutional server"),
         (2, "article table tr:has-text('How you start it')", "How you start it: open the app | annzarro start | gunicorn")],
        data=None, url=page.url)
    page.goto(f"{docs}/getting-started/desktop-app.html")
    page.wait_for_load_state("networkidle")
    shot = shoot(page, "20_docs_desktop_app_downloads")
    rec(page, shot, [
        ("desktop", "Y", "Docs: standalone apps for macOS, Windows and Linux, with their own server inside and no Python installation.")],
        [(1, "article h1", "Desktop app (Electron, its own server inside)"),
         (2, "article table", "download files per system")], data=None, url=page.url)
    page.goto(f"https://github.com/settylab/annzarro/releases/tag/v{A.version}")
    page.wait_for_load_state("networkidle")
    # open the Assets <details> (GitHub loads its list lazily) without toggling it shut
    page.evaluate("() => document.querySelectorAll('details').forEach(d => { if (/Assets/.test(d.querySelector('summary')?.textContent || '')) d.open = true; })")
    # its include-fragment is lazy: bring the Assets list into view so it loads
    page.evaluate("() => [...document.querySelectorAll('details')].find(d => /Assets/.test(d.querySelector('summary')?.textContent || ''))?.scrollIntoView({block: 'start'})")
    page.wait_for_selector('a[href$=".AppImage"]', state="visible", timeout=60000)
    assets = page.evaluate("() => [...document.querySelectorAll('a[href*=\"/releases/download/\"]')].map(a => a.textContent.trim()).filter(Boolean)")
    page.evaluate("() => document.querySelector('a[href$=\".AppImage\"]').closest('details').scrollIntoView({block: 'start'})")
    time.sleep(0.8)
    shot = shoot(page, "21_github_release_desktop_assets")
    rec(page, shot, [
        ("desktop", "Y", f"The v{A.version} GitHub release carries the desktop apps: {', '.join(a for a in assets if a.startswith('AnnZarro'))}.")],
        [(1, 'a[href*="/releases/download/"][href$=".dmg"]', "macOS disk image"),
         (2, 'a[href*="/releases/download/"][href$="setup.exe"]', "Windows installer"),
         (3, 'a[href*="/releases/download/"][href$=".AppImage"]', "Linux AppImage")], data=None, url=page.url)
    page.context.close()


# --------------------------------------------------------------------------- entry
def prepare():
    for d, names in [("data", [SHOWCASE, SPATIAL]), ("data_hosted", [SHOWCASE]), ("httpdata", [SHOWCASE])]:
        p = A.scratch / d
        p.mkdir(parents=True, exist_ok=True)
        for n in names:
            if not (p / n).exists():
                (p / n).symlink_to(A.datadir / n)
    (A.scratch / "home").mkdir(exist_ok=True)
    sessions = A.scratch / "data" / "sessions"
    if sessions.exists():
        shutil.rmtree(sessions)
    hs = A.scratch / "data_hosted" / "sessions"
    if hs.exists():
        shutil.rmtree(hs)


def main():
    global A
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--annzarro", required=True, help="the annzarro CLI of the install under test")
    ap.add_argument("--version", required=True, help="AnnZarro version, e.g. 0.2.0")
    ap.add_argument("--sha", required=True, help="40-hex commit of settylab/annzarro that was installed")
    ap.add_argument("--scratch", type=Path, required=True, help="writable scratch dir (data links, logs, config)")
    ap.add_argument("--data", type=Path, default=REPO / "data", help="dir holding the two stores")
    ap.add_argument("--port", type=int, default=8920)
    ap.add_argument("--phase", default="all", choices=["main", "hosted", "web", "auto", "all"])
    ap.add_argument("--tahoe", type=Path, default=None, help="Tahoe-100M store for --phase auto (s01)")
    ap.add_argument("--tahoe-label", default="Tahoe-100M, 95,624,334 cells (tahoe_panel_95.6M_plot.zarr)")
    ap.add_argument("--docs-base", default="https://annzarro.readthedocs.io/en/latest")
    A = ap.parse_args()
    A.scratch = A.scratch.resolve()
    A.datadir = A.scratch / "data"
    A.software = f"AnnZarro {A.version} (settylab/annzarro@{A.sha[:7]}, pip install from that commit)"
    for n in (SHOWCASE, SPATIAL):
        if not (A.data / n).exists():
            sys.exit(f"missing {A.data / n}")
    real = A.data
    A.datadir = real
    A.realdata = real
    prepare()
    A.datadir = A.scratch / "data"
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for ph, fn in (("main", main_phase), ("hosted", hosted_phase), ("web", web_phase), ("auto", auto_phase)):
                if A.phase == ph or (A.phase == "all" and ph != "auto"):
                    _safe(ph, fn, browser)
        finally:
            browser.close()
    LOG.append(f"done in {time.time() - t0:.0f}s")
    (A.scratch / f"capture_{A.phase}.log").write_text("\n".join(LOG) + "\n")
    print("\n".join(LOG))


if __name__ == "__main__":
    main()
