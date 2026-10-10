"""ShinyCell2 online showcase: open the 'Spatial Data' menu, then 'Side-by-side Spatial' and the spatial violin tab."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
from playwright.sync_api import sync_playwright
OUT = f"{_REPO}/notes/comparison/screens/shinycell/"
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium"); p = b.new_page(viewport={"width": 1400, "height": 900})
    p.goto("https://shinycell.ouyanglab.com/", timeout=120000); p.wait_for_timeout(12000)
    def go(menu, item):
        p.locator("ul.navbar-nav a.dropdown-toggle", has_text=menu).first.click(); p.wait_for_timeout(800)
        p.locator(f"ul.dropdown-menu a[data-value='{item}']:visible").first.click(); p.wait_for_timeout(20000)
    go("Spatial Data", "Side-by-side Spatial")
    print("spatial labels:", p.eval_on_selector_all(".tab-pane.active label", "els=>els.map(e=>e.textContent.trim()).filter(t=>t).slice(0,20)"))
    p.screenshot(path=OUT + "m07_m11_shinycell2_spatial_image_underlay.jpg", type="jpeg", quality=70, full_page=True)
    go("Spatial Data", "Violinplot / Boxplot")
    print("violin labels:", p.eval_on_selector_all(".tab-pane.active label", "els=>els.map(e=>e.textContent.trim()).filter(t=>t).slice(0,30)"))
    p.screenshot(path=OUT + "m10_shinycell2_violin_test_option.jpg", type="jpeg", quality=70, full_page=True)
    b.close()
