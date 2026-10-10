"""UCSC matrix check, part 2 (filter + annotation), local bm_demo on 8906. Legend checkbox of Neutrophil is
at (1209, 200) in a 1400x900 viewport (see m00_plots_render.jpg).
Run: gap_run.sh <venv python> /abs/demos/_focus_run.py ucsc-cell-browser 8906 /abs/demos/ucsc-cell-browser/matrix_check2.py"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
D = f"{_REPO}/notes/comparison/screens/ucsc-cell-browser/"
def shot(page, n): page.screenshot(path=D + n + ".jpg", type="jpeg", quality=70); print("shot", n)
def txt(page, sel, n=200):
    try: return page.locator(sel).first.inner_text(timeout=2000)[:n].replace("\n", " | ")
    except Exception: return "NA"
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:250])
def steps(page, S):
    page.add_init_script("try{localStorage.setItem('introShown','true')}catch(e){}")
    page.goto("http://127.0.0.1:8906/?ds=bm_demo"); page.wait_for_timeout(9000); page.keyboard.press("Escape")
    def filt():
        page.mouse.click(1209, 200); page.wait_for_timeout(2000)
        print("after legend checkbox:", txt(page, "#tpCellCount", 80), "| status", txt(page, "#mpStatus", 80))
        shot(page, "m08_filters_legend_checkbox_selects")
        page.click("#tpOnlySel", timeout=4000); page.wait_for_timeout(2500)
        print("after only-show:", txt(page, "#tpCellCount", 80), "| status", txt(page, "#mpStatus", 80), "| footer", txt(page, "text=/visible cells/", 80))
        shot(page, "m08_filters_only_show_selected")
    step("filter", filt)
    def ann():
        page.locator("a.dropdown-toggle:text-is('Edit')").first.click(); page.wait_for_timeout(800)
        page.click("#tpSelectName"); page.wait_for_timeout(1500)
        page.fill("#tpMetaVal", "neutro_matrixcheck"); page.wait_for_timeout(300)
        shot(page, "m09_annotation_name_selection_dialog")
        page.locator(".ui-dialog-buttonpane button:has-text('OK')").first.click(); page.wait_for_timeout(3000)
        shot(page, "m09_annotation_custom_field_created")
        print("localStorage keys:", page.evaluate("()=>Object.keys(localStorage)"))
        print("color-by now:", txt(page, "#tpLegendTitle", 80))
    step("annotation", ann)
