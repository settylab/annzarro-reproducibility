import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
D=f"{_REPO}/notes/comparison/screens/ucsc-cell-browser/raw_"
def shot(page, n): page.screenshot(path=D+n+".jpg", type="jpeg", quality=70); print("shot", n)
def txt(page, sel, n=200):
    try: return page.locator(sel).first.inner_text(timeout=2000)[:n].replace("\n"," | ")
    except Exception as e: return "NA"
def steps(page, S):
    page.add_init_script("try{localStorage.setItem('introShown','true')}catch(e){}")
    page.goto("http://127.0.0.1:8906/?ds=bm_demo&gene=Mpo", timeout=90000); page.wait_for_timeout(12000)
    page.keyboard.press("Escape"); page.wait_for_timeout(500)
    print("legend:", txt(page, "#tpLegendTitle", 80)); shot(page, "y1_gene")
    page.mouse.click(5, 890); page.keyboard.press("t"); page.wait_for_timeout(5000)
    shot(page, "y2_split_gene_one_side")
    try:
        page.get_by_text("Show on both sides").click(timeout=4000); page.wait_for_timeout(5000)
    except Exception as e: print("both fail", str(e)[:200])
    shot(page, "y3_gene_both_sides"); print("legend:", txt(page, "#tpLegendTitle", 80)); print("url:", page.url)
