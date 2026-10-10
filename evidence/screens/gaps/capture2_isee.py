"""iSEE 2.18.0 (evidence-curator, 2026-10-04): h02 subset Y, "Restrict to selected columns". Starts
notes/comparison/demos/isee/focus_app.R on 127.0.0.1:8902, brushes plot 1 (UMAP), ticks Restrict in plot 2 (PCA), and
stops the app. Steps of notes/comparison/demos/ucsc-cell-browser/recap_portal_isee.py (shots 03, 04). Run under
notes/comparison/demos/scale_probe/gap_run.sh with benchmark/scale/ceiling/.venv/bin/python <this>.
"""
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capture2lib import SCRATCH, TODAY, log, pv, shot  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRV = "evidence/screens/gaps/capture2_isee.py"
IW = dict(software="iSEE 2.18.0 (Bioconductor 3.20)", driver=DRV, data="bm_demo_sce.rds (8,090 cells)", url="http://127.0.0.1:8902")
srv = subprocess.Popen(["$DEMO_ROOT/_mamba/envs/rtools/bin/Rscript", "notes/comparison/demos/isee/focus_app.R"],
                       stdout=open(SCRATCH + "isee_srv.log", "w"), stderr=subprocess.STDOUT)
try:
    for _ in range(120):
        try:
            urllib.request.urlopen("http://127.0.0.1:8902", timeout=2)
            break
        except Exception:
            time.sleep(1)
    log("isee up")
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, channel="chromium")
        p = b.new_page(viewport={"width": 1400, "height": 900})
        p.set_default_timeout(20000)
        p.goto("http://127.0.0.1:8902", timeout=120000)
        p.wait_for_timeout(22000)
        img = p.locator("#ReducedDimensionPlot1 img").first
        bb = img.bounding_box()
        log("rd1", bb)
        x0, y0 = bb["x"] + bb["width"] * 0.12, bb["y"] + bb["height"] * 0.25
        p.mouse.move(x0, y0)
        p.mouse.down()
        p.mouse.move(x0 + bb["width"] * 0.25, y0 + bb["height"] * 0.35, steps=12)
        p.mouse.up()
        p.wait_for_timeout(9000)
        p.check("#ReducedDimensionPlot2_ColumnSelectionRestrict")
        p.wait_for_timeout(8000)
        p.evaluate("window.scrollTo(0,60)")
        p.wait_for_timeout(500)
        shot(p, "isee", "h02_subset_restrict_to_selected.jpg",
             [pv("subset", "Y", f"iSEE 2.18.0 ({TODAY}): 'Restrict to selected columns' makes plot 2 show only the cells brushed in plot 1, a view-only subset (repeatable as gating)"),
              pv("selection", "Y", "the brush in plot 1 is the selection that plot 2 receives")],
             [(1, "#ReducedDimensionPlot1", "brush on plot 1 (UMAP)"), (2, "#ReducedDimensionPlot2", "plot 2 (PCA): only the brushed cells"),
              (3, "#ReducedDimensionPlot2_ColumnSelectionRestrict >> xpath=..", "Restrict to selected columns")], min_callouts=2, **IW)
        b.close()
finally:
    srv.terminate()
    try:
        srv.wait(timeout=20)
    except Exception:
        pass
    subprocess.run(["$DEMO_ROOT/isee/stop.sh"])
log("done")
