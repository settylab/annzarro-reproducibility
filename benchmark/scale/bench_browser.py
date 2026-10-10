#!/usr/bin/env python
"""Time to first plot, recolour time and browser memory for the Tahoe stores.

Headless Chromium (Playwright) opens a deep link with two Cell Plot panels on
the stored embedding (obsm/X_pca_2d, columns 0 and 1):

  A  coloured by the focused gene (layer "X", which the server reads as X, CSC)
  B  coloured by obs cell_line_id (categorical, 50 cell lines)

Modes: ``subset`` (no subset in the link: the server's default, i.e. a
100,000-cell subset above 200,000 cells) and ``all`` (``subset: null`` in the
link: every cell).

Per store, mode and repetition: the store is made cold (bench_http.make_cold),
a fresh server starts, a fresh browser context opens the link, and the clock
runs from navigation until both panels hold the expected number of points and
no API request is in flight (``first_plot_s``). Then the focused gene is
changed three times by typing its name in the Focused Gene box and pressing
Enter; ``recolour_s`` runs from Enter until panel A's colour array is the new
gene's and no request is in flight.

Rendering: Chromium's new headless mode (``--channel chromium``), which draws
WebGL on the GPU when there is one (Metal on Apple silicon). The WebGL
renderer string is recorded in ``note``. The headless shell (``--channel ''``)
always renders WebGL in software (SwiftShader) and is several times slower
at drawing; a GPU-less cluster node does the same.

Memory: ``js_heap`` is performance.memory.usedJSHeapSize (Chromium started
with --enable-precise-memory-info); ``renderer_rss`` is the largest RSS of a
Chromium renderer process, sampled every 50 ms.

Failure: a page crash, a JS heap over --heap-limit or no plot within --limit
seconds ends the repetition (``status``). If the first plot failed, that
mode is not tried at larger N; if only a recolour failed, the remaining
repetitions of that N are skipped and the next N is tried.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
import psutil
import zarr
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

sys.path.insert(0, str(Path(__file__).resolve().parent))
import envcapture  # noqa: E402
from bench_http import Server, make_cold, drop_cold, environment  # noqa: E402

FIELDS = ["site", "store", "n_cells", "mode", "rep", "event", "seq", "gene", "status", "seconds",
          "n_points", "js_heap", "renderer_rss", "server_rss_peak", "note", "timestamp"]
EMB = "X_pca_2d"


def view(gene: str, subset_all: bool) -> dict:
    x = {"type": "obsm", "key": EMB, "column": "0"}
    y = {"type": "obsm", "key": EMB, "column": "1"}
    cfg = {
        "cell-plot-A": {"id": "cell-plot-A", "title": "gene", "x": x, "y": y, "z": None,
                        "color": {"type": "layer", "key": "X", "column": gene, "locked": False},
                        "pointSize": 2, "pointOpacity": 0.8},
        "cell-plot-B": {"id": "cell-plot-B", "title": "cell line", "x": x, "y": y, "z": None,
                        "color": {"type": "obs", "key": "cell_line_id", "column": ""},
                        "pointSize": 2, "pointOpacity": 0.8},
    }
    hier = {"type": "split", "direction": "horizontal",
            "panes": [{"percentage": 50, "controlsVisible": False}, {"percentage": 50, "controlsVisible": False}],
            "children": [{"type": "tile", "id": "cell-plot-A", "controlsVisible": False},
                         {"type": "tile", "id": "cell-plot-B", "controlsVisible": False}]}
    v = {"v": 1, "constants": {"focusedGene": gene},
         "layout": {"v": 1, "hierarchy": [hier], "controlState": {k: False for k in cfg}, "panelConfigs": cfg}}
    if subset_all:
        v["subset"] = None
    return v


def link(base: str, store: Path, v: dict) -> str:
    enc = base64.urlsafe_b64encode(json.dumps(v, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{base}/?dataset_path={store}#view={enc}"


STATE_JS = """() => {
  const vis = e => e.offsetParent !== null && getComputedStyle(e).visibility !== 'hidden';
  const busy = [...document.querySelectorAll('.loading-screen, .loading-overlay, .spinner-border, .fa-spinner')]
      .filter(vis).length;
  const graph = id => document.querySelector(`.tile[data-tile-id="${id}"] .js-plotly-plot`);
  // points drawn per panel: all traces except the focused-cell marker (categorical colour = one trace per category)
  const n = ['cell-plot-A', 'cell-plot-B'].map(id => {
    const g = graph(id);
    if (!g || !g._fullData) return -1;
    return g._fullData.filter(d => d.name !== 'Focused Cell')
                      .reduce((s, d) => s + (d.x ? d.x.length : 0), 0);
  });
  // colour signature over ALL traces but the focused-cell marker: per trace, its point count and its
  // colour (the string of a single-colour trace, as large-plot mode's binned traces have, or a strided
  // weighted sum of a per-point colour array), hashed. A recolour changes it in either drawing mode.
  const colourKey = c => {
    if (c === undefined || c === null) return '-';
    if (typeof c === 'string' || typeof c === 'number') return String(c);
    if (!c.length) return '0';
    let s = 0; const st = 1;   // every value counts: the client re-sorts points by colour, so a prefix can be all zeros
    for (let i = 0; i < c.length; i += st) { const v = +c[i]; if (isFinite(v)) s += v * ((i % 97) + 1); }
    return c.length + '~' + s;
  };
  const traceSig = gd => {
    if (!gd || !gd.data || !gd.data.length) return null;
    let h = 5381;
    const key = gd.data.filter(t => t.name !== 'Focused Cell')
      .map(t => (t.x ? t.x.length : 0) + ':' + colourKey(t.marker && t.marker.color)).join('|');
    for (let i = 0; i < key.length; i++) h = ((h * 33) ^ key.charCodeAt(i)) >>> 0;
    return key.length + ':' + h;
  };
  const sig = traceSig(graph('cell-plot-A'));
  const heap = performance.memory ? performance.memory.usedJSHeapSize : -1;
  return {busy, n, sig, heap, tiles: document.querySelectorAll('.tile').length};
}"""


GL_JS = """() => { const gl = document.createElement('canvas').getContext('webgl');
  if (!gl) return 'no webgl';
  const e = gl.getExtension('WEBGL_debug_renderer_info');
  return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER); }"""


class RendererSampler(threading.Thread):
    """Peak RSS of Chromium renderer processes (children of the browser)."""

    def __init__(self, interval=0.05):
        super().__init__(daemon=True)
        self.interval, self.peak, self.running = interval, 0, True
        self.me = psutil.Process()

    def run(self):
        while self.running:
            best = 0
            for p in self.me.children(recursive=True):
                try:
                    if "--type=renderer" in " ".join(p.cmdline()):
                        best = max(best, p.memory_info().rss)
                except psutil.Error:
                    pass
            self.peak = max(self.peak, best)
            time.sleep(self.interval)


def genes_for(store: Path) -> list[str]:
    g = zarr.open_group(str(store), mode="r")
    nnz = np.diff(g["X/indptr"][:])
    order = np.argsort(-nnz, kind="stable")
    if "gene_order_full" in g["X"].attrs:   # gene-panel store: rank genes as in the all-gene store
        order = np.asarray(g["X"].attrs["gene_order_full"])
    names = g["var/_index"][:]
    return [str(names[i]) for i in order[[0, 1000, 1001, 1002]]]


def run_one(pw, srv: Server, store_link: Path, store: Path, n: int, mode: str, rep: int, a, emit, genes):
    expect = n if (mode == "all" or n <= 200_000) else 100_000
    browser = pw.chromium.launch(channel=a.channel or None,
                                 args=["--enable-precise-memory-info", "--enable-unsafe-swiftshader"])
    sampler = RendererSampler()
    sampler.start()
    status, crashed = "ok", {"v": False}
    try:
        ctx = browser.new_context(viewport={"width": 1600, "height": 900})
        page = ctx.new_page()
        inflight = set()
        page.on("request", lambda r: inflight.add(r) if "/api/" in r.url else None)
        page.on("requestfinished", lambda r: inflight.discard(r))
        page.on("requestfailed", lambda r: inflight.discard(r))
        page.on("crash", lambda *_: crashed.__setitem__("v", True))
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))
        page.goto("about:blank")
        renderer = page.evaluate(GL_JS)
        url = link(srv.base.rsplit("/api/", 1)[0], store_link, view(genes[0], mode == "all"))
        t0 = time.perf_counter()
        page.goto(url, timeout=a.limit * 1000)
        st, heap_peak = None, 0
        while True:
            el = time.perf_counter() - t0
            if crashed["v"]:
                status = "crash"; break
            try:
                st = page.evaluate(STATE_JS)
            except Exception as e:
                status = "crash" if crashed["v"] else f"eval_error:{type(e).__name__}"; break
            heap_peak = max(heap_peak, st["heap"])
            if st["n"] and len(st["n"]) >= 2 and all(x >= expect for x in st["n"][:2]) and st["busy"] == 0 \
                    and not inflight:
                break
            if heap_peak > a.heap_limit:
                status = "heap_limit"; break
            if el > a.limit:
                status = "timeout"
                errors.append(f"state {st}; inflight {[r.url[-80:] for r in inflight]}")
                break
            time.sleep(0.05)
        first = time.perf_counter() - t0
        emit(mode=mode, rep=rep, event="first_plot", seq=0, gene=genes[0], status=status, seconds=first,
             n_points=max(st["n"]) if st and st["n"] else -1, js_heap=heap_peak, renderer_rss=sampler.peak,
             server_rss_peak=srv.sampler.read(), note=("; ".join(errors)[:300] + " | gl: " + renderer
                                                         + f" | loadavg {os.getloadavg()[0]:.1f}"))
        if status != "ok":
            return "first_plot:" + status
        # recolour three times
        for k, gname in enumerate(genes[1:4]):
            rstat, s, t1 = "ok", {"n": [], "heap": -1}, time.perf_counter()
            try:
                before = page.evaluate(STATE_JS)["sig"]
                box = page.locator("#focused-gene")
                box.click()
                box.fill(gname)
                page.wait_for_timeout(300)        # typeahead settles; not counted
                t1 = time.perf_counter()
                box.press("Enter")
                while True:
                    if crashed["v"]:
                        rstat = "crash"; break
                    s = page.evaluate(STATE_JS)
                    heap_peak = max(heap_peak, s["heap"])
                    if s["sig"] != before and s["busy"] == 0 and not inflight:
                        break
                    if s["heap"] > a.heap_limit:
                        rstat = "heap_limit"; break
                    if time.perf_counter() - t1 > a.limit:
                        rstat = "timeout"; break
                    time.sleep(0.02)
            except Exception as e:
                rstat = "crash" if (crashed["v"] or "crash" in str(e).lower()) else f"error:{type(e).__name__}"
            emit(mode=mode, rep=rep, event="recolour", seq=k, gene=gname, status=rstat,
                 seconds=time.perf_counter() - t1, n_points=max(s["n"]) if s.get("n") else -1,
                 js_heap=s.get("heap", -1), renderer_rss=sampler.peak, server_rss_peak=srv.sampler.read(), note="")
            if rstat != "ok":
                return "recolour:" + rstat
        return "ok"
    except PWTimeout:
        emit(mode=mode, rep=rep, event="first_plot", seq=0, gene=genes[0], status="timeout", seconds=a.limit,
             n_points=-1, js_heap=-1, renderer_rss=sampler.peak, server_rss_peak=srv.sampler.read(), note="goto")
        return "first_plot:timeout"
    finally:
        sampler.running = False
        try:
            browser.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stores", nargs="+")
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cold", choices=["clone", "fadvise", "none"],
                    default="clone" if sys.platform == "darwin" else "fadvise")
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--port", type=int, default=8901)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--modes", default="subset,all")
    ap.add_argument("--limit", type=float, default=180, help="seconds before a plot counts as failed")
    ap.add_argument("--heap-limit", type=float, default=4e9)
    ap.add_argument("--channel", default="chromium",
                    help="'chromium' = new headless mode (uses the GPU when there is one; on a GPU-less "
                         "node WebGL falls back to SwiftShader); '' = headless shell (always SwiftShader)")
    a = ap.parse_args()
    envcapture.require_clean_bench()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        with open(out, "w", newline="") as f:
            csv.DictWriter(f, FIELDS).writeheader()
    stores = [Path(s).resolve() for s in a.stores]
    env = environment(argparse.Namespace(site=a.site, cold=a.cold, reps=a.reps, warm=0, timeout=a.limit,
                                         slow=a.limit), stores)
    from importlib.metadata import version
    env["browser"] = "chromium headless shell (playwright " + version("playwright") + ")"
    envcapture.record(out, exe=str(Path(sys.executable).with_name("annzarro")), harness_environment=env)
    failed: set = set()
    with sync_playwright() as pw:
        for store in stores:
            n = int(zarr.open_group(str(store), mode="r")["X"].attrs["shape"][0])
            genes = genes_for(store)
            for mode in a.modes.split(","):
                if mode in failed:
                    with open(out, "a", newline="") as f:
                        csv.DictWriter(f, FIELDS).writerow(dict(site=a.site, store=store.name, n_cells=n, mode=mode,
                            rep=0, event="first_plot", seq=0, gene="", status="skipped", seconds="", n_points="",
                            js_heap="", renderer_rss="", server_rss_peak="", note="failed at a smaller N",
                            timestamp=time.time()))
                    continue
                for rep in range(a.reps):
                    path, _ = make_cold(store, a.cold, Path(a.scratch), f"br_{store.stem}_{mode}_r{rep}")
                    srv = Server(path.parent, a.port, Path(a.scratch) / "home_browser", a.limit * 2)

                    def emit(**kw):
                        with open(out, "a", newline="") as f:
                            csv.DictWriter(f, FIELDS).writerow(dict(site=a.site, store=store.name, n_cells=n,
                                                                     timestamp=time.time(), **kw))
                    try:
                        st = run_one(pw, srv, path, store, n, mode, rep, a, emit, genes)
                    finally:
                        srv.stop()
                        drop_cold(path, store, a.cold)
                    print(f"  {store.name} {mode} rep {rep}: {st}", flush=True)
                    if st.startswith("first_plot:"):      # could not draw at all: stop this mode
                        failed.add(mode)
                        break
                    if st != "ok":                        # drew, but a recolour failed: next N
                        break


if __name__ == "__main__":
    main()
