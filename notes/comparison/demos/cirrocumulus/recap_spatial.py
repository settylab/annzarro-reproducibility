"""Re-capture of m07/m11 (matrix_check_spatial.py) on the lymph node example, with dom sidecars. Run via recap_session_b.sh."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recap_lib import *
DRV = "notes/comparison/demos/cirrocumulus/recap_spatial.py"
def S(page, name, proves, callouts): snap(page, name, proves, callouts, DRV, data=LYMPH)
def steps(page, _):
    page.set_viewport_size({"width": 1400, "height": 1100})
    page.goto("http://127.0.0.1:8901/"); page.wait_for_timeout(9000)
    page.get_by_label("Embeddings").first.click(); page.wait_for_timeout(1000)
    print("embeddings:", page.evaluate("()=>[...document.querySelectorAll('[role=option]')].map(e=>e.innerText.trim())"))
    S(page, "m07_spatial_embeddings_menu.jpg", [pv("spatial", "Y", "With --spatial the dataset gets an embedding tissue_hires")], [(1, LISTBOX, "Embeddings: tissue_hires"), (2, "[role=option]:has-text('tissue_hires')", "tissue_hires")])
    o = page.locator("[role=option]:has-text('tissue_hires')")
    if o.count(): o.first.click(); page.wait_for_timeout(500)
    page.keyboard.press("Escape"); page.wait_for_timeout(4000)
    S(page, "m07_spatial_tissue_hires_clusters.jpg", [pv("spatial", "Y", "Spots drawn in tissue coordinates (tissue_hires)")], [(1, main_plot(page), "spots in tissue coordinates")])
    try: page.locator("text=tissue_hires >> nth=0").click(timeout=3000); page.wait_for_timeout(3000)
    except Exception as e: print("primary click", str(e)[:100])
    c = page.get_by_role("combobox", name="Genes/Features"); c.click(); c.fill("CR2"); page.wait_for_timeout(1500)
    page.keyboard.press("Enter"); page.keyboard.press("Escape"); page.wait_for_timeout(5000)
    S(page, "m11_image_cr2_spots_on_he.jpg", [pv("image", "Y", "The H&E tissue_hires image is drawn under the spots; CR2 colouring on top")], [(1, main_plot(page), "CR2 spots over H&E")])
