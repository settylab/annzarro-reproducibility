import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
D=f"{_REPO}/notes/comparison/screens/cirrocumulus/raw_"
def shot(page, n): page.screenshot(path=D+n+".jpg", type="jpeg", quality=60); print("shot", n)
TIP = """()=>{for(const d of document.querySelectorAll('div')){if(d.style.zIndex=='9999999'&&d.style.visibility!='hidden'&&d.innerText.trim())return d.innerText.trim()}return null}"""
def steps(page, S):
    page.set_viewport_size({"width":1400,"height":1250})
    page.goto("http://127.0.0.1:8901/"); page.wait_for_timeout(7000)
    page.get_by_label("Embeddings").click(); page.wait_for_timeout(500)
    page.click("[role=option]:has-text('X_draw_graph_fa')"); page.keyboard.press("Escape"); page.wait_for_timeout(3000)
    g = page.get_by_role("combobox", name="Genes/Features"); g.click(); g.fill("Mpo"); page.wait_for_timeout(1500)
    page.keyboard.press("Enter"); page.keyboard.press("Escape"); page.wait_for_timeout(4000)
    # make highres_celltype on FA primary by clicking its gallery chart (2nd)
    page.mouse.click(700, 1100); page.wait_for_timeout(3000); shot(page, "c4_primary")
    found=None
    for y in range(250, 700, 6):
        for x in range(600, 1050, 6):
            page.mouse.move(x,y); page.wait_for_timeout(15)
            t = page.evaluate(TIP)
            if t: found=(x,y,t); break
        if found: break
    print("tooltip at", found)
    if found:
        shot(page, "c4_tooltip")
        page.mouse.click(found[0], found[1]); page.wait_for_timeout(1200); shot(page, "c4_singleclick")
        print("after single click:", page.inner_text("body")[:40].replace("\n"," "))
        page.mouse.dblclick(found[0], found[1]); page.wait_for_timeout(2500); shot(page, "c4_dblclick")
        print("after dblclick:", page.inner_text("body")[:40].replace("\n"," "))
