"""Single Cell Portal focus re-capture (evidence-curator, 2026-10-04): shots 01-07 of notes/comparison/single-cell-portal.md's
Focus table on SCP1671 (human lactation, 49,310 cells), not logged in, under their existing filenames with DOM sidecars (the
2026-10-03 driver did not survive; page steps follow notes/comparison/demos/single-cell-portal/matrix_check_fix2.py). Run under
notes/comparison/demos/scale_probe/gap_run.sh with benchmark/scale/ceiling/.venv/bin/python <this>.

01 Explore default and its Options; 05 hover label; 07 a click changes nothing; 02 DE panel, B cells, click CD74: scatter
recolours; 06 the Distribution tab for CD74; 03 Plotly lasso in the CD74 scatter stays in that plot; 04 Filter plotted cells,
macrophage unticked: both scatters grey those cells.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capture2lib import SCRATCH, TODAY, log, pv, shot, step, tag  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRV = "evidence/screens/gaps/capture2_scp.py"
SW = "Single Cell Portal 1.20.0 (singlecell.broadinstitute.org)"
DATA = "SCP1671, human lactation (49,310 cells; All Cells UMAP)"
ST = "https://singlecell.broadinstitute.org/single_cell/study/SCP1671"
P = f"SCP 1.20.0 ({TODAY})"
PLOT = ".js-plotly-plot"


def S(page, name, proves, callouts, minc=2, note=None):
    return shot(page, "single-cell-portal", name, proves, callouts, software=SW, driver=DRV, data=DATA, url=page.url, note=note, min_callouts=minc)


def plots(page):
    r = page.evaluate("""()=>{const ps=[...document.querySelectorAll('.js-plotly-plot')].filter(e=>{const b=e.getBoundingClientRect();return b.width>200&&b.height>200});
      ps.sort((a,b)=>a.getBoundingClientRect().x-b.getBoundingClientRect().x);
      return ps.map((e,i)=>{e.setAttribute('data-cap','plot'+i);const b=e.getBoundingClientRect();return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]})}""")
    log("  plots", r)
    return [f"[data-cap='plot{i}']" for i in range(len(r))]


def find_point(page, sel):
    """Hover over the plot on a grid until a Plotly hover label appears; returns (x, y, text)."""
    b = page.locator(sel).bounding_box()
    for fy in [i / 20 for i in range(4, 17)]:
        for fx in [i / 20 for i in range(4, 17)]:
            x, y = b["x"] + b["width"] * fx, b["y"] + b["height"] * fy
            page.mouse.move(x, y)
            page.wait_for_timeout(60)
            t = page.locator(".hoverlayer .hovertext")
            if t.count():
                return x, y, t.first.inner_text()
    return None


def explore(page):
    page.goto(ST + "#study-visualize", timeout=90000)
    time.sleep(18)
    ps = plots(page)
    opts = tag(page, "opts", "^Clustering", minh=200)
    S(page, "01_explore_default.jpg",
      [pv("focus", "N", f"{P}: Explore holds cluster, annotation and expression views only; no control takes a cell or gene as an index into a pairwise matrix (none exists)")],
      [(1, ps[0] if ps else PLOT, "cluster UMAP (All Cells UMAP)"), (2, opts, "Options: Clustering, Annotation, ... no pairwise matrix")])
    hit = find_point(page, ps[0] if ps else PLOT)
    log("hover", hit)
    if hit:
        S(page, "05_cell_hover.jpg",
          [pv("focus", "N", f"{P}: hovering a point shows a Plotly label (coordinates, cell name, annotation); nothing else changes")],
          [(1, ".hoverlayer .hovertext >> nth=0", "hover label: " + hit[2].replace("\n", " ")[:50]), (2, ps[0] if ps else PLOT, "cluster UMAP")])
        u0 = page.url
        page.mouse.click(hit[0], hit[1])
        page.wait_for_timeout(3000)
        page.mouse.move(5, 990)
        page.wait_for_timeout(800)
        log("url same after click:", page.url == u0)
        S(page, "07_cell_click_no_effect.jpg",
          [pv("focus", "N", f"{P}: a click on a cell changes nothing: same URL, same plots, no selection")],
          [(1, ps[0] if ps else PLOT, "clicked a point: nothing changes"), (2, opts, "Options unchanged")])


def de(page):
    page.goto(ST + "#study-visualize", timeout=90000)
    time.sleep(16)
    page.get_by_role("button", name="Differential expression").first.click()
    time.sleep(4)
    inp = page.locator("[id^=react-select][id$=-input]")
    inp.last.click(force=True)
    inp.last.fill("B cells")
    time.sleep(1)
    page.keyboard.press("Enter")
    time.sleep(8)
    row = page.locator("tr.de-gene-row:has-text('CD74')").first
    log("de rows", page.locator("tr.de-gene-row").count(), "CD74 row", page.locator("tr.de-gene-row:has-text('CD74')").count())
    row.locator("input[type=radio], input").first.click(force=True)
    time.sleep(12)
    ps = plots(page)
    row.evaluate("e=>e.setAttribute('data-cap','cd74')")
    S(page, "02_de_gene_CD74_click_recolours_scatter.jpg",
      [pv("focus", "N", f"{P}: clicking CD74 in the precomputed DE table (B cells) runs a gene search: the scatter tab becomes a CD74 expression UMAP beside the cluster UMAP; a column of the matrix, not a relation row")],
      [(1, "[data-cap='cd74']", "CD74 picked in the DE table"), (2, ps[0] if ps else PLOT, "CD74 expression UMAP"), (3, ps[1] if len(ps) > 1 else PLOT, "reference cluster UMAP")])
    page.get_by_text("Distribution", exact=True).first.click()
    time.sleep(8)
    ps = plots(page)
    S(page, "06_de_gene_CD74_distribution_tab.jpg",
      [pv("focus", "N", f"{P}: the Distribution tab shows CD74 violins per cell type, driven by the same gene search (feature colouring, not a focus)")],
      [(1, ps[0] if ps else PLOT, "CD74 violins per cell type"), (2, "text=Distribution >> nth=0", "Distribution tab")])


def lasso_and_filter(page):
    page.goto(ST + "?genes=CD74#study-visualize", timeout=90000)
    time.sleep(16)
    ps = plots(page)
    if len(ps) < 2:
        log("fewer than two scatters")
        return
    b = page.locator(ps[0]).bounding_box()
    page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    time.sleep(1)
    page.locator(ps[0] + " [data-title='Lasso Select']").first.click()
    time.sleep(1)
    cx, cy, w, h = b["x"] + b["width"] * 0.5, b["y"] + b["height"] * 0.5, b["width"], b["height"]
    pts = [(cx - w * 0.2, cy - h * 0.2), (cx + w * 0.15, cy - h * 0.2), (cx + w * 0.15, cy + h * 0.15), (cx - w * 0.2, cy + h * 0.15), (cx - w * 0.2, cy - h * 0.2)]
    page.mouse.move(*pts[0])
    page.mouse.down()
    for q in pts[1:]:
        page.mouse.move(*q, steps=15)
    page.mouse.up()
    time.sleep(4)
    sel = page.evaluate("""()=>[...document.querySelectorAll('.js-plotly-plot')].map(g=>(g.data||[]).reduce((n,t)=>n+((t.selectedpoints||[]).length||0),0))""")
    log("selected points per plot:", sel)
    S(page, "03_lasso_in_gene_scatter_not_in_cluster_scatter.jpg",
      [pv("selection", "Y", f"{P}: caveat to the Y: a Plotly lasso in the CD74 scatter selects {sel[0] if sel else '?'} points in that plot only; the cluster scatter carries no selection. The cross-plot selection is the facet filter (shot 04)")],
      [(1, ps[0], f"lasso in the CD74 scatter ({sel[0] if sel else '?'} points)"), (2, ps[1], "cluster scatter: no selection")])
    page.get_by_role("button", name="Filter plotted cells").first.click()
    time.sleep(3)
    page.locator("input[name*='macrophage']").first.click()
    time.sleep(10)
    ps = plots(page)
    leg = tag(page, "filtered", "^--Filtered--")
    page.locator("input[name*='macrophage']").first.evaluate("e=>e.setAttribute('data-cap','macro')")
    S(page, "04_filter_macrophage_off_both_scatters.jpg",
      [pv("selection", "Y", f"{P}: 'Filter plotted cells', macrophage unticked, greys those cells in both the CD74 scatter and the cluster scatter at once"),
       pv("subset", "Y", "the facet filter restricts what every plot shows to the chosen cells (view only)")],
      [(1, "[data-cap='macro']", "Cell type: macrophage unticked"), (2, ps[0] if ps else PLOT, "CD74 scatter: macrophages greyed"), (3, ps[1] if len(ps) > 1 else PLOT, "cluster scatter: same cells greyed"),
       (4, leg, "legend: --Filtered--")])


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    p = b.new_page(viewport={"width": 1400, "height": 1000})
    p.set_default_timeout(15000)
    for name, f in [("explore", explore), ("de", de), ("lasso_filter", lasso_and_filter)]:
        step(name, lambda: f(p))
        p.screenshot(path=SCRATCH + f"scp_after_{name}.jpg", type="jpeg", quality=50)
    b.close()
log("done")
