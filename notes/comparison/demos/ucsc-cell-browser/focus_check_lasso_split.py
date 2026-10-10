import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
D=f"{_REPO}/notes/comparison/screens/ucsc-cell-browser/raw_"
def shot(page, n): page.screenshot(path=D+n+".jpg", type="jpeg", quality=70); print("shot", n)
def txt(page, sel, n=200):
    try: return page.locator(sel).first.inner_text(timeout=2000)[:n].replace("\n"," | ")
    except Exception as e: return "NA"
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:300])
def steps(page, S, url="http://127.0.0.1:8906/?ds=bm_demo", tag="v", gene="Mpo"):
    page.add_init_script("try{localStorage.setItem('introShown','true')}catch(e){}")
    page.goto(url, timeout=90000); page.wait_for_timeout(12000)
    page.keyboard.press("Escape"); page.wait_for_timeout(500)
    # 1. single cell hover/click (unsplit)
    found=None
    for y in range(120, 820, 25):
        for x in range(300, 1150, 25):
            page.mouse.move(x,y); page.wait_for_timeout(40)
            t = txt(page, "#tpMetaPanel", 400)
            if "Mature_" in t or "Young" in t or "Old" in t: found=(x,y); break
        if found: break
    print("hover hit", found)
    if found:
        shot(page, tag+"1_hover")
        page.mouse.click(*found); page.wait_for_timeout(2500); shot(page, tag+"2_click")
        print("META click:", txt(page, "#tpMetaPanel", 400)); print("count:", txt(page,"#tpCellCount",100), "|", txt(page,"#mpStatus",100))
    # 2. gene
    def g():
        page.click("#tpGeneTab, a:has-text('Gene')", timeout=3000); page.wait_for_timeout(1000)
        print("combo html:", page.evaluate("()=>{const e=document.getElementById('tpGeneCombo'); return e? (e.style.display+' '+e.className+' next:'+(e.nextElementSibling? e.nextElementSibling.className:'')):'none'}"))
        inp = page.locator("#tpGeneCombo + .selectize-control input, #tpGeneCombo-selectized").first
        inp.click(timeout=4000); page.keyboard.type(gene, delay=120); page.wait_for_timeout(3000)
        print("gene opts:", page.evaluate("()=>[...document.querySelectorAll('.selectize-dropdown .option')].filter(e=>e.offsetParent).map(e=>e.innerText).slice(0,5)"))
        page.keyboard.press("Enter"); page.wait_for_timeout(6000)
    step("gene", g); shot(page, tag+"3_gene")
    print("title:", txt(page, "#mpTitle", 100))
    # 3. split, then legend/lasso select in left pane
    def sp():
        page.mouse.click(5, 890); page.keyboard.press("t"); page.wait_for_timeout(5000)
    step("split", sp); shot(page, tag+"4_split")
    def las():
        page.click("#mpIconModeLasso", timeout=3000); page.wait_for_timeout(300)
        pts=[(420,300),(620,300),(620,520),(420,520),(420,300)]
        page.mouse.move(*pts[0]); page.mouse.down()
        for p in pts[1:]: page.mouse.move(*p, steps=12)
        page.mouse.up(); page.wait_for_timeout(4000)
    step("lasso", las); shot(page, tag+"5_lasso")
    print("count after lasso:", txt(page, "#tpCellCount", 100))
    # force redraw of both panes: zoom in/out button
    step("redraw", lambda: (page.click("#mpCtrlZoom100", timeout=3000), page.wait_for_timeout(3000)))
    shot(page, tag+"6_redraw")
    # click in right pane to make it active, then check
    page.mouse.click(1000, 860); page.wait_for_timeout(2000); shot(page, tag+"7_rightactive")
    print("count end:", txt(page, "#tpCellCount", 100))
