"""Re-capture, one session: UCSC portal p21 shots (m07, m11; steps of matrix_check.py portal()) and the iSEE focus
shots 01-04 (steps of isee/focus_check.py + focus_check_cell.py), each with a dom sidecar (demos/_bin/recap.py).
The iSEE shots were clips of a full page; here the window is scrolled so the viewport shows the same region.
Run: notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python <abs path of this file>"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import sys, time, subprocess, urllib.request
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from recap import snap, pv
from playwright.sync_api import sync_playwright
T0 = time.time()
S = f"{_SCRATCH}"
PORTAL = "https://cells.ucsc.edu/?ds=brain-spatial-omics+p21"
UW = dict(software="UCSC Cell Browser (cells.ucsc.edu portal)", driver="notes/comparison/demos/ucsc-cell-browser/recap_portal_isee.py",
          data="brain-spatial-omics/p21, Mouse P21 spatial RNA+ATAC (2,373 spots)")
IW = dict(software="iSEE 2.18.0 (Bioconductor 3.20)", driver="notes/comparison/demos/ucsc-cell-browser/recap_portal_isee.py",
          data="bm_demo_sce.rds (8,090 cells)")
def t(): return f"[{time.time()-T0:.0f}s]"
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:200])

def portal(b):
    ctx = b.new_context(viewport={"width": 1400, "height": 900}); p = ctx.new_page(); p.set_default_timeout(20000)
    p.add_init_script("try{localStorage.setItem('introShown','true')}catch(e){}")
    p.goto(PORTAL, timeout=90000); p.wait_for_timeout(13000); p.keyboard.press("Escape"); p.wait_for_timeout(300)
    print("layout:", p.evaluate("()=>{const s=document.querySelector('#tpLayoutCombo');return s?s.options[s.selectedIndex].text:null}"))
    snap(p, "ucsc-cell-browser", "m07_spatial_portal_p21.jpg",
         [pv("spatial", "Y", "Portal p21: the Spots layout places 2,373 spots in tissue coordinates"),
          pv("image", "Y", "The tissue image is drawn grey under the spots"),
          pv("hosted", "Y", "cells.ucsc.edu opened the dataset anonymously, no login or install")],
         [(1, "#mpCanvas, canvas", "spots on the tissue image"), (2, "#tpLayoutCombo + div, #tpLayoutCombo", "layout: Spots")], **UW)
    print(t())
    p.goto(PORTAL + "&gene=Mbp", timeout=90000); p.wait_for_timeout(11000); p.keyboard.press("Escape"); p.wait_for_timeout(300)
    snap(p, "ucsc-cell-browser", "m11_image_portal_p21_gene_on_tissue.jpg",
         [pv("image", "Y", "Colouring by Mbp keeps the tissue image visible under the spots")],
         [(1, "#mpCanvas, canvas", "Mbp over the tissue image"), (2, "#tpLegendBar", "legend: gene Mbp")], **UW)
    print(t()); ctx.close()

def isee(b):
    srv = subprocess.Popen([f"{_DEMO_ROOT}/_mamba/envs/rtools/bin/Rscript", f"{_REPO}/notes/comparison/demos/isee/focus_app.R"],
                           stdout=open(S + "/isee_srv.log", "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(90):
            try: urllib.request.urlopen("http://127.0.0.1:8902", timeout=2); break
            except Exception: time.sleep(1)
        print("isee up", t())
        p = b.new_page(viewport={"width": 1400, "height": 900}); p.set_default_timeout(20000)
        p.goto("http://127.0.0.1:8902", timeout=120000); p.wait_for_timeout(22000)
        top = lambda y: (p.evaluate(f"window.scrollTo(0,{y})"), p.wait_for_timeout(400))
        p.fill("#RowDataTable1 input[type=search]", "Mpo"); p.wait_for_timeout(2500)
        p.locator("#RowDataTable1 tbody tr td", has_text="Mpo").first.click(); p.wait_for_timeout(8000)
        top(60)
        snap(p, "isee", "01_gene_Mpo_recolours_two_panels.jpg",
             [pv("focus", "N", "Feature colouring: clicking Mpo in Row data table 1 recolours plot 1 (UMAP) and plot 2 (PCA); a column of the assay, not a relation row")],
             [(1, "#RowDataTable1 tbody tr.selected", "Mpo row clicked"), (2, "#ReducedDimensionPlot1", "plot 1 (UMAP): Mpo (logcounts)"),
              (3, "#ReducedDimensionPlot2", "plot 2 (PCA): Mpo (logcounts)")], **IW)
        print(t())
        p.fill("#ColumnDataTable1 input[type=search]", "TCAATTCAGTGAGGCT"); p.wait_for_timeout(2500)
        p.locator("#ColumnDataTable1 tbody tr td", has_text="Mature_Young_2#TCAATTCAGTGAGGCT").first.click(); p.wait_for_timeout(9000)
        y = p.evaluate("()=>document.getElementById('ColumnDataTable1').getBoundingClientRect().top + window.scrollY") - 50
        p.set_viewport_size({"width": 1400, "height": 620}); p.wait_for_timeout(1500); top(y)
        snap(p, "isee", "02_cell_4236_sample_name_highlight.jpg",
             [pv("focus", "N", "Clicking the cell's row sends it to plot 3 (Color by Sample name): an identity highlight of that one cell, no relation values")],
             [(1, "#ColumnDataTable1 tbody tr.selected", "cell Mature_Young_2#TCAATTCAGTGAGGCT-1"), (2, "#ReducedDimensionPlot3", "plot 3: that one cell marked")], **IW)
        p.set_viewport_size({"width": 1400, "height": 900}); p.wait_for_timeout(1500); top(0)
        print(t())
        img = p.locator("#ReducedDimensionPlot1 img").first; bb = img.bounding_box(); print("rd1", bb)
        x0, y0 = bb["x"] + bb["width"] * 0.12, bb["y"] + bb["height"] * 0.25
        p.mouse.move(x0, y0); p.mouse.down(); p.mouse.move(x0 + bb["width"] * 0.25, y0 + bb["height"] * 0.35, steps=12); p.mouse.up()
        p.wait_for_timeout(9000); top(60)
        snap(p, "isee", "03_brush_umap_highlights_in_pca.jpg",
             [pv("selection", "Y", "A brush on plot 1 (UMAP) highlights the same cells in plot 2 (PCA) and fades the rest")],
             [(1, "#ReducedDimensionPlot1", "brush on plot 1 (UMAP)"), (2, "#ReducedDimensionPlot2", "same cells highlighted in plot 2 (PCA)")], **IW)
        print(t())
        p.check("#ReducedDimensionPlot2_ColumnSelectionRestrict"); p.wait_for_timeout(8000); top(60)
        snap(p, "isee", "04_brush_restrict_in_pca.jpg",
             [pv("selection", "Y", "Restrict to selected columns in plot 2 drops every cell outside plot 1's brush")],
             [(1, "#ReducedDimensionPlot2", "plot 2 shows only the brushed cells"),
              (2, "#ReducedDimensionPlot2_ColumnSelectionRestrict >> xpath=..", "Restrict to selected columns")], **IW)
        print(t()); p.close()
    finally:
        srv.terminate(); srv.wait(timeout=20)
        subprocess.run([f"{_DEMO_ROOT}/isee/stop.sh"])

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    step("portal", lambda: portal(b))
    step("isee", lambda: isee(b))
    b.close()
print("done", t())
