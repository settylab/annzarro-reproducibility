# SCP follow-up 2 (<=3 min): subsampling menu (every_cell/subset) on SCP383, annotation menu (slots) on SCP2510,
# DE panel (de) and "Filter plotted cells" (filters) on SCP1671. Not logged in.
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import time, sys
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT=f"{_REPO}/notes/comparison/screens/single-cell-portal/"
S="https://singlecell.broadinstitute.org/single_cell/study/"
SW="Single Cell Portal 1.20.0 (singlecell.broadinstitute.org)"
T0=time.time()
def pv(c,m,t): return {"column":c,"mark":m,"caption":t}
def snap(p, name, proves, callouts, data):
    path=OUT+name; p.screenshot(path=path, type="jpeg", quality=70)
    try: record(p, path, tool="single-cell-portal", software=SW, by="comparison-auditor", driver=__file__, data=data, proves=proves, callouts=callouts)
    except Exception as e:
        print("  callout failed:", str(e)[:150]); record(p, path, tool="single-cell-portal", software=SW, by="comparison-auditor", driver=__file__, data=data, proves=proves, callouts=[])
    print(f"[{time.time()-T0:.0f}s] shot", name, flush=True)
def open_menu(p, value):
    p.locator(f"div[class*=control]:has(div[class*=singleValue]:text-is('{value}'))").first.click(force=True); time.sleep(2)
    return [t.strip() for t in p.locator("div[class*=option]").all_inner_texts() if t.strip() and len(t)<60]
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader","--enable-unsafe-swiftshader"])
    p=b.new_page(viewport={"width":1400,"height":1000}); p.set_default_timeout(10000)
    try:
        p.goto(S+"SCP383#study-visualize", timeout=90000); time.sleep(18)
        o=open_menu(p,"100000"); print("subsample", o)
        snap(p,"m01_every_cell_subsampling_menu_SCP383.jpg",[pv("every_cell","P","1,306,127 cells; default draws a 100,000 subsample; menu offers "+" | ".join(o)),pv("subset","Y","User picks the subsample size ("+" | ".join(o)+"), coarse")],
             [(1,"div[class*=menu]","Subsampling menu"),(2,"text=/1306127 total cells/","total cells")],"SCP383, 10X 1.3M brain cells E18 (1,306,127 cells)")
        p.keyboard.press("Escape")
    except Exception as e: print("sub",str(e)[:200])
    try:
        p.goto(S+"SCP2510#study-visualize", timeout=90000); time.sleep(18)
        o=open_menu(p,"donor_id"); print("annotations", o)
        snap(p,"m04_slots_annotation_menu_SCP2510.jpg",[pv("slots","P","Annotation menu = cell metadata columns ("+", ".join(o)+"); Clustering = embeddings; no obsp/varp/varm/uns"),
              pv("cells","N","No pairwise cell x cell entry in Clustering, Spatial groups or Annotation menus")],[(1,"div[class*=menu]","annotation menu"),(2,"text=Clustering","clustering = embeddings")],"SCP2510 (1,459,214 cells)")
        p.keyboard.press("Escape")
    except Exception as e: print("ann",str(e)[:200])
    D1671="SCP1671, human lactation (49,310 cells)"
    try:
        p.goto(S+"SCP1671?genes=CD74#study-visualize", timeout=90000); time.sleep(15)
        p.get_by_role("button", name="Differential expression").first.click(); time.sleep(4)
        inp=p.locator("[id^=react-select][id$=-input]"); inp.last.click(force=True); inp.last.fill("B cells"); time.sleep(1); p.keyboard.press("Enter"); time.sleep(8)
        rows=p.locator("tr.de-gene-row"); print("de rows", rows.count())
        snap(p,"m10_de_precomputed_table_SCP1671.jpg",[pv("de","P","DE table for 'B cells' is precomputed at ingest (Wilcoxon, SCP-computed); no control to compute DE for a new group in the GUI")],[(1,"tr.de-gene-row >> nth=0 >> xpath=ancestor::table","precomputed DE table")],D1671)
    except Exception as e: print("de",str(e)[:200])
    try:
        p.goto(S+"SCP1671?genes=CD74#study-visualize", timeout=90000); time.sleep(15)
        p.get_by_role("button", name="Filter plotted cells").first.click(); time.sleep(3)
        p.locator("input[name*='macrophage']").first.click(); time.sleep(10)
        snap(p,"m08_filters_macrophage_off_both_scatters_SCP1671.jpg",[pv("filters","P","'Filter plotted cells' facet: unticking macrophage greys those cells in both scatters (facets, not a table)")],[(1,"input[name*='macrophage']","macrophage unticked"),(2,".js-plotly-plot >> nth=0","filtered cells greyed")],D1671)
    except Exception as e: print("filter",str(e)[:200])
    print(f"elapsed {time.time()-T0:.0f}")
    b.close()
