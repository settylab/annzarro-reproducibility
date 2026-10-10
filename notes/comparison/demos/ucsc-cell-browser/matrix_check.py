"""Matrix-mark screenshots for UCSC Cell Browser: local static build (8906, bm_demo) then the portal
spatial dataset brain-spatial-omics/p21 (2,373 spots, tissue image).
Run (starts and stops the local server):
  notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
      demos/_focus_run.py ucsc-cell-browser 8906 demos/ucsc-cell-browser/matrix_check.py
"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import os
D = f"{_REPO}/notes/comparison/screens/ucsc-cell-browser/"
BASE = "http://127.0.0.1:8906/?ds=bm_demo"
PORTAL = "https://cells.ucsc.edu/?ds=brain-spatial-omics+p21"
def shot(page, n): page.screenshot(path=D + n + ".jpg", type="jpeg", quality=70); print("shot", n)
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:250])
def txt(page, sel, n=200):
    try: return page.locator(sel).first.inner_text(timeout=2000)[:n].replace("\n", " | ")
    except Exception: return "NA"
def menu(page, name):
    page.locator(f"a.dropdown-toggle:text-is('{name}')").first.click(); page.wait_for_timeout(800)
    return page.evaluate("(n)=>{const a=[...document.querySelectorAll('a.dropdown-toggle')].find(e=>e.innerText.trim()===n);return [...a.parentElement.querySelectorAll('ul a')].map(e=>e.innerText.trim().replace(/\\s+/g,' ')).filter(Boolean)}", name)

def local(page):
    reqs = []
    page.on("request", lambda r: reqs.append((r.url.split("8906/")[-1], r.headers.get("range"))) if "8906" in r.url else None)
    page.goto(BASE, timeout=60000); page.wait_for_timeout(10000); page.keyboard.press("Escape")
    shot(page, "m00_plots_render")
    print("startup files:", sorted({u.split("?")[0] for u, _ in reqs})[:30])
    def slots():
        print("annotation fields:", page.evaluate("()=>[...document.querySelectorAll('#tpLeftSidebar .tpMetaBox, #tpMetaPanel .tpMetaLabel, .tpMetaLabel')].map(e=>e.innerText.trim()).filter(Boolean).slice(0,30)"))
        print("layouts:", page.evaluate("()=>[...document.querySelectorAll('#tpLayoutCombo option')].map(e=>e.innerText.trim())"))
        try:
            page.locator("text=Layout").first.click(timeout=2000); page.wait_for_timeout(800)
        except Exception: pass
        shot(page, "m04_slots_layout_tab")
        try:
            page.locator("text=Annotation").first.click(timeout=2000); page.wait_for_timeout(800)
        except Exception: pass
        shot(page, "m04_slots_annotation_tab")
    step("slots", slots)
    def lazy():
        n0 = len(reqs)
        page.goto(BASE + "&gene=Mpo"); page.wait_for_timeout(8000); page.keyboard.press("Escape")
        print("requests when opening with gene=Mpo:", [(u[:60], r) for u, r in reqs[n0:] if "exprMatrix" in u or "gene" in u.lower()][:10])
    step("lazy", lazy)
    def share():
        # change state in the GUI: colour by Age (Annotation tab), zoom in once; read the URL; reopen it
        page.goto(BASE); page.wait_for_timeout(8000); page.keyboard.press("Escape")
        page.locator(".tpMetaBox:has-text('Age'), [data-field-name='Age']").first.click(timeout=4000); page.wait_for_timeout(3000)
        page.mouse.move(800, 450); page.mouse.wheel(0, -400); page.wait_for_timeout(2500)
        print("legend title:", txt(page, "#tpLegendTitle", 60), "| url:", page.url)
        shot(page, "m12_share_state_before")
        p2 = page.context.new_page(); p2.goto(page.url); p2.wait_for_timeout(9000); p2.keyboard.press("Escape")
        print("reopened legend title:", txt(p2, "#tpLegendTitle", 60))
        p2.screenshot(path=D + "m12_share_url_reopened.jpg", type="jpeg", quality=70); print("shot m12 reopened"); p2.close()
    step("share", share)
    def filt():
        page.goto(BASE); page.wait_for_timeout(8000); page.keyboard.press("Escape")
        page.locator("#tpLegendBar >> text=Neutrophil, .tpLegend >> text=Neutrophil").first.click(timeout=4000); page.wait_for_timeout(2000)
        print("after legend click:", txt(page, "#tpCellCount", 80))
        page.click("#tpOnlySel", timeout=4000); page.wait_for_timeout(2500)
        shot(page, "m08_filters_legend_select_only_show_selected")
        print("after only-show:", txt(page, "#tpCellCount", 80))
    step("filter", filt)
    def ann():
        menu(page, "Edit"); page.click("#tpSelectName"); page.wait_for_timeout(1000)
        page.fill("#tpMetaVal", "neutro_matrixcheck"); page.wait_for_timeout(300)
        shot(page, "m09_annotation_name_selection_dialog")
        page.locator(".ui-dialog-buttonpane button:has-text('OK')").first.click(); page.wait_for_timeout(3000)
        shot(page, "m09_annotation_custom_field_created")
        print("localStorage keys:", page.evaluate("()=>Object.keys(localStorage)"))
    step("annotation", ann)
    def tools():
        print("Tools menu:", menu(page, "Tools")); shot(page, "m10_de_tools_menu_no_de"); page.keyboard.press("Escape"); page.mouse.click(5, 890)
    step("tools", tools)
    def export():
        print("File menu:", menu(page, "File")); shot(page, "m13_export_file_menu")
        with page.expect_download(timeout=30000) as d:
            page.click("#tpSaveImage")
        dd = d.value; out = "/tmp/ucsc_view.png"; dd.save_as(out); print("download:", dd.suggested_filename, os.path.getsize(out), "bytes")
    step("export", export)

def portal(page):
    reqs = []
    page.on("request", lambda r: reqs.append(r.url) if "cells.ucsc.edu" in r.url and ("jpg" in r.url or "exprMatrix" in r.url) else None)
    page.goto(PORTAL, timeout=90000); page.wait_for_timeout(15000); page.keyboard.press("Escape")
    shot(page, "m07_spatial_portal_p21")
    print("image requests:", [u.split("cells.ucsc.edu/")[-1][:80] for u in reqs][:6])
    try:
        page.goto(PORTAL + "&gene=" + "Mbp", timeout=90000); page.wait_for_timeout(12000); page.keyboard.press("Escape")
        shot(page, "m11_image_portal_p21_gene_on_tissue")
    except Exception as e: print("portal gene", str(e)[:120])

def steps(page, S):
    page.add_init_script("try{localStorage.setItem('introShown','true')}catch(e){}")
    step("local", lambda: local(page))
    step("portal", lambda: portal(page))
