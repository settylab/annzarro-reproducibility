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
def steps(page, S, url="http://127.0.0.1:8906/?ds=bm_demo", tag="w", gene="Mpo"):
    page.add_init_script("try{localStorage.setItem('introShown','true')}catch(e){}")
    page.goto(url, timeout=90000); page.wait_for_timeout(12000)
    page.keyboard.press("Escape"); page.wait_for_timeout(500)
    hit=None
    for y in range(110, 200, 6):
        for x in range(700, 1000, 6):
            page.mouse.click(x,y); page.wait_for_timeout(120)
            if "selected" in txt(page, "#tpCellCount", 100): hit=(x,y); break
        if hit: break
    print("click hit", hit); page.wait_for_timeout(2500)
    shot(page, tag+"1_cellclick")
    print("META:", txt(page, "#tpMetaPanel", 500)); print("count:", txt(page,"#tpCellCount",100), "| status:", txt(page,"#mpStatus",100))
    page.keyboard.press("Escape"); page.wait_for_timeout(300)
    def g():
        page.click("#tpGeneTab, a:has-text('Gene')", timeout=3000); page.wait_for_timeout(1000)
        inp = page.locator("#tpGeneCombo + .selectize-control input").first
        inp.click(timeout=4000); page.keyboard.type(gene, delay=150); page.wait_for_timeout(4000)
        opts = page.locator(".selectize-dropdown .option")
        print("opts:", [opts.nth(i).inner_text()[:20] for i in range(min(opts.count(),8))])
        for i in range(opts.count()):
            if opts.nth(i).inner_text().strip().split()[0]==gene: opts.nth(i).click(); break
        else: page.keyboard.press("Enter")
        page.wait_for_timeout(6000)
    step("gene", g)
    print("legend title:", txt(page, "#tpLegendTitle", 80))
    def sp():
        page.mouse.click(5, 890); page.keyboard.press("t"); page.wait_for_timeout(5000)
        page.get_by_text("Show on both sides").click(timeout=4000); page.wait_for_timeout(5000)
    step("split+both", sp)
    shot(page, tag+"2_gene_both_sides")
    print("legend title:", txt(page, "#tpLegendTitle", 80))
