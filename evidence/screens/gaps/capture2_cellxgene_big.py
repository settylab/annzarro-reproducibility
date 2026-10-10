"""CZ CELLxGENE Discover Explorer on large hosted datasets (evidence-curator, 2026-10-04): re-captures the focus shots 04-06
(Tabula Sapiens, 1,136,218 cells; steps of notes/comparison/demos/cellxgene/focus_check_explorer_gene.py and
focus_check_explorer_lasso.py) and the scale shots s01, s03 (mouse embryo timelapse, 11,441,407 cells; steps of
$DEMO_ROOT/_browser/probe_web.py, whose WebGL draw-call hook is reused so the shot can state how many points one
draw call drew). steps(page) for _focus_run.py (no local server):
  notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
      notes/comparison/demos/_focus_run.py none 0 evidence/screens/gaps/capture2_cellxgene_big.py [ts|big]
"""
import re
import sys

sys.path.insert(0, "evidence/screens/gaps")
sys.path.insert(0, "$DEMO_ROOT/_browser")
from capture2lib import SCRATCH, TODAY, banner, log, pv, shot, step  # noqa: E402

DRV = "evidence/screens/gaps/capture2_cellxgene_big.py"
SW = f"CZ CELLxGENE Discover Explorer (hosted, as served {TODAY})"
TS = "https://cellxgene.cziscience.com/e/53d208b0-2cfd-4366-9866-c3c6114081bc.cxg/"
EMBRYO = "https://cellxgene.cziscience.com/e/dcfd4feb-18a3-4b30-81d7-1b0c544a8ab3.cxg/"
E = "Explorer (hosted)"
COUNT = "text=/[0-9]+ of [0-9]+ cells/ >> nth=0"
try:
    from probe_web import INIT  # noqa: E402
except Exception as e:  # psutil missing in this venv: fall back to reading the hook out of the file
    src = open("$DEMO_ROOT/_browser/probe_web.py").read()
    INIT = src.split('INIT = r"""', 1)[1].split('"""', 1)[0]
    log("INIT read from file", str(e)[:60])


def tid(t):
    return f"[data-testid='{t}']"


def canvases(page):
    r = page.evaluate("""()=>{const c=[...document.querySelectorAll('canvas')].filter(e=>{const b=e.getBoundingClientRect();return b.width>150&&b.height>150});
      c.sort((a,b)=>b.getBoundingClientRect().width*b.getBoundingClientRect().height-a.getBoundingClientRect().width*a.getBoundingClientRect().height);
      return c.slice(0,3).map((e,i)=>{e.setAttribute('data-cap','cv'+i);const b=e.getBoundingClientRect();return [b.x,b.y,b.width,b.height].map(Math.round)})}""")
    log("  canvases", r)
    return [f"[data-cap='cv{i}']" for i in range(len(r))], r


def ready(page, n=36):
    for i in range(n):
        page.wait_for_timeout(5000)
        if page.locator(tid("layout-choice")).count() and page.locator("canvas").count() and page.locator(COUNT).count():
            log("ready after", (i + 1) * 5, "s")
            break
    page.wait_for_timeout(10000)
    page.keyboard.press("Escape")


def addgene(page, g):
    inp = page.locator(f"{tid('gene-search')} input")
    if inp.count() == 0:
        inp = page.locator(tid("gene-search"))
    inp.first.click()
    page.wait_for_timeout(800)
    inp.first.fill(g)
    page.wait_for_timeout(3000)
    page.locator(".bp3-menu-item, .bp4-menu-item, .bp5-menu-item, [role=option]").filter(has_text=re.compile("^" + g + "$")).first.click()
    page.wait_for_timeout(4000)


def lasso(page, box):
    x0, y0, x1, y1 = box
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    page.mouse.move(*pts[0])
    page.mouse.down()
    for x, y in pts[1:]:
        page.mouse.move(x, y, steps=12)
    page.mouse.up()


def count(page):
    try:
        return page.locator(COUNT).inner_text(timeout=3000)
    except Exception:
        return "NA"


def ts(page):
    D = "Tabula Sapiens, all cells (1,136,218 cells)"
    page.goto(TS, timeout=120000)
    ready(page)
    page.click(tid("side-panel-toggle"), timeout=6000)
    page.wait_for_timeout(15000)
    addgene(page, "MPO")
    page.click(tid("colorby-MPO"))
    page.wait_for_timeout(20000)
    cv, bb = canvases(page)
    S = lambda name, pr, cl: shot(page, "cellxgene", name, pr, cl, software=SW, driver=DRV, data=D, url=TS, min_callouts=2)
    S("04_explorer_mpo_on_main_and_side_panel.jpg",
      [pv("focus", "N", f"{E} ({TODAY}): feature colouring, not a focus: MPO colours the main UMAP and the side-panel embedding together")],
      [(1, cv[0], "main panel coloured by MPO"), (2, cv[1] if len(cv) > 1 else cv[0], "side panel coloured by MPO"), (3, tid("colorby-MPO"), "colour by MPO")])
    main = bb[0]
    page.click(tid("mode-lasso"), timeout=4000)
    cx, cy, w, h = main[0] + main[2] / 2, main[1] + main[3] / 2, main[2], main[3]
    lasso(page, (cx - w * 0.25, cy - h * 0.25, cx + w * 0.1, cy + h * 0.1))
    page.wait_for_timeout(15000)
    c1 = count(page)
    log("after main lasso:", c1)
    S("05_explorer_lasso_in_main_side_panel_unchanged.jpg",
      [pv("selection", "Y", f"{E} ({TODAY}): a lasso in the main panel sets the shared selection count ({c1}); the side panel keeps its colouring (no highlight drawn there)")],
      [(1, cv[0], "lasso in the main panel"), (2, cv[1] if len(cv) > 1 else cv[0], "side panel: no highlight"), (3, COUNT, c1)])
    if len(bb) > 1:
        sx, sy, sw, sh = bb[1]
        page.click(tid("mode-lasso"), timeout=4000)
        lasso(page, (sx + sw * 0.3, sy + sh * 0.3, sx + sw * 0.55, sy + sh * 0.55))
        page.wait_for_timeout(20000)
        c2 = count(page)
        log("after side lasso:", c2)
        S("06_explorer_lasso_in_side_panel_sets_shared_count.jpg",
          [pv("selection", "Y", f"{E} ({TODAY}): a lasso in the side panel replaces the main panel's lasso in one shared selection count ({c1}, then {c2})")],
          [(1, cv[1], "lasso drawn in the side panel"), (2, COUNT, f"shared counter: {c2} (was {c1})"), (3, cv[0], "main panel")])


def big(page):
    D = "Qiu et al. 2024 mouse embryo timelapse, whole dataset (11,441,407 cells)"
    ctx = page.context
    ctx.add_init_script(INIT + "\nwindow.__gl.expect = 11441407;")
    p = ctx.new_page()
    p.set_default_timeout(20000)
    p.goto(EMBRYO, wait_until="domcontentloaded", timeout=600000)
    for i in range(120):
        g = p.evaluate("window.__gl")
        if g and g.get("tFull") is not None:
            break
        p.wait_for_timeout(2000)
    p.keyboard.press("Escape")
    p.wait_for_timeout(4000)
    g = p.evaluate("window.__gl")
    log("gl:", g)
    c = count(p)
    cv, bb = canvases(p)
    banner(p, f"Driver measurement (WebGL draw-call hook of probe_web.py): largest single draw call = {g['max']:,} points; "
              f"first full draw {g['tFull'] / 1000:.1f} s after navigation; renderer {str(g.get('glinfo'))[:60]}", color="#1d2733")
    p.wait_for_timeout(500)
    S = lambda name, pr, cl: shot(p, "cellxgene", name, pr, cl, software=SW, driver=DRV, data=D, url=EMBRYO, min_callouts=2,
                                  note="The dark banner across the top is the driver's own measurement (a WebGL draw-call hook), overlaid on the page; it is not part of Explorer.")
    S("s01_scale_all_cells_drawn.jpg",
      [pv("every_cell", "Y", f"{E} ({TODAY}): all {g['max']:,} cells go out in one WebGL draw call ({c}); no downsampling or density mode")],
      [(1, COUNT, c), (2, cv[0], "every cell drawn as a point"), (3, "#gapbanner", f"one draw call: {g['max']:,} points")])
    p.evaluate("document.getElementById('gapbanner').remove()")
    p.locator(tid("colorby-cell_type")).first.click(timeout=20000)
    p.wait_for_timeout(8000)
    g2 = p.evaluate("window.__gl")
    banner(p, f"Driver measurement after colouring by cell_type: largest single draw call = {g2['max']:,} points", color="#1d2733")
    p.wait_for_timeout(500)
    S("s03_scale_recolour_meta.jpg",
      [pv("every_cell", "Y", f"{E} ({TODAY}): recoloured by cell_type, still all {g2['max']:,} cells in one draw call")],
      [(1, tid("colorby-cell_type"), "colour by cell_type"), (2, cv[0], "all cells recoloured"), (3, COUNT, count(p)), (4, "#gapbanner", "draw-call measurement")])
    p.close()


def steps(page, S_):
    page.set_default_timeout(20000)
    want = [a for a in sys.argv[4:] if a in ("ts", "big")] or ["ts", "big"]
    if "ts" in want:
        step("tabula sapiens", lambda: ts(page))
    if "big" in want:
        step("11M", lambda: big(page))
    page.screenshot(path=SCRATCH + "cxg_big_last.jpg", type="jpeg", quality=50)
    log("done")
