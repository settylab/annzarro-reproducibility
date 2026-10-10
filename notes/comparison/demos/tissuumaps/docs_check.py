"""TissUUmaps docs shot (raw capture): the static-export page (Sharing > Apache), which names the desktop menu item
File > Export to static webpage. Visual for the static column; the observed export itself was not kept as a shot."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import sys, time
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT = f"{_REPO}/notes/comparison/screens/tissuumaps/"
URL = "https://tissuumaps.github.io/TissUUmaps-docs/docs/sharing/apache.html"
def pv(c): return {"column": c, "mark": "?", "caption": "raw capture; verdict and caption pending review of the shot"}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    p = b.new_page(viewport={"width": 1400, "height": 900}); p.goto(URL, timeout=60000); time.sleep(3)
    path = OUT + "g01_static_DOCS_export_to_static_webpage.jpg"; p.screenshot(path=path, type="jpeg", quality=72)
    try:
        record(p, path, tool="tissuumaps", software="TissUUmaps 3 documentation (tissuumaps.github.io)", by="comparison-auditor",
               driver=__file__, data=None, proves=[pv("static")],
               callouts=[(1, "text=Export to static page", "menu > File > Export to static webpage")])
    except Exception as e:
        print("callout failed", str(e)[:120])
        record(p, path, tool="tissuumaps", software="TissUUmaps 3 documentation (tissuumaps.github.io)", by="comparison-auditor",
               driver=__file__, data=None, proves=[pv("static")], callouts=[])
    print("shot", path); b.close()
