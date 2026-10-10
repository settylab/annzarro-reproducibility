"""Cirrocumulus 1.1.61, local `cirro launch` on bm_demo (evidence-curator, 2026-10-04). steps(page) for _focus_run.py, which
starts and stops the server ($DEMO_ROOT/cirrocumulus/start.sh, 127.0.0.1:8901):
  notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
      notes/comparison/demos/_focus_run.py cirrocumulus 8901 evidence/screens/gaps/capture2_cirrocumulus.py

New:          h01 subset P: a legend selection, with the sidebar's Filtered Marker Opacity / Size (dim or shrink the rest).
Re-captured:  m00_plots_render (box the cell count), 04_dblclick_selects_category_all_charts (the header regex now matches
              with or without a selection), m10_de_results (box the dot plot). Steps of
              notes/comparison/demos/cirrocumulus/recap_matrix.py and recap_focus.py.
Side files (bm_demo.json, DE results) are removed afterwards, as recap_session_a.sh does.
"""
import glob
import os
import shutil
import sys

sys.path.insert(0, "evidence/screens/gaps")
sys.path.insert(0, "notes/comparison/demos/cirrocumulus")
from capture2lib import SCRATCH, TODAY, log, pv, shot, step  # noqa: E402
from recap_lib import BM, SW, gallery, main_plot, plots, tagleaf, chip  # noqa: E402

DRV = "evidence/screens/gaps/capture2_cirrocumulus.py"
URL = "http://127.0.0.1:8901/"
COUNT = "[data-recap='count']"
TIP = """()=>{for(const d of document.querySelectorAll('div')){if(d.style.zIndex=='9999999'&&d.style.visibility!='hidden'&&d.innerText.trim()){d.setAttribute('data-recap','tip');return d.innerText.trim()}}return null}"""


def S(page, name, proves, callouts, minc=1, note=None):
    return shot(page, "cirrocumulus", name, proves, callouts, software="Cirrocumulus 1.1.61 (local cirro launch)", driver=DRV, data=BM, note=note, min_callouts=minc)


def count(page):
    """Tag the header's cell count ('8,090 cells' or 'n / 8,090 cells')."""
    tagleaf(page, "count", "8,090 cells$", y1=90)
    try:
        return page.locator(COUNT).inner_text(timeout=1500)
    except Exception:
        return "NA"


def cleanup():
    d = os.path.expanduser("$DEMO_ROOT/_data")
    if os.path.exists(d + "/bm_demo.json"):
        os.remove(d + "/bm_demo.json")
    for f in glob.glob(d + "/results/*"):
        shutil.rmtree(f) if os.path.isdir(f) else os.remove(f)


def render(page):
    page.goto(URL)
    page.wait_for_timeout(8000)
    log("count:", count(page))
    S(page, "m00_plots_render.jpg", [pv("every_cell", "Y", f"Cirrocumulus 1.1.61 ({TODAY}): bm_demo renders all 8,090 cells in the X_umap embedding; the header counts every cell")],
      [(1, main_plot(page), "X_umap, all cells drawn"), (2, COUNT, "8,090 cells")], minc=2)


def setup(page):
    page.goto(URL)
    page.wait_for_timeout(7000)
    page.get_by_label("Embeddings").click()
    page.wait_for_timeout(500)
    page.click("[role=option]:has-text('X_draw_graph_fa')")
    page.keyboard.press("Escape")
    page.wait_for_timeout(3000)
    g = page.get_by_role("combobox", name="Genes/Features")
    g.click()
    g.fill("Mpo")
    page.wait_for_timeout(1500)
    page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    page.wait_for_timeout(4000)


def dblclick(page):
    setup(page)
    page.mouse.click(700, 1100)
    page.wait_for_timeout(3000)
    found = None
    for y in range(250, 700, 6):
        for x in range(600, 1050, 6):
            page.mouse.move(x, y)
            page.wait_for_timeout(15)
            t = page.evaluate(TIP)
            if t:
                found = (x, y, t)
                break
        if found:
            break
    log("tooltip at", found)
    if not found:
        return
    page.mouse.click(found[0], found[1])
    page.wait_for_timeout(1200)
    log("after single click:", count(page))
    page.mouse.dblclick(found[0], found[1])
    page.wait_for_timeout(2500)
    c = count(page)
    log("after dblclick:", c)
    g = gallery(page)
    S(page, "04_dblclick_selects_category_all_charts.jpg",
      [pv("focus", "N", f"Cirrocumulus 1.1.61 ({TODAY}): double-click selects the cell's whole category (no per-cell value); the selection then highlights in all charts"),
       pv("selection", "Y", "the category selection highlights in every gallery chart")],
      [(1, COUNT, f"category selected: {c}"), (2, main_plot(page), "double-clicked plot")] + [(i + 3, s, "gallery chart, selection highlighted") for i, s in enumerate(g)], minc=2)


def subset(page):
    page.goto(URL)
    page.wait_for_timeout(7000)
    cm = page.get_by_label("Cell Metadata").first      # the option click timed out on 2026-10-04 14:07;
    cm.click()                                          # type and pick it as de() does
    cm.type("highres_celltype", delay=60)
    page.wait_for_timeout(1200)
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    page.wait_for_timeout(800)
    page.keyboard.press("Escape")
    page.wait_for_timeout(3000)
    page.get_by_text("Ery P", exact=True).first.click()
    page.wait_for_timeout(3000)
    c = count(page)
    log("after Ery P:", c)
    lab = page.get_by_text("Filtered Marker Opacity", exact=True).first
    lab.scroll_into_view_if_needed()
    page.wait_for_timeout(800)
    sl = page.evaluate("""()=>[...document.querySelectorAll('[role=slider], input[type=range]')].map(s=>[s.getAttribute('aria-valuemin')||s.min, s.getAttribute('aria-valuemax')||s.max, s.getAttribute('aria-valuenow')||s.value])""")
    log("sliders (min, max, now):", sl)
    op = tagleaf(page, "fop", "^Filtered Marker Opacity$", up=1)
    sz = tagleaf(page, "fsz", "^Filtered Marker Size$", up=1)
    S(page, "h01_subset_filtered_marker_opacity_size.jpg",
      [pv("subset", "P", f"Cirrocumulus 1.1.61 ({TODAY}): a selection (here Ery P, {c}) can only dim or shrink the other cells (Filtered Marker Opacity / Size); no show-only-selection view and no recompute")],
      [(1, COUNT, f"selection: {c}"), (2, op, "Filtered Marker Opacity"), (3, sz, "Filtered Marker Size"), (4, main_plot(page), "unselected cells dimmed, still drawn")], minc=2)


def de(page):
    page.goto(URL)
    page.wait_for_timeout(7000)
    mc = page.get_by_label("Metadata Categories").first
    mc.click()
    mc.type("Age", delay=80)
    page.wait_for_timeout(1200)
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    page.wait_for_timeout(800)
    page.keyboard.press("Escape")
    page.get_by_role("button", name="GO").click()
    page.wait_for_timeout(1500)
    mi = page.locator("[role=menuitem]:visible")
    if mi.count() and not page.locator("[role=dialog]:visible").count():
        mi.first.click()
        page.wait_for_timeout(1000)
    page.locator("[role=dialog]:visible input").first.fill("matrix_check_age_one_vs_rest")
    page.get_by_role("button", name="Submit").click()
    page.wait_for_timeout(22000)
    page.get_by_role("tab", name="Results").click()
    page.wait_for_timeout(2000)
    b = page.get_by_text("matrix_check_age_one_vs_rest")
    if b.count():
        b.first.click()
        page.wait_for_timeout(7000)
    ps = plots(page)
    dots = [p for p in ps if p["tag"].lower() == "svg" and p["x"] >= 240 and p["y"] >= 0]
    log("svg candidates:", dots)
    page.screenshot(path=SCRATCH + "cirro_de_debug.jpg", type="jpeg", quality=60)
    dot = max(dots, key=lambda p: p["w"] * p["h"])["sel"] if dots else main_plot(page)
    S(page, "m10_de_results.jpg",
      [pv("de", "Y", f"Cirrocumulus 1.1.61 ({TODAY}): One vs. Rest DE on Age computed in the app; the Results tab shows a dot plot of the top features per group")],
      [(1, dot, "DE dot plot: top features per Age group"), (2, "text=matrix_check_age_one_vs_rest >> nth=0", "the DE job run in this session")], minc=1)


def steps(page, _):
    cleanup()
    page.set_viewport_size({"width": 1400, "height": 1250})
    page.set_default_timeout(20000)
    for name, f in [("render", render), ("subset", subset), ("dblclick", dblclick), ("de", de)]:
        step(name, lambda: f(page))
    cleanup()
    log("done")
