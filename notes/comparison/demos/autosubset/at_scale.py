"""auto_subset at scale (raw capture): open the largest hosted demo of a tool and count the points actually drawn
(WebGL draw-call hook from $DEMO_ROOT/_browser/probe_web.py). argv: vitessce | scope."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import json, sys, time
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin"); sys.path.insert(0, f"{_DEMO_ROOT}/_browser")
from record_json import record
from probe_web import INIT
from playwright.sync_api import sync_playwright
which = sys.argv[1]
CFG = {"vitessce": dict(url="https://vitessce.io/#?dataset=salcher-2022", sw="Vitessce (vitessce.io hosted app)", data="Salcher et al. 2022 LuCA, 1,283,972 cells (vitessce.io demo)", wait=240, headless=True),
       "scope": dict(url="https://scope.aertslab.org/#/FlyCellAtlas/*/welcome", sw="SCope 1.8.2 (scope.aertslab.org)", data="Fly Cell Atlas (scope.aertslab.org)", wait=240, headless=False)}[which]
def pv(c): return {"column": c, "mark": "?", "caption": "raw capture; verdict and caption pending review of the shot"}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=CFG["headless"], channel="chromium")
    ctx = b.new_context(viewport={"width": 1400, "height": 900}); ctx.add_init_script(INIT)
    p = ctx.new_page()
    p.goto(CFG["url"], timeout=120000)
    t0 = time.time(); last = -1
    while time.time() - t0 < CFG["wait"]:
        g = p.evaluate("window.__gl"); time.sleep(5)
        if g["max"] and g["max"] == last and time.time() - t0 > 60: break
        last = g["max"]
    g = p.evaluate("window.__gl"); print(which, json.dumps(g), round(time.time() - t0), flush=True)
    path = f"{_REPO}/notes/comparison/screens/{which}/s_auto_subset_at_scale.jpg"
    p.screenshot(path=path, type="jpeg", quality=72)
    record(p, path, tool=which, software=CFG["sw"], by="comparison-auditor", driver=__file__, data=CFG["data"], proves=[pv("auto_subset"), pv("every_cell")], callouts=[(1, "canvas >> nth=0", "embedding")])
    b.close()
