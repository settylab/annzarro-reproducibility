"""Shared driver for the focus/selection checks: starts $DEMO_ROOT/<tool>/start.sh, runs steps(page) from a script, stops the server.
Run under the bench lock: /usr/bin/lockf -k ~/.annzarro-bench.lock <venv python> _focus_run.py <tool|none> <port> <steps.py>"""
# usage: run.py <tool|none> <port> <steps.py> ; starts server, runs steps(page, S), stops server
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[3])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import sys, subprocess, time, urllib.request, os, runpy, traceback
from playwright.sync_api import sync_playwright
tool, port, steps = sys.argv[1], sys.argv[2], sys.argv[3]
C = os.path.expanduser(f"{_DEMO_ROOT}")
proc = None
if tool != "none":
    proc = subprocess.Popen([f"{C}/{tool}/start.sh"], stdout=open(f"/tmp/focus_{tool}.log","w"), stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < 120:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2); break
        except Exception: time.sleep(1)
    print("server up after", round(time.time()-t0,1), "s")
S = f"{_REPO}/notes/comparison/screens/"
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, channel="chromium")
        ctx = b.new_context(viewport={"width":1400,"height":900})
        page = ctx.new_page()
        page.set_default_timeout(20000)
        ns = runpy.run_path(steps)
        try:
            ns["steps"](page, S)
        except Exception:
            traceback.print_exc()
            page.screenshot(path="/tmp/focus_err.jpg", type="jpeg", quality=60)
        b.close()
finally:
    if proc:
        subprocess.run([f"{C}/{tool}/stop.sh"]); proc.wait(timeout=20)
