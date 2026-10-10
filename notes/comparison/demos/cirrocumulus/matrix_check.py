"""Matrix-mark screenshots for Cirrocumulus 1.1.61, local `cirro launch` on bm_demo.h5ad (8901).
Run with matrix_check_spatial.py in one gap session, see matrix_check.sh."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import os, json
D = f"{_REPO}/notes/comparison/screens/cirrocumulus/"
COPYHOOK = """
(()=>{const o=document.execCommand.bind(document);document.execCommand=function(c,...a){
 if(c==='copy'){const e=document.activeElement;window.__copied=(e&&e.value)||String(window.getSelection());}
 return o(c,...a)}})();"""
def shot(page, n): page.screenshot(path=D + n + ".jpg", type="jpeg", quality=70); print("shot", n)
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:250])
def header(page):
    try: return page.locator("text=/\\/ 8,090 cells/").first.inner_text(timeout=2000)
    except Exception: return "NA"
def options(page):
    return page.evaluate("()=>[...document.querySelectorAll('[role=option]')].map(e=>e.innerText.trim()).slice(0,40)")
def dropdown(page, label, name):
    page.get_by_label(label).first.click(); page.wait_for_timeout(1200)
    print(label, "options:", options(page)); shot(page, name)
    page.keyboard.press("Escape"); page.wait_for_timeout(500)
def gene(page, g):
    c = page.get_by_role("combobox", name="Genes/Features"); c.click(); c.fill(g); page.wait_for_timeout(1500)
    page.keyboard.press("Enter"); page.keyboard.press("Escape"); page.wait_for_timeout(3500)
def legend_click(page, label):
    page.locator(f"td:text-is('{label}'), div:text-is('{label}'), span:text-is('{label}')").first.click(); page.wait_for_timeout(2500)

def steps(page, S):
    page.set_viewport_size({"width": 1400, "height": 1100})
    page.add_init_script(COPYHOOK)
    reqs = []
    page.on("request", lambda r: reqs.append(r.url) if "/api/" in r.url else None)
    page.goto("http://127.0.0.1:8901/"); page.wait_for_timeout(8000)
    shot(page, "m00_plots_render")
    print("startup api:", [u.split("/api/")[1][:80] for u in reqs][:12])
    step("embeddings", lambda: dropdown(page, "Embeddings", "m04_slots_embeddings_menu"))
    step("layers", lambda: dropdown(page, "Layers", "m04_slots_layers_menu"))
    step("meta", lambda: dropdown(page, "Cell Metadata", "m01_obsp_absent_cell_metadata_menu"))
    def g():
        n0 = len(reqs); gene(page, "Mpo")
        print("requests for one gene:", [u.split("/api/")[1][:120] for u in reqs[n0:]])
    step("gene", g)
    # column 8: two legend filters combine (Age Young AND highres_celltype Neutrophil)
    def filt():
        page.locator("text=Age >> nth=0").click(); page.wait_for_timeout(2500)
        legend_click(page, "Young"); print("after Young:", header(page))
        page.locator("text=highres_celltype >> nth=0").click(); page.wait_for_timeout(2500)
        legend_click(page, "Neutrophil"); print("after Young+Neutrophil:", header(page))
        shot(page, "m08_filters_age_and_celltype")
    step("filter", filt)
    # column 10: DE between two selections
    def de():
        page.get_by_label("Compare").first.click(); page.wait_for_timeout(800)
        print("compare options:", options(page)); page.click("[role=option]:has-text('Selection')"); page.wait_for_timeout(800)
        page.get_by_role("button", name="1", exact=True).click(); page.wait_for_timeout(500)
        legend_click(page, "Neutrophil"); legend_click(page, "Monocyte"); print("group2 selection:", header(page))
        page.get_by_role("button", name="2", exact=True).click(); page.wait_for_timeout(500)
        page.get_by_role("button", name="GO").click(); page.wait_for_timeout(1500)
        print("menu after GO:", page.evaluate("()=>[...document.querySelectorAll('[role=menuitem]')].map(e=>e.innerText)"))
        mi = page.locator("[role=menuitem]")
        if mi.count(): mi.first.click(); page.wait_for_timeout(1000)
        page.locator("[role=dialog] input").first.fill("matrix_check_young_neutro_vs_mono"); page.get_by_role("button", name="Submit").click()
        page.wait_for_timeout(20000)
        shot(page, "m10_de_job_submitted")
        page.get_by_role("tab", name="Results").click(); page.wait_for_timeout(2000)
        b = page.locator("text=matrix_check_young_neutro_vs_mono")
        if b.count(): b.first.click(); page.wait_for_timeout(8000)
        shot(page, "m10_de_results")
        page.get_by_role("tab", name="Embeddings").click(); page.wait_for_timeout(2000)
    step("de", de)
    # column 9: annotate a category in the legend (right-click > Annotate)
    def ann():
        page.locator("td:text-is('Neutrophil'), div:text-is('Neutrophil'), span:text-is('Neutrophil')").first.click(button="right"); page.wait_for_timeout(800)
        page.get_by_role("menuitem", name="Annotate").click(); page.wait_for_timeout(800)
        page.locator("[role=dialog] input").first.fill("Neutrophil_matrixcheck"); page.wait_for_timeout(300)
        print("dialog buttons:", page.evaluate("()=>[...document.querySelectorAll('[role=dialog] button')].map(b=>b.innerText)"))
        btns = page.locator("[role=dialog] button")
        for name in ("Update", "Apply", "OK", "Save"):
            b = page.locator(f"[role=dialog] button:has-text('{name}')")
            if b.count(): b.first.click(); break
        page.wait_for_timeout(3000)
        shot(page, "m09_annotation_legend_renamed")
        p = os.path.expanduser(f"{_DEMO_ROOT}/_data/bm_demo.json")
        print("bm_demo.json:", os.path.exists(p) and (os.path.getsize(p), open(p).read()[:300]))
    step("annotate", ann)
    # column 12: Copy Link, reopen
    def share():
        page.get_by_label("Menu").last.click(); page.wait_for_timeout(800)
        print("menu items:", page.evaluate("()=>[...document.querySelectorAll('[role=menuitem]')].map(e=>e.innerText.trim())"))
        shot(page, "m12_share_menu_copy_link")
        page.get_by_role("menuitem", name="Copy Link").click(); page.wait_for_timeout(800)
        link = page.evaluate("()=>window.__copied")
        print("copied link:", (link or "")[:300], "len", len(link or ""))
        p2 = page.context.new_page(); p2.set_viewport_size({"width": 1400, "height": 1100}); p2.goto(link); p2.wait_for_timeout(10000)
        p2.screenshot(path=D + "m12_share_link_reopened.jpg", type="jpeg", quality=70); print("shot m12 reopened; header", header(p2))
        p2.close()
    step("share", share)
    # column 13: Save Image > PNG
    def export():
        page.get_by_label("Save Image").first.click(); page.wait_for_timeout(800)
        shot(page, "m13_export_save_image_menu")
        with page.expect_download(timeout=30000) as d:
            page.get_by_role("menuitem", name="PNG").click()
        dd = d.value; out = "/tmp/cirro_view.png"; dd.save_as(out)
        print("download:", dd.suggested_filename, os.path.getsize(out), "bytes")
    step("export", export)
