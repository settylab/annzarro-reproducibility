#!/usr/bin/env python
"""How many points one AnnZarro Cell Plot draws in Chromium on this machine.

One Cell Plot on obsm/X_umap of a synthetic store (build_stores.py), deep link
with ``"subset": null`` (every cell). Colour:

  cat   obs cell_type (categorical, 50 categories: one scattergl trace each)
  gene  layer X, focused gene GENE0; then the focused gene is changed to
        GENE1..GENE3 (typed in the Focused Gene box, Enter) = ``recolour``

Per run: a fresh server (``--exe``, i.e. the AnnZarro checkout under test),
a fresh browser, navigation, then polling until the panel holds N points, no
loading indicator is visible and no /api/ request is in flight
(``first_plot``; readiness checks as in ../bench_browser.py). Then optional
wheel zooms (``--zoom``): each wheel event's time until Plotly's
``plotly_relayout`` fired and two animation frames passed.

Recorded per event (JSON lines in --out): status, seconds, points drawn,
JS heap (performance.memory, precise), peak RSS of the renderer, GPU and
browser processes, per-API-request timings from the browser (time to first
byte = server read, response end = transfer), console errors and warnings,
crash (Playwright's crash event, or the page's renderer process gone; ``oom`` when
Chromium's stderr says V8 ran out of heap), and the WebGL renderer string. A run is stopped when the system's
memory free percentage (kern.memorystatus_level, what ``memory_pressure``
prints) drops below --min-free.
"""

from __future__ import annotations

import argparse
import atexit
import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
import requests
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import envcapture  # noqa: E402

HERE = Path(__file__).resolve().parent


def free_pct() -> int:
    return int(subprocess.run(["sysctl", "-n", "kern.memorystatus_level"], capture_output=True,
                              text=True).stdout.strip())


class Server:
    def __init__(self, exe: str, data_dir: str, port: int, home: Path):
        home.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, ANNZARRO_HOME=str(home), ANNZARRO_HEADLESS="1")
        self.log = open(home / "server.log", "a")
        self.proc = subprocess.Popen([str(Path(exe).resolve()), "start", "--host", "127.0.0.1", "--port", str(port), "--data-dir",
                                      data_dir, "--no-browser", "--auth-disabled"],
                                     stdout=self.log, stderr=subprocess.STDOUT, env=env, cwd=home,
                                     start_new_session=True)
        self.root = f"http://127.0.0.1:{port}"
        t0 = time.time()
        while True:
            if self.proc.poll() is not None:
                raise RuntimeError("server exited")
            try:
                if requests.get(self.root + "/api/v1/config", timeout=2).status_code == 200:
                    break
            except requests.RequestException:
                pass
            if time.time() - t0 > 60:
                raise RuntimeError("server did not start")
            time.sleep(0.1)
        self.ps = psutil.Process(self.proc.pid)
        self.peak = 0

    def rss(self):
        tot = 0
        for p in [self.ps] + self.ps.children(recursive=True):
            try:
                tot += p.memory_info().rss
            except psutil.Error:
                pass
        self.peak = max(self.peak, tot)
        return tot

    def stop(self):
        try:
            os.killpg(self.proc.pid, 15)
            self.proc.wait(10)
        except Exception:
            try:
                os.killpg(self.proc.pid, 9)
            except Exception:
                pass


class Sampler(threading.Thread):
    """Peak RSS per Chromium process type, server RSS and the system free percentage."""

    def __init__(self, server: Server, min_free: int, interval=0.1):
        super().__init__(daemon=True)
        self.server, self.min_free, self.interval = server, min_free, interval
        self.peak = {"renderer": 0, "gpu": 0, "browser": 0}
        self.cur = dict(self.peak)
        self.min_free_seen, self.low, self.running = 100, False, True
        self.me = psutil.Process()
        self.k = 0
        self.page_pid, self.gone = None, None   # the page's renderer (watch()) and when it vanished

    def renderers(self) -> dict:
        out = {}
        for p in self.me.children(recursive=True):
            try:
                if "--type=renderer" in " ".join(p.cmdline()):
                    out[p.pid] = p.memory_info().rss
            except psutil.Error:
                pass
        return out

    def watch(self):
        """Take the largest renderer as the page's, once the app has loaded (after page.goto).
        A renderer killed by V8 OOM does not always fire Playwright's crash event; page.evaluate
        then never returns (seen at 200M points, guard off). Its pid vanishing is the signal."""
        r = self.renderers()
        self.page_pid = max(r, key=r.get) if r else None

    def check(self) -> bool:
        """The page's renderer gone (or a zombie) right now, without waiting for the next sample."""
        if self.page_pid is not None and self.gone is None:
            try:
                if psutil.Process(self.page_pid).status() == psutil.STATUS_ZOMBIE:
                    self.gone = time.time()
            except psutil.Error:
                self.gone = time.time()
        return self.gone is not None

    def run(self):
        while self.running:
            cur = {"renderer": 0, "gpu": 0, "browser": 0}
            alive = set()
            for p in self.me.children(recursive=True):
                try:
                    cmd = " ".join(p.cmdline())
                    if "annzarro" in cmd and "start" in cmd:
                        continue
                    if "--type=renderer" in cmd:
                        cur["renderer"] = max(cur["renderer"], p.memory_info().rss)
                        alive.add(p.pid)
                    elif "--type=gpu-process" in cmd:
                        cur["gpu"] = max(cur["gpu"], p.memory_info().rss)
                    elif "--type=" not in cmd and ("chrom" in cmd.lower()):
                        cur["browser"] = max(cur["browser"], p.memory_info().rss)
                except psutil.Error:
                    pass
            self.cur = cur
            if self.page_pid is not None and self.page_pid not in alive and self.gone is None:
                self.gone = time.time()
            for k, v in cur.items():
                self.peak[k] = max(self.peak[k], v)
            self.server.rss()
            if self.k % 10 == 0:
                f = free_pct()
                self.min_free_seen = min(self.min_free_seen, f)
                if f < self.min_free:
                    self.low = True
            self.k += 1
            time.sleep(self.interval)


class Watchdog(threading.Thread):
    """Kill this process's browsers when a Playwright call has not returned in
    `limit` seconds. Chrome (stable) does not always report a renderer that died
    of OOM; page.evaluate then never returns. With a Sampler, it fires at once once the page's
    renderer is gone, instead of after `limit`."""

    def __init__(self, limit: float, smp: Sampler | None = None):
        super().__init__(daemon=True)
        self.limit, self.since, self.fired, self.running, self.smp = limit, None, False, True, smp

    def arm(self):
        self.since = time.time()

    def disarm(self):
        self.since = None

    def run(self):
        while self.running:
            if self.since and (time.time() - self.since > self.limit or (self.smp and self.smp.gone)):
                self.fired = True
                for p in psutil.Process().children(recursive=True):
                    try:
                        cmd = " ".join(p.cmdline())
                        if "--type=" not in cmd and ("Chrome" in cmd or "chrom" in cmd) and "annzarro" not in cmd:
                            p.kill()
                    except psutil.Error:
                        pass
                self.since = None
            time.sleep(0.2)


class BrowserStderr(threading.Thread):
    """Chromium's own account of a renderer's death. With DEBUG=pw:browser (set before Playwright
    starts) the Playwright driver forwards the browser's stdout and stderr to its stderr, which is this
    process's fd 2. This thread puts a pipe in front of fd 2, passes every byte on unchanged, and keeps
    the lines that say a renderer ran out of memory, e.g. 'V8 javascript OOM (CALL_AND_RETRY_LAST).'"""
    OOM = re.compile(r"V8 javascript OOM[^\n]{0,120}|Fatal JavaScript out of memory[^\n]{0,120}|"
                     r"Oilpan: Out of memory[^\n]{0,120}")

    def __init__(self):
        super().__init__(daemon=True)
        self.oom = []   # (time, line)
        sys.stderr.flush()
        self.orig = os.dup(2)
        self.r, w = os.pipe()
        os.dup2(w, 2)
        os.close(w)
        atexit.register(self.close)

    def run(self):
        tail = b""
        while chunk := os.read(self.r, 65536):
            out = chunk
            while out:
                out = out[os.write(self.orig, out):]
            *lines, tail = (tail + chunk).split(b"\n")
            tail = tail[-4096:]
            for ln in lines:
                m = self.OOM.search(ln.decode("utf-8", "replace"))
                if m:
                    self.oom.append((time.time(), m.group(0).strip()))

    def since(self, t: float) -> str | None:
        return next((ln for tt, ln in self.oom if tt >= t), None)

    def close(self):
        sys.stderr.flush()
        os.dup2(self.orig, 2)   # our own fd 2 back; the reader ends when the driver's copy closes too
        self.join(2)


ERR: BrowserStderr | None = None


def start_stderr():
    """Once per process, before sync_playwright(): browser stderr into the log and into ERR."""
    global ERR
    if ERR is None:
        d = os.environ.get("DEBUG", "")
        if "pw:browser" not in d:
            os.environ["DEBUG"] = ",".join(x for x in (d, "pw:browser") if x)
        ERR = BrowserStderr()
        ERR.start()


# What the view shows; main() sets these from the command line.
VIEW = {"emb": "X_umap", "cat": "cell_type", "genes": ["GENE0", "GENE1", "GENE2", "GENE3"],
        "subset": None, "point_size": 1, "opacity": 0.5}
ABSENT = object()   # VIEW["subset"]: no subset key in the link (the server's default subset)


def view(color: str, gene: str | None = None) -> dict:
    gene = gene or VIEW["genes"][0]
    x = {"type": "obsm", "key": VIEW["emb"], "column": "0"}
    y = {"type": "obsm", "key": VIEW["emb"], "column": "1"}
    col = ({"type": "obs", "key": VIEW["cat"], "column": ""} if color == "cat"
           else {"type": "layer", "key": "X", "column": gene, "locked": False})
    panel = {"id": "cell-plot-A", "title": color, "x": x, "y": y, "z": None, "color": col}
    if VIEW["point_size"] is not None:
        panel["pointSize"] = VIEW["point_size"]
    if VIEW["opacity"] is not None:
        panel["pointOpacity"] = VIEW["opacity"]
    panel.update(VIEW.get("panel_extra") or {})
    v = {"v": 1, "constants": {"focusedGene": gene},
         "layout": {"v": 1, "hierarchy": [{"type": "tile", "id": "cell-plot-A", "controlsVisible": False}],
                    "controlState": {"cell-plot-A": False}, "panelConfigs": {"cell-plot-A": panel}}}
    if VIEW["subset"] is not ABSENT:
        v["subset"] = VIEW["subset"]
    return v


def n_cells(store) -> int:
    """Cells in an AnnData zarr store (format 2), from the obs index's metadata."""
    obs = Path(store) / "obs"
    index = json.loads((obs / ".zattrs").read_text()).get("_index", "_index")
    return int(json.loads((obs / index / ".zarray").read_text())["shape"][0])


def link(root: str, store: str, v: dict) -> str:
    enc = base64.urlsafe_b64encode(json.dumps(v, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{root}/?dataset_path={store}#view={enc}"


STATE_JS = """() => {
  const vis = e => e.offsetParent !== null && getComputedStyle(e).visibility !== 'hidden';
  const busy = [...document.querySelectorAll('.loading-screen, .loading-overlay, .spinner-border, .fa-spinner')]
      .filter(vis).length;
  const g = document.querySelector('.tile[data-tile-id="cell-plot-A"] .js-plotly-plot');
  let n = -1, sig = null, traces = 0;
  if (g && g._fullData) {
    // the large path's colour bar is a one-point trace with showscale
    const d = g._fullData.filter(t => t.name !== 'Focused Cell'
                                      && !(t.marker && t.marker.showscale && t.x && t.x.length === 1));
    traces = d.length;
    n = d.reduce((s, t) => s + (t.x ? t.x.length : 0), 0);
  }
  // colour signature over ALL traces but the focused-cell marker: per trace, its point count and its
  // colour (the string of a single-colour trace, as large-plot mode's binned traces have, or a strided
  // weighted sum of a per-point colour array), hashed. A recolour changes it in either drawing mode.
  const colourKey = c => {
    if (c === undefined || c === null) return '-';
    if (typeof c === 'string' || typeof c === 'number') return String(c);
    if (!c.length) return '0';
    let s = 0; const st = Math.ceil(c.length / 200000);
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
  sig = traceSig(g);
  const err = [...document.querySelectorAll('.alert-danger, .toast, .notification')].filter(vis)
      .map(e => e.innerText.slice(0, 200));
  const heap = performance.memory ? performance.memory.usedJSHeapSize : -1;
  return {busy, n, sig, heap, traces, err};
}"""

# When a draw finishes: every Plotly call that renders (newPlot, react, restyle, update, relayout, redraw,
# addTraces, deleteTraces, extendTraces) is wrapped, and the time its promise resolves, which is after Plotly's
# plotly_afterplot, is pushed to window.__drawn (page time, ms). A recolour then ends at the last draw that
# follows it, not when gd.data first carries the new colours: the client may set the data before one batched
# Plotly.react draws it (plotly-batch.js).
DRAWHOOK_JS = """(() => {
  window.__drawn = [];
  const wrap = P => {
    if (!P || P.__wrapped) return P;
    for (const f of ['newPlot', 'react', 'restyle', 'update', 'relayout', 'redraw', 'addTraces',
                     'deleteTraces', 'extendTraces']) {
      const orig = P[f];
      if (typeof orig !== 'function') continue;
      P[f] = function (...args) {
        const r = orig.apply(this, args);
        const done = () => window.__drawn.push(performance.now());
        if (r && typeof r.then === 'function') r.then(done, done); else done();
        return r;
      };
    }
    P.__wrapped = true;
    return P;
  };
  let cur = window.Plotly;
  if (cur) wrap(cur);
  Object.defineProperty(window, 'Plotly', { configurable: true, get: () => cur, set: v => { cur = wrap(v); } });
})()"""

# Wait until no draw has finished for `quiet` ms after the data looked done; return the last draw time
# (page ms) after t0 (page ms), or null.
SETTLE_JS = """async ([t0, quiet, cap]) => {
  const start = performance.now();
  let last = Math.max(0, ...window.__drawn.filter(t => t >= t0));
  while (performance.now() - start < cap) {
    await new Promise(r => setTimeout(r, 50));
    const l = Math.max(0, ...window.__drawn.filter(t => t >= t0));
    if (l !== last) { last = l; continue; }
    if (performance.now() - Math.max(last, start) >= quiet) break;
  }
  return last > 0 ? last : null;
}"""

GL_JS = """() => { const gl = document.createElement('canvas').getContext('webgl');
  if (!gl) return 'no webgl';
  const e = gl.getExtension('WEBGL_debug_renderer_info');
  return (e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) +
    ' | maxbuf? ' + gl.getParameter(gl.MAX_TEXTURE_SIZE); }"""

# Zoom: Plotly.relayout to half (dir -1) or double (dir 1) the axis ranges around
# the centre; time until the relayout promise resolved plus two animation frames.
ZOOM_JS = """async (dir) => {
  const g = document.querySelector('.tile[data-tile-id="cell-plot-A"] .js-plotly-plot');
  const f = dir < 0 ? 0.25 : 1.0;
  const upd = {};
  for (const ax of ['xaxis', 'yaxis']) {
    const [a, b] = g._fullLayout[ax].range; const c = (a + b) / 2, h = (b - a) * f;
    upd[ax + '.range'] = [c - h, c + h];
  }
  const t0 = performance.now();
  await Plotly.relayout(g, upd);
  const t1 = performance.now();
  await new Promise(res => requestAnimationFrame(() => requestAnimationFrame(res)));
  return {relayout_ms: t1 - t0, frame_ms: performance.now() - t0};
}"""


# Pan by mouse drag (dragmode pan): frame intervals while the mouse moves (Plotly
# redraws the WebGL scene with a new range on every move), then the time from
# mouse-up until plotly_relayout plus two frames (the relayout re-uploads data).
DRAG_SETUP_JS = """async () => {
  const g = document.querySelector('.tile[data-tile-id="cell-plot-A"] .js-plotly-plot');
  await Plotly.relayout(g, {dragmode: 'pan'});
  const r = g.querySelector('.nsewdrag').getBoundingClientRect();
  window.__frames = []; const gen = (window.__gen = (window.__gen || 0) + 1);
  const tick = (t) => { if (window.__gen !== gen) return; window.__frames.push(t); requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
  window.__relayout = new Promise(res => g.once('plotly_relayout', () => res(performance.now())));
  return {x: r.x + r.width / 2, y: r.y + r.height / 2};
}"""
DRAG_END_JS = """async ([tDown, tUp]) => {
  const tRel = await Promise.race([window.__relayout, new Promise(res => setTimeout(() => res(null), 120000))]);
  await new Promise(res => requestAnimationFrame(() => requestAnimationFrame(res)));
  window.__gen++;
  const f = window.__frames, d = [];
  for (let i = 1; i < f.length; i++) if (f[i - 1] >= tDown && f[i] <= tUp) d.push(f[i] - f[i - 1]);
  d.sort((a, b) => a - b);
  const q = p => d.length ? d[Math.min(d.length - 1, Math.floor(p * d.length))] : null;
  return {frames: d.length, median_ms: q(0.5), p95_ms: q(0.95), max_ms: d.length ? d[d.length - 1] : null,
          relayout_after_up_ms: tRel === null ? null : tRel - tUp, settled_ms: performance.now() - tUp};
}"""


# One redraw of the WebGL scene at the current range, synchronised with the GPU
# (readPixels waits for the draw): the cost of one pan frame. Median of 5.
DRAW_JS = """() => {
  const g = document.querySelector('.tile[data-tile-id="cell-plot-A"] .js-plotly-plot');
  const sc = g._fullLayout._plots.xy._scene;
  const gl = g.querySelector('canvas.gl-canvas-context').getContext('webgl');
  const px = new Uint8Array(4), t = [];
  for (let k = 0; k < 5; k++) {
    const t0 = performance.now(); sc.draw(); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
    t.push(performance.now() - t0);
  }
  t.sort((a, b) => a - b);
  return t[2];
}"""


def drag(page, steps=20):
    c = page.evaluate(DRAG_SETUP_JS)
    page.mouse.move(c["x"], c["y"])
    t_down = page.evaluate("() => performance.now()")
    page.mouse.down()
    for k in range(steps):
        page.mouse.move(c["x"] + 8 * (k + 1), c["y"] + 5 * (k + 1))
        page.wait_for_timeout(30)
    t_up = page.evaluate("() => performance.now()")
    page.mouse.up()
    out = page.evaluate(DRAG_END_JS, [t_down, t_up])
    out["gpu_draw_ms"] = page.evaluate(DRAW_JS)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stores", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="")
    ap.add_argument("--exe", default=str(HERE / ".venv/bin/annzarro"))
    ap.add_argument("--port", type=int, default=8951)
    ap.add_argument("--channel", default="chromium", help="chromium (bundled, new headless) or chrome")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--args", default="", help="extra browser flags, space separated")
    ap.add_argument("--colors", default="cat,gene")
    ap.add_argument("--recolour", type=int, default=3)
    ap.add_argument("--zoom", type=int, default=0)
    ap.add_argument("--emb", default="X_umap", help="obsm key; columns 0 and 1 are x and y")
    ap.add_argument("--cat", default="cell_type", help="categorical obs column (colour 'cat')")
    ap.add_argument("--genes", default="GENE0,GENE1,GENE2,GENE3",
                    help="first = colour 'gene', the rest = recolour targets")
    ap.add_argument("--subset", default="null",
                    help="'null' every cell; 'absent' the server's default; or a JSON subset spec")
    ap.add_argument("--expect", type=int, default=0, help="points to wait for (default: every cell, or the "
                    "subset's n, or 100000 for 'absent')")
    ap.add_argument("--point-size", default="1", help="'default' = the app's default")
    ap.add_argument("--panel-extra", default="{}", help="JSON merged into the panel config, e.g. axis titles")
    ap.add_argument("--opacity", default="0.5", help="'default' = the app's default")
    ap.add_argument("--drag", type=int, default=0, help="pan drags (mouse) after the zooms")
    ap.add_argument("--recolour-cat", default="", help="after the gene recolours, colour by this obs column")
    ap.add_argument("--part-steps", type=int, default=0, help="steps to the subset's next part (header ›)")
    ap.add_argument("--balance", default="", help="then apply a subset balanced by this obs column (dialog)")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--rep-base", type=int, default=0, help="number of the first rep (one rep per call)")
    ap.add_argument("--warm", action="store_true", help="reuse one server across reps (server cache warm)")
    ap.add_argument("--cold", action="store_true",
                    help="each rep reads an APFS clone of the store (cp -c: new files, not in the page cache) "
                         "through a fresh server")
    ap.add_argument("--cold-dir", default="", help="where the clones go (same APFS volume; default: next "
                    "to the store)")
    ap.add_argument("--limit", type=float, default=600)
    ap.add_argument("--min-free", type=int, default=25)
    ap.add_argument("--stop-on-fail", action="store_true", default=True)
    ap.add_argument("--shots", default=str(HERE / "shots"))
    ap.add_argument("--heap-snapshot", default="", help="write a heap snapshot after first plot")
    ap.add_argument("--block-prewarm", action="store_true",
                    help="abort the client's background cell-name index prewarm (/data/names, entity=cells, q='')")
    ap.add_argument("--trace", default="", help="write a Chrome performance trace of the first plot here (.json)")
    ap.add_argument("--cpu-profile", default="", help="write a V8 CPU profile of the first plot here (.cpuprofile)")
    a = ap.parse_args()
    envcapture.require_clean_bench()
    VIEW.update(emb=a.emb, cat=a.cat, genes=a.genes.split(","),
                subset=ABSENT if a.subset == "absent" else json.loads(a.subset),
                point_size=None if a.point_size == "default" else float(a.point_size),
                opacity=None if a.opacity == "default" else float(a.opacity),
                panel_extra=json.loads(a.panel_extra))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    Path(a.shots).mkdir(parents=True, exist_ok=True)
    flags = ["--enable-precise-memory-info"] + [f for f in a.args.split() if f]
    failed = set()

    def emit(**kw):
        # clean: run outside any known live session or unlocked test window
        # (summarize_rerun.py OVERLAP rechecks the time against them)
        kw["tag"], kw["time"], kw["clean"] = a.tag, time.time(), True
        with open(out, "a") as f:
            f.write(json.dumps(kw) + "\n")
        brief = {k: kw.get(k) for k in ("store", "color", "rep", "event", "status", "seconds", "n_points",
                                         "js_heap", "renderer_rss", "gpu_rss")}
        print(json.dumps(brief), flush=True)

    start_stderr()
    with sync_playwright() as pw:
        srv = None
        for store in a.stores:
            n = n_cells(store)
            if a.expect:
                n = a.expect
            elif VIEW["subset"] is ABSENT:
                n = min(n, 100000) if n > 200000 else n
            elif isinstance(VIEW["subset"], dict) and VIEW["subset"].get("n"):
                n = min(n, VIEW["subset"]["n"])
            for color in a.colors.split(","):
                if color in failed:
                    emit(store=Path(store).name, n=n, color=color, event="first_plot", status="skipped")
                    continue
                for rep in range(a.rep_base, a.rep_base + a.reps):
                    if srv is None or not a.warm:
                        if srv:
                            srv.stop()
                        srv = Server(a.exe, str(Path(store).parent), a.port, HERE / "home" / f"p{a.port}")
                    target = store
                    if a.cold:
                        target = str(Path(a.cold_dir or Path(store).parent / "_cold") / f"{Path(store).stem}_{color}_r{rep}.zarr")
                        Path(target).parent.mkdir(exist_ok=True)
                        subprocess.run(["cp", "-c", "-R", store, target], check=True)
                        if srv:
                            srv.stop()
                        srv = Server(a.exe, str(Path(target).parent), a.port, HERE / "home" / f"p{a.port}")
                    try:
                        st = run_one(pw, a, flags, srv, target, n, color, rep, emit)
                    finally:
                        if a.cold:
                            srv.stop()
                            srv = None
                            subprocess.run(["rm", "-rf", target])
                    if not a.warm and srv:
                        srv.stop()
                        srv = None
                    if st != "ok":
                        failed.add(color)
                        break
            if srv and a.warm:
                srv.stop()
                srv = None


def run_one(pw, a, flags, srv, store, n, color, rep, emit):
    launch = dict(headless=not a.headed, args=flags)
    if a.channel and a.channel != "bundled":
        launch["channel"] = a.channel
    browser = pw.chromium.launch(**launch)
    version = browser.version
    if not getattr(run_one, "env_done", False):   # once per invocation, with the first server and browser
        envcapture.record(a.out, exe=a.exe, server_root=srv.root,
                          browser={"channel": a.channel, "version": version, "flags": flags, "headless": not a.headed},
                          tag=a.tag, stores=a.stores)
        run_one.env_done = True
    smp = Sampler(srv, a.min_free)
    smp.start()
    wd = Watchdog(240, smp)
    wd.start()
    console, crashed, reqs = [], {"v": False}, {}
    t_launch, died = time.time(), {}

    def dead() -> str | None:
        """'oom' or 'crash' once the page's renderer died (crash event or its process gone), else None.
        The cause is in `died` (crash_reason): Chromium's OOM line, if it printed one within 3 s."""
        if not died and (crashed["v"] or smp.check()):
            t_end = time.time() + 3
            while ERR and not ERR.since(t_launch) and time.time() < t_end:
                time.sleep(0.1)
            line = ERR.since(t_launch) if ERR else None
            died.update(status="oom" if line else "crash",
                        crash_reason=line or ("crash event" if crashed["v"] is True
                                               else "renderer process gone, no crash event" if smp.gone
                                               else "Playwright: Target crashed"))
        return died.get("status")
    status = "ok"
    base = dict(store=Path(store).name, n=n, color=color, rep=rep, browser=f"{a.channel} {version}",
                flags=" ".join(flags), headed=a.headed)
    try:
        ctx = browser.new_context(viewport={"width": 1400, "height": 1000})
        page = ctx.new_page()
        page.add_init_script(DRAWHOOK_JS)
        if a.trace:
            # long tasks and gaps between animation frames, in page time (performance.now(), ms)
            page.add_init_script("""(() => { window.__lt = []; window.__gaps = []; window.__marks = {};
              try { new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push([e.startTime, e.duration])))
                    .observe({type: 'longtask', buffered: true}); } catch (e) {}
              let last = performance.now();
              const f = t => { if (t - last > 100) window.__gaps.push([last, t - last]); last = t; requestAnimationFrame(f); };
              requestAnimationFrame(f);
              const log = console.info.bind(console);
              console.info = (...x) => { if (String(x[0]).startsWith('Large cell plot')) window.__marks.large_log = performance.now(); log(...x); };
            })()""")
            browser.start_tracing(page=page, path=a.trace, screenshots=True,
                                  categories=["devtools.timeline", "disabled-by-default-devtools.timeline",
                                              "disabled-by-default-devtools.timeline.frame", "v8", "gpu", "blink",
                                              "disabled-by-default-v8.gc", "toplevel"])
        inflight = set()

        def on_req(r):
            # the cell-name index prewarm (/data/names) runs in the background
            # after the plot is drawn; it is recorded but not waited for
            if "/api/" in r.url and "/data/names" not in r.url:
                inflight.add(r)
            if "/api/" in r.url:
                reqs[r] = {"url": r.url.split("/api/v1/")[-1][:140], "t_start": time.perf_counter()}

        def on_done(r, failed=False):
            inflight.discard(r)
            if r in reqs:
                d = reqs[r]
                d["t_end"] = time.perf_counter()
                d["failed"] = failed or None
                try:
                    tm = r.timing
                    d["ttfb_ms"] = tm["responseStart"] - tm["requestStart"]
                    d["recv_ms"] = tm["responseEnd"] - tm["responseStart"]
                except Exception:
                    pass
                try:
                    if not failed:
                        resp = r.response()
                        d["bytes"] = int(resp.headers.get("content-length", -1)) if resp else -1
                        d["status"] = resp.status if resp else None
                except Exception:
                    pass
        page.on("request", on_req)
        page.on("requestfinished", lambda r: on_done(r))
        page.on("requestfailed", lambda r: on_done(r, True))
        page.on("crash", lambda *_: crashed.__setitem__("v", True))
        page.on("console", lambda m: console.append(f"{m.type}: {m.text[:300]}")
                if m.type in ("error", "warning") or m.text.startswith(("Large cell plot", "Cell names:"))
                else None)
        marks = {}   # when the app logged its large-plot timing line (s after navigation)
        page.on("console", lambda m: marks.setdefault("large_log_t", time.perf_counter())
                if m.text.startswith("Large cell plot") else None)
        if a.block_prewarm:
            page.route("**/api/v1/data/names?*", lambda route: route.abort()
                       if "entity=cells" in route.request.url and "q=&" in route.request.url
                       else route.continue_())
        page.on("pageerror", lambda e: console.append(f"pageerror: {str(e)[:300]}"))
        page.goto("about:blank")
        gl = page.evaluate(GL_JS)
        cdp = page.context.new_cdp_session(page)
        hpk = {"used": 0, "backing": 0}

        def heap_usage():
            # armed: on a renderer that died without a crash event this CDP call
            # never returns (seen at 200M points); the watchdog then kills the browser
            if died or smp.gone:
                return {}
            try:
                wd.arm()
                h = cdp.send("Runtime.getHeapUsage")
                wd.disarm()
                hpk["used"] = max(hpk["used"], h.get("usedSize", 0))
                hpk["backing"] = max(hpk["backing"], h.get("backingStorageSize", 0))
                return h
            except Exception:
                return {}
        url = link(srv.root, store, view(color))
        if a.cpu_profile:
            cdp.send("Profiler.enable")
            cdp.send("Profiler.setSamplingInterval", {"interval": 1000})
            cdp.send("Profiler.start")
        t0 = time.perf_counter()
        wd.arm()
        try:
            page.goto(url, timeout=a.limit * 1000)
        finally:
            wd.disarm()
        if wd.fired:
            raise RuntimeError("page.goto hung; browser killed by the watchdog")
        smp.watch()
        st, heap_peak = {}, 0
        last_key, last_change = None, time.perf_counter()
        while True:
            el = time.perf_counter() - t0
            if dead():
                status = dead(); break
            if smp.low:
                status = "low_memory"; break
            try:
                wd.arm()
                st = page.evaluate(STATE_JS)
                wd.disarm()
            except Exception as e:
                status = dead() or ("hung_killed" if wd.fired
                                    else f"eval_error:{type(e).__name__}:{str(e)[:100]}"); break
            heap_peak = max(heap_peak, st["heap"])
            heap_usage()
            if st["n"] >= n and st["busy"] == 0 and not inflight:
                break
            key = (st["n"], st["busy"], len(inflight), len(console))
            if key != last_key or inflight:
                last_key, last_change = key, time.perf_counter()
            elif time.perf_counter() - last_change > 45 and st["n"] < n:
                status = "stalled"; break
            if el > a.limit:
                status = "timeout"; break
            time.sleep(0.1)
        first = time.perf_counter() - t0
        page_t = None
        # a dead page answers nothing: no further page, CDP or browser call (a CDP call on it never returns)
        if a.trace and not died:
            try:
                page_t = page.evaluate("() => ({now: performance.now(), lt: window.__lt, gaps: window.__gaps, marks: window.__marks})")
            except Exception as e:
                page_t = {"error": str(e)[:200]}
            browser.stop_tracing()
        if a.cpu_profile and status == "ok":
            prof = cdp.send("Profiler.stop")["profile"]
            Path(a.cpu_profile).write_text(json.dumps(prof))
        shot = None
        if status == "ok":
            shot = str(Path(a.shots) / f"{a.tag}_{Path(store).stem}_{color}_r{rep}.png")
            try:
                page.locator('.tile[data-tile-id="cell-plot-A"]').screenshot(path=shot, timeout=120000)
            except Exception as e:
                shot = f"screenshot failed: {e}"[:200]
        tile_text = None
        if status != "ok" and not died:   # what the panel shows instead of a plot (e.g. the memory guard's refusal)
            try:
                tile_text = page.evaluate("""() => { const t = document.querySelector('.tile[data-tile-id="cell-plot-A"]');
                    return t ? t.innerText.slice(0, 600) : null; }""")
            except Exception as e:
                tile_text = f"unavailable: {type(e).__name__}"
        api = sorted(({k: v for k, v in d.items() if k != "t_start"} | {"t_rel": d["t_start"] - t0}
                      for d in reqs.values() if d["t_start"] >= t0), key=lambda d: d["t_rel"])
        emit(**base, event="first_plot", status=status, seconds=first, n_points=st.get("n"),
             traces=st.get("traces"), busy=st.get("busy"), ui_errors=st.get("err"), js_heap=heap_peak,
             v8_used_peak=hpk["used"], v8_backing_peak=hpk["backing"],
             heap_usage_end=None if died else heap_usage(),
             renderer_rss=smp.peak["renderer"], gpu_rss=smp.peak["gpu"], browser_rss=smp.peak["browser"],
             server_rss=srv.peak, min_free=smp.min_free_seen, gl=gl, console=console[:30], api=api, shot=shot,
             large_log_t=(marks["large_log_t"] - t0) if "large_log_t" in marks else None,
             block_prewarm=a.block_prewarm or None, page_timing=page_t, tile_text=tile_text,
             crash_reason=died.get("crash_reason"))
        if status != "ok":
            return status
        if a.heap_snapshot:
            snap(page, a.heap_snapshot)
        if color == "gene":
            for k, g in enumerate(VIEW["genes"][1:1 + a.recolour]):
                before = page.evaluate(STATE_JS)["sig"]
                box = page.locator("#focused-gene")
                box.click(); box.fill(g)
                page.wait_for_timeout(400)
                reqs.clear(); console.clear()
                p0 = page.evaluate("performance.now()")
                t1 = time.perf_counter()
                box.press("Enter")
                rs = "ok"
                while True:
                    if dead():
                        rs = dead(); break
                    if smp.low:
                        rs = "low_memory"; break
                    if any("Error loading plot data" in c for c in console):   # the panel's own failure
                        rs = "error"; break
                    try:
                        wd.arm()
                        s = page.evaluate(STATE_JS)
                        wd.disarm()
                    except Exception:
                        if not dead():
                            raise
                        rs = dead(); break
                    heap_peak = max(heap_peak, s["heap"])
                    heap_usage()
                    if s["sig"] != before and s["busy"] == 0 and not inflight:
                        break
                    if time.perf_counter() - t1 > a.limit:
                        rs = "timeout"; break
                    time.sleep(0.05)
                data_s = time.perf_counter() - t1
                drawn_s = None
                if rs == "ok":
                    last = page.evaluate(SETTLE_JS, [p0, 500, 60000])
                    drawn_s = (last - p0) / 1000 if last else None
                api = [{k: v for k, v in d.items() if k != "t_start"} | {"t_rel": d["t_start"] - t1}
                       for d in reqs.values()]
                emit(**base, event="recolour", seq=k, gene=g, status=rs,
                     seconds=max(data_s, drawn_s or 0), seconds_data=data_s, seconds_drawn=drawn_s,
                     n_points=s.get("n"), js_heap=s["heap"], v8_used_peak=hpk["used"],
                     v8_backing_peak=hpk["backing"], renderer_rss=smp.peak["renderer"],
                     gpu_rss=smp.peak["gpu"], renderer_now=smp.cur["renderer"], server_rss=srv.peak,
                     min_free=smp.min_free_seen, console=console[:10], api=api,
                     crash_reason=died.get("crash_reason"))
                if rs != "ok":
                    return rs

        def interact(event, action, **extra):
            """Run `action(page)`, then wait until the panel's colour signature
            changed, it holds n points, nothing is loading and no API request
            is in flight; emit the event. Returns its status."""
            nonlocal heap_peak
            before = page.evaluate(STATE_JS)["sig"]
            reqs.clear(); console.clear()
            p0 = page.evaluate("performance.now()")
            t1 = time.perf_counter()
            action(page)
            rs, s = "ok", {}
            while True:
                if dead():
                    rs = dead(); break
                if smp.low:
                    rs = "low_memory"; break
                if any("Error loading plot data" in c for c in console):   # the panel's own failure, not a wait
                    rs = "error"; break
                try:
                    wd.arm()
                    s = page.evaluate(STATE_JS)
                    wd.disarm()
                except Exception:
                    if not dead():
                        raise
                    rs = dead(); break
                heap_peak = max(heap_peak, s["heap"])
                heap_usage()
                if s["sig"] != before and s["n"] >= n and s["busy"] == 0 and not inflight:
                    break
                if time.perf_counter() - t1 > a.limit:
                    rs = "timeout"; break
                time.sleep(0.05)
            data_s = time.perf_counter() - t1
            drawn_s = None
            if rs == "ok":
                last = page.evaluate(SETTLE_JS, [p0, 500, 60000])
                drawn_s = (last - p0) / 1000 if last else None
            api = [{k: v for k, v in d.items() if k != "t_start"} | {"t_rel": d["t_start"] - t1}
                   for d in reqs.values()]
            emit(**base, event=event, status=rs, seconds=max(data_s, drawn_s or 0), seconds_data=data_s,
                 seconds_drawn=drawn_s, n_points=s.get("n"),
                 js_heap=s.get("heap"), v8_used_peak=hpk["used"], v8_backing_peak=hpk["backing"],
                 renderer_rss=smp.peak["renderer"], gpu_rss=smp.peak["gpu"], renderer_now=smp.cur["renderer"],
                 server_rss=srv.peak, min_free=smp.min_free_seen, console=console[:10], api=api,
                 crash_reason=died.get("crash_reason"), **extra)
            return rs

        # Recolour by a category: what choosing an obs column as Colour does
        # (the axis listeners call loadDataAndCreatePlot, as refreshPlot does).
        if color == "gene" and a.recolour_cat:
            js = ("c => { const p = window.PanelManager.getPanel('cell-plot-A');"
                  " p.updateConfig({color: {type: 'obs', key: c, column: ''}}); p.refreshPlot(); }")
            if interact("recolour_cat", lambda pg: pg.evaluate(js, a.recolour_cat), key=a.recolour_cat) != "ok":
                return "recolour_cat_failed"
        # The subset's next part (the › button in the header).
        for k in range(a.part_steps):
            if interact("part_step", lambda pg: pg.click("#subset-part-next"), seq=k) != "ok":
                return "part_step_failed"
        # Balanced subset: the subset dialog, Sampling = balanced by a column, Apply.
        if a.balance:
            def bal(pg):
                pg.click("#subset-button")
                pg.wait_for_selector("#subset-balance", state="visible")
                pg.select_option("#subset-balance", a.balance)
                pg.wait_for_selector("#subset-apply:not([disabled])")
                pg.click("#subset-apply")
            if interact("balance", bal, key=a.balance) != "ok":
                return "balance_failed"
        for k in range(a.zoom):
            try:
                z = page.evaluate(ZOOM_JS, -1 if k % 2 == 0 else 1)
                emit(**base, event="zoom", seq=k, status="ok", seconds=z["frame_ms"] / 1000,
                     relayout_ms=z["relayout_ms"], js_heap=page.evaluate(STATE_JS)["heap"],
                     renderer_rss=smp.peak["renderer"], gpu_rss=smp.peak["gpu"])
            except Exception as e:
                emit(**base, event="zoom", seq=k, status=f"error:{str(e)[:120]}")
                break
        for k in range(a.drag):
            try:
                dres = drag(page)
                emit(**base, event="drag", seq=k, status="ok", seconds=dres["settled_ms"] / 1000, **dres,
                     renderer_rss=smp.peak["renderer"], gpu_rss=smp.peak["gpu"])
            except Exception as e:
                emit(**base, event="drag", seq=k, status=f"error:{str(e)[:120]}")
                break
        return "ok"
    except Exception as e:
        if "Target crashed" in str(e):   # Playwright's own word for a renderer that died
            smp.check()
            crashed["v"] = crashed["v"] or "target_crashed"
        st = dead()   # an exception from a dead page is the death, not a harness error
        emit(**base, event="first_plot", status=st or f"exception:{type(e).__name__}", note=str(e)[:400],
             console=console[:30], renderer_rss=smp.peak["renderer"], gpu_rss=smp.peak["gpu"],
             crashed=crashed["v"], crash_reason=died.get("crash_reason"))
        return st or "exception"
    finally:
        smp.running = False
        wd.running = False
        try:
            if not died:   # the watchdog already killed a dead page's browser
                browser.close()
        except Exception:
            pass


def snap(page, path):
    cdp = page.context.new_cdp_session(page)
    chunks = []
    cdp.on("HeapProfiler.addHeapSnapshotChunk", lambda p: chunks.append(p["chunk"]))
    cdp.send("HeapProfiler.takeHeapSnapshot", {"reportProgress": False, "captureNumericValue": False})
    Path(path).write_text("".join(chunks))


if __name__ == "__main__":
    main()
