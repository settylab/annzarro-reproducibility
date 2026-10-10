"""CELLxGENE Annotate matrix check, part 2 (filter, DE, annotation, menu), local 8903.
Run: gap_run.sh <venv python> /abs/demos/_focus_run.py cellxgene 8903 /abs/demos/cellxgene/matrix_check2.py"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import os, glob
D = f"{_REPO}/notes/comparison/screens/cellxgene/"
def shot(page, n): page.screenshot(path=D + n + ".jpg", type="jpeg", quality=70); print("shot", n)
def tid(t): return f"[data-testid='{t}']"
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:300])
def footer(page):
    try: return page.locator("text=/out of 8090/").first.inner_text(timeout=2000)
    except Exception: return "NA"
def toggle(page, cat, val):
    page.locator(f"label:has(#value-toggle-checkbox-{cat}-{val})").first.click(); page.wait_for_timeout(1500)
def fill_in(page, t, text):
    loc = page.locator(f"input{tid(t)}, {tid(t)} input")
    loc.first.fill(text)
def steps(page, S):
    page.goto("http://127.0.0.1:8903/"); page.wait_for_timeout(12000)
    page.locator(".bp3-dialog input").first.fill("matrixcheck"); page.click("text=Create user generated data directory"); page.wait_for_timeout(2000)
    def filt():
        page.click(tid("colorby-Age")); page.wait_for_timeout(1500)
        page.click(tid("Age:category-expand")); page.wait_for_timeout(1000)
        toggle(page, "Age", "Mid"); toggle(page, "Age", "Old")
        print("after unchecking Age Mid+Old:", footer(page))
        shot(page, "m08_filters_annotate_age_young_only")
    step("filter", filt)
    def de():
        page.click(tid("cellset-button-1")); page.wait_for_timeout(1000)
        print("set1:", page.inner_text(tid("cellset-count-1"))[:40])
        toggle(page, "Age", "Old"); toggle(page, "Age", "Young")
        page.click(tid("cellset-button-2")); page.wait_for_timeout(1000)
        print("set2:", page.inner_text(tid("cellset-count-2"))[:40], "|", footer(page))
        page.click(tid("diffexp-button")); page.wait_for_timeout(12000)
        print("DE panel text:", page.locator("text=/Differentially Expressed|Cell set/").count())
        shot(page, "m10_de_annotate_young_vs_old")
        try:
            page.get_by_text("Pop1 high").first.click(); page.wait_for_timeout(3000)
            print("Pop1 genes:", page.evaluate("()=>[...document.querySelectorAll('[data-testid$=\\:gene-label]')].map(e=>e.innerText.trim()).slice(0,10)"))
            shot(page, "m10_de_annotate_pop1_high_genes")
        except Exception as e: print("expand", str(e)[:100])
    step("de", de)
    def ann():
        page.get_by_text("Create new category").first.click(); page.wait_for_timeout(1000)
        print("inputs in dialog:", page.evaluate("()=>[...document.querySelectorAll('.bp3-dialog input')].map(i=>i.getAttribute('data-testid')||i.placeholder||i.name)"))
        page.locator(".bp3-dialog input").first.fill("matrix_check"); page.wait_for_timeout(300)
        page.click(tid("submit-category")); page.wait_for_timeout(1500)
        page.click(tid("matrix_check:see-actions")); page.wait_for_timeout(500)
        page.click(tid("matrix_check:add-new-label-to-category")); page.wait_for_timeout(1000)
        page.locator(".bp3-dialog input").first.fill("old_cells"); page.wait_for_timeout(300)
        page.locator(f"{tid('matrix_check:submit-label')}, .bp3-dialog button:has-text('Add label')").first.click(); page.wait_for_timeout(1500)
        try: page.click(tid("matrix_check:category-expand"), timeout=3000)
        except Exception: pass
        page.wait_for_timeout(800)
        print("matrix_check testids:", page.evaluate("()=>[...document.querySelectorAll('[data-testid*=matrix_check]')].map(e=>e.getAttribute('data-testid'))"))
        shot(page, "m09_annotation_annotate_category_and_label")
        page.click(tid("matrix_check:old_cells:see-actions")); page.wait_for_timeout(500)
        page.click(tid("matrix_check:old_cells:add-current-selection-to-this-label")); page.wait_for_timeout(2500)
        page.click(tid("colorby-matrix_check")); page.wait_for_timeout(2500)
        shot(page, "m09_annotation_annotate_label_created")
        page.wait_for_timeout(8000)
        base = os.path.expanduser(f"{_DEMO_ROOT}/cellxgene")
        print("annotation files:", [(os.path.relpath(f, base), os.path.getsize(f)) for f in glob.glob(base + "/annotations/**/*", recursive=True) if os.path.isfile(f)])
        for f in glob.glob(base + "/annotations/**/*matrix*", recursive=True):
            if os.path.isfile(f): print("head", f, open(f).read()[:250].replace("\n", " | "))
    step("annotation", ann)
    def menubar():
        page.locator(tid("menu")).click(force=True); page.wait_for_timeout(1000)
        print("menu items:", page.evaluate("()=>[...document.querySelectorAll('.bp3-menu-item, .bp3-popover-content a, .bp3-popover-content button')].map(e=>e.innerText.trim()).filter(Boolean)"))
        shot(page, "m13_export_annotate_menu_no_export")
    step("menubar", menubar)
