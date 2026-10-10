import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import subprocess, time, urllib.request
from playwright.sync_api import sync_playwright
S=f"{_SCRATCH}"
OUT=f"{_REPO}/notes/comparison/screens/shinycell/"
srv = subprocess.Popen([f"{_DEMO_ROOT}/shinycell/start.sh"], stdout=open(S+"/shiny_srv.log","w"), stderr=subprocess.STDOUT)
def sel(p, id_, text):
    # same effect as picking the entry in the dropdown (selectize API; typing into the widget was not reliable headless)
    p.evaluate("([i,v])=>{const s=$('#'+i)[0].selectize; if(!s.options[v]) s.addOption({value:v,label:v}); s.setValue(v);}", [id_, text])
    p.wait_for_timeout(300)
def shot(p, name, sel_=None):
    if sel_: p.locator(sel_).first.screenshot(path=OUT+name, type="jpeg", quality=70)
    else: p.screenshot(path=OUT+name, type="jpeg", quality=70, full_page=True)
try:
    for _ in range(90):
        try: urllib.request.urlopen("http://127.0.0.1:8907", timeout=2); break
        except Exception: time.sleep(1)
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, channel="chromium")
        p = b.new_page(viewport={"width":1400,"height":900})
        p.goto("http://127.0.0.1:8907", timeout=60000); p.wait_for_timeout(8000)
        # tab 1: left = cell info, right = gene
        sel(p, "sc1a1inp1", "highres_celltype"); sel(p, "sc1a1inp2", "Mpo"); p.wait_for_timeout(6000)
        shot(p, "01_tab1_celltype_vs_Mpo.jpg")
        # check another tab's gene input is untouched
        p.click("a:has-text('GeneExpr vs GeneExpr')"); p.wait_for_timeout(5000)
        print("tab1:", p.eval_on_selector("#sc1a1inp1","e=>e.value"), p.eval_on_selector("#sc1a1inp2","e=>e.value")); print("tab3 genes:", p.eval_on_selector("#sc1a3inp1", "e=>e.value"), p.eval_on_selector("#sc1a3inp2", "e=>e.value"))
        shot(p, "02_tab3_genes_unchanged.jpg")
        p.click("a:has-text('CellInfo vs GeneExpr')"); p.wait_for_timeout(2000)
        # stored relation row as cell info
        sel(p, "sc1a1inp1", "diffusion_distance_to_4236"); p.wait_for_timeout(6000)
        # click a point in the left plot: does anything happen?
        img = p.locator("#sc1a1oup1 img").first
        bb = img.bounding_box(); print("img", bb)
        srcs = lambda: p.eval_on_selector_all("img", "els=>els.map(e=>e.src.length+':'+e.src.slice(-40))")
        before = srcs(); inputs_before = p.evaluate("()=>Object.keys(Shiny.shinyapp.$inputValues).length")
        img.click(position={"x": bb["width"]*0.5, "y": bb["height"]*0.5}); p.wait_for_timeout(4000)
        print("any image changed after click:", srcs() != before, "| new shiny inputs:", p.evaluate("()=>Object.keys(Shiny.shinyapp.$inputValues).length") - inputs_before)
        shot(p, "03_stored_row_4236_and_click.jpg")
        # subset toggle (per-plot)
        p.click("#sc1a1togL"); p.wait_for_timeout(1500)
        sel(p, "sc1a1sub1", "Age"); p.wait_for_timeout(2500)
        boxes = p.locator("#sc1a1sub1\\.ui input[type=checkbox]")
        print("subset boxes", boxes.count())
        if boxes.count() > 1: boxes.nth(0).uncheck(); p.wait_for_timeout(6000)
        p.click("a:has-text('GeneExpr vs GeneExpr')"); p.wait_for_timeout(1000)
        print("tab3 subset toggle count:", p.eval_on_selector("#sc1a3togL", "e=>e.getAttribute('data-val')"))
        p.click("a:has-text('CellInfo vs GeneExpr')"); p.wait_for_timeout(2000)
        shot(p, "04_subset_per_plot.jpg")
        b.close()
finally:
    subprocess.run([f"{_DEMO_ROOT}/shinycell/stop.sh"]); srv.terminate()
