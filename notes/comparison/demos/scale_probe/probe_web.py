"""Load a hosted single-cell viewer in headless Chromium and measure what it draws.

Usage: probe_web.py <label> <url> --expect N [--reps 3] [--timeout 900] [--out results.jsonl]

Per rep (fresh browser each time):
  * points drawn: every WebGL draw call is wrapped by an init script, which records the
    largest point/instance count of any single call (and its time since navigation start);
  * time to first full render: first draw call whose count >= --expect (or, without it, the
    time the largest draw was first seen);
  * network bytes per URL (Playwright request sizes), top files reported;
  * memory after render: JS heap (performance.memory, CDP JSHeapUsedSize) and the peak RSS
    of the renderer and GPU processes (psutil over this script's children, 0.2 s sampling);
  * responsiveness: a mouse-wheel zoom on the plot centre, time until the next full draw.
Chromium flags follow benchmark/scale/ceiling/ceiling.py (bundled chromium, new headless,
--enable-precise-memory-info). A screenshot is saved per rep.
"""
import argparse
import re
import json
import threading
import time
from pathlib import Path

import psutil
from playwright.sync_api import sync_playwright

INIT = r"""
(() => {
  try { localStorage.setItem("introShown", "true"); } catch (e) {}
  const S = window.__gl = {max: 0, tMax: null, tFull: null, calls: 0, expect: 0, last: 0, tLast: null, glinfo: null};
  const rec = (n) => {
    S.calls++; const t = performance.now();
    if (n > S.max) { S.max = n; S.tMax = t; }
    if (S.expect && n >= S.expect && S.tFull === null) S.tFull = t;
    if (n >= S.max * 0.99) { S.last = n; S.tLast = t; }
  };
  for (const P of [WebGLRenderingContext.prototype, WebGL2RenderingContext.prototype]) {
    const da = P.drawArrays, de = P.drawElements;
    P.drawArrays = function (m, f, c) { if (m === 0) rec(c); return da.apply(this, arguments); };
    P.drawElements = function (m, c, ty, o) { if (m === 0) rec(c); return de.apply(this, arguments); };
  }
  const P2 = WebGL2RenderingContext.prototype;
  const dai = P2.drawArraysInstanced, dei = P2.drawElementsInstanced;
  P2.drawArraysInstanced = function (m, f, c, n) { rec(n); return dai.apply(this, arguments); };
  P2.drawElementsInstanced = function (m, c, ty, o, n) { rec(n); return dei.apply(this, arguments); };
  const gc = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (kind) {
    const ctx = gc.apply(this, arguments);
    if (ctx && /webgl/.test(kind) && !S.glinfo) {
      try { const e = ctx.getExtension('WEBGL_debug_renderer_info');
            S.glinfo = e ? ctx.getParameter(e.UNMASKED_RENDERER_WEBGL) : ctx.getParameter(ctx.RENDERER); } catch (err) {}
    }
    return ctx;
  };
})();
"""


class RSS(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.peak = {"renderer": 0, "gpu": 0}
        self.running = True

    def run(self):
        me = psutil.Process()
        while self.running:
            for p in me.children(recursive=True):
                try:
                    cmd = " ".join(p.cmdline())
                    k = "renderer" if "--type=renderer" in cmd else "gpu" if "--type=gpu-process" in cmd else None
                    if k:
                        self.peak[k] = max(self.peak[k], p.memory_info().rss)
                except psutil.Error:
                    pass
            time.sleep(0.2)


def one(pw, a, rep):
    browser = pw.chromium.launch(headless=True, channel="chromium", args=["--enable-precise-memory-info"])
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    ctx.add_init_script(INIT + f"\nwindow.__gl.expect = {a.expect};")
    page = ctx.new_page()
    sizes = {}
    page.on("requestfinished", lambda r: sizes.__setitem__(r.url, sizes.get(r.url, 0) + (r.sizes().get("responseBodySize", 0) or 0)))
    rss = RSS()
    rss.start()
    t0 = time.time()
    page.goto(a.url, wait_until="domcontentloaded", timeout=a.timeout * 1000)
    status, gl = "timeout", {}
    while time.time() - t0 < a.timeout:
        gl = page.evaluate("window.__gl")
        if (a.expect and gl["tFull"] is not None) or (not a.expect and gl["max"] > 0 and time.time() - t0 > 30
                                                       and performance_quiet(page, gl)):
            status = "ok"
            break
        time.sleep(1)
    page.keyboard.press("Escape")
    page.wait_for_timeout(3000)
    gl = page.evaluate("window.__gl")
    cdp = ctx.new_cdp_session(page)
    cdp.send("Performance.enable")
    m = {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}
    heap = page.evaluate("performance.memory ? performance.memory.usedJSHeapSize : -1")
    shot = Path(a.shots) / f"{a.label}_r{rep}.png"
    page.screenshot(path=str(shot))
    # responsiveness: each site action, then time until the next draw of >= 99% of all points
    timings = {}
    for name, act in SITE_ACTIONS.get(a.site, []):
        tz = page.evaluate("performance.now()")
        timings[name] = None
        try:
            act(page)
        except Exception as e:  # record and go on: one failed action must not lose the rep
            timings[name] = f"action failed: {type(e).__name__}"
            continue
        for _ in range(600):
            page.wait_for_timeout(100)
            last = page.evaluate("window.__gl.tLast")
            if last is not None and last > tz:
                timings[name] = round(last - tz)
                break
        page.wait_for_timeout(1500)
        page.screenshot(path=str(Path(a.shots) / f"{a.label}_r{rep}_{name}.png"))
    rss.running = False
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:6]
    row = dict(label=a.label, url=a.url, rep=rep, status=status, expect=a.expect, max_points_one_draw=gl["max"],
               draw_calls=gl["calls"], t_full_render_s=round(gl["tFull"] / 1000, 2) if gl["tFull"] else None,
               t_max_draw_s=round(gl["tMax"] / 1000, 2) if gl["tMax"] else None, redraw_ms=timings,
               js_heap_mb=round(heap / 2**20), cdp_js_heap_mb=round(m.get("JSHeapUsedSize", 0) / 2**20),
               renderer_rss_peak_mb=round(rss.peak["renderer"] / 2**20), gpu_rss_peak_mb=round(rss.peak["gpu"] / 2**20),
               net_total_mb=round(sum(sizes.values()) / 2**20, 1),
               net_top=[(u[-90:], round(b / 2**20, 2)) for u, b in top], gl_renderer=gl["glinfo"],
               browser=browser.version, wall_s=round(time.time() - t0, 1), shot=str(shot),
               date=time.strftime("%Y-%m-%d %H:%M"))
    browser.close()
    return row


# Malat1; the PanSci build indexes genes by Ensembl id only, not by symbol.
GENE_UCSC = "ENSMUSG00000092341"


def _ucsc_gene(page):
    page.get_by_text("Gene", exact=True).first.click(timeout=5000)
    box = page.locator("#tpGeneCombo-selectized")
    box.click()
    box.type(GENE_UCSC, delay=50)
    opt = page.locator(".selectize-dropdown.tpCombo").get_by_text(re.compile(GENE_UCSC)).first
    opt.wait_for(state="visible", timeout=20000)
    opt.click()


def _cxg_colorby(field):
    def f(page):
        page.locator(f"[data-testid='colorby-{field}']").first.click(timeout=20000)
    return f


SITE_ACTIONS = {
    "cxg": [
        ("zoom", lambda p: (p.mouse.move(700, 450), p.mouse.wheel(0, -600))),
        ("recolour_meta", _cxg_colorby("cell_type")),
    ],
    "ucsc": [
        ("zoom", lambda p: (p.mouse.move(700, 450), p.mouse.wheel(0, -600))),
        ("recolour_meta", lambda p: p.click("text=Organ name", timeout=5000)),
        ("recolour_gene", _ucsc_gene),
    ],
}


def performance_quiet(page, gl):
    return gl["tLast"] is not None and page.evaluate("performance.now()") - gl["tLast"] > 5000


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("url")
    ap.add_argument("--expect", type=int, default=0)
    ap.add_argument("--site", default="")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--out", default=str(Path(__file__).parent / "results.jsonl"))
    ap.add_argument("--shots", default=str(Path(__file__).parent / "shots"))
    a = ap.parse_args()
    Path(a.shots).mkdir(exist_ok=True)
    with sync_playwright() as pw:
        for rep in range(a.reps):
            row = one(pw, a, rep)
            print(json.dumps({k: v for k, v in row.items() if k not in ("net_top",)}), flush=True)
            with open(a.out, "a") as f:
                f.write(json.dumps(row) + "\n")
