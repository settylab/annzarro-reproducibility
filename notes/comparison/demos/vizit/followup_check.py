"""VizIt follow-up (raw capture, hosted pd5d.yale.edu): Spatial Tx View with the H&E switch on; Cluster View with a
cluster chosen (marker panel); Gene View UMAP with its plot toolbar shown (where a selection tool would be)."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import json, sys, time
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT = f"{_REPO}/notes/comparison/screens/vizit/"
SW = "VizIt v1.0.0 as deployed at pd5d.yale.edu (Parkinson's Cell Atlas)"; B = "https://pd5d.yale.edu"
LOG = {}
def pv(c): return {"column": c, "mark": "?", "caption": "raw capture; verdict and caption pending review of the shot"}
def snap(p, name, cols, callouts, data):
    path = OUT + name; p.screenshot(path=path, type="jpeg", quality=72)
    try: record(p, path, tool="vizit", software=SW, by="comparison-auditor", driver=__file__, data=data, proves=[pv(c) for c in cols], callouts=callouts)
    except Exception as e:
        print("callout failed", str(e)[:120]); record(p, path, tool="vizit", software=SW, by="comparison-auditor", driver=__file__, data=data, proves=[pv(c) for c in cols], callouts=[])
    print("shot", name, flush=True)
def refresh(p):
    for t in ["LOAD METADATA / REFRESH PLOTS", "REFRESH PLOTS"]:
        if p.get_by_text(t).count():
            try: p.get_by_text(t).first.click(timeout=5000); break
            except Exception: pass
    time.sleep(20)
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    p = b.new_context(viewport={"width": 1400, "height": 1000}).new_page(); p.set_default_timeout(15000)
    p.goto(f"{B}/views/visiumview?dataset=PD5D_MTG_VisiumST&gene=SNCA&sample=BN2003", timeout=90000); time.sleep(12); refresh(p)
    try:
        p.locator("label:has-text('Show H&E image') input[type=checkbox]").first.check(force=True); time.sleep(15)
    except Exception as e:
        LOG["he_err"] = str(e)[:200]
    LOG["he_checked"] = p.locator("label:has-text('Show H&E image') input[type=checkbox]").first.is_checked() if p.locator("label:has-text('Show H&E image') input").count() else None
    LOG["images"] = p.eval_on_selector_all("img, image", "es=>es.map(e=>(e.src||e.getAttribute('href')||'').slice(-80))")[:10]
    snap(p, "f01_image_he_on.jpg", ["image", "spatial"], [(1, "label:has-text('Show H&E image')", "H&E switch"), (2, ".js-plotly-plot >> nth=0", "spots")], "PD5D_MTG_VisiumST, sample BN2003 (hosted)")
    p.goto(f"{B}/views/clusters?dataset=PD5D_MTG_snRNAseq", timeout=90000); time.sleep(10)
    try:
        p.get_by_label("Select a cluster").first.click(); time.sleep(2)
        p.locator("li[role=option]").first.click(); time.sleep(2); refresh(p)
    except Exception as e:
        LOG["cluster_err"] = str(e)[:200]
    LOG["cluster_text"] = p.inner_text("body")[:2500]
    snap(p, "f02_de_cluster_markers.jpg", ["de"], [(1, "body", "Cluster View with a cluster chosen")], "PD5D_MTG_snRNAseq (hosted)")
    p.goto(f"{B}/views/geneview?dataset=PD5D_MTG_snRNAseq&gene=SNCA", timeout=90000); time.sleep(10); refresh(p)
    try:
        p.locator(".js-plotly-plot").first.hover(); time.sleep(1)
        LOG["modebar"] = p.locator(".js-plotly-plot >> nth=0").locator(".modebar-btn").evaluate_all("es=>es.map(e=>e.getAttribute('data-title'))")
    except Exception as e:
        LOG["modebar_err"] = str(e)[:200]
    snap(p, "f03_selection_umap_toolbar.jpg", ["selection"], [(1, ".js-plotly-plot >> nth=0 >> .modebar", "UMAP plot toolbar")], "PD5D_MTG_snRNAseq (hosted)")
    b.close()
print(json.dumps(LOG, default=str)[:3000])
