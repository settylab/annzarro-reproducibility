"""UCSC Cell Browser, local static build (evidence-curator, 2026-10-04). steps(page) for _focus_run.py, which starts and stops
the demo server ($DEMO_ROOT/ucsc-cell-browser/start.sh, 127.0.0.1:8906):
  notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
      notes/comparison/demos/_focus_run.py ucsc-cell-browser 8906 evidence/screens/gaps/capture2_ucsc.py

h02 lazy Y: request log of opening ?ds=bm_demo&gene=Mpo; exprMatrix.bin is fetched with an HTTP Range (206), a few kB of
    the 111 MB matrix.
h03 subset Y: legend tick Neutrophil, then "Only show selected" hides every other cell (view only).
"""
import os
import sys
import urllib.parse

sys.path.insert(0, "evidence/screens/gaps")
import gaplib  # noqa: E402
from capture2lib import BY, TODAY, log, pv, shot, step, tag  # noqa: E402

gaplib.BY = BY
TOOL = "ucsc-cell-browser"
SW = "UCSC Cell Browser, cellbrowser 1.2.20 (local static build)"
DATA = "bm_demo.h5ad (8,090 cells)"
DRV = "evidence/screens/gaps/capture2_ucsc.py"
BASE = "http://127.0.0.1:8906/?ds=bm_demo"
STATUS = "#tpCellCount"
MATRIX = "$DEMO_ROOT/ucsc-cell-browser/html/bm_demo/exprMatrix.bin"


def txt(page, sel, n=200):
    try:
        return page.locator(sel).first.inner_text(timeout=1500)[:n].replace("\n", " | ")
    except Exception:
        return "NA"


def lazy(page):
    rows = []

    def onresp(r):
        try:
            rq = r.request
            hd = rq.headers
            body = r.headers.get("content-length", "?")
            rows.append((rq.resource_type, rq.method, urllib.parse.urlparse(r.url).path + (("?" + urllib.parse.urlparse(r.url).query) if urllib.parse.urlparse(r.url).query else ""),
                         hd.get("range", ""), r.status, body, r.headers.get("content-range", "")))
        except Exception as e:
            log("resp err", str(e)[:80])
    page.on("response", onresp)
    page.goto(BASE + "&gene=Mpo", timeout=60000)
    page.wait_for_timeout(9000)
    page.keyboard.press("Escape")
    page.remove_listener("response", onresp)
    data = [r for r in rows if "/bm_demo/" in r[2]]
    for r in data:
        log("REQ", r)
    size = os.path.getsize(MATRIX)
    hl = [i for i, r in enumerate(data) if "exprMatrix.bin" in r[2] and r[4] == 206]
    if not hl:
        log("no 206 on exprMatrix.bin: no shot")
        return
    rng = data[hl[0]]
    p2 = page.context.new_page()
    p2.set_viewport_size({"width": 1400, "height": 900})
    gaplib.table_shot(
        p2, tool=TOOL, name="h02_lazy_request_log_exprmatrix_range_206.jpg",
        title="Request log: UCSC Cell Browser fetches one gene with an HTTP Range request",
        sub=f"{SW}, served by a static file server with Range support on 127.0.0.1:8906; ?ds=bm_demo&amp;gene=Mpo opened {TODAY} "
            f"(Playwright request and response log, dataset files only). exprMatrix.bin is {size:,} bytes on disk.",
        header=["type", "method", "path", "Range (request)", "status", "bytes", "Content-Range"],
        rows=[[r[0], r[1], r[2][:70], r[3], r[4], r[5], r[6]] for r in data], hl=hl,
        note=f"Highlighted: the Mpo row of the expression matrix, {rng[5]} bytes by HTTP Range (206 Partial Content) out of {size:,}; "
             "the index exprMatrix.json, coordinates and metadata load whole.",
        proves=[pv("lazy", "Y", f"request log, UCSC Cell Browser cellbrowser 1.2.20 ({TODAY}): choosing Mpo fetches {rng[5]} bytes of the {size:,}-byte exprMatrix.bin by HTTP Range (206)")],
        callouts=[(1, f"#r{hl[0]}", f"exprMatrix.bin, Range {rng[3]}: 206, {rng[5]} bytes"), (2, "#note", "partial read of the matrix file")],
        software=SW, driver=DRV, data=DATA, url=BASE + "&gene=Mpo")
    p2.close()


def subset(page):
    page.goto(BASE, timeout=60000)
    page.wait_for_timeout(8000)
    page.keyboard.press("Escape")
    page.mouse.click(1209, 200)
    page.wait_for_timeout(2000)
    log("after legend checkbox:", txt(page, STATUS, 80))
    page.click("#tpOnlySel", timeout=4000)
    page.wait_for_timeout(2500)
    log("after only-show:", txt(page, STATUS, 80))
    log("buttons:", page.evaluate("()=>[...document.querySelectorAll('#tpToolbar button, button')].map(b=>b.id+':'+b.innerText.trim()).filter(s=>s.length>1).slice(0,30)"))
    cl = [(1, "#tpOnlySel", "Only show selected: the other cells are hidden"), (2, STATUS, "cells shown of 8.1k"), (3, "#mpCanvas", "only the selected cells drawn")]
    if page.locator("#tpHideSel").count():
        cl.append((4, "#tpHideSel", "Hide selected"))
    shot(page, TOOL, "h03_subset_only_show_selected.jpg",
         [pv("subset", "Y", f"UCSC Cell Browser cellbrowser 1.2.20 ({TODAY}): after a selection, 'Only show selected' restricts the plot to that subset (view only, nothing recomputed)"),
          pv("filters", "P", "the subset comes from a legend selection, not a table filter")],
         cl, software=SW, driver=DRV, data=DATA, url=BASE)


PORTAL = "https://cells.ucsc.edu/?ds=brain-spatial-omics+p21"
PW_ = dict(software="UCSC Cell Browser (cells.ucsc.edu portal)", driver=DRV, data="brain-spatial-omics/p21, Mouse P21 spatial RNA+ATAC (2,373 spots)")


def portal(page):
    """m07 re-capture (steps of notes/comparison/demos/ucsc-cell-browser/recap_portal_isee.py): box the layout and the image."""
    p = page.context.new_page()
    p.set_viewport_size({"width": 1400, "height": 900})
    p.add_init_script("try{localStorage.setItem('introShown','true')}catch(e){}")
    p.goto(PORTAL, timeout=90000)
    p.wait_for_timeout(13000)
    p.keyboard.press("Escape")
    p.wait_for_timeout(300)
    lay = p.evaluate("()=>{const s=document.querySelector('#tpLayoutCombo');return s?s.options[s.selectedIndex].text:null}")
    log("layout:", lay, "| widgets:", p.evaluate("()=>[...document.querySelectorAll('[id*=Layout],[id*=layout],[id*=mage]')].filter(e=>e.getBoundingClientRect().width>0).map(e=>e.id+':'+e.tagName+':'+Math.round(e.getBoundingClientRect().x)+','+Math.round(e.getBoundingClientRect().y)).slice(0,20)"))
    lsel = "#tpLayoutCombo_chosen" if p.locator("#tpLayoutCombo_chosen").count() else tag(p, "lay", "^" + (lay or "Spots") + "$", y1=200)
    img = tag(p, "img", "(?i)^(show )?(tissue )?image", y1=300)
    shot(p, TOOL, "m07_spatial_portal_p21.jpg",
         [pv("spatial", "Y", f"UCSC Cell Browser portal ({TODAY}): p21 opens in the '{lay}' layout, 2,373 spots placed in tissue coordinates"),
          pv("image", "Y", "the tissue image is drawn under the spots"),
          pv("hosted", "Y", "cells.ucsc.edu opened the dataset anonymously, no login or install")],
         [(1, "#mpCanvas", "spots in tissue coordinates over the tissue image"), (2, lsel, f"layout: {lay} (spatial coordinates)"), (3, img, "tissue image control")],
         min_callouts=2, url=PORTAL, **PW_)
    p.close()


def steps(page, S):
    page.set_default_timeout(15000)
    step("lazy", lambda: lazy(page))
    step("subset", lambda: subset(page))
    step("portal", lambda: portal(page))
    log("done")
