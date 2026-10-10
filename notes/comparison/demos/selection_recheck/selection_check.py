"""Re-check the proposed 'selection cross-filters linked views' marks for Kana and SCope (2026-10-04).
Kana: copy the UMAP to the gallery, switch the main view to another embedding, lasso there, and see whether
the saved gallery plot greys out the unselected cells (source: Gallery/index.js passes selectedPoints to
uDimPlot.js, which greys non-selected cells, kana ecb0360). Headless, live build.
SCope: headed Chromium (its WebGL viewer does not draw headless), Regulon page with three viewers; lasso in one
viewer and see whether the others show the selection (source: Viewer.jsx repaintLassoSelections).
Shots + sidecars into notes/comparison/screens/<tool>/s_sel_*.jpg."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import os, sys, time
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
SCR = f"{_REPO}/notes/comparison/screens/"
BM = os.path.expanduser(f"{_DEMO_ROOT}/_data/bm_demo.h5ad")
def pv(c, m=None, t=None):
    # Raw capture only: the mark and caption are written after the shot has been looked at (coordinator's rule,
    # 2026-10-04); this records just which column the shot is meant to inform.
    return {"column": c, "mark": "?", "caption": "raw capture; verdict and caption pending review of the shot"}
def snap(p, tool, name, sw, data, proves, callouts):
    path = SCR + f"{tool}/{name}"; p.screenshot(path=path, type="jpeg", quality=70)
    try: record(p, path, tool=tool, software=sw, by="comparison-auditor", driver=__file__, data=data, proves=proves, callouts=callouts)
    except Exception as e:
        print("callout failed", str(e)[:120]); record(p, path, tool=tool, software=sw, by="comparison-auditor", driver=__file__, data=data, proves=proves, callouts=[])
    print("shot", tool, name, flush=True)
def lasso(p, canvas, pts):
    box = canvas.bounding_box(); x0, y0, W, H = box["x"], box["y"], box["width"], box["height"]
    p.mouse.move(x0 + W * pts[0][0], y0 + H * pts[0][1]); p.mouse.down()
    for fx, fy in pts[1:]: p.mouse.move(x0 + W * fx, y0 + H * fy, steps=12)
    p.mouse.up()
which = sys.argv[1] if len(sys.argv) > 1 else "both"
print("start", which, flush=True)
with sync_playwright() as pw:
    if which in ("both", "kana"):
        SW = "Kana v3.2.0 (live build, kanaverse.org)"; DATA = "bm_demo.h5ad (8,090 cells)"
        b = pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        p = b.new_context(viewport={"width": 1800, "height": 950}).new_page()
        p.goto("https://www.kanaverse.org/kana/", timeout=120000); time.sleep(4)
        p.get_by_text("I want to explore existing analysis results").click(); time.sleep(3)
        p.locator("input[type=file]").first.set_input_files(BM); time.sleep(8)
        p.get_by_role("button", name="Explore", exact=True).first.click()
        p.get_by_text("Copy to gallery").first.wait_for(timeout=180000); time.sleep(5)
        try:
            p.get_by_text("Copy to gallery").first.click(timeout=8000); time.sleep(3)
        except Exception as e:
            print("copy-to-gallery failed", str(e)[:150])
        tabs = p.locator("text=/X_draw_graph_fa|draw_graph/").all_inner_texts(); print("embedding tabs", tabs[:4])
        try:
            p.get_by_text("X_draw_graph_fa", exact=True).first.click(timeout=8000); time.sleep(5)
        except Exception as e:
            print("switch embedding failed", str(e)[:150])
        snap(p, "kana", "s_sel_gallery_before_lasso.jpg", SW, DATA, [pv("selection")], [])
        p.get_by_role("button", name="Selection").first.evaluate("e=>e.click()"); time.sleep(1)
        lasso(p, p.locator("canvas").first, [(0.10, 0.55), (0.35, 0.55), (0.35, 0.95), (0.10, 0.95), (0.10, 0.55)]); time.sleep(5)
        print("SELTXT", p.locator("text=/cells selected/").all_inner_texts()[:3])
        snap(p, "kana", "s_sel_gallery_after_lasso.jpg", SW, DATA,
             [pv("selection")],
             [(1, "canvas >> nth=0", "lasso on the main embedding"), (2, "canvas >> nth=-1", "gallery copy")])
        b.close()
    if which in ("both", "scope"):
        SW = "SCope 1.8.2 (scope.aertslab.org)"; DATA = "Wouters_Human_Melanoma / 10_Baselines_filteredRegulons.loom (4,322 cells)"
        BASE = "https://scope.aertslab.org/#/Wouters_Human_Melanoma/Wouters_Human_Melanoma%2F10_Baselines_filteredRegulons.loom/"
        b = pw.chromium.launch(headless=False, channel="chromium")
        p = b.new_context(viewport={"width": 1400, "height": 900}).new_page()
        p.goto(BASE + "regulon", timeout=90000); time.sleep(10)
        try: p.get_by_text("I decline").first.click(timeout=3000)
        except Exception: pass
        t = time.time()
        while time.time() - t < 150 and p.locator(".ui.loader:visible").count(): time.sleep(2)
        print("loaders left", p.locator(".ui.loader:visible").count(), "after", round(time.time() - t), "s", flush=True)
        try:
            srch = p.locator("input[placeholder='Search...']").first; srch.click(); srch.type("MITF", delay=80); time.sleep(4)
            p.locator(".results .result").filter(has_text="MITF").first.click(); time.sleep(15)
        except Exception as e:
            print("gene pick failed", str(e)[:120])
        time.sleep(3)
        try:
            p.locator("[title='Lasso Tool']").first.click(timeout=8000); time.sleep(1)
        except Exception as e:
            print("lasso tool failed", str(e)[:150])
        cv = p.locator("canvas").first
        lasso(p, cv, [(0.30, 0.30), (0.70, 0.30), (0.70, 0.70), (0.30, 0.70), (0.30, 0.30)]); time.sleep(5)
        print("canvases", p.locator("canvas").count(), "selection text", p.locator("text=/[Ss]election/").all_inner_texts()[:4])
        snap(p, "scope", "s_sel_lasso_all_viewers.jpg", SW, DATA,
             [pv("selection")],
             [(1, "canvas >> nth=0", "lasso drawn here"), (2, "canvas >> nth=1", "second viewer")])
        b.close()
