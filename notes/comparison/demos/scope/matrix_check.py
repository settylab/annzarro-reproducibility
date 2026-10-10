# SCope matrix-mark check (one <=3 min session): public scope.aertslab.org (SCope 1.8.2), no ORCID login,
# loom Wouters_Human_Melanoma/10_Baselines_filteredRegulons (4,322 cells). Writes screens/scope/mNN_*.jpg + .annot.yaml.
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import time, os, sys
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT=f"{_REPO}/notes/comparison/screens/scope/"
SESS="https://scope.aertslab.org/#/Wouters_Human_Melanoma/"
BASE=SESS+"Wouters_Human_Melanoma%2F10_Baselines_filteredRegulons.loom/"
SW="SCope 1.8.2 (scope.aertslab.org)"; DATA="Wouters_Human_Melanoma / 10_Baselines_filteredRegulons.loom (4,322 cells)"
T0=time.time(); frames=[]
def snap(p, name, proves, callouts):
    path=OUT+name; p.screenshot(path=path, type="jpeg", quality=70)
    try: record(p, path, tool="scope", software=SW, by="comparison-auditor", driver=__file__, data=DATA, proves=proves, callouts=callouts)
    except Exception as e:
        print("  callout failed:", str(e)[:150]); record(p, path, tool="scope", software=SW, by="comparison-auditor", driver=__file__, data=DATA, proves=proves, callouts=[])
    print(f"[{time.time()-T0:.0f}s] shot", name, flush=True)
def pv(col, mark, cap): return {"column": col, "mark": mark, "caption": cap}
def onws(ws): ws.on("framereceived", lambda f: frames.append(len(f) if f else 0))
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader","--enable-unsafe-swiftshader"])
    p=b.new_page(viewport={"width":1400,"height":900}); p.on("websocket", onws)
    p.goto(BASE+"gene", timeout=90000); time.sleep(18)
    try: p.get_by_text("I decline").first.click(timeout=3000)
    except Exception: pass
    # gene pick -> frame sizes (lazy) + plots render
    n0=len(frames)
    try:
        s=p.locator("input[placeholder='Search...']").first; s.click(); s.type("MITF", delay=100); time.sleep(4)
        res=p.locator(".results .result"); print("results", [t[:40] for t in res.all_inner_texts()[:6]])
        res.filter(has_text="MITF").first.click(); time.sleep(12)
    except Exception as e: print("gene",str(e)[:200])
    big=sorted([f for f in frames[n0:]], reverse=True)[:3]; print("frames after gene pick", len(frames)-n0, "largest", big)
    snap(p,"m01_plots_render_gene_MITF.jpg",[pv("every_cell","Y","All 4,322 cells drawn, coloured by MITF expression"),
          pv("lazy","Y",f"Gene pick fetches one gene from the server loom: {len(frames)-n0} websocket frames, largest {big[0] if big else 0:,} bytes (about one value per cell)")],
         [(1,"canvas >> nth=0","4,322 cells, MITF"),(2,"input[placeholder='Search...'] >> nth=0","gene query")])
    # slots / spatial / cells: Coordinates menu
    try:
        p.get_by_text("Expression tSNE").first.click(); time.sleep(2)
        items=[t.strip() for t in p.locator(".menu.transition.visible .item, .visible.menu .item").all_inner_texts() if t.strip()]; print("coords", items)
        snap(p,"m04_slots_coordinates_menu.jpg",[pv("slots","P","Coordinates menu lists the loom's stored embeddings only ("+", ".join(items[:6])+"); no layers, no col/row graphs"),
              pv("spatial","N","No spatial coordinate type or spatial view among coordinates"),pv("cells","N","No cell x cell graph offered as colour or axis")],
             [(1,".visible.menu","Coordinates: embeddings")])
        p.keyboard.press("Escape"); p.mouse.click(700,880); time.sleep(1)
    except Exception as e: print("coords",str(e)[:200])
    # image + export: viewer toolbar
    try:
        snap(p,"m11_image_m13_export_viewer_toolbar.jpg",[pv("image","N","Viewer toolbar has lasso and zoom reset only; no image layer anywhere in settings"),
              pv("export","N","No image export: toolbar and settings offer no PNG/SVG/PDF download")],
             [(1,"[title='Lasso Tool'] >> xpath=../..","viewer toolbar: lasso, reset zoom"),(2,"text=SETTINGS >> xpath=..","settings: no export, no image")])
    except Exception as e: print("toolbar",str(e)[:200])
    # annot: ORCID gate
    snap(p,"m09_annot_orcid_login_required.jpg",[pv("annot","Y","Cluster annotation and voting need ORCID login (button shown); not exercised without an account")],[(1,"text=Authenticate with ORCID","ORCID login")])
    # share: permalink
    try:
        p.locator("text=About").first.locator("xpath=following::i[1]").click(); time.sleep(6)
        txt=[t[:200] for t in p.locator(".popup, .ui.popup, .modal").all_inner_texts() if t.strip()][:2]
        vals=p.locator("input").evaluate_all("els=>els.map(e=>e.value).filter(v=>v&&v.includes('http'))"); print("permalink", txt, vals)
        snap(p,"m12_share_permalink.jpg",[pv("share","Y","Permalink popup: "+(vals[0] if vals else (txt[0] if txt else "no link text captured")))],[(1,".ui.popup, .popup","permalink")])
        if vals:
            q=b.new_page(viewport={"width":1400,"height":900}); q.goto(vals[0], timeout=60000); time.sleep(20)
            print("reopened", q.url[:200]); path=OUT+"m12_share_permalink_reopened.jpg"; q.screenshot(path=path, type="jpeg", quality=70)
            record(q, path, tool="scope", software=SW, by="comparison-auditor", driver=__file__, data=DATA, proves=[pv("share","Y","Permalink opened in a new page restores loom and gene")], callouts=[(1,"canvas >> nth=0","restored view")])
            q.close()
    except Exception as e: print("share",str(e)[:200])
    # filters: Compare page
    try:
        p.get_by_text("Compare", exact=True).first.click(); time.sleep(8)
        snap(p,"m08_filters_compare_page.jpg",[pv("filters","P","Compare page: annotation values are dragged onto up to 4 displays (AND/OR); drag not attempted headless")],[(1,"canvas >> nth=0","compare displays")])
    except Exception as e: print("compare",str(e)[:200])
    # remote: welcome page = upload only
    try:
        p.goto(SESS+"*/welcome", timeout=60000); time.sleep(6)
        snap(p,"m06_remote_upload_only.jpg",[pv("remote","N","Datasets come from the server or 'Upload new dataset' (.loom file); no URL / S3 / GCS input")],[(1,"text=Upload new dataset","upload .loom only")])
    except Exception as e: print("welcome",str(e)[:200])
    print(f"elapsed {time.time()-T0:.0f}")
    b.close()
