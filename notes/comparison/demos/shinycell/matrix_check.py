"""ShinyCell matrix-mark screenshots. Run under gap_run.sh with the playwright venv.
Local app (ShinyCell 2.1.0 on bm_demo, port 8907) plus the online ShinyCell2 showcase for spatial/image."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import subprocess, time, urllib.request, os
from playwright.sync_api import sync_playwright
S = f"{_SCRATCH}/shinycell_matrix"
os.makedirs(S, exist_ok=True)
OUT = f"{_REPO}/notes/comparison/screens/shinycell/"
URL = "http://127.0.0.1:8907"

def jpg(t, name, **kw):
    t.screenshot(path=OUT + name, type="jpeg", quality=70, **kw); print("saved", name)
def sel(p, id_, v):
    p.evaluate("([i,v])=>{const s=$('#'+i)[0].selectize; if(!s.options[v]) s.addOption({value:v,label:v}); s.setValue(v);}", [id_, v]); p.wait_for_timeout(300)
def opts(p, id_):
    return p.evaluate(f"()=>{{const s=$('#{id_}')[0]; return s&&s.selectize?Object.keys(s.selectize.options):null}}")

srv = subprocess.Popen([f"{_DEMO_ROOT}/shinycell/start.sh"], stdout=open(S + "/srv.log", "w"), stderr=subprocess.STDOUT)
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    ctx = b.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True)
    p = ctx.new_page()
    try:
        for _ in range(90):
            try: urllib.request.urlopen(URL, timeout=2); break
            except Exception: time.sleep(1)
        p.goto(URL, timeout=60000); p.wait_for_timeout(9000)
        sel(p, "sc1a1inp1", "highres_celltype"); sel(p, "sc1a1inp2", "Mpo"); p.wait_for_timeout(7000)
        jpg(p, "m00_plots_render.jpg")
        url0 = p.url
        # columns 1, 2, 4: what the dropdowns offer
        print("dimred X options:", opts(p, "sc1a1drX"))
        print("cell information options:", opts(p, "sc1a1inp1"))
        p.evaluate("()=>$('#sc1a1drX')[0].selectize.open()"); p.wait_for_timeout(700)
        jpg(p, "m04_slots_dimred_dropdown.jpg", clip={"x": 0, "y": 0, "width": 1400, "height": 520})
        p.evaluate("()=>$('#sc1a1drX')[0].selectize.close()")
        p.evaluate("()=>{const s=$('#sc1a1inp1')[0].selectize; s.open()}"); p.wait_for_timeout(700)
        p.locator("#sc1a1inp1").locator("xpath=..").scroll_into_view_if_needed()
        jpg(p, "m04_slots_cellinfo_dropdown.jpg")
        p.evaluate("()=>$('#sc1a1inp1')[0].selectize.close()")
        # column 12: does the URL ever carry state?
        p.click("a:has-text('GeneExpr vs GeneExpr')"); p.wait_for_timeout(3000)
        print("url before/after changing inputs and tab:", url0, p.url)
        print("bookmark/share controls:", p.locator("text=/bookmark|share|copy link/i").count())
        p.click("a:has-text('CellInfo vs GeneExpr')"); p.wait_for_timeout(2000)
        # column 10: violin/box tab controls (no DE ranking in ShinyCell 1)
        p.click("a:has-text('Violinplot / Boxplot')"); p.wait_for_timeout(6000)
        print("violin tab inputs:", p.eval_on_selector_all(".tab-pane.active label", "els=>els.map(e=>e.textContent.trim()).filter(t=>t).slice(0,30)"))
        jpg(p, "m10_violin_tab_no_de.jpg")
        p.click("a:has-text('CellInfo vs GeneExpr')"); p.wait_for_timeout(3000)
        # column 13: Download PDF / PNG under the gene plot
        p.locator("#sc1a1oup2\\.pdf").scroll_into_view_if_needed(); p.wait_for_timeout(500)
        jpg(p, "m13_download_buttons.jpg")
        for bid in ["sc1a1oup2.pdf", "sc1a1oup2.png"]:
            with p.expect_download(timeout=120000) as dl:
                p.click("#" + bid.replace(".", "\\."))
            d = dl.value; f = f"{S}/{d.suggested_filename}"; d.save_as(f)
            print("download:", bid, "->", d.suggested_filename, os.path.getsize(f), "bytes")
    finally:
        subprocess.run([f"{_DEMO_ROOT}/shinycell/stop.sh"]); srv.terminate()
    p.wait_for_timeout(4000)
    jpg(p, "m16_server_stopped_page_greys_out.jpg")
    print("disconnected overlay:", p.locator("#shiny-disconnected-overlay").count())
    # ---------------- online ShinyCell2 showcase: spatial, image, DE overlay, hosted ----------------
    try:
        p.goto("https://shinycell.ouyanglab.com/", timeout=120000); p.wait_for_timeout(15000)
        print("SC2 title:", p.title())
        tabs = p.eval_on_selector_all("ul.navbar-nav a", "els=>els.map(e=>e.textContent.trim())"); print("SC2 tabs:", tabs)
        jpg(p, "m15_hosted_shinycell2_showcase.jpg")
        p.click("ul.navbar-nav a:has-text('Side-by-side Spatial')"); p.wait_for_timeout(20000)
        jpg(p, "m07_m11_shinycell2_spatial_image_underlay.jpg")
        print("spatial tab labels:", p.eval_on_selector_all(".tab-pane.active label", "els=>els.map(e=>e.textContent.trim()).filter(t=>t).slice(0,25)"))
        vio = [t for t in tabs if "iolin" in t]
        if vio:
            p.click(f"ul.navbar-nav a:has-text('{vio[0]}')"); p.wait_for_timeout(15000)
            print("SC2 violin labels:", p.eval_on_selector_all(".tab-pane.active label", "els=>els.map(e=>e.textContent.trim()).filter(t=>t).slice(0,40)"))
            jpg(p, "m10_shinycell2_violin_test_option.jpg")
    except Exception as e:
        print("online failed:", e)
    b.close()
