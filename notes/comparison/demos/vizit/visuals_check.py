"""VizIt visuals (raw capture): the hosted PD5D home page and the install docs (hosted), and a click on a UMAP cell in
Gene View (focus): records the URL, the API calls and the other plots' data before and after the click."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import json, os, sys, time
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT = f"{_REPO}/notes/comparison/screens/vizit/"
SW = "VizIt v1.0.0 as deployed at pd5d.yale.edu (Parkinson's Cell Atlas)"; B = "https://pd5d.yale.edu"
D = "PD5D_MTG_snRNAseq"; DATA = "PD5D_MTG_snRNAseq (snRNA-seq), hosted"
def pv(c): return {"column": c, "mark": "?", "caption": "raw capture; verdict and caption pending review of the shot"}
def snap(p, name, cols, data, sw=SW):
    path = OUT + name; p.screenshot(path=path, type="jpeg", quality=72)
    record(p, path, tool="vizit", software=sw, by="comparison-auditor", driver=__file__, data=data, proves=[pv(c) for c in cols], callouts=[])
    print("shot", name, flush=True)
SIG = """() => [...document.querySelectorAll('.js-plotly-plot')].map(gd => JSON.stringify((gd.data||[]).map(t => [t.type, (t.x||[]).length, (t.marker&&t.marker.color&&t.marker.color.length)||0, (t.selectedpoints||null)])))"""
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    p = b.new_context(viewport={"width": 1400, "height": 1000}).new_page(); p.set_default_timeout(15000)
    p.goto(B + "/", timeout=90000); time.sleep(8); snap(p, "h01_hosted_pd5d_home.jpg", ["hosted"], "landing page")
    p.goto("https://thedonglab.github.io/VizIt/install/", timeout=60000); time.sleep(3)
    snap(p, "g01_hosted_DOCS_install.jpg", ["hosted"], None, sw="VizIt documentation (thedonglab.github.io/VizIt)")
    api = []
    p.on("requestfinished", lambda r: api.append(r.url.split("pd5d.yale.edu")[-1][:140]) if "/api/" in r.url else None)
    p.goto(f"{B}/views/geneview?dataset={D}&gene=SNCA", timeout=90000); time.sleep(10)
    for t in ["LOAD METADATA / REFRESH PLOTS", "REFRESH PLOTS", "LOAD PLOTS"]:
        if p.get_by_text(t).count():
            try: p.get_by_text(t).first.click(timeout=5000); break
            except Exception: pass
    time.sleep(25)
    before = {"url": p.url, "api": len(api), "plots": p.evaluate(SIG)}
    box = p.locator(".js-plotly-plot .nsewdrag").first.bounding_box()
    p.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5); time.sleep(6)
    after = {"url": p.url, "api_new": api[before["api"]:], "plots": p.evaluate(SIG)}
    print(json.dumps({"url_same": before["url"] == after["url"], "api_new": after["api_new"],
                      "plots_same": before["plots"] == after["plots"], "n_plots": len(before["plots"])}), flush=True)
    snap(p, "f04_focus_cell_click_no_change.jpg", ["focus"], DATA)
    b.close()
