"""TissUUmaps follow-up (raw capture): save a project in server mode (opened with ?path=. so the save target is
known), reopen the saved .tmap, then draw a rectangle region from the Regions tab. Server on 127.0.0.1:8908."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import json, os, sys, time
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
sys.path.insert(0, f"{_DEMO_ROOT}/_browser")
from record_json import record
from probe_web import INIT
from playwright.sync_api import sync_playwright
OUT = f"{_REPO}/notes/comparison/screens/tissuumaps/"
SW = "TissUUmaps 3.2.1.11 (server build, pip; TU4 is beta)"; BM = "bm_demo_csc.h5ad (8,090 cells x 16,285 genes)"
LOG = {}
def pv(c): return {"column": c, "mark": "?", "caption": "raw capture; verdict and caption pending review of the shot"}
def snap(p, name, cols, callouts):
    path = OUT + name; p.screenshot(path=path, type="jpeg", quality=72)
    try: record(p, path, tool="tissuumaps", software=SW, by="comparison-auditor", driver=__file__, data=BM, proves=[pv(c) for c in cols], callouts=callouts)
    except Exception as e:
        print("callout failed", str(e)[:120]); record(p, path, tool="tissuumaps", software=SW, by="comparison-auditor", driver=__file__, data=BM, proves=[pv(c) for c in cols], callouts=[])
    print("shot", name, flush=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    ctx = b.new_context(viewport={"width": 1400, "height": 900}); ctx.add_init_script(INIT)
    p = ctx.new_page(); p.set_default_timeout(15000)
    p.goto("http://127.0.0.1:8908/bm_demo_csc.h5ad?path=.", timeout=120000); time.sleep(8)
    p.locator("text=Categorical observations").locator("xpath=following::span[contains(@class,'select2-selection')][1]").first.click(); time.sleep(1)
    p.locator("li.select2-results__option", has_text="highres_celltype").first.click(); time.sleep(8)
    # regions: open the tab first (its UI is built there), then rectangle mode and a drag
    try:
        p.locator("#title-tab-regions").click(); time.sleep(2)
        p.evaluate("regionUtils.setMode('rectangle')"); time.sleep(1)
        box = p.locator(".openseadragon-container").first.bounding_box(); x0, y0, W, H = box["x"], box["y"], box["width"], box["height"]
        p.mouse.move(x0 + W * 0.30, y0 + H * 0.55); p.mouse.down(); p.mouse.move(x0 + W * 0.55, y0 + H * 0.85, steps=15); p.mouse.up(); time.sleep(3)
        p.evaluate("regionUtils.setMode(null)")
        LOG["n_regions"] = p.evaluate("Object.keys(regionUtils._regions||{}).length")
        LOG["regions_text"] = p.locator("#markers-regions-panel, .tab-pane.active").first.inner_text()[:1500]
        snap(p, "f01_regions_rectangle.jpg", ["annot", "selection"], [(1, ".openseadragon-container", "viewer with the drawn region"), (2, "#title-tab-regions", "Regions tab")])
    except Exception as e:
        LOG["regions_err"] = str(e)[:300]
    p.locator("#title-tab-markers").click(); time.sleep(1)
    # save project (server mode writes <name>.tmap under ?path)
    try:
        p.locator("#navbarDropdownMenuLink, #a_menubar_File").first.click(); time.sleep(1)
        p.get_by_text("Save project").first.click(); time.sleep(2)
        p.locator(".modal-dialog input[type=text]").last.fill("comparison_check"); time.sleep(0.5)
        p.locator(".modal-dialog button:has-text('Ok')").last.click(); time.sleep(4)
    except Exception as e:
        LOG["save_err"] = str(e)[:300]
    LOG["tmap_exists"] = os.path.exists(os.path.expanduser(f"{_DEMO_ROOT}/tissuumaps/data/comparison_check.tmap"))
    if LOG["tmap_exists"]:
        p2 = ctx.new_page()
        p2.goto("http://127.0.0.1:8908/comparison_check.tmap?path=.", timeout=120000); time.sleep(12)
        LOG["reopen_gl"] = p2.evaluate("window.__gl"); LOG["reopen_text"] = p2.locator("#markers-iss-gui").inner_text()[:800]
        snap(p2, "f02_share_project_reopened.jpg", ["share"], [(1, ".openseadragon-container", "reopened project"), (2, "#markers-iss-gui", "restored marker settings")])
    b.close()
print(json.dumps(LOG, default=str)[:3000])
