#!/usr/bin/env python3
"""Drive a running scSVA app in headless Chromium: load the three HDF5 inputs through its
File tab, draw the 2D view (density, MALAT1 / chosen gene, groups), probe hover/click/brush,
and save screenshots + timings.

  python -I drive.py URL INPUTDIR OUTDIR GENE [--shots]

File choice: scSVA's file buttons open a shinyFiles modal (a directory browser rooted at
getVolumes()). The modal is opened and screenshotted once, then the chosen path is
delivered with Shiny.setInputValue in the exact value shape shinyFiles sends
({files: {"0": ["", dir parts..., file]}, root}); parseFilePaths() on the server reads it
as it would a click. Everything after the file choice is real clicks on the app's widgets.
"""
import json, sys, time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL, INDIR, OUT, GENE = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
SHOTS = "--shots" in sys.argv
OUT.mkdir(parents=True, exist_ok=True)
T = {}
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(f"{time.strftime('%H:%M:%S')} {s}"); _last[0] = time.time()
    print(LOG[-1], flush=True)


def shot(pg, name):
    if SHOTS or name.startswith("ladder"):
        pg.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
        log("shot", name)


def busy_wait(pg, timeout_s):
    """Wait until Shiny is idle (no 'shiny-busy' class on <html>) for 2 s in a row."""
    t0 = time.time(); idle_since = None
    while time.time() - t0 < timeout_s:
        busy = pg.evaluate("document.documentElement.classList.contains('shiny-busy')")
        if not busy:
            idle_since = idle_since or time.time()
            if time.time() - idle_since > 2:
                return time.time() - t0
        else:
            idle_since = None
        time.sleep(0.25)
    raise TimeoutError(f"shiny still busy after {timeout_s}s")


def soft(name, fn):
    """Run a step; on timeout record it and carry on (some tabs never go idle)."""
    try:
        return fn()
    except TimeoutError as e:
        T[name + "_timeout"] = str(e)[:200]; log("TIMEOUT", name, e); return None


def choose_file(pg, input_id, path):
    parts = [""] + [p for p in str(path).split("/") if p]
    pg.evaluate("([id, parts]) => Shiny.setInputValue(id, {files: {'0': parts}, root: ROOT}, {priority: 'event'})"
                .replace("ROOT", "window.__scsva_root"), [input_id, parts])


def selectize(pg, input_id, value, timeout_s=600):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        opts = pg.evaluate(f"(() => {{const s=document.getElementById('{input_id}'); if(!s||!s.selectize) return null; return Object.keys(s.selectize.options);}})()")
        if opts and value in opts:
            pg.evaluate(f"document.getElementById('{input_id}').selectize.setValue({json.dumps(value)})")
            return
        time.sleep(0.5)
    raise TimeoutError(f"{input_id}: option {value!r} never appeared (have {opts})")


def set_verified(pg, pairs, timeout_s=120):
    """Set several selectize inputs and confirm Shiny holds each value (a late
    updateSelectizeInput from the server can overwrite an earlier set)."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        for k, v in pairs.items():
            selectize(pg, k, v)
        time.sleep(2)
        got = pg.evaluate("(ks) => ks.map(k => Shiny.shinyapp.$inputValues[k] !== undefined ? Shiny.shinyapp.$inputValues[k] : (Shiny.shinyapp.$inputValues[k + ':shiny.selectize'] || null))", list(pairs))
        if all(g == v for g, v in zip(got, pairs.values())):
            log("verified", pairs); return
        log("re-set", pairs, "got", got)
    raise TimeoutError(f"inputs never held {pairs}")


def plot_src_hash(pg, out_id):
    return pg.evaluate(f"(() => {{const i=document.querySelector('#{out_id} img'); return i ? i.src.length + ':' + i.src.slice(-64) : null;}})()")


def wait_new_plot(pg, out_id, before, timeout_s):
    """New image in out_id AND settled: the output no longer carries Shiny's 'recalculating' class,
    no progress/notification panel is visible, and the image is unchanged for 2 s.
    (Run 10171744: a src change alone fired while scSVA's 'Getting groups' progress was at ~10%.)"""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        h = plot_src_hash(pg, out_id)
        settled = pg.evaluate(f"""(() => {{const o=document.getElementById('{out_id}');
            const recalc = o && o.classList.contains('recalculating');
            const prog = [...document.querySelectorAll('.shiny-progress, .shiny-notification, .progress-message')].some(e => e.offsetParent);
            return !recalc && !prog; }})()""")
        if h and h != before and settled:
            time.sleep(2)
            if plot_src_hash(pg, out_id) == h:
                return time.time() - t0
        time.sleep(0.5)
    raise TimeoutError(f"{out_id} did not redraw and settle in {timeout_s}s")


import threading, os
_last = [time.time()]
def _watchdog(limit=1200):
    while True:
        time.sleep(15)
        if time.time() - _last[0] > limit:
            T["status"] = f"watchdog: no step finished in {limit}s (last: {LOG[-1] if LOG else '-'})"
            (OUT / "timings.json").write_text(json.dumps(T, indent=1)); (OUT / "drive.log").write_text("\n".join(LOG) + "\n")
            os._exit(9)
threading.Thread(target=_watchdog, daemon=True).start()


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 1600, "height": 1000})
        t0 = time.time()
        pg.goto(URL, wait_until="domcontentloaded", timeout=600_000)
        pg.wait_for_function("window.Shiny && Shiny.shinyapp && Shiny.shinyapp.isConnected()", timeout=600_000)
        busy_wait(pg, 600)
        T["app_ready_s"] = round(time.time() - t0, 2)
        shot(pg, "01_file_tab")

        # open the real shinyFiles modal once (evidence of the file chooser) and read its root name
        pg.click("#inputFile_XY"); time.sleep(4)
        shot(pg, "02_file_chooser_modal")
        root = pg.evaluate("""(() => { for (const s of document.querySelectorAll('select')) {
              if (s.offsetParent && [...s.options].some(o => o.value === 'Computer')) return s.value; }
              return null; })()""")
        T["modal_visible_text"] = pg.evaluate("(() => {const m=[...document.querySelectorAll('.modal')].find(e=>e.offsetParent); return m ? m.innerText.slice(0,300) : null;})()")
        log("shinyFiles root (from modal)", root, "| modal:", T["modal_visible_text"])
        for sel in ["button:has-text('Cancel'):visible", ".modal button.close:visible"]:
            el = pg.query_selector(sel)
            if el:
                el.click(); time.sleep(1); break
        pg.keyboard.press("Escape"); time.sleep(1)
        pg.evaluate(f"window.__scsva_root = {json.dumps(root or 'Computer')}")

        # XY
        choose_file(pg, "inputFile_XY", INDIR / "coords.h5")
        set_verified(pg, {"X_coord": "/X", "Y_coord": "/Y"})
        t = time.time(); pg.click("#load_dataset_XY"); time.sleep(1); busy_wait(pg, 3600)
        T["load_xy_s"] = round(time.time() - t, 2)
        # Genes (HDF5 group, one dataset per gene)
        choose_file(pg, "inputFile_Genes", INDIR / "genes.h5")
        pg.click("input[name='h5_type'][value='G']"); time.sleep(1)
        set_verified(pg, {"inputGenes": "/"})
        t = time.time(); pg.click("#load_dataset_GE"); time.sleep(1); busy_wait(pg, 3600)
        T["load_gene_list_s"] = round(time.time() - t, 2)
        # Groups
        choose_file(pg, "inputFile_Clusters", INDIR / "clusters.h5")
        set_verified(pg, {"inputClusters": "/clusters"})
        t = time.time(); pg.click("#load_dataset_CL"); time.sleep(1); busy_wait(pg, 3600)
        T["load_groups_s"] = round(time.time() - t, 2)
        shot(pg, "03_file_tab_loaded")

        # 2D density
        pg.click("a:has-text('Visualize')"); pg.click("a:has-text('2D')")
        t = time.time(); T["density_draw_s"] = round(wait_new_plot(pg, "plot1", None, 3600), 2)
        busy_wait(pg, 600)
        shot(pg, "04_2d_density_grid512")
        T["plot1_img_natural"] = pg.evaluate("(() => {const i=document.querySelector('#plot1 img'); return [i.naturalWidth, i.naturalHeight];})()")

        # hover probe: plotOutput('plot1') is declared with click/dblclick/brush but no hover
        box = pg.query_selector("#plot1 img").bounding_box()
        cx, cy = box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5
        pg.mouse.move(cx, cy); time.sleep(2)
        T["hover_input_exists"] = pg.evaluate("Object.keys(Shiny.shinyapp.$inputValues).filter(k => k.indexOf('hover') >= 0)")
        shot(pg, "05_hover_no_tooltip")

        # Gene and group views, driven from the 2D tab. The Analysis tab's plotly panels froze headless
        # Chromium 105 (server idle, page unresponsive >12 min, run 10168843), so its two inputs are set
        # through Shiny; server.R L1250-1270 then switches the SAME plot1 to the gene view (plot.ID 2).
        before = plot_src_hash(pg, "plot1")
        pg.evaluate(f"Shiny.setInputValue('choose_gene', {json.dumps(GENE)}, {{priority: 'event'}})")
        time.sleep(4)
        pg.evaluate("Shiny.setInputValue('plot_expression', true, {priority: 'event'})")
        r = soft("gene_draw", lambda: wait_new_plot(pg, "plot1", before, 900)); T["gene_draw_s"] = round(r, 2) if r else None
        time.sleep(2); shot(pg, "06_2d_gene_mean_per_bin")

        # brush a rectangle on plot1, then double-click: scSVA zooms by re-binning the window (server.R L1019-1028)
        b1 = pg.query_selector("#plot1 img").bounding_box()
        x0, y0 = b1["x"] + b1["width"] * 0.40, b1["y"] + b1["height"] * 0.40
        pg.mouse.move(x0, y0); pg.mouse.down(); pg.mouse.move(x0 + b1["width"] * 0.15, y0 + b1["height"] * 0.15, steps=10); pg.mouse.up()
        time.sleep(2); shot(pg, "07_brush_on_bins")
        T["brush_input"] = pg.evaluate("JSON.stringify(Shiny.shinyapp.$inputValues['plot1_brush'] || null).slice(0, 300)")
        before = plot_src_hash(pg, "plot1")
        pg.mouse.dblclick(x0 + b1["width"] * 0.07, y0 + b1["height"] * 0.07)
        r = soft("zoom_draw", lambda: wait_new_plot(pg, "plot1", before, 900)); T["zoom_draw_s"] = round(r, 2) if r else None
        time.sleep(2); shot(pg, "08_zoomed_rebinned")
        pg.click("#reset_view"); time.sleep(3)

        # groups (Metadata > Groups > show_clusters), shown on plot1
        pg.evaluate("Shiny.setInputValue('plot_expression', false, {priority: 'event'})"); time.sleep(3)
        before = plot_src_hash(pg, "plot1")
        pg.evaluate("Shiny.setInputValue('show_clusters', true, {priority: 'event'})")
        r = soft("groups_draw", lambda: wait_new_plot(pg, "plot1", before, 900)); T["groups_draw_s"] = round(r, 2) if r else None
        time.sleep(2); shot(pg, "09_2d_groups")
        pg.click("a:has-text('Metadata')"); time.sleep(1); pg.click("a:has-text('Groups')"); time.sleep(3)
        shot(pg, "10_groups_tab")
        pg.click("a:has-text('Annotation')"); time.sleep(3); shot(pg, "11_annotation_tab")
        T["total_s"] = round(time.time() - t0, 2)
        b.close()


try:
    main(); T["status"] = "ok"
except Exception as e:  # record where it stopped; the run's status is in timings.json
    T["status"] = f"error: {type(e).__name__}: {e}"[:600]
    log("ERROR", T["status"])
finally:
    (OUT / "timings.json").write_text(json.dumps(T, indent=1))
    (OUT / "drive.log").write_text("\n".join(LOG) + "\n")
    print(json.dumps(T, indent=1))
