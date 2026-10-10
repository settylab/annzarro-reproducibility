# Kana matrix-mark check (one session): live build https://www.kanaverse.org/kana/ (v3.2.0),
# Explore mode with $DEMO_ROOT/_data/bm_demo.h5ad, plus a 2,023-cell copy with a synthetic
# obsm['spatial'] grid (scratchpad bm_spatial_test.h5ad). Writes screens/kana/mNN_*.jpg + .annot.yaml.
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import time, os, sys, urllib.parse
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT=f"{_REPO}/notes/comparison/screens/kana/"
DL=f"{_SCRATCH}/matrix/kana_dl/"
SPAT=f"{_SCRATCH}/matrix/bm_spatial_test.h5ad"
BM=os.path.expanduser(f"{_DEMO_ROOT}/_data/bm_demo.h5ad")
SW="Kana v3.2.0 (live build, kanaverse.org)"; DATA="bm_demo.h5ad (8,090 cells)"
os.makedirs(DL, exist_ok=True)
T0=time.time(); hosts={}
def snap(p, name, proves, callouts, data=DATA):
    path=OUT+name; p.screenshot(path=path, type="jpeg", quality=70)
    try: record(p, path, tool="kana", software=SW, by="comparison-auditor", driver=__file__, data=data, proves=proves, callouts=callouts)
    except Exception as e:
        print("  callout failed:", str(e)[:150]); record(p, path, tool="kana", software=SW, by="comparison-auditor", driver=__file__, data=data, proves=proves, callouts=[])
    print(f"[{time.time()-T0:.0f}s] shot", name, flush=True)
def pv(col, mark, cap): return {"column": col, "mark": mark, "caption": cap}
def load(p, f):
    p.goto("https://www.kanaverse.org/kana/", timeout=120000); time.sleep(4)
    p.get_by_text("I want to explore existing analysis results").click(); time.sleep(3)
    p.locator("input[type=file]").first.set_input_files(f); time.sleep(10)
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader","--enable-unsafe-swiftshader"])
    ctx=b.new_context(viewport={"width":1800,"height":950}, accept_downloads=True)
    p=ctx.new_page()
    p.on("request", lambda r: hosts.__setitem__(urllib.parse.urlparse(r.url).netloc, hosts.get(urllib.parse.urlparse(r.url).netloc,0)+1))
    # column remote: New Analysis sources
    p.goto("https://www.kanaverse.org/kana/", timeout=120000); time.sleep(4)
    p.get_by_text("I want to analyze a new dataset").first.click(); time.sleep(3)
    snap(p,"m06_remote_new_analysis_tabs.jpg",[pv("remote","P","Only remote source is a fixed ExperimentHub list (8 datasets, downloaded whole); other tabs are local file pickers")],
         [(1,"text=Choose an ExperimentHub dataset >> xpath=..","fixed ExperimentHub list"),(2,"text=10X MatrixMarket >> xpath=..","source tabs: no URL / S3 / GCS")])
    p.get_by_text("H5AD", exact=True).first.click(); time.sleep(2)
    print("H5AD tab inputs", p.locator("input").evaluate_all("els=>els.map(e=>e.type)"))
    snap(p,"m06_remote_h5ad_tab_file_only.jpg",[pv("remote","P","H5AD tab takes a local file only; there is no URL field")],[(1,"text=H5AD","H5AD tab"),(2,"input[type=file] >> xpath=..","local file picker only")])
    # column spatial: synthetic obsm['spatial'] shows up as one more embedding tab
    load(p, SPAT)
    p.get_by_role("button", name="Explore", exact=True).first.click()
    for i in range(12):
        time.sleep(4)
        if p.get_by_text("spatial", exact=True).count(): break
    time.sleep(5); p.get_by_text("spatial", exact=True).first.click(); time.sleep(5)
    p.locator("select").first.select_option("highres_celltype"); time.sleep(3)
    snap(p,"m07_spatial_obsm_spatial_plotted_as_embedding.jpg",[pv("spatial","P","obsm['spatial'] (synthetic grid) is offered as an ordinary embedding tab; nothing spatial-aware (no image, no aspect/scale handling)")],
         [(1,"button:has-text('spatial')","obsm key 'spatial' as embedding tab"),(2,"canvas","grid drawn as x/y")], data="bm_spatial_test.h5ad (2,023 cells, synthetic obsm['spatial'] grid)")
    # main dataset: load dialog
    load(p, BM)
    print("dialog selects", p.locator("select").evaluate_all("els=>els.map(s=>[...s.options].map(o=>o.text))"))
    snap(p,"m04_slots_load_dialog_assay_choices.jpg",[pv("slots","N","Primary assay offers X or layers/counts only; obsp/varp/varm are never read")],[(1,"select >> nth=0","assay: X | layers/counts")])
    t1=time.time(); p.get_by_role("button", name="Explore", exact=True).first.click()
    for i in range(14):
        time.sleep(4)
        if p.get_by_text("X_umap", exact=True).count(): break
    print(f"explore load took ~{time.time()-t1:.0f}s"); time.sleep(6)
    p.get_by_text("X_umap", exact=True).first.click(); time.sleep(4)
    p.locator("select").first.select_option("highres_celltype"); time.sleep(3)
    url0=p.url
    snap(p,"m01_plots_render_umap_celltype.jpg",[pv("every_cell","Y","All 8,090 cells drawn on the stored X_umap, coloured by highres_celltype")],[(1,"canvas","X_umap, 8,090 cells"),(2,"text=Choose annotation","colour by obs column")])
    # slots / cells / genes / image: embedding tabs + colour-by select (its options read from the DOM; a native select cannot be shown open headless)
    opts=p.locator("select").first.evaluate("s=>[...s.options].map(o=>o.text)"); print("annotation options", opts)
    snap(p,"m04_slots_tabs_and_annotation_list.jpg",[
        pv("slots","N","Embedding tabs = the 4 obsm keys; colour-by options (from the DOM) = obs columns only: "+", ".join(opts)+"; no obsp, varp, varm, uns"),
        pv("cells","N","No obsp entry (connectivities, distances, diffusion_distance) among tabs or colour-by options"),
        pv("image","N","No image layer or image input: tabs are obsm keys only")],
        [(1,"button:has-text('X_diffusion') >> xpath=..","embedding tabs: obsm keys only"),(2,"select >> nth=0","colour by: obs columns only (13 options)")])
    # filters: legend click highlights; marker-table sliders
    p.locator("text=GMP").first.click(); time.sleep(4)
    snap(p,"m08_filters_legend_click_highlights_GMP.jpg",[pv("filters","P","Clicking a legend entry highlights that cluster (others grey); no table-driven filter of cells")],[(1,"text=GMP","legend entry clicked"),(2,"canvas","GMP highlighted")])
    p.get_by_role("button", name="Click to filter markers").first.click(); time.sleep(3)
    snap(p,"m08_filters_marker_table_sliders.jpg",[pv("filters","P","Marker-table sliders (Log-FC, delta-detected, expression) filter table rows only; the plot is unchanged")],[(1,"text=Log-FC >> nth=-1","marker filters"),(2,"canvas","plot unchanged")])
    # de: markers for a chosen cluster
    sels=p.locator("select"); sels.nth(2).select_option("highres_celltype"); time.sleep(6)
    sels.nth(3).select_option("HSC"); time.sleep(8)
    snap(p,"m10_de_markers_HSC_vs_rest.jpg",[pv("de","Y","Markers for HSC vs rest computed in the browser after choosing annotation and cluster")],[(1,"select >> nth=3","cluster: HSC"),(2,"text=rowNames >> xpath=../..","marker table")])
    # annot: lasso -> Save -> Selection 1
    p.get_by_role("button", name="Selection").first.evaluate("e=>e.click()"); time.sleep(1)
    box=p.locator("canvas").first.bounding_box(); x0,y0,W,H=box["x"],box["y"],box["width"],box["height"]
    pts=[(0.40,0.12),(0.62,0.12),(0.64,0.32),(0.50,0.33),(0.40,0.20),(0.40,0.12)]
    p.mouse.move(x0+W*pts[0][0],y0+H*pts[0][1]); p.mouse.down()
    for fx,fy in pts[1:]: p.mouse.move(x0+W*fx,y0+H*fy,steps=12)
    p.mouse.up(); time.sleep(4)
    print("SELTXT", p.locator("text=/cells selected/").all_inner_texts()[:3])
    p.get_by_role("button", name="Save", exact=True).first.click(); time.sleep(8)
    print("text inputs", p.locator("input[type=text]").evaluate_all("els=>els.map(e=>e.placeholder||e.value)"))
    snap(p,"m09_annot_saved_selection_no_rename.jpg",[pv("annot","P","Lasso saved as auto-named 'Selection 1' (delete icon only, no rename or label field)")],[(1,"text=Custom Selections","saved lasso"),(2,"text=Selection 1","auto-named, delete icon only")])
    # export
    with p.expect_download(timeout=30000) as d: p.get_by_role("button", name="Save as SVG").first.click()
    dl=d.value; fn=DL+dl.suggested_filename; dl.save_as(fn); print("DOWNLOAD", dl.suggested_filename, os.path.getsize(fn))
    snap(p,"m13_export_save_as_svg.jpg",[pv("export","Y",f"'Save as SVG' downloads {dl.suggested_filename} ({os.path.getsize(fn):,} bytes)")],[(1,"button:has-text('Save as SVG')","Save as SVG")])
    # share
    print("URL before/after", url0, p.url)
    snap(p,"m12_share_url_unchanged_no_save_in_explore.jpg",[pv("share","P",f"URL stays {p.url} after embedding, colour, cluster and selection changes; Explore mode has no SAVE (the .kana export exists only in New Analysis)")],[(1,"text=EXPLORE >> xpath=../..","sidebar: LOAD, EXPLORE, LOGS; no SAVE")])
    print("hosts", hosts); print(f"elapsed {time.time()-T0:.0f}")
    b.close()
