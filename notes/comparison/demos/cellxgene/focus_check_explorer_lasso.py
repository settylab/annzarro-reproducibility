import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
D=f"{_REPO}/notes/comparison/screens/cellxgene/raw_"
def shot(page, n): page.screenshot(path=D+n+".jpg", type="jpeg", quality=70); print("shot", n)
def lasso(page, box):
    x0,y0,x1,y1 = box
    pts=[(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]
    page.mouse.move(*pts[0]); page.mouse.down()
    for x,y in pts[1:]: page.mouse.move(x,y,steps=12)
    page.mouse.up()
def steps(page, S):
    page.goto("https://cellxgene.cziscience.com/e/53d208b0-2cfd-4366-9866-c3c6114081bc.cxg/", timeout=120000)
    for i in range(30):
        page.wait_for_timeout(5000)
        if page.evaluate("()=>document.querySelectorAll('[data-testid]').length")>30 and page.locator("canvas").count()>0: print("loaded", (i+1)*5); break
    page.wait_for_timeout(8000)
    page.mouse.click(1357, 778); page.wait_for_timeout(500)
    page.click("[data-testid='side-panel-toggle']", timeout=6000); page.wait_for_timeout(12000)
    # expand side panel? switch its layout
    try:
        page.mouse.click(680, 511); page.wait_for_timeout(1500)
        page.get_by_text("uncorrected_umap:", exact=False).last.click(timeout=4000); page.wait_for_timeout(15000)
        print("side layout switched")
    except Exception as e: print("side layout fail", str(e)[:150])
    page.mouse.click(1200, 600); page.wait_for_timeout(1500); page.keyboard.press("Escape"); page.wait_for_timeout(1000)
    shot(page, "e11_side_uncorrected")
    try: page.click("[data-testid='mode-lasso']", timeout=3000)
    except Exception as e: print("lasso mode", str(e)[:100])
    lasso(page, (670, 150, 780, 220)); page.wait_for_timeout(20000)
    shot(page, "e11_lasso")
    print("count:", page.locator("text=/of [0-9]+ cells/").first.inner_text(timeout=3000))
    page.mouse.move(820, 700); page.wait_for_timeout(2000); page.mouse.wheel(0, 1); page.wait_for_timeout(8000)
    shot(page, "e11_after_hover_side")
    # now lasso inside the side panel (small region), see whether main follows
    page.mouse.click(1200, 300); page.wait_for_timeout(3000)
    lasso(page, (700, 640, 780, 720)); page.wait_for_timeout(20000)
    shot(page, "e11_lasso_in_side")
    print("count2:", page.locator("text=/of [0-9]+ cells/").first.inner_text(timeout=3000))
    # zoom screenshot of side panel region
    page.screenshot(path=D+"e11_lasso_sidecrop.jpg", type="jpeg", quality=80, clip={"x":624,"y":488,"width":400,"height":400})
