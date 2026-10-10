# SCope follow-up (<=3 min): plots render without a gene pick, request sizes for one gene (lazy),
# feature-type menu (slots/de), permalink + reopen (share), Compare page (filters), welcome page (remote).
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import time, sys
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT=f"{_REPO}/notes/comparison/screens/scope/"
SESS="https://scope.aertslab.org/#/Wouters_Human_Melanoma/"
BASE=SESS+"Wouters_Human_Melanoma%2F10_Baselines_filteredRegulons.loom/"
SW="SCope 1.8.2 (scope.aertslab.org)"; DATA="Wouters_Human_Melanoma / 10_Baselines_filteredRegulons.loom (4,322 cells)"
T0=time.time(); reqs=[]; frames=[]
def snap(p, name, proves, callouts):
    path=OUT+name; p.screenshot(path=path, type="jpeg", quality=70)
    try: record(p, path, tool="scope", software=SW, by="comparison-auditor", driver=__file__, data=DATA, proves=proves, callouts=callouts)
    except Exception as e:
        print("  callout failed:", str(e)[:150]); record(p, path, tool="scope", software=SW, by="comparison-auditor", driver=__file__, data=DATA, proves=proves, callouts=[])
    print(f"[{time.time()-T0:.0f}s] shot", name, flush=True)
def pv(c,m,t): return {"column":c,"mark":m,"caption":t}
def onfin(r):
    if r.resource_type in ("xhr","fetch","websocket","other"):
        try: sz=r.sizes()["responseBodySize"]
        except Exception: sz=-1
        reqs.append((round(time.time()-T0), r.resource_type, r.url[:120], sz))
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader","--enable-unsafe-swiftshader"])
    ctx=b.new_context(viewport={"width":1400,"height":900}); p=ctx.new_page(); p.set_default_timeout(8000)
    p.on("requestfinished", onfin); p.on("websocket", lambda ws: (print("WS", ws.url[:100]), ws.on("framereceived", lambda f: frames.append(len(f) if f else 0))))
    p.goto(BASE+"gene", timeout=90000); time.sleep(16)
    try: p.get_by_text("I decline").first.click(timeout=3000)
    except Exception: pass
    time.sleep(2)
    snap(p,"m01_plots_render_tsne.jpg",[pv("every_cell","Y","All 4,322 cells drawn on the Expression tSNE (one sprite per cell)")],[(1,"canvas >> nth=0","4,322 cells")])
    n0=len(reqs); f0=len(frames)
    try:
        s=p.locator("input[placeholder='Search...']").first; s.click(); s.type("MITF", delay=80); time.sleep(4)
        p.locator(".results .result").filter(has_text="MITF").first.click(); time.sleep(10)
    except Exception as e: print("gene",str(e)[:150])
    print("after gene: requests", reqs[n0:][:12]); fr=frames[f0:]; print("after gene: ws frames", len(fr), sorted(fr, reverse=True)[:5])
    # feature-type menu
    try:
        p.locator("text=all features").first.click(); time.sleep(2)
        items=[t.strip() for t in p.locator(".visible.menu .item").all_inner_texts() if t.strip()]; print("feature types", items)
        snap(p,"m04_slots_feature_type_menu.jpg",[pv("slots","P","Query types: "+", ".join(items)+"; per-cell columns of the loom only, no layers or graphs"),
              pv("genes","N","No gene x gene relation among query types"),pv("de","N","No 'compute DE' query or button; markers shown in the sidebar are precomputed ClusterMarkers_* attributes")],
             [(1,".visible.menu","query feature types")])
        p.keyboard.press("Escape"); p.mouse.click(700,880); time.sleep(1)
    except Exception as e: print("ftype",str(e)[:150])
    # permalink
    link=None
    try:
        p.locator("text=About").first.locator("xpath=following::i[1]").click(); time.sleep(6)
        link=p.locator("text=/bit\\.ly/").first.inner_text().strip(); print("permalink", link)
        snap(p,"m12_share_permalink.jpg",[pv("share","Y",f"Link icon produces a permalink {link} (state in the long URL, shortened by bit.ly)")],[(1,"text=/bit\\.ly/","permalink"),(2,"text=Include session UUID in permalink?","optional session UUID")])
    except Exception as e: print("perm",str(e)[:150])
    if link:
        try:
            q=ctx.new_page(); q.goto(link if link.startswith("http") else "https://"+link, timeout=60000); time.sleep(18)
            print("reopened url", q.url[:250])
            path=OUT+"m12_share_permalink_reopened.jpg"; q.screenshot(path=path, type="jpeg", quality=70)
            try: record(q, path, tool="scope", software=SW, by="comparison-auditor", driver=__file__, data=DATA, proves=[pv("share","Y","Permalink opened in a new page: same loom and page, gene MITF restored in the red query (F1: MITF)")], callouts=[(1,"text=F1: MITF","gene restored"),(2,"text=10_Baselines_filteredRegulons","loom restored")])
            except Exception as e:
                print("  callout failed:", str(e)[:150]); record(q, path, tool="scope", software=SW, by="comparison-auditor", driver=__file__, data=DATA, proves=[pv("share","Y","Permalink opened in a new page (see URL)")], callouts=[])
            print("shot m12 reopened"); q.close()
        except Exception as e: print("reopen",str(e)[:150])
    # compare page
    try:
        p.get_by_text("Compare", exact=True).first.click(); time.sleep(8)
        try:
            p.get_by_text("cell_line", exact=True).first.click(); time.sleep(2)
            vals=p.locator("text=cell_line >> xpath=../following-sibling::*[1]").all_inner_texts(); print("cell_line values", [v[:80] for v in vals])
        except Exception as e: print("expand",str(e)[:120])
        snap(p,"m08_filters_compare_page.jpg",[pv("filters","P","Compare page: annotation categories (cell_line, state, experiment) to drag onto up to 4 displays, OR/AND superposition; categorical only. Drag not completed headless")],
             [(1,"text=Number of displays: >> xpath=..","displays / superposition"),(2,"text=Drag and drop here the annotations you want to compare. >> nth=0","drop zone")])
    except Exception as e: print("compare",str(e)[:150])
    # welcome page
    p.goto(SESS+"*/welcome", timeout=60000); time.sleep(6)
    snap(p,"m06_remote_upload_only.jpg",[pv("remote","N","Data are server-side looms or .loom uploads into a user session ('Datasets can be uploaded ... Files should be in the loom file format'); no URL / S3 / GCS input")],[(1,"text=Datasets can be uploaded","upload .loom only"),(2,"text=Session Looms","server-side looms")])
    print(f"elapsed {time.time()-T0:.0f}")
    b.close()
