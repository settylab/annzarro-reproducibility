#!/usr/bin/env python
"""Does the regular path's heap grow with repeated subset swaps, and since when?

One server from WORKTREE on STORE, one Chromium. A Cell Plot opens on a
100,000-cell subset; then K times: subset BIG, subset 100,000. After every
swap, two forced GCs and the V8 heap (Runtime.getHeapUsage usedSize) and
ArrayBuffers. Version-agnostic: it waits on the cell count and the plot's
point count, not on anything newer than v0.2.0. The large-plot threshold is
set above BIG so every version draws the regular path.

Usage: swap_repeat.py WORKTREE STORE --big 4000000 --k 5 --out F.jsonl --tag T
"""
import argparse
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import envcapture  # noqa: E402

PY = "$ANNZARRO_SRC/.venv-test/bin/python"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("worktree")
    ap.add_argument("store")
    ap.add_argument("--big", type=int, default=4_000_000)
    ap.add_argument("--small", type=int, default=100_000)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    if not os.environ.get("MEMGUARD_DEV"):
        envcapture.require_clean_bench()
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    home = Path(tempfile.mkdtemp(prefix="swap_"))
    (home / "c.yaml").write_text(f"ui:\n  defaults:\n    large_plot_points: {a.big * 10}\n  memory:\n    enforce: \"off\"\n")
    srv = subprocess.Popen([PY, "-m", "annzarro.cli", "start", "--config", str(home / "c.yaml"), "--host", "127.0.0.1",
                            "--port", str(port), "--data-dir", str(Path(a.store).parent), "--no-browser", "--auth-disabled"],
                           env=dict(os.environ, ANNZARRO_HOME=str(home), ANNZARRO_HEADLESS="1", PYTHONPATH=a.worktree),
                           cwd=a.worktree, stdout=open(home / "server.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    root = f"http://127.0.0.1:{port}"
    for _ in range(240):
        try:
            urllib.request.urlopen(root + "/api/v1/config", timeout=1)
            break
        except OSError:
            time.sleep(0.25)
    commit = subprocess.run(["git", "-C", a.worktree, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    x = {"type": "obsm", "key": "X_umap", "column": "0"}
    y = {"type": "obsm", "key": "X_umap", "column": "1"}
    cfg = {"cell-plot-A": {"id": "cell-plot-A", "x": x, "y": y, "z": None, "color": {"type": "obs", "key": "cell_line_id", "column": ""}}}
    view = {"v": 1, "subset": {"n": a.small, "seed": 0},
            "layout": {"v": 1, "hierarchy": [{"type": "tile", "id": "cell-plot-A", "controlsVisible": False}],
                       "controlState": {"cell-plot-A": False}, "panelConfigs": cfg}}
    link = f"{root}/?dataset_path={a.store}#view=" + base64.urlsafe_b64encode(json.dumps(view).encode()).decode().rstrip("=")
    out = open(a.out, "a")
    state_js = """async () => {
        const { DataManager } = await import('/static/js/data-manager.js');
        const cells = DataManager.getCells();
        const gd = document.querySelector('.js-plotly-plot');
        const pts = gd && gd.data ? gd.data.reduce((s, t) => s + ((t.x && t.x.length) || 0), 0) : 0;
        const busy = [...document.querySelectorAll('.loading-overlay, .spinner-border')].filter(e => e.offsetParent !== null).length;
        return { cells: cells ? cells.length : 0, pts, busy };
    }"""

    def drawn(page, n, limit=600):
        last, same, t0 = None, 0, time.time()
        while time.time() - t0 < limit:
            st = page.evaluate(state_js)
            ok = st["cells"] == n and st["pts"] > 0 and not st["busy"]
            same = same + 1 if ok and st == last else 0
            last = st
            if same >= 3:
                return st
            time.sleep(0.5)
        raise TimeoutError(f"not drawn at {n}: {last}")

    def subset(page, n):
        page.click("#subset-button")
        page.wait_for_selector("#subset-apply", state="visible")
        if not page.is_checked("#subset-enabled"):
            page.click("#subset-enabled")
        if page.is_checked("#subset-n-all"):
            page.click("#subset-n-all")
        page.fill("#subset-n", str(n))
        page.wait_for_function("() => !document.getElementById('subset-apply').disabled")
        page.click("#subset-apply")
        page.wait_for_selector("#subset-modal", state="hidden")
        time.sleep(1)
        return drawn(page, n)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--enable-precise-memory-info"])
            envcapture.record(a.out, python=PY, server_root=root,
                              browser={"channel": "bundled", "version": browser.version, "headless": True},
                              worktree=a.worktree, commit=commit, store=a.store, big=a.big, k=a.k, tag=a.tag)
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            cdp = page.context.new_cdp_session(page)

            def heap():
                for _ in range(2):
                    cdp.send("HeapProfiler.collectGarbage")
                h = cdp.send("Runtime.getHeapUsage")
                return h["usedSize"], h.get("backingStorageSize")

            page.goto(link)
            drawn(page, a.small)
            steps = [("open", a.small)] + [s for i in range(a.k) for s in (("big", a.big), ("small", a.small))]
            for i, (name, n) in enumerate(steps):
                if i:
                    subset(page, n)
                used, backing = heap()
                rec = {"tag": a.tag, "commit": commit, "store": Path(a.store).name, "step": i, "name": name, "n": n,
                       "heap": used, "backing": backing}
                out.write(json.dumps(rec) + "\n")
                out.flush()
                print(json.dumps({k: rec[k] for k in ("step", "name", "n")}), round(used / 1e6), "MB heap", round((backing or 0) / 1e6), "MB AB", flush=True)
            browser.close()
    finally:
        os.killpg(srv.pid, 15)


if __name__ == "__main__":
    main()
