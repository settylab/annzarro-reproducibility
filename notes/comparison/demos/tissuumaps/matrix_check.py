"""TissUUmaps 3.2.1.11 (server build, tissuumaps_server on 127.0.0.1:8908) matrix-mark shots with DOM sidecars.
Data: bm_demo_csc.h5ad (8,090 cells, X as CSC) and spatial_demo.h5ad (2,693 Visium spots, obsp spatial_connectivities
= the stored kNN graph, a synthetic grey tissue image in uns/spatial; see $DEMO_ROOT/tissuumaps/make_data.py).
The WebGL draw-call hook (probe_web.INIT) counts points drawn. Writes screens/tissuumaps/mNN_*.jpg + .annot.yaml."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import json, os, sys, time
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
sys.path.insert(0, f"{_DEMO_ROOT}/_browser")
from record_json import record
from probe_web import INIT
from playwright.sync_api import sync_playwright
OUT = f"{_REPO}/notes/comparison/screens/tissuumaps/"; os.makedirs(OUT, exist_ok=True)
DL = f"{_SCRATCH}/tu_dl/"; os.makedirs(DL, exist_ok=True)
SW = "TissUUmaps 3.2.1.11 (server build, pip; TU4 is beta)"
BM = "bm_demo_csc.h5ad (8,090 cells x 16,285 genes)"; SP = "spatial_demo.h5ad (2,693 Visium spots; synthetic grey tissue image)"
LOG = {}
def pv(c, m=None, t=None):
    # Raw capture only: the mark and caption are written after the shot has been looked at (coordinator's rule,
    # 2026-10-04); this records just which column the shot is meant to inform.
    return {"column": c, "mark": "?", "caption": "raw capture; verdict and caption pending review of the shot"}
def snap(p, name, proves, callouts, data):
    path = OUT + name; p.screenshot(path=path, type="jpeg", quality=72)
    try: record(p, path, tool="tissuumaps", software=SW, by="comparison-auditor", driver=__file__, data=data, proves=proves, callouts=callouts)
    except Exception as e:
        print("  callout failed:", str(e)[:140], flush=True)
        record(p, path, tool="tissuumaps", software=SW, by="comparison-auditor", driver=__file__, data=data, proves=proves, callouts=[])
    print("shot", name, flush=True)
def open_select(p, label):
    p.locator(f"text={label}").locator("xpath=following::span[contains(@class,'select2-selection')][1]").first.click(); time.sleep(1)
def choose(p, label, value, search=False):
    if p.locator(".select2-container--open").count() == 0:
        open_select(p, label)
    if search:
        p.locator(".select2-search__field").last.fill(value); time.sleep(2)
    p.locator("li.select2-results__option", has_text=value).first.click(); time.sleep(8)
def gl(p): return p.evaluate("window.__gl")
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    ctx = b.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True); ctx.add_init_script(INIT)
    p = ctx.new_page(); p.set_default_timeout(15000)
    # bone marrow: slots lists, render, gene colouring
    p.goto("http://127.0.0.1:8908/bm_demo_csc.h5ad", timeout=120000); time.sleep(8)
    open_select(p, "Categorical observations")
    LOG["cat_opts"] = p.locator("li.select2-results__option").all_inner_texts()
    snap(p, "m04_slots_obs_categorical_list.jpg", [pv("slots")],
         [(1, ".select2-results", "categorical obs columns"), (2, "text=Gene expression", "X genes (16,285)")], BM)
    choose(p, "Categorical observations", "highres_celltype"); time.sleep(4)
    g = gl(p); LOG["gl_cat"] = g
    snap(p, "m00_every_cell_bm_umap_celltype.jpg", [pv("every_cell")],
         [(1, "#ISS_viewer, .openseadragon-container", "markers drawn on the UMAP")], BM)
    choose(p, "Gene expression", "Mpo", search=True); time.sleep(3)
    LOG["gl_gene"] = gl(p)
    snap(p, "m03_focus_gene_mpo.jpg", [pv("focus")],
         [(1, "text=Gene expression", "gene picker")], BM)
    # subset: per-category visibility checkboxes in the marker table
    try:
        choose(p, "Categorical observations", "highres_celltype"); time.sleep(3)
        cbs = p.locator("#markers-iss-gui input[type=checkbox]")
        LOG["n_checkboxes"] = cbs.count()
        if cbs.count() > 3:
            cbs.nth(2).click(); time.sleep(4)
        LOG["gl_after_hide"] = gl(p)
        snap(p, "m18_subset_category_toggle.jpg", [pv("subset")],
             [(1, "#markers-iss-gui input[type=checkbox] >> nth=2", "category hidden"), (2, ".openseadragon-container", "remaining cells")], BM)
    except Exception as e:
        LOG["subset_err"] = str(e)[:200]
    # regions: draw a rectangle, see it listed, and what it offers (selection / annotation)
    try:
        p.evaluate("regionUtils.setMode('rectangle')"); time.sleep(1)
        box = p.locator(".openseadragon-container").first.bounding_box()
        x0, y0, W, H = box["x"], box["y"], box["width"], box["height"]
        p.mouse.move(x0 + W * 0.35, y0 + H * 0.35); p.mouse.down()
        p.mouse.move(x0 + W * 0.60, y0 + H * 0.60, steps=15); p.mouse.up(); time.sleep(3)
        p.evaluate("regionUtils.setMode(null)")
        LOG["regions"] = p.evaluate("Object.keys(regionUtils._regions||{}).length")
        snap(p, "m09_annot_region_drawn.jpg", [pv("annot")],
             [(1, ".openseadragon-container", "rectangle region over the cells")], BM)
        p.locator("#title-tab-regions").click(); time.sleep(2)
        LOG["regions_tab"] = p.locator("#markers-regions-panel, #regions-gui, .tab-pane.active").first.inner_text()[:1500]
        snap(p, "m08_selection_regions_tab.jpg", [pv("selection")],
             [(1, "#title-tab-regions", "Regions tab")], BM)
        p.locator("#title-tab-markers").click(); time.sleep(1)
    except Exception as e:
        LOG["regions_err"] = str(e)[:200]
    # File menu: open, save project, capture viewport
    p.locator("#navbarDropdownMenuLink, #a_menubar_File").first.click(); time.sleep(1)
    LOG["file_menu"] = p.locator("#menubar_File").inner_text()
    snap(p, "m12_m13_file_menu.jpg", [pv("share"), pv("export")],
         [(1, "#menubar_File", "Open / Save project / Capture viewport")], BM)
    try:
        p.get_by_text("Capture viewport").first.click(); time.sleep(2)
        snap(p, "m13_export_capture_dialog.jpg", [pv("export")],
             [(1, ".modal-dialog >> nth=-1", "capture dialog")], BM)
        with p.expect_download(timeout=60000) as d:
            p.locator(".modal-dialog button:has-text('OK'), .modal-dialog button:has-text('Capture'), .modal-dialog .btn-primary").last.click()
        dl = d.value; fn = DL + dl.suggested_filename; dl.save_as(fn); LOG["capture"] = [dl.suggested_filename, os.path.getsize(fn)]
    except Exception as e:
        LOG["capture_err"] = str(e)[:200]
    p.keyboard.press("Escape"); time.sleep(1)
    try:
        p.locator("#navbarDropdownMenuLink, #a_menubar_File").first.click(); time.sleep(1)
        p.get_by_text("Save project").first.click(); time.sleep(2)
        snap(p, "m12_share_save_project_dialog.jpg", [pv("share")],
             [(1, ".modal-dialog >> nth=-1", "save project dialog")], BM)
        with p.expect_download(timeout=30000) as d:
            p.locator(".modal-dialog .btn-primary, .modal-dialog button:has-text('Save')").last.click()
        dl = d.value; fn = DL + dl.suggested_filename; dl.save_as(fn); LOG["tmap"] = [dl.suggested_filename, os.path.getsize(fn)]
    except Exception as e:
        LOG["save_err"] = str(e)[:200]
    p.keyboard.press("Escape")
    # spatial demo: spots on the tissue image, edges from obsp/spatial_connectivities, layers tab
    p.goto("http://127.0.0.1:8908/spatial_demo.h5ad", timeout=120000); time.sleep(8)
    choose(p, "Categorical observations", "leiden"); time.sleep(4)
    LOG["gl_sp"] = gl(p)
    snap(p, "m07_m11_spatial_spots_over_image.jpg", [pv("spatial"), pv("image")],
         [(1, "#ISS_viewer, .openseadragon-container", "spots over the image")], SP)
    p.locator("#title-tab-image").click(); time.sleep(2)
    snap(p, "m11_image_layers_tab.jpg", [pv("image")],
         [(1, "#title-tab-image", "Layers tab")], SP)
    p.locator("#title-tab-markers").click(); time.sleep(1)
    LOG["sp_text"] = p.locator("#markers-iss-gui").inner_text()[:2000]
    # zoom in to see the obsp edges, if drawn
    box = p.locator(".openseadragon-container").first.bounding_box()
    p.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
    for _ in range(6): p.mouse.wheel(0, -400); time.sleep(0.4)
    time.sleep(3)
    snap(p, "m01_cells_obsp_edges_zoom.jpg", [pv("cells")],
         [(1, ".openseadragon-container", "zoomed spots; edges if drawn")], SP)
    (open(DL + "matrix_log.json", "w")).write(json.dumps(LOG, indent=1, default=str))
    b.close()
print(json.dumps({k: (v if not isinstance(v, str) else v[:200]) for k, v in LOG.items() if k != "sp_text"}, default=str)[:1500])
