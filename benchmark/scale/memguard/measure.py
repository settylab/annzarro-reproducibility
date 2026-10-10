#!/usr/bin/env python
"""What each AnnZarro action costs in browser memory: the data for the
browser memory guard's models (annzarro static/js/utils/memory-guard.js).

One run = one fresh Chromium (bundled, new headless, as ceiling.py) and one
annzarro server on one store, then a list of STEPS on that page. For every
step it writes one JSON line with:

  heap_peak     V8 heap at its highest during the step: the largest "before"
                size of every GC V8 traced (--js-flags=--trace-gc, read from a
                pty so the lines arrive as they happen). Runtime.getHeapUsage
                cannot be asked while a long task runs; a GC can.
  renderer_peak, gpu_peak   RSS of the page's renderer and the GPU process,
                sampled every 0.1 s (psutil)
  after         once the step is done and two forced GCs ran:
                on-heap (Runtime.getHeapUsage usedSize), ArrayBuffers
                (backingStorageSize), renderer and GPU RSS, live WebGL
                contexts, the guard's ledger
  verdict       ok | crash | timeout | error

Steps (see STEPS below): load, panel[:ID], dup, snapshot, export_full,
export_plotly, close[:ID], all (subset off: every cell), subset:N, cycle:K
(open and close a plot K times), exports:K.

Usage:
  measure.py STORE --worktree WT --python PY --steps load,panel,export_full \
      [--large-threshold N] [--color gene|cat] [--subset absent|null|N] --out F.jsonl --tag T
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pty
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import psutil
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import envcapture  # noqa: E402

GC_RE = re.compile(r"(Mark-Compact|Scavenge|Minor Mark-Compact|Mark-Sweep)[^\d]*([\d.]+) \(([\d.]+)\) -> ([\d.]+)")
MB = 1024 * 1024


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class GcLog(threading.Thread):
    """Chromium's stdout/stderr through a pty: every --trace-gc line, timestamped."""

    def __init__(self, fd, path):
        super().__init__(daemon=True)
        self.fd, self.out = fd, open(path, "w")
        self.events = []        # (time, before_bytes, after_bytes)
        self.lock = threading.Lock()

    def run(self):
        buf = b""
        while True:
            try:
                chunk = os.read(self.fd, 65536)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            *lines, buf = buf.split(b"\n")
            now = time.time()
            for raw in lines:
                line = raw.decode(errors="replace")
                m = GC_RE.search(line)
                if m:
                    with self.lock:
                        self.events.append((now, float(m.group(2)) * MB, float(m.group(4)) * MB))
                elif line.strip():
                    # flushed per line: a crash's last words must reach the file
                    self.out.write(f"{now:.2f} {line}\n")
                    self.out.flush()

    def peak(self, t0, t1):
        with self.lock:
            vals = [b for t, b, _ in self.events if t0 <= t <= t1 + 0.5]
        return max(vals) if vals else None


class Sampler(threading.Thread):
    """Peak RSS of the renderer and GPU processes under Chromium's browser process."""

    def __init__(self, browser_pid):
        super().__init__(daemon=True)
        self.root = psutil.Process(browser_pid)
        self.peak = {"renderer": 0, "gpu": 0}
        self.running = True

    def current(self):
        out = {"renderer": 0, "gpu": 0}
        for p in self.root.children(recursive=True):
            try:
                cmd = " ".join(p.cmdline())
                rss = p.memory_info().rss
            except psutil.Error:
                continue
            if "--type=renderer" in cmd and "--extension-process" not in cmd:
                out["renderer"] = max(out["renderer"], rss)
            elif "--type=gpu-process" in cmd:
                out["gpu"] = max(out["gpu"], rss)
        return out

    def reset(self):
        self.peak = self.current()

    def run(self):
        while self.running:
            c = self.current()
            for k in c:
                self.peak[k] = max(self.peak[k], c[k])
            time.sleep(0.1)


def user_chrome():
    """The user's own Chrome renderers running meanwhile (a review session may overlap a run)."""
    n, rss, cpu = 0, 0, 0.0
    for p in psutil.process_iter(["cmdline"]):
        try:
            cmd = " ".join(p.info["cmdline"] or [])
            if "/Applications/Google Chrome.app" in cmd and "--type=renderer" in cmd:
                n += 1
                rss += p.memory_info().rss
                cpu += p.cpu_percent(interval=None)
        except psutil.Error:
            continue
    return {"renderers": n, "rss": rss}


def other_load(own_root_pid):
    """Other agents' tests beside this run: pytest processes and Chromium browser
    processes not under this run's browser (renderer/GPU footprints and times
    are sensitive to them; per-isolate heap is not)."""
    try:
        mine = {own_root_pid} | {p.pid for p in psutil.Process(own_root_pid).children(recursive=True)}
    except psutil.Error:
        mine = {own_root_pid}
    pytest, chromium = 0, 0
    for p in psutil.process_iter(["cmdline"]):
        try:
            cmd = " ".join(p.info["cmdline"] or [])
            if "pytest" in cmd and "python" in cmd:
                pytest += 1
            elif "ms-playwright" in cmd and "--type=" not in cmd and p.pid not in mine:
                chromium += 1
        except psutil.Error:
            continue
    return {"pytest": pytest, "chromium": chromium}


def view(store, color, subset, panels=1, cat="cell_line_id", gene="FN1"):
    x = {"type": "obsm", "key": "X_umap", "column": "0"}
    y = {"type": "obsm", "key": "X_umap", "column": "1"}
    col = ({"type": "obs", "key": cat, "column": ""} if color == "cat"
           else {"type": "layer", "key": "X", "column": gene, "locked": False})
    cfgs, tiles = {}, []
    for i in range(panels):
        pid = f"cell-plot-{chr(ord('A') + i)}"
        cfgs[pid] = {"id": pid, "title": pid, "x": x, "y": y, "z": None, "color": col}
        tiles.append({"type": "tile", "id": pid, "controlsVisible": False})

    def nest(nodes):
        if len(nodes) == 1:
            return nodes[0]
        return {"type": "split", "direction": "horizontal", "panes": [{"percentage": 50}, {"percentage": 50}],
                "children": [nodes[0], nest(nodes[1:])]}
    hierarchy = [nest(tiles)] if tiles else []
    v = {"v": 1, "constants": {"focusedGene": gene},
         "layout": {"v": 1, "hierarchy": hierarchy, "controlState": {t["id"]: False for t in tiles}, "panelConfigs": cfgs}}
    if subset != "absent":
        v["subset"] = None if subset == "null" else {"n": int(subset), "seed": 0}
    return v, col


def link(root, store, v):
    enc = base64.urlsafe_b64encode(json.dumps(v, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{root}/?dataset_path={store}#view={enc}"


AFTER_JS = """async () => {
  const g = await import('/static/js/utils/memory-guard-ui.js');
  const r = await import('/static/js/utils/release-plot.js');
  return { contexts: r.liveWebglContexts(),
           ledger: g.ledger.panels().map(e => ({ id: e.id, n: e.n, large: e.large, heap: Math.round(e.resident.heap) })),
           pending: [...g.ledger.pending.keys()],
           jsHeap: performance.memory ? performance.memory.usedJSHeapSize : null,
           limit: performance.memory ? performance.memory.jsHeapSizeLimit : null,
           points: [...document.querySelectorAll('.js-plotly-plot')].map(gd => gd._pointCount || 0) };
}"""

WAIT_DRAWN = """async ([id, n]) => {
  const g = await import('/static/js/utils/memory-guard-ui.js');
  const e = g.ledger.get(id);
  const ph = document.querySelector(`.tile[data-tile-id="${id}"] .coverage-placeholder`);
  if (ph) return 'placeholder: ' + ph.innerText.slice(0, 200);
  return e && !g.ledger.pending.has(id) && (!n || e.n === n) ? 'ok' : null;
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("store")
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--python", required=True)
    ap.add_argument("--steps", required=True)
    ap.add_argument("--color", default="gene")
    ap.add_argument("--cat", default="cell_line_id")
    ap.add_argument("--gene", default="FN1")
    ap.add_argument("--subset", default="null", help="absent | null (every cell) | N")
    ap.add_argument("--panels", type=int, default=0, help="plots in the link (0: none, add with 'panel')")
    ap.add_argument("--large-threshold", type=int, default=None)
    ap.add_argument("--limit", type=float, default=900)
    ap.add_argument("--tag", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if not os.environ.get("MEMGUARD_DEV"):      # a development run of an uncommitted script: never a result
        envcapture.require_clean_bench()

    work = Path(tempfile.mkdtemp(prefix="memguard_"))
    cfg = "ui:\n  memory:\n    enforce: \"off\"\n"
    if a.large_threshold is not None:
        cfg += f"  defaults:\n    large_plot_points: {a.large_threshold}\n"
    (work / "config.yaml").write_text(cfg)
    port = free_port()
    env = dict(os.environ, ANNZARRO_HOME=str(work), ANNZARRO_HEADLESS="1", PYTHONPATH=a.worktree)
    srv = subprocess.Popen([a.python, "-m", "annzarro.cli", "start", "--config", str(work / "config.yaml"),
                            "--host", "127.0.0.1", "--port", str(port), "--data-dir", str(Path(a.store).parent),
                            "--no-browser", "--auth-disabled"], env=env, cwd=a.worktree,
                           stdout=open(work / "server.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    root = f"http://127.0.0.1:{port}"
    import urllib.request
    for _ in range(240):
        try:
            urllib.request.urlopen(root + "/api/v1/config", timeout=1)
            break
        except OSError:
            time.sleep(0.25)
    else:
        sys.exit("server did not start")

    out = open(a.out, "a")
    t_start = time.time()
    base = {"tag": a.tag, "store": Path(a.store).name, "color": a.color, "subset": a.subset,
            "large_threshold": a.large_threshold, "worktree_commit": subprocess.run(
                ["git", "-C", a.worktree, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()}

    with sync_playwright() as pw:
        exe = pw.chromium.executable_path
        cdp_port = free_port()
        master, slave = pty.openpty()
        flags = ["--headless=new", f"--remote-debugging-port={cdp_port}", f"--user-data-dir={work / 'profile'}",
                 "--no-first-run", "--no-default-browser-check", "--enable-precise-memory-info",
                 "--js-flags=--trace-gc", "--enable-unsafe-swiftshader", "about:blank"]
        chrome = subprocess.Popen([exe, *flags], stdout=slave, stderr=slave, start_new_session=True)
        os.close(slave)
        gclog = GcLog(master, work / "chrome.log")
        gclog.start()
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/version", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
        version = browser.version
        envcapture.record(a.out, python=a.python, server_root=root,
                          browser={"channel": "bundled", "version": version, "flags": flags, "headless": True},
                          store=a.store, steps=a.steps, tag=a.tag)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_viewport_size({"width": 1400, "height": 900})
        page.set_default_timeout(a.limit * 1000)
        crashed = {"v": False}
        page.on("crash", lambda *_: crashed.__setitem__("v", True))
        cdp = ctx.new_cdp_session(page)
        sampler = Sampler(chrome.pid)
        sampler.start()

        def after():
            for _ in range(2):
                cdp.send("HeapProfiler.collectGarbage")
            h = cdp.send("Runtime.getHeapUsage")
            cur = sampler.current()
            res = {"heap": h.get("usedSize"), "backing": h.get("backingStorageSize"),
                   "renderer": cur["renderer"], "gpu": cur["gpu"]}
            try:
                res.update(page.evaluate(AFTER_JS))
            except Exception as e:     # noqa: BLE001
                res["page_error"] = str(e)[:200]
            return res

        def wait_drawn(pid, n=None):
            t0 = time.time()
            while time.time() - t0 < a.limit:
                if crashed["v"]:
                    raise RuntimeError("crash")
                r = page.evaluate(WAIT_DRAWN, [pid, n])
                if r:
                    return r
                time.sleep(0.25)
            raise TimeoutError(pid)

        v, col = view(a.store, a.color, a.subset, a.panels, a.cat, a.gene)

        def panel_cfg(pid):
            return {"id": pid, "title": pid, "x": {"type": "obsm", "key": "X_umap", "column": "0"},
                    "y": {"type": "obsm", "key": "X_umap", "column": "1"}, "z": None, "color": col}

        def run_step(step):
            name, _, arg = step.partition(":")
            if name == "load":
                page.goto(link(root, a.store, v))
                # the dataset is loaded before its cell names have arrived (a
                # 1M-cell list takes a moment, and the list is replaced once
                # more meanwhile); a plot created then says the dataset has no
                # names. Polled here: wait_for_function does not await an
                # async predicate (its Promise is truthy at once).
                names_js = """async () => {
                    const { DataManager } = await import('/static/js/data-manager.js');
                    const cells = DataManager.getCells();
                    return DataManager.isDatasetLoaded() && cells ? cells.length : 0;
                }"""
                stable, t0 = 0, time.time()
                while stable < 4:
                    stable = stable + 1 if page.evaluate(names_js) > 0 else 0
                    if time.time() - t0 > a.limit:
                        raise TimeoutError("cell names")
                    time.sleep(0.25)
                for i in range(a.panels):
                    wait_drawn(f"cell-plot-{chr(ord('A') + i)}")
                return {}
            if name in ("panel", "dup"):
                pid = arg or ("cell-plot-B" if name == "dup" else "cell-plot-A")
                page.evaluate("cfg => { window.PanelManager.createPanelInLayout('cell-plot', cfg); }", panel_cfg(pid))
                return {"drawn": wait_drawn(pid)}
            if name == "clearcache":     # drop the client cache, to tell cache from leak
                return {"cache_before": page.evaluate("""async () => {
                    const { CacheManager } = await import('/static/js/cache-manager.js');
                    const b = CacheManager.bytes();
                    CacheManager.clear();
                    return b; }""")}
            if name == "close":
                page.evaluate("id => window.PanelManager.closePanel(id)", arg or "cell-plot-A")
                return {}
            gd = "document.querySelector('.js-plotly-plot')"
            if name == "snapshot":
                return {"bytes": page.evaluate(f"async () => (await (await import('/static/js/utils/plot-export.js')).snapshotImage({gd}, {{format: 'png'}})).length")}
            if name == "export_full":
                return {"bytes": page.evaluate(f"async () => (await (await import('/static/js/utils/plot-export.js')).fullImage({gd}, {{format: 'png', width: 1200, height: 800, scale: 2}})).length")}
            if name == "export_plotly":
                return {"bytes": page.evaluate(f"async () => (await Plotly.toImage({gd}, {{format: 'png', width: 1200, height: 800, scale: 2}})).length")}
            if name == "exports":
                k = int(arg or 10)
                for _ in range(k):
                    page.evaluate(f"async () => (await (await import('/static/js/utils/plot-export.js')).fullImage({gd}, {{format: 'png', width: 1200, height: 800, scale: 2}})).length")
                return {"k": k}
            if name == "cycle":
                k = int(arg or 10)
                per = []
                for i in range(k):
                    page.evaluate("cfg => { window.PanelManager.createPanelInLayout('cell-plot', cfg); }", panel_cfg("cell-plot-Z"))
                    wait_drawn("cell-plot-Z")
                    page.evaluate("id => window.PanelManager.closePanel(id)", "cell-plot-Z")
                    a_ = after()
                    per.append({k2: a_.get(k2) for k2 in ("heap", "backing", "renderer", "gpu", "contexts")})
                return {"cycles": per}
            if name in ("all", "subset"):
                page.click("#subset-button")
                page.wait_for_selector("#subset-apply", state="visible")
                if name == "all":
                    if page.is_checked("#subset-enabled"):
                        page.click("#subset-enabled")
                else:
                    if not page.is_checked("#subset-enabled"):
                        page.click("#subset-enabled")
                    page.fill("#subset-n", str(arg))
                page.wait_for_function("() => !document.getElementById('subset-apply').disabled")
                page.click("#subset-apply")
                ids = page.evaluate("async () => (await import('/static/js/utils/memory-guard-ui.js')).ledger.panels().filter(e => e.kind === 'cell-plot').map(e => e.id)")
                time.sleep(1)
                want = None if name == "all" else int(arg)
                for pid in ids:
                    wait_drawn(pid, want or page.evaluate("async () => (await import('/static/js/data-manager.js')).DataManager.getCells().length"))
                return {"plots": ids}
            raise ValueError(step)

        for step in a.steps.split(","):
            sampler.reset()
            t0 = time.time()
            rec = {**base, "step": step, "t_start": round(t0 - t_start, 2), "user_chrome": user_chrome(),
                   "other_load": other_load(chrome.pid)}
            try:
                h = cdp.send("Runtime.getHeapUsage")
                rec["before"] = {"heap": h.get("usedSize"), "backing": h.get("backingStorageSize")}
            except Exception:      # noqa: BLE001
                pass
            try:
                rec.update(run_step(step))
                rec["verdict"] = "ok"
            except Exception as e:      # noqa: BLE001
                rec["verdict"] = "crash" if crashed["v"] else ("timeout" if isinstance(e, TimeoutError) else "error")
                rec["error"] = str(e)[:300]
            t1 = time.time()
            rec["seconds"] = round(t1 - t0, 2)
            rec["heap_peak"] = gclog.peak(t0, t1)
            rec["renderer_peak"], rec["gpu_peak"] = sampler.peak["renderer"], sampler.peak["gpu"]
            if rec["verdict"] == "ok":
                try:
                    rec["after"] = after()
                except Exception as e:      # noqa: BLE001
                    rec["verdict"], rec["error"] = ("crash" if crashed["v"] else "error"), str(e)[:300]
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(json.dumps({k: rec.get(k) for k in ("step", "verdict", "seconds", "heap_peak", "renderer_peak", "error")}), flush=True)
            if rec["verdict"] != "ok":
                break
        sampler.running = False
        try:
            browser.close()
        except Exception:      # noqa: BLE001
            pass
    for proc in (chrome, srv):
        try:
            os.killpg(proc.pid, 15)
        except Exception:      # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
