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
try:
    for _ in range(120):
        try: urllib.request.urlopen("http://127.0.0.1:8902", timeout=2); break
        except Exception: time.sleep(1)
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, channel="chromium")
        p = b.new_page(viewport={"width":1400,"height":1100})
        p.goto("http://127.0.0.1:8902", timeout=120000); p.wait_for_timeout(25000)
        opts = lambda i: p.evaluate("(i)=>{const s=$('#'+i)[0]; return s&&s.selectize?Object.keys(s.selectize.options):null}", i)
        print("RD3 sample sources:", opts("ReducedDimensionPlot3_ColorBySampleSource"))
        print("RD1 feature sources:", opts("ReducedDimensionPlot1_ColorByFeatureSource"))
        print("RD2 column selection sources:", opts("ReducedDimensionPlot2_ColumnSelectionSource"))
        p.fill("#ColumnDataTable1 input[type=search]", "TCAATTCAGTGAGGCT"); p.wait_for_timeout(3000)
        p.locator("#ColumnDataTable1 tbody tr td", has_text="Mature_Young_2#TCAATTCAGTGAGGCT").first.click(); p.wait_for_timeout(10000)
        p.locator("#ColumnDataTable1").scroll_into_view_if_needed()
        top = p.evaluate("()=>document.getElementById('ColumnDataTable1').getBoundingClientRect().top + window.scrollY") - 50
        p.screenshot(path=OUT+"02_cell_4236_sample_name_highlight.jpg", type="jpeg", quality=70, full_page=True,
                     clip={"x":0,"y":top,"width":1400,"height":620})
        b.close()
finally:
    srv.terminate(); srv.wait(timeout=20)
    subprocess.run([f"{_DEMO_ROOT}/isee/stop.sh"])
