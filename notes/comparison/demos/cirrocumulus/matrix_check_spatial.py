"""Matrix-mark screenshots for Cirrocumulus spatial + image underlay: repo example V1_Human_Lymph_Node
(cirrocumulus src docs/V1_Human_Lymph_Node.zip, unzipped to $DEMO_ROOT/cirrocumulus/lymph),
launched with `cirro launch V1_Human_Lymph_Node.h5ad --spatial spatial` on 8901. See matrix_check.sh."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
D = f"{_REPO}/notes/comparison/screens/cirrocumulus/"
def shot(page, n): page.screenshot(path=D + n + ".jpg", type="jpeg", quality=70); print("shot", n)
def steps(page, S):
    page.set_viewport_size({"width": 1400, "height": 1100})
    page.goto("http://127.0.0.1:8901/"); page.wait_for_timeout(9000)
    page.get_by_label("Embeddings").first.click(); page.wait_for_timeout(1000)
    print("embeddings:", page.evaluate("()=>[...document.querySelectorAll('[role=option]')].map(e=>e.innerText.trim())"))
    shot(page, "m07_spatial_embeddings_menu")
    o = page.locator("[role=option]:has-text('tissue_hires')")
    if o.count(): o.first.click(); page.wait_for_timeout(500)
    page.keyboard.press("Escape"); page.wait_for_timeout(4000)
    shot(page, "m07_spatial_tissue_hires_clusters")
    try:
        page.locator("text=tissue_hires >> nth=0").click(timeout=3000); page.wait_for_timeout(3000)
    except Exception as e: print("primary click", str(e)[:100])
    c = page.get_by_role("combobox", name="Genes/Features"); c.click(); c.fill("CR2"); page.wait_for_timeout(1500)
    page.keyboard.press("Enter"); page.keyboard.press("Escape"); page.wait_for_timeout(5000)
    shot(page, "m11_image_cr2_spots_on_he")
