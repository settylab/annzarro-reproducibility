#!/usr/bin/env python
"""The web-tool task: start the tool's server, open it in headless Chromium,
colour the UMAP by cell line, then by one gene, screenshot each. Run inside
`memmon.py --web`, which splits the memory into client (every Chromium
process) and server (the tool's processes); this driver and Playwright's node
driver are not counted.

Browser: Playwright's bundled Chromium (new headless, WebGL on the GPU via
ANGLE Metal), 1600 x 900, --enable-precise-memory-info: as ../scale/ceiling.

Every cell drawn, checked two ways where the tool allows:
- the tool's own statement in the page (e.g. CELLxGENE "umap: N out of N cells");
- a WebGL draw-call counter injected before the page loads: per animation
  frame, the sum of point primitives (drawArrays/drawElements with mode POINTS)
  and of instances (instanced draws, one instance per point in deck.gl and
  regl point sprites). The largest frame total is reported as `gl_points`.

With --server-url (CELLxGENE, Cirrocumulus, iSEE) the tool's server is
already running elsewhere: nothing is started here, INPUT is ignored, and only
the client is measured; --proxy routes Chromium through a SOCKS proxy.

Usage: web_task.py TOOL VARIANT INPUT OUTPREFIX --n N [--port 8930] [--server-url URL] [--proxy socks5://...]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
COMPARE = Path.home() / "annzarro_compare"
GENE, COLOUR = "MALAT1", "cell_line_id"
LIMIT = 1750  # s; memmon kills the whole run at 1800

GL_HOOK = """
(() => {
  const st = window.__glc = {cur: {pts: 0, inst: 0}, max: {pts: 0, inst: 0}, last: {pts: 0, inst: 0}, calls: 0, maxcall: 0};
  const add = (k, v) => { st.cur[k] += v; st.calls++; st.maxcall = Math.max(st.maxcall, v); };
  function hook(o, names) {
    if (!o) return;
    const [da, de, dai, dei] = names;
    const f = {da: o[da], de: o[de], dai: o[dai], dei: o[dei]};
    if (f.da) o[da] = function (m, first, c) { if (m === 0) add('pts', c); return f.da.apply(this, arguments); };
    if (f.de) o[de] = function (m, c) { if (m === 0) add('pts', c); return f.de.apply(this, arguments); };
    if (f.dai) o[dai] = function (m, first, c, n) { add('inst', n); return f.dai.apply(this, arguments); };
    if (f.dei) o[dei] = function (m, c, t, off, n) { add('inst', n); return f.dei.apply(this, arguments); };
  }
  hook(WebGLRenderingContext.prototype, ['drawArrays', 'drawElements']);
  if (window.WebGL2RenderingContext)
    hook(WebGL2RenderingContext.prototype, ['drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced']);
  const ge = WebGLRenderingContext.prototype.getExtension;
  WebGLRenderingContext.prototype.getExtension = function (name) {
    const e = ge.apply(this, arguments);
    if (e && name === 'ANGLE_instanced_arrays' && !e.__hooked) {
      e.__hooked = true;
      hook(e, [null, null, 'drawArraysInstancedANGLE', 'drawElementsInstancedANGLE']);
    }
    return e;
  };
  function tick() {
    for (const k of ['pts', 'inst']) {
      if (st.cur[k]) { st.max[k] = Math.max(st.max[k], st.cur[k]); st.last[k] = st.cur[k]; }
      st.cur[k] = 0;
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
})();
"""


class Run:
    def __init__(self, a):
        self.a = a
        self.rec = {"tool": a.tool, "variant": a.variant, "input": a.input, "n": a.n, "phases": {}, "checks": {},
                    "versions": {}, "console": []}
        self.t0 = time.time()
        self.srv = None

    def mark(self, k):
        self.rec["phases"][k] = round(time.time() - self.t0, 2)
        print(f"[{self.rec['phases'][k]:8.1f}s] {k}", file=sys.stderr, flush=True)
        self.save()

    def save(self):
        Path(self.a.out + ".json").write_text(json.dumps(self.rec, indent=1))

    def base(self) -> str:
        return (self.a.server_url or f"http://127.0.0.1:{self.a.port}").rstrip("/")

    def start_server(self, cmd, url, cwd=None, env=None, ready=200, wait=LIMIT):
        if self.a.server_url:  # remote server: nothing to start here, nothing measured
            self.rec["server_url"] = self.a.server_url
            return
        import socket
        t = time.time()
        while time.time() - t < 120:  # a previous run's server may still be releasing the port
            with socket.socket() as so:
                if so.connect_ex(("127.0.0.1", self.a.port)) != 0:
                    break
            time.sleep(2)
        else:
            raise RuntimeError(f"harness: port {self.a.port} still in use after 120 s")
        log = open(self.a.out + ".server.log", "w")
        self.srv = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                    env=dict(os.environ, **(env or {})))
        t = time.time()
        while time.time() - t < wait:
            if self.srv.poll() is not None:
                raise RuntimeError(f"server exited rc={self.srv.returncode}")
            try:
                if requests.get(url, timeout=5).status_code == ready:
                    self.mark("server_ready")
                    return
            except requests.RequestException:
                pass
            time.sleep(0.5)
        raise TimeoutError("server not ready")

    def stop_server(self):
        if self.srv and self.srv.poll() is None:
            self.srv.terminate()
            try:
                self.srv.wait(10)
            except subprocess.TimeoutExpired:
                self.srv.kill()

    def gl(self, page) -> dict:
        return page.evaluate("window.__glc ? {max: __glc.max, last: __glc.last, maxcall: __glc.maxcall} : null")

    def gl_reset(self, page):
        page.evaluate("if (window.__glc) { __glc.max = {pts: 0, inst: 0}; __glc.last = {pts: 0, inst: 0};"
                      " __glc.maxcall = 0; }")

    def wait_gl(self, page, n, crit="call", stable=3.0, limit=LIMIT):
        """Wait until the WebGL counter shows n points (crit "call": in one draw
        call; "frame": summed over one animation frame), then until it stops
        growing for `stable` s. Returns the counter."""
        t = time.time()
        best, since, g = -1, time.time(), None
        while time.time() - t < limit:
            if self.rec.get("pageerrors") and time.time() - t > 30:  # an uncaught page error, and no draw for 30 s
                g = self.gl(page) or {"max": {"pts": 0, "inst": 0}, "maxcall": 0}
                if max(g["max"]["pts"], g["max"]["inst"], g["maxcall"]) == 0:
                    raise RuntimeError("page error: " + self.rec["pageerrors"][0])
            g = self.gl(page) or {"max": {"pts": 0, "inst": 0}, "maxcall": 0}
            m = g["maxcall"] if crit == "call" else max(g["max"]["pts"], g["max"]["inst"])
            if m > best:
                best, since = m, time.time()
            if best >= n and time.time() - since > stable:
                break
            page.wait_for_timeout(250)
        return {"crit": crit, "drawn": best, "frame_max": g["max"] if g else None, "call_max": g["maxcall"] if g else None}

    def check(self, page, tag, gl, stated=None):
        png = f"{self.a.out}_{tag}.png"
        page.screenshot(path=png)
        n = self.a.n
        self.rec["checks"][tag] = {"gl": gl, "stated": stated, "png": png,
                                   "all_cells": bool((gl and gl["drawn"] >= n) or (stated is not None and stated >= n))}
        self.mark(f"plot_{tag}")


# --------------------------------------------------------------------------- tools
def cellxgene(r: Run, page):
    """CELLxGENE Annotate 1.3.0 (`cellxgene launch`). default: the h5ad in
    memory; backed: --backed (X read lazily from the h5ad, documented in
    `cellxgene launch --help`)."""
    d = COMPARE / "cellxgene"
    r.rec["versions"]["cellxgene"] = subprocess.run([str(d / ".venv/bin/cellxgene"), "--version"],
                                                    capture_output=True, text=True).stdout.strip()
    cmd = [str(d / ".venv/bin/cellxgene"), "launch", r.a.input, "--host", "127.0.0.1", "--port", str(r.a.port),
           "--disable-annotations", "--disable-gene-sets-save"] + (["--backed"] if r.a.variant == "backed" else [])
    r.start_server(cmd, f"http://127.0.0.1:{r.a.port}/")
    page.goto(r.base() + "/", timeout=LIMIT * 1000)
    stat = page.get_by_text(re.compile(r"umap: [\d,]+ out of [\d,]+ cells"))
    stat.wait_for(timeout=LIMIT * 1000)
    r.mark("first_plot")

    def stated():
        m = re.search(r"umap: ([\d,]+) out of ([\d,]+) cells", stat.inner_text())
        return int(m.group(1).replace(",", "")) if m else None

    r.gl_reset(page)
    page.get_by_test_id(f"colorby-{COLOUR}").click()
    r.check(page, "cat", r.wait_gl(page, r.a.n), stated())
    r.gl_reset(page)
    item = page.locator(".bp3-menu-item", has_text=GENE).first
    for attempt in range(6):  # the suggestion list sometimes misses the first keystrokes
        box = page.get_by_test_id("gene-search")
        box.click()
        box.fill("")
        page.keyboard.type(GENE, delay=50)
        try:
            item.wait_for(timeout=20000)
            break
        except Exception:  # noqa: BLE001
            r.rec.setdefault("retries", []).append(f"gene search attempt {attempt}")
    item.wait_for()
    page.keyboard.press("Enter")
    r.mark("gene_added")
    page.get_by_test_id(f"colorby-{GENE}").click(timeout=LIMIT * 1000)
    r.check(page, "gene", r.wait_gl(page, r.a.n), stated())


def cirrocumulus(r: Run, page):
    """Cirrocumulus (`cirro launch`). default: the h5ad, read into memory by
    anndata; prepared: the output of `cirro prepare_data --format zarr`, which
    cirro reads lazily (ZarrDataset). The main view draws every cell in one
    draw call; the gallery below draws each chosen feature again."""
    d = COMPARE / "cirrocumulus"
    r.rec["versions"]["cirrocumulus"] = subprocess.run(
        [str(d / ".venv/bin/python"), "-c", "import importlib.metadata as m; print(m.version('cirrocumulus'))"],
        capture_output=True, text=True).stdout.strip()
    r.start_server([str(d / ".venv/bin/cirro"), "launch", "--host", "127.0.0.1", "--port", str(r.a.port), "--no-open",
                    r.a.input], f"http://127.0.0.1:{r.a.port}/")
    page.goto(r.base() + "/", timeout=LIMIT * 1000)
    page.get_by_text(f"{r.a.n:,} cells").first.wait_for(timeout=LIMIT * 1000)
    r.wait_gl(page, r.a.n)
    r.mark("first_plot")
    for tag, label, key in (("cat", "Cell Metadata", COLOUR), ("gene", "Genes/Features", GENE)):
        r.gl_reset(page)
        page.get_by_label(label).first.click()
        page.keyboard.type(key)
        page.get_by_role("option", name=key, exact=True).first.wait_for()
        page.keyboard.press("Enter")
        r.check(page, tag, r.wait_gl(page, r.a.n))


def ucsc(r: Run, page):
    """UCSC Cell Browser: the static site that cbImportScanpy (--clusterField
    cell_line_id, -f mtx) and cbBuild wrote (INPUT = that html directory; both
    steps are measured as conversion runs). Served by a static Range server,
    whose memory is the "server" here. The tool's statement "N visible cells
    loaded" is the check; the WebGL counter is recorded too (at 50k cells the
    page drew on a 2D canvas; the hosted 21.8M PanSci set draws with one
    drawArrays(POINTS) call, comparison-auditor). The default colouring is the cluster field, cell_line_id."""
    d = COMPARE / "ucsc-cell-browser"
    r.rec["versions"]["cellbrowser"] = subprocess.run(
        [str(d / ".venv/bin/python"), "-c", "import importlib.metadata as m; print(m.version('cellbrowser'))"],
        capture_output=True, text=True).stdout.strip()
    if r.a.server_url:  # the site is served elsewhere: read its dataset list through the proxy
        prox = r.a.proxy.replace("socks5://", "socks5h://") if r.a.proxy else None
        ds = requests.get(r.base() + "/dataset.json", timeout=120,
                          proxies={"http": prox, "https": prox} if prox else None).json()["datasets"][0]["name"]
    else:
        ds = json.loads((Path(r.a.input) / "dataset.json").read_text())["datasets"][0]["name"]
    r.start_server([str(d / ".venv/bin/python"), str(COMPARE / "_bin/serve.py"), r.a.input, str(r.a.port)],
                   f"http://127.0.0.1:{r.a.port}/index.html")
    page.goto(f"{r.base()}/?ds={ds}", timeout=LIMIT * 1000)
    # "N visible cells loaded" on the 2D canvas, "N cells loaded" when WebGL draws (maxPlot.js setStatus)
    loaded = page.get_by_text(re.compile(r"[\d,]+ (?:visible )?cells loaded"))

    def stated():
        m = re.search(r"([\d,]+) (?:visible )?cells loaded", loaded.inner_text())
        return int(m.group(1).replace(",", "")) if m else None

    loaded.wait_for(timeout=LIMIT * 1000)
    page.keyboard.press("Escape")  # the first-visit tutorial
    page.get_by_text("cell line id").first.wait_for()
    r.mark("first_plot")
    def gl():
        g = r.gl(page)
        return {"crit": "call", "drawn": g["maxcall"], "frame_max": g["max"], "call_max": g["maxcall"]} if g else None

    r.check(page, "cat", gl(), stated())
    r.gl_reset(page)
    # the first-visit tutorial can open after the cells are drawn (at 5M it did,
    # after the Escape above) and then covers the page
    try:
        page.get_by_text("I know. Close this window.").click(timeout=15000)
    except Exception:  # noqa: BLE001  (no tutorial)
        pass
    page.get_by_role("link", name="Gene", exact=True).click()
    page.locator("#tpGeneCombo-selectized").click()
    page.keyboard.type(GENE)
    page.wait_for_timeout(1500)
    page.keyboard.press("Enter")
    page.get_by_text(f"Gene: {GENE}").wait_for(timeout=LIMIT * 1000)
    page.wait_for_timeout(2000)
    r.check(page, "gene", gl(), stated())


RT = COMPARE / "_mamba/envs/rtools/bin/Rscript"
RC = Path("$ENVS_ROOT/rceiling/bin/Rscript")


def r_version(pkg):
    return subprocess.run([str(RT), "-e", f'cat(as.character(packageVersion("{pkg}")))'], capture_output=True,
                          text=True).stdout.strip()


def shiny_idle(page):
    page.wait_for_function("window.Shiny && Shiny.shinyapp && !document.documentElement.classList.contains('shiny-busy')",
                           timeout=LIMIT * 1000)


def wait_img(page, sel, old=None):
    """Wait for a Shiny plot <img> with a new src, then for Shiny to be idle."""
    page.wait_for_function("([s, o]) => { const e = document.querySelector(s);"
                           " return e && e.src && e.src.length > 100 && e.src !== o; }", arg=[sel, old],
                           timeout=LIMIT * 1000)
    shiny_idle(page)
    return page.eval_on_selector(sel, "e => e.src")


def isee(r: Run, page):
    """iSEE: isee_app.R on the SingleCellExperiment .rds (to_sce.R), one
    ReducedDimensionPlot coloured by cell_line_id, then switched to the gene
    (the panel's ColorBy inputs, set through Shiny as the radio button and
    gene box would). Drawn server-side by ggplot2 with Downsample = FALSE,
    iSEE's default, so every cell is drawn (the check is that setting)."""
    rs = RC if r.a.variant == "hdf5" else RT  # 7b: HDF5-backed SCE needs HDF5Array (tool_ceiling's R env)
    r.rec["versions"].update(iSEE=r_version("iSEE"), shiny=r_version("shiny"), Rscript=str(rs))
    r.start_server([str(rs), str(HERE / "isee_app.R"), r.a.input, str(r.a.port)], f"http://127.0.0.1:{r.a.port}/")
    page.goto(r.base() + "/", timeout=LIMIT * 1000)
    sel = "#ReducedDimensionPlot1 img"
    src = wait_img(page, sel)
    r.mark("first_plot")
    r.check(page, "cat", None, r.a.n)
    page.evaluate(f"Shiny.setInputValue('ReducedDimensionPlot1_ColorByFeatureName', '{GENE}');"
                  " Shiny.setInputValue('ReducedDimensionPlot1_ColorBy', 'Feature name')")
    wait_img(page, sel, src)
    r.check(page, "gene", None, r.a.n)
    r.rec["every_cell_basis"] = "Downsample = FALSE (iSEE default); not counted in the page"


def shinycell(r: Run, page):
    """ShinyCell: the app shinycell_build.R wrote (INPUT = app directory), run
    with shiny::runApp. Its first tab draws cell information and gene
    expression side by side: the gene panel opens on MALAT1; the cell
    information panel opens on plate (makeShinyApp left the default empty) and
    is then switched to cell_line_id. ggplot2 server-side; the server shuffles
    every row before plotting and has no downsampling (the check is the code)."""
    r.rec["versions"].update(ShinyCell=r_version("ShinyCell"), shiny=r_version("shiny"))
    r.start_server([str(RT), "-e", f'shiny::runApp("{r.a.input}", host = "127.0.0.1", port = {r.a.port}, '
                    'launch.browser = FALSE)'], f"http://127.0.0.1:{r.a.port}/")
    page.goto(r.base() + "/", timeout=LIMIT * 1000)
    wait_img(page, "#sc1a1oup2 img")
    src = wait_img(page, "#sc1a1oup1 img")
    r.mark("first_plot")
    r.check(page, "gene", None, r.a.n)
    page.evaluate(f"Shiny.setInputValue('sc1a1inp1', '{COLOUR}')")
    wait_img(page, "#sc1a1oup1 img", src)
    r.check(page, "cat", None, r.a.n)
    r.rec["every_cell_basis"] = "server.R plots ggData[sample(nrow(ggData))]: every row, shuffled; not counted in the page"


VITESSCE_FLAGS = ["--disable-features=LocalNetworkAccessChecks,PrivateNetworkAccessSendPreflights,"
                  "PrivateNetworkAccessRespectPreflightResults,BlockInsecurePrivateNetworkRequests"]


def vitessce(r: Run, page):
    """Vitessce: the hosted app (vitessce.io) reading a view config and the
    AnnData zarr store (X stored CSC, which Vitessce reads per gene) from a
    local static Range server (INPUT = a directory with config.json and
    store.zarr; vitessce_config.py). Chromium's local-network-access checks
    are switched off for this tool only, so the public page may read
    127.0.0.1. Colour: with initStrategy "auto" the first plot is already
    coloured by the cell sets of obs/cell_line_id (seen in the screenshots);
    then MALAT1 is picked in the Gene List. deck.gl draws one instance per
    cell."""
    r.start_server([str(COMPARE / "ucsc-cell-browser/.venv/bin/python"), str(COMPARE / "_bin/serve.py"), r.a.input,
                    str(r.a.port)], f"http://127.0.0.1:{r.a.port}/config.json")
    page.goto(f"https://vitessce.io/?url=http://127.0.0.1:{r.a.port}/config.json", timeout=LIMIT * 1000)
    page.get_by_text(f"{r.a.n:,} cells").first.wait_for(timeout=LIMIT * 1000)
    gl = r.wait_gl(page, r.a.n)
    r.mark("first_plot")
    r.rec["versions"]["vitessce"] = page.evaluate(
        "(() => { const m = [...document.scripts].map(s => s.src).find(s => /vitessce/.test(s)); return m || null; })()")
    r.check(page, "cat", gl)
    r.gl_reset(page)
    page.get_by_placeholder("Search").fill(GENE)
    page.get_by_text(GENE, exact=True).first.click()
    r.check(page, "gene", r.wait_gl(page, r.a.n))


def kana(r: Run, page):
    """Kana (hosted live build, kanaverse.org): "explore existing analysis
    results", H5AD file given to the file input (read in the browser, nothing
    uploaded), assay X, Explore. The whole file and matrix go into the page
    (WebAssembly heap, 4 GiB cap in this build). Colour: the first obs column,
    cell_line_id (Kana's default), then MALAT1 from the marker table (gene names
    switched to rowNames, the gene's colour button). The check is Kana's header
    "N cells"; it draws in a worker, outside the WebGL counter's reach."""
    page.goto("https://www.kanaverse.org/kana/", timeout=LIMIT * 1000)
    r.rec["versions"]["kana"] = (re.findall(r"v\d+\.\d+\.\d+", page.inner_text("body")) or [None])[0]
    page.get_by_text("I want to explore existing analysis results").click()
    page.locator("input[type=file]").first.set_input_files(r.a.input)
    page.get_by_role("button", name="Explore", exact=True).first.click(timeout=LIMIT * 1000)
    t = time.time()
    while time.time() - t < LIMIT:  # the plot's tab, or Kana's error toast
        if page.get_by_text("X_umap", exact=True).count():
            break
        toast = page.locator(".bp4-toast, .bp4-callout-intent-danger")
        if toast.count():
            raise RuntimeError("Kana error: " + toast.first.inner_text()[:300])
        body = page.inner_text("body")
        m = re.search(r"(EXPLORE|ANALYSIS) ERROR\s+([^\n]+)", body)  # Kana's error panel (e.g. a Wasm abort)
        if m:
            raise RuntimeError(f"Kana {m.group(1)} ERROR: {m.group(2)[:300]}")
        page.wait_for_timeout(1000)
    page.get_by_text("X_umap", exact=True).first.click()
    page.wait_for_timeout(3000)
    r.mark("first_plot")
    m = re.search(r"([\d,]+) cells", page.inner_text("body"))
    stated = int(m.group(1).replace(",", "")) if m else None
    r.check(page, "cat", None, stated)
    page.locator("select").filter(has=page.locator("option", has_text="rowNames")).first.select_option("rowNames")
    page.get_by_placeholder("Search gene...").fill(GENE)
    row = page.locator(".row-container", has=page.get_by_text(GENE, exact=True)).first
    row.locator("button").nth(1).click()
    page.get_by_text("Gradient for").wait_for(timeout=LIMIT * 1000)  # the gene legend
    page.wait_for_timeout(3000)
    r.check(page, "gene", None, stated)
    r.rec["every_cell_basis"] = "Kana's header 'N cells' after the explore load (it draws every loaded cell)"


def tissuumaps(r: Run, page):
    """TissUUmaps 3.2.1.11 (server build; comparison-auditor's env): tissuumaps_server
    on the directory of a CSC h5ad (to_h5ad.py --csc), page /<name>.h5ad. The
    browser reads the h5ad lazily (h5wasm, 1 MB range reads); markers are drawn
    with WebGL in instanced calls of up to 65,536 markers each: the counter's
    per-frame sum is the check).
    Colour: "Categorical observations" cell_line_id, then "Gene expression"
    MALAT1 (select2 boxes; helpers as comparison-auditor's matrix_check.py)."""
    env = COMPARE / "_mamba/envs/tissuumaps"
    r.rec["versions"]["tissuumaps"] = subprocess.run(
        [str(env / "bin/python"), "-c", "import importlib.metadata as m; print(m.version('tissuumaps'))"],
        capture_output=True, text=True).stdout.strip()
    path = Path(r.a.input)
    r.start_server([str(env / "bin/tissuumaps_server"), "-l", "127.0.0.1", "-p", str(r.a.port), str(path.parent)],
                   f"http://127.0.0.1:{r.a.port}/")
    page.goto(f"{r.base()}/{path.name}", timeout=LIMIT * 1000)
    page.get_by_text("Categorical observations").first.wait_for(timeout=LIMIT * 1000)
    r.mark("first_plot")

    def choose(label, value, search=False):
        if page.locator(".select2-container--open").count() == 0:
            page.locator(f"text={label}").locator(
                "xpath=following::span[contains(@class,'select2-selection')][1]").first.click()
        if search:
            page.locator(".select2-search__field").last.fill(value)
        page.locator("li.select2-results__option", has_text=value).first.click(timeout=LIMIT * 1000)

    # markers are drawn in instanced calls of at most 65,536 (seen at 1M): count per frame
    r.gl_reset(page)
    choose("Categorical observations", COLOUR)
    r.check(page, "cat", r.wait_gl(page, r.a.n, crit="frame"))
    r.gl_reset(page)
    choose("Gene expression", GENE, search=True)
    r.check(page, "gene", r.wait_gl(page, r.a.n, crit="frame"))


TOOLS = {"kana": kana, "tissuumaps": tissuumaps, "vitessce": vitessce, "cellxgene": cellxgene, "cirrocumulus": cirrocumulus, "ucsc": ucsc, "isee": isee, "shinycell": shinycell}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tool", choices=sorted(TOOLS))
    ap.add_argument("variant")
    ap.add_argument("input")
    ap.add_argument("out")
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--port", type=int, default=8930)
    ap.add_argument("--server-url", default="", help="CELLxGENE, Cirrocumulus, iSEE: a server already running elsewhere")
    ap.add_argument("--proxy", default="", help="e.g. socks5://127.0.0.1:8767 (Chromium --proxy-server)")
    a = ap.parse_args()
    r = Run(a)
    ok = False
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chromium", args=["--enable-precise-memory-info"]
                                   + (VITESSCE_FLAGS if a.tool == "vitessce" else [])
                                   + ([f"--proxy-server={a.proxy}",  # names resolved by the proxy, never locally
                                       "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost"] if a.proxy else []))
            r.rec["versions"]["chromium"] = b.version
            ctx = b.new_context(viewport={"width": 1600, "height": 900})
            ctx.add_init_script(GL_HOOK)
            page = ctx.new_page()
            page.on("console", lambda m: r.rec["console"].append(f"{m.type}: {m.text[:200]}")
                    if m.type in ("error", "warning") and len(r.rec["console"]) < 50 else None)
            page.on("pageerror", lambda e: r.rec.setdefault("pageerrors", []).append(str(e)[:300]))
            crashed = {"v": False}
            page.on("crash", lambda *_: crashed.update(v=True))
            page.set_default_timeout(LIMIT * 1000)
            TOOLS[a.tool](r, page)
            r.rec["gl_renderer"] = page.evaluate(
                "(() => { const g = document.createElement('canvas').getContext('webgl');"
                " const e = g && g.getExtension('WEBGL_debug_renderer_info');"
                " return e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : null; })()")
            r.rec["crashed"] = crashed["v"]
            ok = len(r.rec["checks"]) == 2 and all(c["all_cells"] for c in r.rec["checks"].values())
            b.close()
    except Exception as e:  # noqa: BLE001  (recorded, then non-zero exit)
        r.rec["error"] = f"{type(e).__name__}: {str(e)[:500]}"
        print(r.rec["error"], file=sys.stderr)
    finally:
        r.stop_server()
        r.rec["ok"] = ok
        r.mark("done")
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()
