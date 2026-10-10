"""Cirrocumulus matrix check, part 2 (filters, DE, annotation), local bm_demo on 8901.
Run: gap_run.sh <venv python> /abs/demos/_focus_run.py cirrocumulus 8901 /abs/demos/cirrocumulus/matrix_check2.py"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import os, glob
D = f"{_REPO}/notes/comparison/screens/cirrocumulus/"
def shot(page, n): page.screenshot(path=D + n + ".jpg", type="jpeg", quality=70); print("shot", n)
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:300])
def header(page):
    return page.evaluate("()=>{const e=[...document.querySelectorAll('header *, .MuiToolbar-root *')].find(x=>/cells/.test(x.innerText||'')&&x.children.length===0);return e?e.innerText:'NA'}")
def gallery_click(page, label):
    # click the gallery chart whose title is `label` (gallery sits below y=800)
    els = page.get_by_text(label, exact=True)
    for i in range(els.count()):
        b = els.nth(i).bounding_box()
        if b and b["y"] > 790: els.nth(i).click(); page.wait_for_timeout(2500); return True
    return False
def steps(page, S):
    page.set_viewport_size({"width": 1400, "height": 1100})
    page.goto("http://127.0.0.1:8901/"); page.wait_for_timeout(8000)
    def filt():
        page.get_by_label("Cell Metadata").first.click(); page.wait_for_timeout(800)
        page.click("[role=option]:text-is('Age')"); page.keyboard.press("Escape"); page.wait_for_timeout(3000)
        print("gallery Age clicked:", gallery_click(page, "Age"))
        page.get_by_text("Young", exact=True).first.click(); page.wait_for_timeout(2500)
        print("after Young:", header(page))
        print("gallery celltype clicked:", gallery_click(page, "highres_celltype"))
        page.get_by_text("Neutrophil", exact=True).first.click(); page.wait_for_timeout(2500)
        print("after Young AND Neutrophil:", header(page))
        shot(page, "m08_filters_age_and_celltype")
    step("filter", filt)
    def ann():
        page.get_by_text("Monocyte", exact=True).first.click(button="right"); page.wait_for_timeout(800)
        page.get_by_role("menuitem", name="Annotate").click(); page.wait_for_timeout(800)
        page.locator("[role=dialog] input").first.fill("Monocyte_matrixcheck"); page.wait_for_timeout(300)
        print("dialog buttons:", page.evaluate("()=>[...document.querySelectorAll('[role=dialog] button')].map(b=>b.innerText)"))
        for name in ("Update", "Apply", "OK", "Save"):
            b = page.locator(f"[role=dialog] button:has-text('{name}')")
            if b.count(): b.first.click(); break
        page.wait_for_timeout(3000)
        shot(page, "m09_annotation_legend_renamed")
        p = os.path.expanduser(f"{_DEMO_ROOT}/_data/bm_demo.json")
        print("bm_demo.json:", os.path.exists(p) and (os.path.getsize(p), open(p).read()[:300]))
    step("annotate", ann)
    def de():
        mc = page.get_by_label("Metadata Categories").first; mc.click(); mc.fill("Age"); page.wait_for_timeout(1000)
        page.click("[role=option]:text-is('Age')"); page.keyboard.press("Escape"); page.wait_for_timeout(500)
        page.get_by_role("button", name="GO").click(); page.wait_for_timeout(1500)
        mi = page.locator("[role=menuitem]")
        print("menu after GO:", [mi.nth(i).inner_text() for i in range(mi.count())])
        if mi.count(): mi.first.click(); page.wait_for_timeout(1000)
        page.locator("[role=dialog] input").first.fill("matrix_check_age_one_vs_rest"); page.get_by_role("button", name="Submit").click()
        page.wait_for_timeout(25000)
        shot(page, "m10_de_job_submitted")
        page.get_by_role("tab", name="Results").click(); page.wait_for_timeout(2000)
        shot(page, "m10_de_results_list")
        b = page.get_by_text("matrix_check_age_one_vs_rest")
        if b.count(): b.first.click(); page.wait_for_timeout(8000)
        shot(page, "m10_de_results")
        print("results files:", [(f, os.path.getsize(f)) for f in glob.glob(os.path.expanduser(f"{_DEMO_ROOT}/_data/results/**"), recursive=True) if os.path.isfile(f)][:5])
    step("de", de)
