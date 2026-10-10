import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import subprocess, time, urllib.request
from playwright.sync_api import sync_playwright
S=f"{_SCRATCH}"
OUT=f"{_REPO}/notes/comparison/screens/isee/"
srv = subprocess.Popen([f"{_DEMO_ROOT}/_mamba/envs/rtools/bin/Rscript", f"{_REPO}/notes/comparison/demos/isee/focus_app.R"],
                       stdout=open(S+"/isee_srv.log","w"), stderr=subprocess.STDOUT)
def clip(p, y0, h, name):
    p.screenshot(path=OUT+name, type="jpeg", quality=70, full_page=True, clip={"x":0,"y":y0,"width":1400,"height":h})
try:
    for _ in range(120):
        try: urllib.request.urlopen("http://127.0.0.1:8902", timeout=2); break
        except Exception: time.sleep(1)
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, channel="chromium")
        p = b.new_page(viewport={"width":1400,"height":900})
        p.goto("http://127.0.0.1:8902", timeout=120000); p.wait_for_timeout(25000)
        print("sample sources:", p.eval_on_selector_all("#ReducedDimensionPlot3_ColorBySampleSource option, #ReducedDimensionPlot3_ColorBySampleSource + div .option", "els=>els.map(e=>e.textContent)"))
        print("RD4 colour-by column data options:", p.evaluate("()=>{const s=$('#ReducedDimensionPlot4_ColorByColumnData')[0]; return s&&s.selectize?Object.keys(s.selectize.options):null}"))
        # (a2) gene focus: Mpo in Row data table 1
        p.fill("#RowDataTable1 input[type=search]", "Mpo"); p.wait_for_timeout(3000)
        rows = p.locator("#RowDataTable1 tbody tr")
        print("gene rows:", [rows.nth(i).inner_text()[:20] for i in range(min(rows.count(),5))])
        p.locator("#RowDataTable1 tbody tr td", has_text="Mpo").first.click(); p.wait_for_timeout(9000)
        clip(p, 60, 900, "01_gene_Mpo_recolours_two_panels.jpg")
        # single-cell: focus cell 4236 in Column data table 1
        p.fill("#ColumnDataTable1 input[type=search]", "TCAATTCAGTGAGGCT"); p.wait_for_timeout(3000)
        rows = p.locator("#ColumnDataTable1 tbody tr")
        print("cell rows:", [rows.nth(i).inner_text()[:50] for i in range(min(rows.count(),5))])
        p.locator("#ColumnDataTable1 tbody tr td", has_text="Mature_Young_2#TCAATTCAGTGAGGCT").first.click(); p.wait_for_timeout(9000)
        y = p.locator("#ColumnDataTable1").bounding_box()["y"] - 60
        clip(p, y, 900, "02_cell_4236_sample_name_highlight.jpg")
        # (b) brush in RD1 -> RD2 (PCA) highlights the same cells
        p.evaluate("window.scrollTo(0,0)")
        img = p.locator("#ReducedDimensionPlot1 img").first; bb = img.bounding_box(); print("rd1", bb)
        x0, y0 = bb["x"]+bb["width"]*0.12, bb["y"]+bb["height"]*0.25
        p.mouse.move(x0, y0); p.mouse.down(); p.mouse.move(x0+bb["width"]*0.25, y0+bb["height"]*0.35, steps=12); p.mouse.up()
        p.wait_for_timeout(10000)
        clip(p, 60, 900, "03_brush_umap_highlights_in_pca.jpg")
        p.check("#ReducedDimensionPlot2_ColumnSelectionRestrict"); p.wait_for_timeout(9000)
        clip(p, 60, 900, "04_brush_restrict_in_pca.jpg")
        print("RD2 info:", p.inner_text("#ReducedDimensionPlot2_INTERNAL_PanelMultiSelectInfo")[:200] if p.locator("#ReducedDimensionPlot2_INTERNAL_PanelMultiSelectInfo").count() else "-")
        b.close()
finally:
    srv.terminate(); srv.wait(timeout=20)
    subprocess.run([f"{_DEMO_ROOT}/isee/stop.sh"])
