"""Matrix-mark screenshots for CELLxGENE: Annotate (local, 8903) then hosted Explorer (Discover, small Visium dataset).
Run (starts and stops Annotate):
  notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
      demos/_focus_run.py cellxgene 8903 demos/cellxgene/matrix_check.py
"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import re, os, glob
D = f"{_REPO}/notes/comparison/screens/cellxgene/"
VISIUM = "https://cellxgene.cziscience.com/e/85585f3f-d16a-412d-b93a-406d52721221.cxg/"  # Visium, human muscle healthy control_2, 4,992 spots
def shot(page, n): page.screenshot(path=D + n + ".jpg", type="jpeg", quality=70); print("shot", n)
def tid(t): return f"[data-testid='{t}']"
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:250])
def fill(page, t, text):
    loc = page.locator(f"{tid(t)} input")
    if loc.count() == 0: loc = page.locator(tid(t))
    loc.first.fill(text)
def footer(page):
    try: return page.locator("text=/out of 8090/").first.inner_text(timeout=2000)
    except Exception: return "NA"
def lasso(page, box):
    x0, y0, x1, y1 = box
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    page.mouse.move(*pts[0]); page.mouse.down()
    for x, y in pts[1:]: page.mouse.move(x, y, steps=12)
    page.mouse.up(); page.wait_for_timeout(3000)
def addgene(page, g):
    inp = page.locator(f"{tid('gene-search')} input")
    if inp.count() == 0: inp = page.locator(tid("gene-search"))
    inp.first.click(); page.wait_for_timeout(600); inp.first.fill(g); page.wait_for_timeout(2500)
    items = page.locator(".bp3-menu-item, .bp4-menu-item, .bp5-menu-item, [role=option]")
    items.filter(has_text=re.compile("^" + g + "$")).first.click(); page.wait_for_timeout(3500)

def annotate(page):
    reqs = []
    page.on("request", lambda r: reqs.append(r.url) if "/api/" in r.url else None)
    page.goto("http://127.0.0.1:8903/"); page.wait_for_timeout(12000)
    page.locator(".bp3-dialog input").first.fill("matrixcheck"); page.click("text=Create user generated data directory"); page.wait_for_timeout(2000)
    shot(page, "m00_plots_annotate_render")
    print("startup api requests:", len(reqs), sorted({re.sub(r"\?.*", "", u.split("/api/")[1]) for u in reqs}))
    # columns 1, 2, 4: what the layout menu offers
    def layouts():
        page.click(tid("layout-choice")); page.wait_for_timeout(1000)
        print("layouts:", page.evaluate("()=>[...document.querySelectorAll('.bp3-popover-content label, .bp3-popover-content [role=menuitem]')].map(e=>e.innerText.trim()).filter(Boolean)"))
        shot(page, "m04_slots_annotate_layout_menu")
        page.mouse.click(700, 880); page.wait_for_timeout(800)
    step("layouts", layouts)
    # column 5: per-gene requests
    def gene():
        n0 = len(reqs); addgene(page, "Mpo")
        print("requests for one gene:", [u.split("/api/")[1][:90] for u in reqs[n0:]])
        page.click(tid("colorby-Mpo")); page.wait_for_timeout(2500)
        print("url after colouring by Mpo:", page.url)
        shot(page, "m12_share_annotate_coloured_before_reload")
    step("gene", gene)
    # column 12: same URL in a fresh page
    def share():
        p2 = page.context.new_page(); p2.goto(page.url); p2.wait_for_timeout(12000)
        try: p2.locator(".bp3-dialog input").first.fill("matrixcheck", timeout=3000); p2.click("text=Create user generated data directory"); p2.wait_for_timeout(1500)
        except Exception: pass
        p2.screenshot(path=D + "m12_share_annotate_same_url_reopened.jpg", type="jpeg", quality=70); print("shot m12 reopened, url", p2.url)
        p2.close()
    step("share", share)
    # column 8: categorical filter masks the embedding
    def filt():
        page.click(tid("colorby-Age")); page.wait_for_timeout(1500)
        page.click(tid("Age:category-expand")); page.wait_for_timeout(1000)
        for v in ("Mid", "Old"): page.click(tid(f"categorical-value-select-Age-{v}")); page.wait_for_timeout(1500)
        print("after unchecking Age Mid+Old:", footer(page))
        shot(page, "m08_filters_annotate_age_young_only")
    step("filter", filt)
    # column 10: DE Young vs Old
    def de():
        page.click(tid("cellset-button-1")); page.wait_for_timeout(1000)
        print("set1:", page.inner_text(tid("cellset-count-1"))[:40])
        page.click(tid("categorical-value-select-Age-Old")); page.click(tid("categorical-value-select-Age-Young")); page.wait_for_timeout(1500)
        page.click(tid("cellset-button-2")); page.wait_for_timeout(1000)
        print("set2:", page.inner_text(tid("cellset-count-2"))[:40], "|", footer(page))
        page.click(tid("diffexp-button")); page.wait_for_timeout(12000)
        shot(page, "m10_de_annotate_young_vs_old")
    step("de", de)
    # column 9: create a category, a label, assign the current selection (Age Old)
    def ann():
        page.click(tid("open-annotation-dialog")); page.wait_for_timeout(800)
        fill(page, "new-annotation-name", "matrix_check"); page.click(tid("submit-annotation")); page.wait_for_timeout(1500)
        page.wait_for_timeout(500)
        page.click(tid("matrix_check:see-actions")); page.click(tid("matrix_check:add-new-label-to-category")); page.wait_for_timeout(800)
        fill(page, "matrix_check:new-label-name", "old_cells"); page.click(tid("matrix_check:submit-label")); page.wait_for_timeout(1500)
        try: page.click(tid("matrix_check:category-expand"), timeout=3000)
        except Exception: pass
        page.wait_for_timeout(800)
        page.click(tid("matrix_check:old_cells:see-actions")); page.click(tid("matrix_check:old_cells:add-current-selection-to-this-label")); page.wait_for_timeout(2500)
        page.click(tid("colorby-matrix_check")); page.wait_for_timeout(2500)
        shot(page, "m09_annotation_annotate_label_created")
        page.wait_for_timeout(6000)  # autosave
        print("annotation files:", [(os.path.relpath(f, os.path.expanduser(f"{_DEMO_ROOT}/cellxgene")), os.path.getsize(f)) for f in glob.glob(os.path.expanduser(f"{_DEMO_ROOT}/cellxgene/annotations/**/*"), recursive=True) if os.path.isfile(f)])
    step("annotation", ann)
    # column 13: menu bar of Annotate (no download/export item)
    def menubar():
        print("menubar buttons:", page.evaluate("()=>[...document.querySelectorAll('[data-testid=header] ~ * button, button')].map(b=>(b.getAttribute('aria-label')||b.getAttribute('data-testid')||b.innerText||'').trim()).filter(Boolean).slice(0,40)"))
        page.click(tid("menu")); page.wait_for_timeout(1000)
        print("menu items:", page.evaluate("()=>[...document.querySelectorAll('.bp3-menu-item')].map(e=>e.innerText.trim())"))
        shot(page, "m13_export_annotate_menu_no_export")
        page.keyboard.press("Escape")
    step("menubar", menubar)

def explorer(page):
    reqs = []
    page.on("request", lambda r: reqs.append(r.url) if "api.cellxgene" in r.url else None)
    page.goto(VISIUM, timeout=120000)
    for i in range(24):
        page.wait_for_timeout(5000)
        if page.locator(tid("layout-choice")).count() and page.locator("canvas").count(): print("explorer ready after", (i + 1) * 5, "s"); break
    page.wait_for_timeout(8000)
    shot(page, "m07_spatial_explorer_visium_default")
    print("explorer api:", sorted({re.sub(r"\?.*", "", u.split("/api/v0.3/")[-1]) for u in reqs})[:20])
    def lay():
        page.click(tid("layout-choice")); page.wait_for_timeout(1500)
        print("E layouts/options:", page.evaluate("()=>[...document.querySelectorAll('[role=menuitem],[role=option],[role=radio],label,[role=switch]')].map(e=>e.innerText.trim()).filter(t=>t&&t.length<40).slice(0,30)"))
        shot(page, "m04_slots_explorer_embedding_menu")
        page.mouse.click(1380, 880); page.wait_for_timeout(800)
    step("E layouts", lay)
    def gene():
        n0 = len(reqs); addgene(page, "MYH7")
        print("E requests for one gene:", [u.split("/api/v0.3/")[-1][:100] for u in reqs[n0:]])
        page.click(tid("colorby-MYH7")); page.wait_for_timeout(5000)
        shot(page, "m11_image_explorer_myh7_on_tissue")
        print("E url after gene:", page.url)
    step("E gene", gene)
    def dl():
        page.click(tid("download-menu-button")); page.wait_for_timeout(1000)
        print("download items:", page.evaluate("()=>[...document.querySelectorAll('[role=menuitem], .bp5-menu-item, .bp4-menu-item, .bp3-menu-item')].map(e=>e.innerText.trim()).filter(Boolean)"))
        shot(page, "m13_export_explorer_download_menu")
        with page.expect_download(timeout=60000) as d:
            page.get_by_text("Current view (.png)").click()
        dd = d.value; out = "/tmp/cxg_explorer_view.png"; dd.save_as(out)
        print("download:", dd.suggested_filename, os.path.getsize(out), "bytes")
    step("E download", dl)
    def share():
        p2 = page.context.new_page(); p2.goto(page.url, timeout=120000); p2.wait_for_timeout(25000)
        p2.screenshot(path=D + "m12_share_explorer_same_url_reopened.jpg", type="jpeg", quality=70); print("shot m12 explorer reopened", p2.url)
        p2.close()
    step("E share", share)

def steps(page, S):
    step("annotate", lambda: annotate(page))
    step("explorer", lambda: explorer(page))
