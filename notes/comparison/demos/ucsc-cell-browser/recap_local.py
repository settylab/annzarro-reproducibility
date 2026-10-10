"""Re-capture of the UCSC Cell Browser focus (01-03) and local matrix shots, each with a dom sidecar (demos/_bin/recap.py).
Same steps as focus_check_click.py, focus_check_gene_split.py, focus_check_lasso_split.py, matrix_check.py (local part)
and matrix_check2.py, one session, final filenames. Run:
  notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
      demos/_focus_run.py ucsc-cell-browser 8906 demos/ucsc-cell-browser/recap_local.py"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import os, sys, time
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from recap import snap as _snap, pv
BASE = "http://127.0.0.1:8906/?ds=bm_demo"
SW = "UCSC Cell Browser, cellbrowser 1.2.20 (local static build)"
DATA = "bm_demo.h5ad (8,090 cells)"
DRV = "notes/comparison/demos/ucsc-cell-browser/recap_local.py"
T0 = time.time()
def snap(p, name, proves, callouts): _snap(p, "ucsc-cell-browser", name, proves, callouts, software=SW, driver=DRV, data=DATA); print(f"  [{time.time()-T0:.0f}s]")
def txt(page, sel, n=200):
    try: return page.locator(sel).first.inner_text(timeout=1500)[:n].replace("\n", " | ")
    except Exception: return "NA"
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:200])
CANVAS = "#mpCanvas, canvas"
STATUS = "#tpCellCount"
def dump(page):
    print("DOM:", page.evaluate("""()=>[...document.querySelectorAll('[id^=mp],[id^=tp],canvas')].filter(e=>e.offsetParent&&e.getBoundingClientRect().width>60)
      .map(e=>{const r=e.getBoundingClientRect();return (e.id||e.tagName)+':'+[r.x,r.y,r.width,r.height].map(Math.round).join(',')}).slice(0,60).join(' ')"""))
def openb(page, url=BASE, w=9000):
    page.goto(url, timeout=60000); page.wait_for_timeout(w); page.keyboard.press("Escape"); page.wait_for_timeout(300)

def focus(page):
    openb(page)
    dump(page)
    hit = None
    for y in range(110, 200, 6):
        for x in range(700, 1000, 6):
            page.mouse.click(x, y); page.wait_for_timeout(80)
            if "selected" in txt(page, STATUS, 100) and "1 selected" in txt(page, STATUS, 100): hit = (x, y); break
        if hit: break
    print("click hit", hit, "| count", txt(page, STATUS, 80)); page.wait_for_timeout(2000)
    print("META:", txt(page, "#tpMetaPanel", 200))
    snap(page, "01_single_cell_click_selects_and_shows_meta.jpg",
         [pv("focus", "N", "A click selects that one cell and lists its own metadata; no neighbour, distance or other relation is shown")],
         [(1, "#tpMetaPanel", "clicked cell's own metadata"), (2, STATUS, "1 cell selected")])
    # (a2) gene on both split panes
    openb(page, BASE + "&gene=Mpo", 9000)
    page.mouse.click(5, 890); page.keyboard.press("t"); page.wait_for_timeout(4000)
    step("both", lambda: (page.get_by_text("Show on both sides").click(timeout=4000), page.wait_for_timeout(4000)))
    tag_right(page); print("legend:", txt(page, "#tpLegendTitle", 60))
    snap(page, "02_split_gene_mpo_on_both_panes.jpg",
         [pv("focus", "N", "Feature colouring: Mpo (one column of X) colours both split panes; not a relation row, so column 3 stays N")],
         [(1, "#mpCanvas", "left pane coloured by Mpo"), (2, RIGHT, "right pane coloured by Mpo (drawn partly in headless)"),
          (3, "text=Show on both sides", "Gene tab: Show on both sides")])
    # (b) lasso in left pane of split, shows in right pane and violin
    openb(page, BASE + "&gene=Mpo", 9000)
    page.mouse.click(5, 890); page.keyboard.press("t"); page.wait_for_timeout(4000)
    def las():
        page.click("#mpIconModeLasso", timeout=3000); page.wait_for_timeout(300)
        pts = [(420, 300), (620, 300), (620, 520), (420, 520), (420, 300)]
        page.mouse.move(*pts[0]); page.mouse.down()
        for q in pts[1:]: page.mouse.move(*q, steps=12)
        page.mouse.up(); page.wait_for_timeout(3000)
    step("lasso", las)
    step("redraw", lambda: (page.click("#mpCtrlZoom100", timeout=3000), page.wait_for_timeout(2500)))
    print("count after lasso:", txt(page, STATUS, 80)); tag_right(page)
    page.mouse.move(5, 890); page.wait_for_timeout(600)  # drop the zoom button tooltip
    snap(page, "03_lasso_selection_both_panes_and_violin.jpg",
         [pv("selection", "Y", "A lasso in the left pane selects 1.1k cells; the right pane highlights the same cells and the violin splits Selected vs Others")],
         [(1, "#mpCanvas", "lasso selection, left pane"), (2, RIGHT, "same cells highlighted, right pane"),
          (3, "#tpViolin", "violin: Selected vs Others"), (4, STATUS, "cells selected")])

def menu(page, name):
    page.locator(f"a.dropdown-toggle:text-is('{name}')").first.click(); page.wait_for_timeout(800)
TAB = lambda n: f"#tpLeftTabs a:text-is('{n}')"
RIGHT = "[data-recap=right]"
def tag_right(page):
    print("right pane:", page.evaluate("""()=>{const c=[...document.querySelectorAll('div')].filter(e=>{const r=e.getBoundingClientRect();return e.offsetParent&&Math.abs(r.x-725)<8&&r.width>400&&r.width<500&&r.height>700});
      c.sort((a,b)=>b.getBoundingClientRect().height-a.getBoundingClientRect().height); if(!c.length) return null; c[0].setAttribute('data-recap','right');
      const r=c[0].getBoundingClientRect(); return (c[0].id||c[0].className)+':'+[r.x,r.y,r.width,r.height].map(Math.round).join(',')}"""))
MENU = lambda n: f"a.dropdown-toggle:text-is('{n}') >> xpath=.. >> ul"

def matrix(page):
    openb(page)
    snap(page, "m00_plots_render.jpg", [pv("static", "Y", "The local static build of bm_demo (plain file server, no backend) renders all 8,090 cells")],
         [(1, CANVAS, "UMAP of bm_demo, 8,090 cells"), (2, STATUS, "cell count")])
    def slots():
        print("layouts:", page.evaluate("()=>[...document.querySelectorAll('#tpLayoutCombo option')].map(e=>e.innerText.trim())"))
        page.locator(TAB("Layout")).first.click(timeout=3000); page.wait_for_timeout(800)
        snap(page, "m04_slots_layout_tab.jpg", [pv("slots", "P", "Layout tab: the embedding dropdown holds UMAP and ForceAtlas2 only; X_pca, X_diffusion, layers and obsp were dropped at import")],
             [(1, "#tpLayoutTab", "embedding dropdown")])
        page.locator(TAB("Annotation")).first.click(timeout=3000); page.wait_for_timeout(800)
        snap(page, "m04_slots_annotation_tab.jpg",
             [pv("cells", "N", "The Annotation tab lists obs fields only; no obsp matrix anywhere"),
              pv("genes", "N", "No varp anywhere; the Gene tab searches genes of X only")],
             [(1, "#tpLeftSidebar, #tpLeftTabs", "Annotation tab: obs fields only")])
    step("slots", slots)
    def share():
        page.locator(".tpMetaBox:has-text('Age'), [data-field-name='Age']").first.click(timeout=4000); page.wait_for_timeout(2500)
        print("legend:", txt(page, "#tpLegendTitle", 60), "| url:", page.url)
        snap(page, "m12_share_state_before.jpg", [pv("share", "Y", "Colouring by Age writes meta=Age into the URL")],
             [(1, "#tpLegendBar", "legend: Age"), (2, ".tpMetaBox:has-text('Age')", "Age chosen as colour")])
        p2 = page.context.new_page(); p2.goto(page.url); p2.wait_for_timeout(8000); p2.keyboard.press("Escape")
        print("reopened legend:", txt(p2, "#tpLegendTitle", 60))
        snap(p2, "m12_share_url_reopened.jpg", [pv("share", "Y", "The copied URL (?ds=bm_demo&meta=Age) reopens with the Age colouring and legend")],
             [(1, "#tpLegendBar", "legend: Age, restored from the URL"), (2, CANVAS, "plot coloured by Age")]); p2.close()
    step("share", share)
    def filt():
        openb(page, BASE, 8000)
        page.mouse.click(1209, 200); page.wait_for_timeout(2000)
        print("after legend checkbox:", txt(page, STATUS, 80))
        snap(page, "m08_filters_legend_checkbox_selects.jpg", [pv("filters", "P", "Ticking Neutrophil in the legend selects its 2,221 cells; selection on one plot, no table")],
             [(1, "#tpLegendBar", "legend checkbox: Neutrophil"), (2, STATUS, "2.2k selected")])
        page.click("#tpOnlySel", timeout=4000); page.wait_for_timeout(2500)
        print("after only-show:", txt(page, STATUS, 80))
        snap(page, "m08_filters_only_show_selected.jpg", [pv("filters", "P", "Only show selected leaves 2.2k of 8.1k cells; legend selection, not a table filter")],
             [(1, "#tpOnlySel", "Only show selected"), (2, STATUS, "2.2k of 8.1k cells shown")])
    step("filter", filt)
    def ann():
        menu(page, "Edit"); page.click("#tpSelectName"); page.wait_for_timeout(1200)
        page.fill("#tpMetaVal", "neutro_matrixcheck"); page.wait_for_timeout(300)
        snap(page, "m09_annotation_name_selection_dialog.jpg", [pv("annot", "Y", "Edit > Name selection... opens 'Annotate selected cells' for the 2,221 selected cells")],
             [(1, ".ui-dialog", "Annotate selected cells dialog")])
        page.locator(".ui-dialog-buttonpane button:has-text('OK')").first.click(); page.wait_for_timeout(2500)
        print("color-by now:", txt(page, "#tpLegendTitle", 80))
        snap(page, "m09_annotation_custom_field_created.jpg", [pv("annot", "Y", "OK adds the colour-by field 'My custom annotations' (neutro matrixcheck 27.5%), stored in localStorage")],
             [(1, "#tpLegendBar", "new field: My custom annotations")])
    step("annotation", ann)
    def tools():
        openb(page, BASE, 8000)  # clean page, as in matrix_check.py
        menu(page, "Tools")
        snap(page, "m10_de_tools_menu_no_de.jpg", [pv("de", "N", "The Tools menu has no Differential expression item (DE UI is off by default and has no released backend)")],
             [(1, MENU("Tools"), "Tools menu: no DE item")])
        page.keyboard.press("Escape"); page.mouse.click(5, 890); page.wait_for_timeout(300)
    step("tools", tools)
    def export():
        menu(page, "File")
        snap(page, "m13_export_file_menu.jpg", [pv("export", "Y", "File menu: Download bitmap image (PNG) and vector image (SVG)")],
             [(1, MENU("File"), "File menu: PNG and SVG download")])
        page.keyboard.press("Escape"); page.mouse.click(5, 890)
    step("export", export)

ONLY = None  # set of stems to re-shoot; None = all
def steps(page, S):
    page.add_init_script("try{localStorage.setItem('introShown','true')}catch(e){}")
    step("focus", lambda: focus(page))
    if not os.environ.get("RECAP_FOCUS_ONLY"): step("matrix", lambda: matrix(page))
    print(f"done {time.time()-T0:.0f}s")
