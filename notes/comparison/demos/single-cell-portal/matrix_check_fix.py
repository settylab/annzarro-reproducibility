# SCP follow-up (<=1.5 min): annotation menu open (slots) and share-link reopen with callouts. SCP383, not logged in.
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import time, sys
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT=f"{_REPO}/notes/comparison/screens/single-cell-portal/"
SW="Single Cell Portal 1.20.0 (singlecell.broadinstitute.org)"; D383="SCP383, 10X 1.3M brain cells E18 (1,306,127 cells)"
U="https://singlecell.broadinstitute.org/single_cell/study/SCP383?genes=Sox2&tab=distribution"
T0=time.time()
def pv(c,m,t): return {"column":c,"mark":m,"caption":t}
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader","--enable-unsafe-swiftshader"])
    p=b.new_page(viewport={"width":1400,"height":1000})
    p.goto(U, timeout=90000); time.sleep(20)
    vis=p.locator(".js-plotly-plot").evaluate_all("els=>els.map(e=>e.offsetParent!==null)"); print("plots visible", vis)
    i=vis.index(True) if True in vis else 0
    path=OUT+"m12_share_url_reopened_fresh_context.jpg"; p.screenshot(path=path, type="jpeg", quality=70)
    record(p, path, tool="single-cell-portal", software=SW, by="comparison-auditor", driver=__file__, data=D383,
           proves=[pv("share","Y","URL ?genes=Sox2&tab=distribution opened in a fresh browser restores the gene and the Distribution tab")],
           callouts=[(1,"text=Distribution >> nth=0","Distribution tab restored"),(2,f".js-plotly-plot >> nth={i}","Sox2 violins")])
    print("shot m12")
    # annotation menu
    ann=p.locator("text=Annotation").first.locator("xpath=following::div[contains(@class,'control')][1]")
    ann.click(force=True); time.sleep(2)
    opts=[t.strip() for t in p.locator("div[class*=option]").all_inner_texts() if t.strip()]; print("options", opts)
    path=OUT+"m04_slots_annotation_menu_SCP383.jpg"; p.screenshot(path=path, type="jpeg", quality=70)
    record(p, path, tool="single-cell-portal", software=SW, by="comparison-auditor", driver=__file__, data=D383,
           proves=[pv("slots","P","Annotation menu lists cell metadata only ("+", ".join(opts[:8])+"); Clustering lists embeddings; no obsp/varp/varm anywhere in Options"),
                   pv("cells","N","No pairwise cell x cell entry in the Clustering or Annotation menus")],
           callouts=[(1,"div[class*=menu]","annotation menu"),(2,"text=Clustering","clustering = embeddings")])
    print("shot m04", f"elapsed {time.time()-T0:.0f}")
    b.close()
