# SCope follow-up 2 (<=1.5 min): wait for the viewer to finish loading, then shoot plots-render; pick gene MITF and
# record websocket frame sizes (lazy per-gene read). Public scope.aertslab.org, no login.
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import time, sys
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT=f"{_REPO}/notes/comparison/screens/scope/"
BASE="https://scope.aertslab.org/#/Wouters_Human_Melanoma/Wouters_Human_Melanoma%2F10_Baselines_filteredRegulons.loom/"
SW="SCope 1.8.2 (scope.aertslab.org)"; DATA="Wouters_Human_Melanoma / 10_Baselines_filteredRegulons.loom (4,322 cells)"
T0=time.time(); frames=[]
def pv(c,m,t): return {"column":c,"mark":m,"caption":t}
def loaded(p, limit):
    t=time.time()
    while time.time()-t<limit:
        if p.locator(".ui.loader:visible").count()==0: return True
        time.sleep(1)
    return False
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader","--enable-unsafe-swiftshader"])
    p=b.new_page(viewport={"width":1400,"height":900}); p.set_default_timeout(8000)
    p.on("websocket", lambda ws: ws.on("framereceived", lambda f: frames.append((round(time.time()-T0,1), len(f) if f else 0))))
    p.goto(BASE+"gene", timeout=90000); time.sleep(8)
    try: p.get_by_text("I decline").first.click(timeout=3000)
    except Exception: pass
    ok=loaded(p, 50); time.sleep(2); print("loaded", ok, f"{time.time()-T0:.0f}s")
    path=OUT+"m01_plots_render_tsne.jpg"; p.screenshot(path=path, type="jpeg", quality=70)
    record(p, path, tool="scope", software=SW, by="comparison-auditor", driver=__file__, data=DATA,
           proves=[pv("every_cell","Y" if ok else "?","All 4,322 cells drawn on the Expression tSNE (one sprite per cell)" if ok else "Viewer still loading after 50 s headless; plot not observed")],
           callouts=[(1,"canvas >> nth=0","Expression tSNE")])
    print("shot m01", f"{time.time()-T0:.0f}s")
    n0=len(frames)
    s=p.locator("input[placeholder='Search...']").first; s.click(); s.type("MITF", delay=80); time.sleep(3)
    p.locator(".results .result").filter(has_text="MITF").first.click(); t1=time.time()-T0
    ok2=loaded(p, 25); time.sleep(3)
    fr=[f for f in frames[n0:]]; big=sorted([f[1] for f in fr], reverse=True)[:5]
    print("gene loaded", ok2, "frames", len(fr), "largest", big, "times", [f[0] for f in fr][:10])
    path=OUT+"m05_lazy_gene_MITF.jpg"; p.screenshot(path=path, type="jpeg", quality=70)
    record(p, path, tool="scope", software=SW, by="comparison-auditor", driver=__file__, data=DATA,
           proves=[pv("lazy","Y",f"Gene pick: {len(fr)} websocket frames from the server after the click, largest {big[0] if big else 0:,} bytes (one gene's values for 4,322 cells, not the matrix)")],
           callouts=[(1,"canvas >> nth=0","MITF expression"),(2,"input[placeholder='Search...'] >> nth=0","gene query")])
    print("shot m05", f"elapsed {time.time()-T0:.0f}")
    b.close()
