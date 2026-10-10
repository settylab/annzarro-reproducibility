# Single Cell Portal matrix-mark check (one <=3 min session), public studies, not logged in.
# SCP383 (1,306,127 cells) and SCP2510 (spatial). Writes screens/single-cell-portal/mNN_*.jpg + .annot.yaml.
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import time, os, sys, re
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT=f"{_REPO}/notes/comparison/screens/single-cell-portal/"
DL=f"{_SCRATCH}/matrix/scp_dl/"
S="https://singlecell.broadinstitute.org/single_cell/study/"
SW="Single Cell Portal 1.20.0 (singlecell.broadinstitute.org)"
os.makedirs(DL, exist_ok=True)
T0=time.time(); reqs=[]
def snap(p, name, proves, callouts, data):
    path=OUT+name; p.screenshot(path=path, type="jpeg", quality=70)
    try: record(p, path, tool="single-cell-portal", software=SW, by="comparison-auditor", driver=__file__, data=data, proves=proves, callouts=callouts)
    except Exception as e:
        print("  callout failed:", str(e)[:150]); record(p, path, tool="single-cell-portal", software=SW, by="comparison-auditor", driver=__file__, data=data, proves=proves, callouts=[])
    print(f"[{time.time()-T0:.0f}s] shot", name, flush=True)
def pv(col, mark, cap): return {"column": col, "mark": mark, "caption": cap}
def onfin(r):
    if "api/v1" in r.url:
        try: sz=r.sizes()["responseBodySize"]
        except Exception: sz=-1
        reqs.append((r.url, sz))
D383="SCP383, 10X 1.3M brain cells E18 (1,306,127 cells)"; D2510="SCP2510, human lung cancer stem-immunity hubs (1,459,214 cells)"
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader","--enable-unsafe-swiftshader"])
    ctx=b.new_context(viewport={"width":1400,"height":1000}, accept_downloads=True)
    p=ctx.new_page(); p.on("requestfinished", onfin)
    p.goto(S+"SCP383?genes=Sox2#study-visualize", timeout=90000); time.sleep(22)
    for u,sz in reqs: print("REQ", u[:230], sz)
    gene=[(u,sz) for u,sz in reqs if "Sox2" in u]; coords=[(u,sz) for u,sz in reqs if "/clusters/" in u]
    gtxt="; ".join(f"{u.split('/api/v1/')[1].split('?')[0]} {sz:,} B" for u,sz in gene[:3]) or "no request naming Sox2 seen"
    snap(p,"m01_plots_render_SCP383_Sox2.jpg",[
        pv("every_cell","P","Default view draws a 100,000-cell subsample of 1,306,127 (Subsampling menu offers 'All Cells')"),
        pv("lazy","Y","Server reads one gene on demand: requests naming Sox2: "+gtxt)],
        [(1,"text=subsample[100000] >> nth=0","subsample of 1,306,127"),(2,".js-plotly-plot >> nth=0","Sox2 expression")], D383)
    # export: Plotly modebar camera
    try:
        pl=p.locator(".js-plotly-plot").first; pl.hover(); time.sleep(2)
        cam=pl.locator(".modebar-btn[data-title='Download plot as a png']").first; cam.hover(); time.sleep(1)
        with p.expect_download(timeout=30000) as d: cam.click()
        dl=d.value; fn=DL+dl.suggested_filename; dl.save_as(fn); sz=os.path.getsize(fn); print("DOWNLOAD", dl.suggested_filename, sz)
        pl.hover(); time.sleep(1); cam.hover(); time.sleep(1)
        snap(p,"m13_export_plotly_png.jpg",[pv("export","Y",f"Plotly 'Download plot as a png' saved {dl.suggested_filename} ({sz:,} bytes)")],[(1,".js-plotly-plot >> nth=0 >> .modebar-btn[data-title='Download plot as a png']","Download plot as a png")], D383)
    except Exception as e: print("export",str(e)[:200])
    # slots: annotation menu open
    try:
        ctl=p.locator("div[class*=singleValue]").filter(has_text=re.compile(r"^Cluster$")).first
        ctl.click(); time.sleep(2)
        opts=[t.strip() for t in p.locator("div[class*=option]").all_inner_texts() if t.strip()]; print("annotation options", opts)
        snap(p,"m04_slots_annotation_menu_SCP383.jpg",[pv("slots","P","Annotation menu lists obs-type metadata only ("+", ".join(opts[:8])+"); no obsp/varp/varm anywhere in Options"),
              pv("cells","N","No pairwise cell x cell entry in Clustering or Annotation menus")],[(1,"div[class*=menu]","annotation menu"),(2,"text=Clustering","clustering = embeddings")], D383)
        p.keyboard.press("Escape"); time.sleep(1)
    except Exception as e: print("ann",str(e)[:200])
    # annot: sign-in gate on the create-annotation button
    try:
        btn=p.locator("button[data-analytics-name=toggle-create-annotation-signedout]").first; btn.hover(); time.sleep(2)
        print("tooltip", p.locator(".tooltip").all_inner_texts()[:2])
        snap(p,"m09_annot_create_requires_signin.jpg",[pv("annot","Y","'+' next to Annotation: 'You must sign in to create custom annotations' (feature exists, login-gated; not exercised here)")],[(1,"button[data-analytics-name=toggle-create-annotation-signedout]","create annotation (+)"),(2,".tooltip","sign-in required")], D383)
    except Exception as e: print("annot",str(e)[:200])
    # share: Distribution tab, copy URL, reopen in a fresh context
    try:
        p.get_by_text("Distribution", exact=True).first.click(); time.sleep(6)
        url=p.url; print("URL", url)
        c2=b.new_context(viewport={"width":1400,"height":1000}); q=c2.new_page(); q.goto(url, timeout=90000); time.sleep(18)
        snap(q,"m12_share_url_reopened_fresh_context.jpg",[pv("share","Y","URL ?genes=Sox2&tab=distribution opened in a fresh browser context restores gene and Distribution tab")],[(1,"text=Distribution >> nth=0","Distribution tab restored"),(2,".js-plotly-plot >> nth=0","Sox2 violins")], D383)
        c2.close()
    except Exception as e: print("share",str(e)[:200])
    # spatial + image: SCP2510 spatial group
    p.goto(S+"SCP2510?spatialGroups=spatial_Pt38#study-visualize", timeout=90000); time.sleep(28)
    print("plots", p.locator(".js-plotly-plot").count(), "imgs in plots area", p.locator("#study-visualize img").count())
    snap(p,"m07_spatial_SCP2510_Pt38.jpg",[pv("spatial","Y","Spatial group spatial_Pt38 drawn as an X/Y scatter beside the UMAP"),
          pv("image","N","Spatial plot is points only; no tissue image layer or image option in Options")],[(1,".js-plotly-plot >> nth=-1","spatial_Pt38 X/Y"),(2,"text=Spatial groups","spatial group picker")], D2510)
    print(f"elapsed {time.time()-T0:.0f}")
    b.close()
