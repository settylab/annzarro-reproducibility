"""VizIt (hosted Parkinson's Cell Atlas, pd5d.yale.edu, 'an implementation of VizIt!') matrix-mark shots with DOM
sidecars. Views are opened through their URL parameters (dataset, gene, sample, color), which is itself the
shareable-state mechanism. Plotly figures are read for their point counts (sum of trace lengths)."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import json, os, sys, time
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT = f"{_REPO}/notes/comparison/screens/vizit/"; os.makedirs(OUT, exist_ok=True)
DL = f"{_SCRATCH}/vz_dl/"; os.makedirs(DL, exist_ok=True)
SW = "VizIt v1.0.0 as deployed at pd5d.yale.edu (Parkinson's Cell Atlas)"
B = "https://pd5d.yale.edu"
LOG = {}
def pv(c, m=None, t=None):
    # Raw capture only: the mark and caption are written after the shot has been looked at (coordinator's rule,
    # 2026-10-04); this records just which column the shot is meant to inform.
    return {"column": c, "mark": "?", "caption": "raw capture; verdict and caption pending review of the shot"}
def snap(p, name, proves, callouts, data):
    path = OUT + name; p.screenshot(path=path, type="jpeg", quality=72, full_page=False)
    try: record(p, path, tool="vizit", software=SW, by="comparison-auditor", driver=__file__, data=data, proves=proves, callouts=callouts)
    except Exception as e:
        print("  callout failed:", str(e)[:140], flush=True)
        record(p, path, tool="vizit", software=SW, by="comparison-auditor", driver=__file__, data=data, proves=proves, callouts=[])
    print("shot", name, flush=True)
PLOTLY = """() => [...document.querySelectorAll('.js-plotly-plot')].map(gd => ({traces: (gd.data||[]).length,
   points: (gd.data||[]).reduce((a,t)=>a+((t.x&&t.x.length)||0),0), type: (gd.data||[])[0] && gd.data[0].type,
   title: (gd.layout && gd.layout.title && (gd.layout.title.text||gd.layout.title)) || ''}))"""
def refresh(p):
    for t in ["LOAD METADATA / REFRESH PLOTS", "REFRESH PLOTS", "LOAD PLOTS"]:
        if p.get_by_text(t).count():
            try: p.get_by_text(t).first.click(timeout=5000); break
            except Exception: pass
    time.sleep(20)
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    ctx = b.new_context(viewport={"width": 1400, "height": 1000}, accept_downloads=True)
    p = ctx.new_page(); p.set_default_timeout(15000)
    api = []
    p.on("requestfinished", lambda r: api.append([r.url.split("pd5d.yale.edu")[-1][:160], r.sizes().get("responseBodySize")]) if "/api/" in r.url else None)
    D = "PD5D_MTG_snRNAseq"; DATA = "PD5D_MTG_snRNAseq (snRNA-seq, 94 samples), hosted"
    p.goto(f"{B}/views/geneview?dataset={D}&gene=SNCA", timeout=90000); time.sleep(10); refresh(p)
    LOG["gene_plots"] = p.evaluate(PLOTLY); LOG["gene_api"] = api[-25:]; LOG["gene_url"] = p.url
    LOG["gene_text"] = p.inner_text("body")[:2500]
    snap(p, "m00_every_cell_geneview_umap.jpg", [pv("every_cell")],
         [(1, ".js-plotly-plot >> nth=0", "UMAP plot")], DATA)
    snap(p, "m12_share_url_state.jpg", [pv("share")],
         [(1, "body", "view opened from a URL with dataset and gene parameters")], DATA)
    # export: plotly modebar download
    try:
        p.locator(".js-plotly-plot").first.hover(); time.sleep(1)
        with p.expect_download(timeout=30000) as d:
            p.locator(".modebar-btn[data-title*='Download']").first.click()
        dl = d.value; fn = DL + dl.suggested_filename; dl.save_as(fn); LOG["export"] = [dl.suggested_filename, os.path.getsize(fn)]
        snap(p, "m13_export_plotly_download.jpg", [pv("export")],
             [(1, ".modebar-btn[data-title*='Download'] >> nth=0", "download button")], DATA)
    except Exception as e:
        LOG["export_err"] = str(e)[:200]
    # clusters view: record what panels and controls exist
    api.clear()
    p.goto(f"{B}/views/clusters?dataset={D}", timeout=90000); time.sleep(10); refresh(p)
    LOG["clusters_text"] = p.inner_text("body")[:2500]; LOG["clusters_api"] = api[-25:]
    snap(p, "m10_de_clusters_view.jpg", [pv("de")],
         [(1, "body", "Cluster View")], DATA)
    # spatial view with H&E
    api.clear()
    V = "PD5D_MTG_VisiumST"
    p.goto(f"{B}/views/visiumview?dataset={V}&gene=SNCA", timeout=90000); time.sleep(12); refresh(p)
    try:
        p.get_by_text("Show H&E image").first.click(timeout=5000); time.sleep(10)
    except Exception as e:
        LOG["he_err"] = str(e)[:150]
    LOG["visium_plots"] = p.evaluate(PLOTLY); LOG["visium_api"] = api[-25:]; LOG["visium_text"] = p.inner_text("body")[:2000]
    snap(p, "m07_m11_spatial_he.jpg", [pv("spatial"), pv("image")],
         [(1, ".js-plotly-plot >> nth=0", "spots (and H&E) plot"), (2, "text=Show H&E image", "H&E toggle")], "PD5D_MTG_VisiumST (Visium, hosted)")
    (open(DL + "matrix_log.json", "w")).write(json.dumps(LOG, indent=1, default=str))
    b.close()
print(json.dumps({k: v for k, v in LOG.items() if not k.endswith("_text")}, default=str)[:3000])
