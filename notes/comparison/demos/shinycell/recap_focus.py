"""Re-capture of ShinyCell focus shots 01-04 (focus_check.py) with dom sidecars. The originals were full-page shots; here the
viewport is grown to the page height first, so the image is the same full page and DOM boxes stay inside the viewport.
Run: notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python <this>"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import subprocess, time, urllib.request, sys
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
import recap
from recap import pv
from playwright.sync_api import sync_playwright
DRV = "notes/comparison/demos/shinycell/recap_focus.py"
SW = "ShinyCell 2.1.0 (local Shiny app built by build.R)"; DATA = "bm_demo_sce.rds (8,090 cells)"
srv = subprocess.Popen([f"{_DEMO_ROOT}/shinycell/start.sh"], stdout=open("/tmp/shiny_recap.log", "w"), stderr=subprocess.STDOUT)
def sel(p, id_, text):
    p.evaluate("([i,v])=>{const s=$('#'+i)[0].selectize; if(!s.options[v]) s.addOption({value:v,label:v}); s.setValue(v);}", [id_, text]); p.wait_for_timeout(300)
def C(i): return f"#{i} + .selectize-control"
def shot(p, name, proves, callouts):
    h = p.evaluate("()=>document.documentElement.scrollHeight"); p.set_viewport_size({"width": 1400, "height": max(900, h)}); p.wait_for_timeout(800)
    recap.snap(p, "shinycell", name, proves, callouts, software=SW, driver=DRV, data=DATA, url="http://127.0.0.1:8907")
    p.set_viewport_size({"width": 1400, "height": 900})
try:
    for _ in range(90):
        try: urllib.request.urlopen("http://127.0.0.1:8907", timeout=2); break
        except Exception: time.sleep(1)
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, channel="chromium")
        p = b.new_page(viewport={"width": 1400, "height": 900}); p.set_default_timeout(20000)
        p.goto("http://127.0.0.1:8907", timeout=60000); p.wait_for_timeout(8000)
        sel(p, "sc1a1inp1", "highres_celltype"); sel(p, "sc1a1inp2", "Mpo"); p.wait_for_timeout(6000)
        shot(p, "01_tab1_celltype_vs_Mpo.jpg", [pv("focus", "N", "Feature colouring stays in one plot: Gene name = Mpo recolours only the right-hand plot; the left keeps highres_celltype")],
             [(1, C("sc1a1inp2"), "Gene name: Mpo"), (2, "#sc1a1oup2 img", "only this plot shows Mpo"), (3, "#sc1a1oup1 img", "left plot keeps cell information")])
        p.click("a:has-text('GeneExpr vs GeneExpr')"); p.wait_for_timeout(5000)
        print("tab3 genes:", p.eval_on_selector("#sc1a3inp1", "e=>e.value"), p.eval_on_selector("#sc1a3inp2", "e=>e.value"))
        shot(p, "02_tab3_genes_unchanged.jpg", [pv("focus", "N", "Other tabs keep their own gene inputs (GeneExpr vs GeneExpr still Mrpl15 / Lypla1)")],
             [(1, C("sc1a3inp1"), "gene 1 unchanged"), (2, C("sc1a3inp2"), "gene 2 unchanged")])
        p.click("a:has-text('CellInfo vs GeneExpr')"); p.wait_for_timeout(2000)
        sel(p, "sc1a1inp1", "diffusion_distance_to_4236"); p.wait_for_timeout(6000)
        img = p.locator("#sc1a1oup1 img").first; bb = img.bounding_box()
        srcs = lambda: p.eval_on_selector_all("img", "els=>els.map(e=>e.src.length+':'+e.src.slice(-40))")
        before = srcs(); n0 = p.evaluate("()=>Object.keys(Shiny.shinyapp.$inputValues).length")
        img.click(position={"x": bb["width"] * 0.5, "y": bb["height"] * 0.5}); p.wait_for_timeout(4000)
        print("image changed after click:", srcs() != before, "| new inputs:", p.evaluate("()=>Object.keys(Shiny.shinyapp.$inputValues).length") - n0)
        shot(p, "03_stored_row_4236_and_click.jpg", [pv("focus", "N", "Only a precomputed colData column fixed to cell 4236 can be shown; no cell can be picked, and a click on the plot does nothing")],
             [(1, C("sc1a1inp1"), "Cell information: diffusion_distance_to_4236"), (2, "#sc1a1oup1 img", "static PNG, click had no effect")])
        p.click("#sc1a1togL"); p.wait_for_timeout(1500)
        sel(p, "sc1a1sub1", "Age"); p.wait_for_timeout(2500)
        boxes = p.locator("#sc1a1sub1\\.ui input[type=checkbox]"); print("subset boxes", boxes.count())
        if boxes.count() > 1: boxes.nth(0).uncheck(); p.wait_for_timeout(6000)
        p.click("a:has-text('GeneExpr vs GeneExpr')"); p.wait_for_timeout(1000)
        p.click("a:has-text('CellInfo vs GeneExpr')"); p.wait_for_timeout(2000)
        shot(p, "04_subset_per_plot.jpg", [pv("selection", "N", "No selection in any plot; the only cell-set control is a per-tab subset form (Age, Mid unticked)"), pv("filters", "N", "Subset form filters one tab's two plots; no table filter")],
             [(1, "#sc1a1sub1\\.ui", "subset checkboxes (per tab)"), (2, "#sc1a1oup1 img", "left plot subset"), (3, "#sc1a1oup2 img", "right plot subset")])
        b.close()
finally:
    subprocess.run([f"{_DEMO_ROOT}/shinycell/stop.sh"]); srv.terminate()
