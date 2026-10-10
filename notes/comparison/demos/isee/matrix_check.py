"""iSEE matrix-mark screenshots. Run under gap_run.sh with the playwright venv.
Starts demos/isee/matrix_app.R three times (main, landing, restore) on port 8902, then opens the
online shiny-contest instance. Screens go to screens/isee/mNN_*.jpg."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import subprocess, time, urllib.request, os, sys, zipfile
from playwright.sync_api import sync_playwright
S = f"{_SCRATCH}/isee_matrix"
os.makedirs(S, exist_ok=True)
OUT = f"{_REPO}/notes/comparison/screens/isee/"
APP = f"{_REPO}/notes/comparison/demos/isee/matrix_app.R"
RS = f"{_DEMO_ROOT}/_mamba/envs/rtools/bin/Rscript"
URL = "http://127.0.0.1:8902"
STEP = sys.argv[1] if len(sys.argv) > 1 else "all"

def serve(*args):
    srv = subprocess.Popen([RS, APP, *args], stdout=open(f"{S}/srv_{args[0]}.log", "w"), stderr=subprocess.STDOUT)
    for _ in range(120):
        try: urllib.request.urlopen(URL, timeout=2); return srv
        except Exception: time.sleep(1)
    return srv

def stop(srv):
    srv.terminate()
    try: srv.wait(timeout=20)
    except Exception: srv.kill()

def box(p, sel):
    return p.locator(sel).locator("xpath=ancestor::div[contains(@class,'box')][1]").first

def jpg(loc_or_page, name, **kw):
    loc_or_page.screenshot(path=OUT + name, type="jpeg", quality=70, **kw); print("saved", name)

def export_menu(p):
    p.locator("a.dropdown-toggle:has(i.fa-download)").first.click(); p.wait_for_timeout(800)

def opts(p, sel):
    return p.evaluate(f"()=>{{const s=$('{sel}')[0]; return s&&s.selectize?Object.keys(s.selectize.options):(s?[...s.options].map(o=>o.value):null)}}")

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    ctx = b.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True)
    p = ctx.new_page()
    # ---------------- session A: main app ----------------
    srv = serve("main")
    try:
        p.goto(URL, timeout=120000); p.wait_for_timeout(25000)
        jpg(p, "m00_plots_render.jpg")
        # columns 1, 2, 4, 7: what the panels can read
        print("RD1 ColorBy radio:", p.eval_on_selector_all("input[name=ReducedDimensionPlot1_ColorBy]", "els=>els.map(e=>e.value)"))
        print("RD1 Type options:", opts(p, "#ReducedDimensionPlot1_Type"))
        print("RD1 colour-by column data:", opts(p, "#ReducedDimensionPlot1_ColorByColumnData"))
        print("FAP1 assay options:", opts(p, "#FeatureAssayPlot1_Assay"))
        p.evaluate("()=>$('#ReducedDimensionPlot1_Type')[0].selectize.open()"); p.wait_for_timeout(800)
        jpg(box(p, "#ReducedDimensionPlot1"), "m04_slots_colourby_and_type_dropdown.jpg")
        p.evaluate("()=>$('#ReducedDimensionPlot1_Type')[0].selectize.close()")
        p.evaluate("()=>$('#FeatureAssayPlot1_Assay')[0].selectize.open()"); p.wait_for_timeout(800)
        jpg(box(p, "#FeatureAssayPlot1"), "m04_slots_assay_dropdown.jpg")
        p.evaluate("()=>$('#FeatureAssayPlot1_Assay')[0].selectize.close()")
        # column 8: table search masks a linked plot
        p.fill("#ColumnDataTable1 input[type=search]", "Neutrophil"); p.wait_for_timeout(9000)
        print("CDT1 info:", p.inner_text("#ColumnDataTable1 .dataTables_info")[:120])
        print("RD2 select info:", p.inner_text("#ReducedDimensionPlot2_INTERNAL_PanelMultiSelectInfo")[:200] if p.locator("#ReducedDimensionPlot2_INTERNAL_PanelMultiSelectInfo").count() else "-")
        bb1 = box(p, "#ColumnDataTable1").bounding_box(); bb2 = box(p, "#ReducedDimensionPlot2").bounding_box()
        sy = p.evaluate("window.scrollY")
        y0 = min(bb1["y"], bb2["y"]) + sy; h = max(bb1["y"] + bb1["height"], bb2["y"] + bb2["height"]) + sy - y0
        jpg(p, "m08_table_search_restricts_plot.jpg", full_page=True, clip={"x": bb1["x"], "y": y0, "width": bb2["x"] + bb2["width"] - bb1["x"], "height": min(h, 1000)})
        # column 10: brush in RD1 -> DynamicMarkerTable1 runs scran::findMarkers on the selection
        p.evaluate("window.scrollTo(0,0)")
        img = p.locator("#ReducedDimensionPlot1 img").first; bb = img.bounding_box()
        x0, yy = bb["x"] + bb["width"] * 0.12, bb["y"] + bb["height"] * 0.25
        p.mouse.move(x0, yy); p.mouse.down(); p.mouse.move(x0 + bb["width"] * 0.25, yy + bb["height"] * 0.35, steps=12); p.mouse.up()
        t0 = time.time()
        for _ in range(90):
            p.wait_for_timeout(2000)
            r = p.locator("#DynamicMarkerTable1 tbody tr")
            if r.count() and "No data" not in r.first.inner_text() and time.time() - t0 > 6: break
        print("DMT wait s:", round(time.time() - t0), "rows:", [r.nth(i).inner_text().replace("\t", " ")[:90] for i in range(min(r.count(), 4))])
        print("DMT header:", p.inner_text("#DynamicMarkerTable1 thead")[:200].replace("\n", " "))
        print("DMT info:", p.inner_text("#DynamicMarkerTable1 .dataTables_info")[:120] if p.locator("#DynamicMarkerTable1 .dataTables_info").count() else "-")
        p.wait_for_timeout(1500)
        bbA = box(p, "#ReducedDimensionPlot1").bounding_box(); bbB = box(p, "#DynamicMarkerTable1").bounding_box()
        jpg(box(p, "#DynamicMarkerTable1"), "m10_dynamic_marker_table_on_brush.jpg")
        p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(500)
        jpg(box(p, "#ReducedDimensionPlot1"), "m10_brush_source_umap.jpg")
        # column 13 and code: Export menu
        export_menu(p); jpg(p, "m13_export_menu.jpg", clip={"x": 700, "y": 0, "width": 700, "height": 420})
        p.locator("button#iSEE_INTERNAL_tracked_code").first.click(); p.wait_for_timeout(3000)
        code = p.locator(".modal .ace_content").first.inner_text()
        print("R code first lines:", code[:500].replace("\n", " | "))
        print("R code length chars:", len(code))
        jpg(p, "m13_extract_r_code.jpg")
        p.keyboard.press("Escape"); p.wait_for_timeout(1500)
        export_menu(p); p.click("#iSEE_INTERNAL_export_content"); p.wait_for_timeout(3000)
        print("export choices:", p.eval_on_selector_all("input[name=iSEE_INTERNAL_export_content_choices]", "els=>els.map(e=>e.value)"))
        jpg(p, "m13_download_panel_output_dialog.jpg")
        with p.expect_download(timeout=180000) as dl:
            p.click("#iSEE_INTERNAL_export_content_download")
        d = dl.value; f = f"{S}/{d.suggested_filename}"; d.save_as(f)
        print("export file:", d.suggested_filename, os.path.getsize(f), "bytes")
        for zi in zipfile.ZipFile(f).infolist(): print("  zip:", zi.filename, zi.file_size)
        p.keyboard.press("Escape"); p.wait_for_timeout(1500)
        # column 12: panel settings -> Download RDS
        export_menu(p); p.click("#iSEE_INTERNAL_panel_settings"); p.wait_for_timeout(3000)
        p.uncheck("#iSEE_INTERNAL_memory_se") if p.locator("#iSEE_INTERNAL_memory_se").count() else None
        jpg(p, "m12_panel_settings_download_rds.jpg")
        with p.expect_download(timeout=120000) as dl:
            p.click("#iSEE_INTERNAL_memory_export")
        d = dl.value; state = f"{S}/{d.suggested_filename}"; d.save_as(state)
        print("state file:", d.suggested_filename, os.path.getsize(state), "bytes")
        p.keyboard.press("Escape")
    finally:
        stop(srv)
    # ---------------- session B: default landing page, upload SE + state ----------------
    srv = serve("landing")
    try:
        p.goto(URL, timeout=120000); p.wait_for_timeout(8000)
        p.set_input_files("#se", f"{_DEMO_ROOT}/_data/bm_demo_sce.rds"); p.wait_for_timeout(6000)
        p.set_input_files("#initial", state); p.wait_for_timeout(3000)
        jpg(p, "m12_landing_page_upload.jpg")
        p.click("#iSEE_INTERNAL_launch_init"); p.wait_for_timeout(30000)
        print("landing notifications:", [n.inner_text()[:150] for n in p.locator(".shiny-notification").all()])
        print("landing panels:", p.eval_on_selector_all("div.box h3.box-title", "els=>els.map(e=>e.textContent.trim())"))
        jpg(p, "m12_landing_page_after_launch.jpg")
    finally:
        stop(srv)
    print("--- landing server log tail:"); print(open(f"{S}/srv_landing.log").read()[-800:])
    # ---------------- session C: relaunch from the state file ----------------
    srv = serve("restore", state)
    try:
        p.goto(URL, timeout=120000); p.wait_for_timeout(30000)
        print("restored panels:", p.eval_on_selector_all("div.box h3.box-title", "els=>els.map(e=>e.textContent.trim())"))
        r = p.locator("#DynamicMarkerTable1 tbody tr")
        print("restored DMT rows:", [r.nth(i).inner_text().replace("\t", " ")[:60] for i in range(min(r.count(), 2))])
        jpg(p, "m12_restored_from_state_file.jpg")
    finally:
        stop(srv)
    p.wait_for_timeout(4000)
    jpg(p, "m16_server_stopped_page_greys_out.jpg")
    print("disconnected overlay:", p.locator("#shiny-disconnected-overlay").count())
    # ---------------- column 15: the hosted instance ----------------
    try:
        p.goto("https://kevinrue.shinyapps.io/isee-shiny-contest/", timeout=120000); p.wait_for_timeout(45000)
        print("hosted title:", p.title())
        jpg(p, "m15_hosted_shinyapps_instance.jpg")
    except Exception as e:
        print("hosted failed:", e)
    b.close()
