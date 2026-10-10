#!/usr/bin/env python
"""Recolour an every-cell plot at the memory edge, with the guard on.

One run: one annzarro server (WORKTREE, default settings unless --enforce),
one Chromium (bundled, new headless, --trace-gc through a pty as measure.py),
a Cell Plot of every cell coloured by GENE, then K times: colour by CAT, colour
by GENE (each a full redraw in large-plot mode). Per step one JSON line:
verdict (drawn | refused | crash | timeout), the guard's refusal text if any,
the V8 heap peak (largest GC "before" size during the step), on-heap and
ArrayBuffers after two forced GCs (CDP Runtime.getHeapUsage), renderer RSS
peak, and the user's Chrome / other agents' processes beside it.

Usage: recolour_edge.py STORE --worktree WT --gene G --cat C --k 5 --out F --tag T [--enforce off]
"""
import argparse
import base64
import json
import os
import pty
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import envcapture  # noqa: E402
from measure import GcLog, Sampler, free_port, other_load, user_chrome  # noqa: E402

PY = "$ANNZARRO_SRC/.venv-test/bin/python"

STATE = """async (id) => {
    const g = await import('/static/js/utils/memory-guard-ui.js');
    const tile = document.querySelector(`.tile[data-tile-id="${id}"]`);
    const tag = tile && tile.querySelector('.ps-tag[data-tag="memory"]');
    const ph = tile && tile.querySelector('.coverage-placeholder');
    const e = g.ledger.get(id);
    return { committed: !!e && !g.ledger.pending.has(id), n: e ? e.n : 0, colour: e ? e.colour : null,
             refusal: tag ? tag.getAttribute('title') : (ph ? ph.innerText.slice(0, 300) : null) };
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("store")
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--gene", required=True)
    ap.add_argument("--cat", required=True)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--enforce", default=None)
    ap.add_argument("--limit", type=float, default=900)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    if not os.environ.get("MEMGUARD_DEV"):
        envcapture.require_clean_bench()
    work = Path(tempfile.mkdtemp(prefix="recolour_"))
    cfg = f"ui:\n  memory:\n    enforce: \"{a.enforce}\"\n" if a.enforce else "ui: {}\n"
    (work / "c.yaml").write_text(cfg)
    port = free_port()
    srv = subprocess.Popen([PY, "-m", "annzarro.cli", "start", "--config", str(work / "c.yaml"), "--host", "127.0.0.1",
                            "--port", str(port), "--data-dir", str(Path(a.store).parent), "--no-browser", "--auth-disabled"],
                           env=dict(os.environ, ANNZARRO_HOME=str(work), ANNZARRO_HEADLESS="1", PYTHONPATH=a.worktree),
                           cwd=a.worktree, stdout=open(work / "server.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    root = f"http://127.0.0.1:{port}"
    for _ in range(240):
        try:
            urllib.request.urlopen(root + "/api/v1/config", timeout=1)
            break
        except OSError:
            time.sleep(0.25)
    commit = subprocess.run(["git", "-C", a.worktree, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    gene = {"type": "layer", "key": "X", "column": a.gene, "locked": False}
    cat = {"type": "obs", "key": a.cat, "column": ""}
    view = {"v": 1, "subset": None, "constants": {"focusedGene": a.gene},
            "layout": {"v": 1, "hierarchy": [], "controlState": {}, "panelConfigs": {}}}
    link = f"{root}/?dataset_path={a.store}#view=" + base64.urlsafe_b64encode(json.dumps(view).encode()).decode().rstrip("=")
    out = open(a.out, "a")
    base = {"tag": a.tag, "store": Path(a.store).name, "commit": commit, "enforce": a.enforce or "default"}
    t_start = time.time()
    with sync_playwright() as pw:
        cdp_port = free_port()
        master, slave = pty.openpty()
        flags = ["--headless=new", f"--remote-debugging-port={cdp_port}", f"--user-data-dir={work / 'profile'}",
                 "--no-first-run", "--no-default-browser-check", "--enable-precise-memory-info",
                 "--js-flags=--trace-gc", "--enable-unsafe-swiftshader", "about:blank"]
        chrome = subprocess.Popen([pw.chromium.executable_path, *flags], stdout=slave, stderr=slave, start_new_session=True)
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
        envcapture.record(a.out, python=PY, server_root=root,
                          browser={"channel": "bundled", "version": browser.version, "flags": flags, "headless": True},
                          store=a.store, worktree=a.worktree, commit=commit, k=a.k, tag=a.tag, enforce=a.enforce)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_viewport_size({"width": 1400, "height": 900})
        crashed = {"v": False}
        page.on("crash", lambda *_: crashed.__setitem__("v", True))
        cdp = ctx.new_cdp_session(page)
        sampler = Sampler(chrome.pid)
        sampler.start()

        def after():
            for _ in range(2):
                cdp.send("HeapProfiler.collectGarbage")
            h = cdp.send("Runtime.getHeapUsage")
            return {"heap": h.get("usedSize"), "backing": h.get("backingStorageSize")}

        def settle(colour_key, limit):
            t0 = time.time()
            while time.time() - t0 < limit:
                if crashed["v"]:
                    return "crash", None
                st = page.evaluate(STATE, "cell-plot-A")
                if st["refusal"]:
                    return "refused", st["refusal"]
                if st["committed"] and st["colour"] == colour_key:
                    return "drawn", None
                time.sleep(0.25)
            return "timeout", None

        def step(name, action, colour_key):
            sampler.reset()
            t0 = time.time()
            rec = {**base, "step": name, "user_chrome": user_chrome(), "other_load": other_load(chrome.pid)}
            try:
                action()
                verdict, refusal = settle(colour_key, a.limit)
            except Exception as e:      # noqa: BLE001
                verdict, refusal = ("crash" if crashed["v"] else "error"), str(e)[:200]
            t1 = time.time()
            rec.update(verdict=verdict, refusal=refusal, seconds=round(t1 - t0, 2), heap_peak=gclog.peak(t0, t1),
                       renderer_peak=sampler.peak["renderer"], gpu_peak=sampler.peak["gpu"],
                       gc_last=gclog.events[-3:] if gclog.events else None)
            if verdict != "drawn":
                # Chromium's own words about the crash (V8 OOM, GPU, renderer)
                time.sleep(2)
                try:
                    rec["chrome_tail"] = Path(work / "chrome.log").read_text().splitlines()[-25:]
                except OSError:
                    rec["chrome_tail"] = None
            if verdict == "drawn":
                rec["after"] = after()
                try:
                    rec["after"]["contexts"] = page.evaluate(
                        "async () => (await import('/static/js/utils/release-plot.js')).liveWebglContexts()")
                except Exception:      # noqa: BLE001
                    pass
                rec["after"].update({"renderer": sampler.current()["renderer"], "gpu": sampler.current()["gpu"]})
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(json.dumps({k: rec.get(k) for k in ("step", "verdict", "seconds", "heap_peak", "refusal")}),
                  round((rec.get("after") or {}).get("heap", 0) / 1e9, 3), flush=True)
            return verdict

        page.goto(link)
        names_js = """async () => { const { DataManager } = await import('/static/js/data-manager.js');
            const c = DataManager.getCells(); return DataManager.isDatasetLoaded() && c ? c.length : 0; }"""
        stable = 0
        while stable < 4:
            stable = stable + 1 if page.evaluate(names_js) > 0 else 0
            time.sleep(0.25)
        cfg = {"id": "cell-plot-A", "title": "A", "x": {"type": "obsm", "key": "X_umap", "column": "0"},
               "y": {"type": "obsm", "key": "X_umap", "column": "1"}, "z": None, "color": gene}
        ok = step("draw", lambda: page.evaluate("c => { window.PanelManager.createPanelInLayout('cell-plot', c); }", cfg),
                  "numeric") == "drawn"
        for i in range(a.k if ok else 0):
            for key, col, kind in (("cat", cat, "categorical"), ("gene", gene, "numeric")):
                v = step(f"recolour{i + 1}:{key}", lambda col=col: page.evaluate("""async (c) => {
                    const p = window.PanelManager.getPanel('cell-plot-A');
                    p.setConfig({ color: c });
                    p.refreshPlot();
                }""", col), kind)
                if v != "drawn":
                    ok = False
                    break
            if not ok:
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
    print("total", round(time.time() - t_start), "s")


if __name__ == "__main__":
    main()
