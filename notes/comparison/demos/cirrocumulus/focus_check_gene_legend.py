import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
D=f"{_REPO}/notes/comparison/screens/cirrocumulus/raw_"
def shot(page, n): page.screenshot(path=D+n+".jpg", type="jpeg", quality=60); print("shot", n)
def steps(page, S):
    page.set_viewport_size({"width":1400,"height":1250})
    page.goto("http://127.0.0.1:8901/"); page.wait_for_timeout(7000)
    page.get_by_label("Embeddings").click(); page.wait_for_timeout(500)
    page.click("[role=option]:has-text('X_draw_graph_fa')"); page.keyboard.press("Escape"); page.wait_for_timeout(3000)
    g = page.get_by_role("combobox", name="Genes/Features"); g.click(); g.fill("Mpo"); page.wait_for_timeout(1500)
    page.keyboard.press("Enter"); page.keyboard.press("Escape"); page.wait_for_timeout(4000)
    shot(page, "c3_gene")
    # hover + click a single cell in main plot (dense area near yellow)
    page.mouse.move(880, 170); page.wait_for_timeout(1500); shot(page, "c3_hover")
    page.mouse.click(880, 170); page.wait_for_timeout(1500); shot(page, "c3_click")
    # make highres_celltype primary by clicking its chip
    page.click("text=highres_celltype >> nth=0"); page.wait_for_timeout(2500)
    shot(page, "c3_ct_primary")
    # click legend category
    page.click("text=Ery P", timeout=5000); page.wait_for_timeout(3000)
    shot(page, "c3_legend_sel")
    print(page.inner_text("body")[:200].replace("\n"," | "))
