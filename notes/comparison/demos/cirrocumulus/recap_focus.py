"""Re-capture of the focus shots 01-04 (focus_check_gene_legend.py, focus_check_click.py) under their final names, each with a
dom sidecar. Run via recap_session_b.sh."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recap_lib import *
DRV = "notes/comparison/demos/cirrocumulus/recap_focus.py"
TIP = """()=>{for(const d of document.querySelectorAll('div')){if(d.style.zIndex=='9999999'&&d.style.visibility!='hidden'&&d.innerText.trim()){d.setAttribute('data-recap','tip');return d.innerText.trim()}}return null}"""
def S(page, name, proves, callouts): snap(page, name, proves, callouts, DRV)
def setup(page):
    page.goto("http://127.0.0.1:8901/"); page.wait_for_timeout(7000)
    page.get_by_label("Embeddings").click(); page.wait_for_timeout(500)
    page.click("[role=option]:has-text('X_draw_graph_fa')"); page.keyboard.press("Escape"); page.wait_for_timeout(3000)
    g = page.get_by_role("combobox", name="Genes/Features"); g.click(); g.fill("Mpo"); page.wait_for_timeout(1500)
    page.keyboard.press("Enter"); page.keyboard.press("Escape"); page.wait_for_timeout(4000)
def steps(page, _):
    page.set_viewport_size({"width": 1400, "height": 1250})
    try:
        setup(page)
        g = gallery(page)
        S(page, "01_gene_mpo_on_both_embeddings.jpg", [pv("focus", "N", "Feature colouring, not a focus: Mpo (one column of X) colours every chosen embedding, the primary FA plot and the X_umap gallery chart")],
          [(1, main_plot(page), "primary: Mpo on X_draw_graph_fa")] + [(i + 2, s, "gallery chart") for i, s in enumerate(g)])
        page.click("text=highres_celltype >> nth=0"); page.wait_for_timeout(2500)
        page.click("text=Ery P", timeout=5000); page.wait_for_timeout(3000)
        print("header:", page.locator(HEADER).inner_text())
        g = gallery(page)
        S(page, "03_legend_selection_highlights_gallery.jpg", [pv("selection", "Y", "Clicking Ery P in the legend selects its 687 cells; every gallery chart highlights them and a highres_celltype filter chip appears")],
          [(1, tagleaf(page, "eryp", "^Ery P$", x0=1000, up=1), "legend: Ery P 687 / 687"), (2, HEADER, "687 / 8,090 cells"), (3, chip(page, "chipct", "highres_celltype"), "filter chip")] + [(i + 4, s, "gallery chart, selection highlighted") for i, s in enumerate(g)])
    except Exception as e: print("FAIL gene_legend", str(e)[:250])
    try:
        setup(page)
        page.mouse.click(700, 1100); page.wait_for_timeout(3000)
        found = None
        for y in range(250, 700, 6):
            for x in range(600, 1050, 6):
                page.mouse.move(x, y); page.wait_for_timeout(15)
                t = page.evaluate(TIP)
                if t: found = (x, y, t); break
            if found: break
        print("tooltip at", found)
        if found:
            S(page, "02_hover_shows_value_only.jpg", [pv("focus", "N", "Hover shows only the current colouring's value for that cell; a single click changes nothing")],
              [(1, "[data-recap='tip']", f"tooltip: {found[2][:30]}"), (2, main_plot(page), "primary plot")])
            page.mouse.click(found[0], found[1]); page.wait_for_timeout(1200)
            print("after single click:", page.locator(HEADER).inner_text())
            page.mouse.dblclick(found[0], found[1]); page.wait_for_timeout(2500)
            print("after dblclick:", page.locator(HEADER).inner_text())
            g = gallery(page)
            S(page, "04_dblclick_selects_category_all_charts.jpg", [pv("focus", "N", "Double-click selects the cell's whole category (no per-cell value); the selection then highlights in all charts"), pv("selection", "Y", "The category selection highlights in every gallery chart")],
              [(1, HEADER, "category selected"), (2, main_plot(page), "double-clicked plot")] + [(i + 3, s, "gallery chart") for i, s in enumerate(g)])
    except Exception as e: print("FAIL click", str(e)[:250])
