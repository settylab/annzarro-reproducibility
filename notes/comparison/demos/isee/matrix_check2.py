"""iSEE follow-up: relaunch from the saved state file (brush on plot 1 included) and capture the
DynamicMarkerTable, then brush a new region live and watch whether the table updates."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import subprocess, time, urllib.request
from playwright.sync_api import sync_playwright
S = f"{_SCRATCH}/isee_matrix"
OUT = f"{_REPO}/notes/comparison/screens/isee/"
srv = subprocess.Popen([f"{_DEMO_ROOT}/_mamba/envs/rtools/bin/Rscript",
    f"{_REPO}/notes/comparison/demos/isee/matrix_app.R", "restore", S + "/iSEE_memory.rds"],
    stdout=open(S + "/srv_restore2.log", "w"), stderr=subprocess.STDOUT)
def box(p, sel): return p.locator(sel).locator("xpath=ancestor::div[contains(@class,'box')][1]").first
def rows(p):
    r = p.locator("#DynamicMarkerTable1 tbody tr"); return [r.nth(i).inner_text().replace("\t", " ")[:70] for i in range(min(r.count(), 3))]
try:
    for _ in range(120):
        try: urllib.request.urlopen("http://127.0.0.1:8902", timeout=2); break
        except Exception: time.sleep(1)
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, channel="chromium"); p = b.new_page(viewport={"width": 1400, "height": 900})
        t0 = time.time(); p.goto("http://127.0.0.1:8902", timeout=120000)
        for _ in range(60):
            p.wait_for_timeout(2000)
            if rows(p) and "No data" not in rows(p)[0]: break
        print(f"restored DMT after {time.time()-t0:.0f}s:", rows(p), p.inner_text("#DynamicMarkerTable1 .dataTables_info")[:80])
        box(p, "#DynamicMarkerTable1").screenshot(path=OUT + "m10_dynamic_marker_table_filled.jpg", type="jpeg", quality=70)
        # live: brush a different region (right-hand neutrophil arm) and time the table update
        p.evaluate("window.scrollTo(0,0)"); img = p.locator("#ReducedDimensionPlot1 img").first; bb = img.bounding_box()
        x0, y0 = bb["x"] + bb["width"] * 0.45, bb["y"] + bb["height"] * 0.05
        p.mouse.move(x0, y0); p.mouse.down(); p.mouse.move(x0 + bb["width"] * 0.45, y0 + bb["height"] * 0.3, steps=12); p.mouse.up()
        before = rows(p); t0 = time.time(); changed = False
        for _ in range(90):
            p.wait_for_timeout(2000)
            if rows(p) != before and rows(p) and "No data" not in rows(p)[0]: changed = True; break
        print(f"live re-brush: table changed={changed} after {time.time()-t0:.0f}s:", rows(p))
        box(p, "#DynamicMarkerTable1").screenshot(path=OUT + "m10_dynamic_marker_table_after_rebrush.jpg", type="jpeg", quality=70)
        b.close()
finally:
    srv.terminate(); srv.wait(timeout=20); subprocess.run([f"{_DEMO_ROOT}/isee/stop.sh"])
