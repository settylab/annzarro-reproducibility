"""Re-capture of the bm_demo matrix shots (matrix_check.py, matrix_check2.py, matrix_check3.py in one session), each with
a dom sidecar. Run via recap_session_a.sh (gap_run; starts and stops the server, removes the annotation/DE side files)."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import os, glob, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recap_lib import *
DRV = "notes/comparison/demos/cirrocumulus/recap_matrix.py"
COPYHOOK = """(()=>{const o=document.execCommand.bind(document);document.execCommand=function(c,...a){
 if(c==='copy'){const e=document.activeElement;window.__copied=(e&&e.value)||String(window.getSelection());}
 return o(c,...a)}})();"""
def S(page, name, proves, callouts): snap(page, name, proves, callouts, DRV)
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:250])
def header(page):
    try: return page.locator(HEADER).inner_text(timeout=2000)
    except Exception: return "NA"
def gene(page, g):
    c = page.get_by_role("combobox", name="Genes/Features"); c.click(); c.fill(g); page.wait_for_timeout(1500)
    page.keyboard.press("Enter"); page.keyboard.press("Escape"); page.wait_for_timeout(3500)
def gallery_click(page, label):
    els = page.get_by_text(label, exact=True)
    for i in range(els.count()):
        b = els.nth(i).bounding_box()
        if b and b["y"] > 790: els.nth(i).click(); page.wait_for_timeout(2500); return True
    return False
def dd(page, label, name, proves, lab):
    page.get_by_label(label).first.click(); page.wait_for_timeout(1200)
    print(label, "options:", page.evaluate("()=>[...document.querySelectorAll('[role=option]')].map(e=>e.innerText.trim()).slice(0,40)"))
    S(page, name, proves, [(1, LISTBOX, lab)])
    page.keyboard.press("Escape"); page.wait_for_timeout(500)
def steps(page, _):
    page.set_viewport_size({"width": 1400, "height": 1100}); page.add_init_script(COPYHOOK)
    page.goto("http://127.0.0.1:8901/"); page.wait_for_timeout(8000)
    S(page, "m00_plots_render.jpg", [pv("every_cell", "Y", "bm_demo (8,090 cells) renders in local cirro launch")], [(1, main_plot(page), "X_umap, all cells"), (2, HEADER, "cell count")])
    step("emb", lambda: dd(page, "Embeddings", "m04_slots_embeddings_menu.jpg", [pv("slots", "P", "Embeddings offers X_umap and X_draw_graph_fa only; X_pca and X_diffusion are not offered")], "Embeddings: two of four obsm entries"))
    step("lay", lambda: dd(page, "Layers", "m04_slots_layers_menu.jpg", [pv("slots", "P", "Layers lists counts")], "Layers: counts"))
    step("meta", lambda: dd(page, "Cell Metadata", "m01_obsp_absent_cell_metadata_menu.jpg", [pv("cells", "N", "Cell Metadata lists obs columns only; no obsp matrix in any dropdown"), pv("genes", "N", "No varp in any dropdown")], "obs columns only, no obsp"))
    step("gene", lambda: gene(page, "Mpo"))
    def share():
        page.get_by_label("Menu").last.click(); page.wait_for_timeout(800)
        print("menu items:", page.evaluate("()=>[...document.querySelectorAll('[role=menuitem]')].map(e=>e.innerText.trim())"))
        S(page, "m12_share_menu_copy_link.jpg", [pv("share", "Y", "The top-right menu offers Copy Link, a URL that carries the view state")], [(1, "[role=menuitem]:has-text('Copy Link')", "Copy Link")])
        page.get_by_role("menuitem", name="Copy Link").click(); page.wait_for_timeout(800)
        link = page.evaluate("()=>window.__copied"); print("copied link len", len(link or ""), (link or "")[:160])
        p2 = page.context.new_page(); p2.set_viewport_size({"width": 1400, "height": 1100}); p2.goto(link); p2.wait_for_timeout(10000)
        snap(p2, "m12_share_link_reopened.jpg", [pv("share", "Y", "The copied link, opened in a new tab, restores X_umap, Mpo colouring and the gallery")], [(1, main_plot(p2), "Mpo colouring restored"), (2, "text=Mpo >> nth=0", "active feature Mpo")], DRV)
        print("reopened header", header(p2)); p2.close()
    step("share", share)
    def export():
        page.get_by_label("Save Image").first.click(); page.wait_for_timeout(800)
        S(page, "m13_export_save_image_menu.jpg", [pv("export", "Y", "Save Image offers PNG and SVG")], [(1, MENU, "PNG / SVG"), (2, "[aria-label='Save Image'] >> nth=0", "Save Image button")])
        with page.expect_download(timeout=20000) as d: page.get_by_role("menuitem", name="PNG").click()
        out = "/tmp/cirro_view.png"; d.value.save_as(out); print("download:", d.value.suggested_filename, os.path.getsize(out))
    step("export", export)
    # part 2 (matrix_check2.py): filters and annotation, fresh page
    page.goto("http://127.0.0.1:8901/"); page.wait_for_timeout(7000)
    def filt():
        page.get_by_label("Cell Metadata").first.click(); page.wait_for_timeout(800)
        page.click("[role=option]:text-is('Age')"); page.keyboard.press("Escape"); page.wait_for_timeout(3000)
        print("gallery Age clicked:", gallery_click(page, "Age"))
        page.get_by_text("Young", exact=True).first.click(); page.wait_for_timeout(2500)
        print("after Young:", header(page))
        S(page, "m08_filters_age_young_chip.jpg", [pv("filters", "Y", "Clicking Young in the Age legend adds an Age filter chip; header 2,917 / 8,090 cells; gallery dims the rest")],
          [(1, chip(page, "chipAge", "Age"), "filter chip Age"), (2, HEADER, "2,917 / 8,090 cells"), (3, tagleaf(page, "comb", "^AND$", up=1), "AND/OR Combine switch")])
        print("gallery celltype clicked:", gallery_click(page, "highres_celltype"))
        page.get_by_text("Neutrophil", exact=True).first.click(); page.wait_for_timeout(2500)
        print("after Young AND Neutrophil (no shot):", header(page))
    step("filter", filt)
    def ann():
        page.get_by_text("Monocyte", exact=True).first.click(button="right"); page.wait_for_timeout(800)
        page.get_by_role("menuitem", name="Annotate").click(); page.wait_for_timeout(800)
        page.locator("[role=dialog] input").first.fill("Monocyte_matrixcheck"); page.wait_for_timeout(300)
        for name in ("Update", "Apply", "OK", "Save"):
            b = page.locator(f"[role=dialog] button:has-text('{name}')")
            if b.count(): b.first.click(); break
        page.wait_for_timeout(3000)
        S(page, "m09_annotation_legend_renamed.jpg", [pv("annot", "Y", "Right-click > Annotate renamed Monocyte to Monocyte_matrixcheck in the legend; saved server-side")],
          [(1, tagleaf(page, "ren", "^Monocyte_matrixcheck$", x0=1000, up=1), "renamed category")])
        p = os.path.expanduser(f"{_DEMO_ROOT}/_data/bm_demo.json"); print("bm_demo.json:", os.path.exists(p) and os.path.getsize(p))
    step("annotate", ann)
    # part 3 (matrix_check3.py): DE One vs. Rest on Age, fresh page
    def de():
        page.goto("http://127.0.0.1:8901/"); page.wait_for_timeout(7000)
        mc = page.get_by_label("Metadata Categories").first
        mc.click(); mc.type("Age", delay=80); page.wait_for_timeout(1200)
        page.keyboard.press("ArrowDown"); page.keyboard.press("Enter"); page.wait_for_timeout(800); page.keyboard.press("Escape")
        page.get_by_role("button", name="GO").click(); page.wait_for_timeout(1500)
        mi = page.locator("[role=menuitem]:visible")
        if mi.count() and not page.locator("[role=dialog]:visible").count(): mi.first.click(); page.wait_for_timeout(1000)
        page.locator("[role=dialog]:visible input").first.fill("matrix_check_age_one_vs_rest"); page.get_by_role("button", name="Submit").click()
        page.wait_for_timeout(22000)
        page.get_by_role("tab", name="Results").click(); page.wait_for_timeout(2000)
        b = page.get_by_text("matrix_check_age_one_vs_rest")
        if b.count(): b.first.click(); page.wait_for_timeout(7000)
        S(page, "m10_de_results.jpg", [pv("de", "Y", "One vs. Rest DE on Age computed in the app; Results tab shows a dot plot of the top features per group")],
          [(1, main_plot(page), "DE dot plot"), (2, "text=matrix_check_age_one_vs_rest >> nth=0", "the DE job")])
    step("de", de)
