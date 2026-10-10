import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import re
D=f"{_REPO}/notes/comparison/screens/cellxgene/raw_"
def shot(page, n): page.screenshot(path=D+n+".jpg", type="jpeg", quality=70); print("shot", n)
def T(page,tid):
    try: return page.inner_text(f"[data-testid='{tid}']", timeout=2000)[:120].replace("\n"," ")
    except Exception as e: return "ERR"
def ids(page, pat):
    return page.evaluate("(p)=>[...new Set([...document.querySelectorAll('[data-testid]')].map(e=>e.getAttribute('data-testid')).filter(s=>new RegExp(p).test(s)))]", pat)
def addgene(page, g):
    inp = page.locator("[data-testid='gene-search'] input")
    if inp.count()==0: inp = page.locator("[data-testid='gene-search']")
    inp.first.click(); page.wait_for_timeout(800)
    inp.first.fill(g); page.wait_for_timeout(3000)
    items = page.locator(".bp3-menu-item, .bp4-menu-item, .bp5-menu-item, [role=option]")
    txt = [items.nth(i).inner_text() for i in range(min(items.count(),6))]
    print("menu", txt)
    items.filter(has_text=re.compile("^"+g+"$")).first.click(); page.wait_for_timeout(4000)
def lasso(page, box):
    x0,y0,x1,y1 = box
    pts=[(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]
    page.mouse.move(*pts[0]); page.mouse.down()
    for x,y in pts[1:]: page.mouse.move(x,y,steps=12)
    page.mouse.up(); page.wait_for_timeout(4000)
def annotate(page):
    page.goto("http://127.0.0.1:8903/"); page.wait_for_timeout(12000)
    page.locator(".bp3-dialog input").first.fill("focuscheck"); page.click("text=Create user generated data directory"); page.wait_for_timeout(1500)
    addgene(page, "Mpo"); addgene(page, "Elane")
    print("ids", ids(page, "Mpo|Elane"))
    page.click("[data-testid='colorby-Mpo']"); page.wait_for_timeout(3000)
    shot(page, "x5_gene")
    for t in ids(page, "Mpo|Elane"):
        if re.search("plot-x.*Mpo", t) or re.search("plot-y.*Elane", t):
            page.click(f"[data-testid='{t}']"); page.wait_for_timeout(1500)
    page.wait_for_timeout(3000); shot(page, "x5_scatter")
    page.mouse.click(820, 650); page.wait_for_timeout(1500); shot(page, "x5_click")
    print("after click cellset1:", T(page,"cellset-count-1"), "| footer", page.locator("text=/out of 8090/").first.inner_text())
    page.click("[data-testid='mode-lasso']"); page.wait_for_timeout(300)
    lasso(page, (640,150,960,300))
    shot(page, "x5_lasso")
    print("after lasso cellset1:", T(page,"cellset-count-1"), "| footer", page.locator("text=/out of 8090/").first.inner_text())
def explorer(page):
    page.goto("https://cellxgene.cziscience.com/e/53d208b0-2cfd-4366-9866-c3c6114081bc.cxg/", timeout=120000)
    for i in range(30):
        page.wait_for_timeout(5000)
        n = page.evaluate("()=>document.querySelectorAll('[data-testid]').length")
        if n>30 and page.locator("canvas").count()>0: print("loaded after", (i+1)*5, "s"); break
    page.wait_for_timeout(8000)
    try: page.mouse.click(1357, 778); page.wait_for_timeout(500)
    except Exception: pass
    shot(page, "e7_load")
    try:
        page.click("[data-testid='side-panel-toggle']", timeout=4000); page.wait_for_timeout(15000); print("side panel opened")
    except Exception as e: print("no side panel", str(e)[:80])
    shot(page, "e7_side")
    try:
        addgene(page, "MPO")
        page.click("[data-testid='colorby-MPO']"); page.wait_for_timeout(20000)
    except Exception as e: print("gene fail", str(e)[:200])
    shot(page, "e7_gene")
    cs = page.locator("canvas"); bb=[cs.nth(i).bounding_box() for i in range(cs.count())]
    bb=[b for b in bb if b and b['width']>200]
    print("canvases", [(round(b['x']),round(b['y']),round(b['width']),round(b['height'])) for b in bb])
    try: page.click("[data-testid='mode-lasso']", timeout=3000)
    except Exception as e: print("lasso mode", str(e)[:80])
    big = sorted(bb, key=lambda b:b['x'])[0]
    cx, cy, w, h = big['x']+big['width']/2, big['y']+big['height']/2, big['width'], big['height']
    lasso(page, (cx-w*0.25, cy-h*0.25, cx+w*0.1, cy+h*0.1)); page.wait_for_timeout(15000)
    shot(page, "e7_lasso")
    print("E after lasso cellset1:", T(page,"cellset-count-1"))
    page.mouse.click(cx+w*0.3, cy+h*0.3); page.wait_for_timeout(4000); shot(page, "e7_click")
    print("E after click cellset1:", T(page,"cellset-count-1"))
    print("E counts text:", page.locator("text=/of [0-9,]+ cells/").first.inner_text(timeout=3000))
def steps(page, S):
    try: explorer(page)
    except Exception as e: print("EXPLORER FAIL", str(e)[:300]); shot(page, "e_err")
