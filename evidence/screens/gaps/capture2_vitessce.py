import re
"""Vitessce (evidence-curator, 2026-10-04): the hosted app at vitessce.io reading the local bone marrow zarr on 127.0.0.1:8904,
plus the human lymph node demo (remote zarr). steps(page) for _focus_run.py, which starts and stops the data server:
  notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
      notes/comparison/demos/_focus_run.py vitessce 8904 evidence/screens/gaps/capture2_vitessce.py

New:   h03 remote Y (request log of the lymph node demo: zarr chunk reads from data-1.vitessce.io and GCS at load, after a
       Gene List click and after zooming the spatial view; job vit_remote runs only this step: extra argument 'remote'),
       h04 every_cell Y (all 8,090 cells drawn), h05 subset N (the plot options menu: no subset or hide).
Re-captured with DOM sidecars (same filenames; steps of notes/comparison/demos/vitessce/recap_a.py, recap_b.py):
       04_cellset_uncheck_CD4_both_views, 03_lasso_UMAP_highlights_FA (config.json),
       m09_annotation_lasso_creates_set, m09_annotation_set_menu (config_matrix.json; the set menu also proves de N).
"""
import os
import sys
import urllib.parse

sys.path.insert(0, "evidence/screens/gaps")
import gaplib  # noqa: E402
from capture2lib import BY, SCRATCH, TODAY, log, pv, shot, step, tag  # noqa: E402

gaplib.BY = BY
TOOL = "vitessce"
SW = "Vitessce (hosted app at vitessce.io, @vitessce 4.0.10)"
DATA = "bm_demo.zarr (8,090 cells), served on 127.0.0.1:8904"
APP = "https://vitessce.io/#?url=http://127.0.0.1:8904/"
LYMPH = "https://vitessce.io/#?dataset=human-lymph-node-10x-visium"
DRV = "evidence/screens/gaps/capture2_vitessce.py"
LASSO = "[title='Select lasso']"


def S(page, name, proves, callouts, data=DATA, note=None, minc=1):
    return shot(page, TOOL, name, proves, callouts, software=SW, driver=DRV, data=data, note=note, min_callouts=minc)


def openapp(page, cfg, wait=12000):
    page.goto("about:blank")
    page.goto(APP + cfg, timeout=90000)
    try:
        page.wait_for_selector(LASSO, timeout=45000)
    except Exception:
        log("no lasso tool after 45 s; titles:", page.evaluate("()=>[...document.querySelectorAll('[title],[aria-label]')].map(e=>e.getAttribute('title')||e.getAttribute('aria-label')).slice(0,40)"))
        page.screenshot(path=SCRATCH + f"vit_nolasso_{cfg}.jpg", type="jpeg", quality=60)
    page.wait_for_timeout(wait)


def panel(page, title, key):
    """Tag the view (title bar + body) whose title starts with `title`."""
    return tag(page, key, "^" + title, minh=300)


def expand_celltype(page):
    if page.locator("button:text-is('CD4 T cell')").count() and page.locator("button:text-is('CD4 T cell')").first.is_visible():
        return
    sw = page.locator("li.rc-tree-treenode:has(button:text-is('Cell type')) .rc-tree-switcher").first
    sw.click()
    page.wait_for_timeout(1500)
    log("  CD4 visible after expand:", page.locator("button:text-is('CD4 T cell')").count())


def lasso(page, sel, fr):
    page.locator(LASSO).first.click()
    page.wait_for_timeout(700)
    b = page.locator(sel).bounding_box()
    x, y, w, h = b["x"], b["y"], b["width"], b["height"]
    pts = [(x + w * fx, y + h * fy) for fx, fy in fr]
    page.mouse.move(*pts[0])
    page.mouse.down()
    for q in pts[1:]:
        page.mouse.move(*q, steps=25)
        page.wait_for_timeout(40)
    page.mouse.up()
    page.wait_for_timeout(4000)
    n = page.locator("button:text-is('My Selections')").count()
    log("  My Selections after lasso:", n)
    return n


ARM = [(0.43, 0.06), (0.82, 0.06), (0.95, 0.33), (0.80, 0.40), (0.43, 0.10), (0.43, 0.06)]


def bm(page):
    openapp(page, "config.json")
    um, fa = panel(page, "Scatterplot \\(UMAP\\)", "umap"), panel(page, "Scatterplot \\(FA\\)", "fa")
    cs = panel(page, "Cell Sets", "cellsets")
    foot = tag(page, "hmfoot", "8,090 cells × 16,285 genes")
    S(page, "h04_every_cell_all_cells_drawn.jpg",
      [pv("every_cell", "Y", f"Vitessce @vitessce 4.0.10 ({TODAY}): both scatterplots draw every one of the 8,090 cells (one deck.gl ScatterplotLayer over the whole embedding, no downsampling)")],
      [(1, um, "UMAP: all cells as points"), (2, fa, "FA: all cells as points"), (3, foot, "8,090 cells × 16,285 genes"), (4, cs, "Cell Sets with per-set counts")])

    def options():
        page.locator(um + " [aria-label='Open plot options menu']").first.click()
        page.wait_for_timeout(1200)
        log("  options:", page.evaluate("()=>[...document.querySelectorAll('[aria-label=\"Menu of options available for the view\"] *')].filter(e=>!e.children.length).map(e=>(e.innerText||e.textContent||'').trim()).filter(Boolean).slice(0,40)"))
        S(page, "h05_subset_N_plot_options_no_subset.jpg",
          [pv("subset", "N", f"Vitessce @vitessce 4.0.10 ({TODAY}): the scatterplot options offer set labels, polygons, radius and opacity, and Cell Sets only colour or highlight sets; no subset, hide-others or sample control")],
          [(1, "[aria-label='Menu of options available for the view']", "plot options: no subset or hide"), (2, cs, "Cell Sets: highlight only")])
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
        page.mouse.click(1380, 880)
        page.wait_for_timeout(600)
    step("options", options)

    def uncheck():
        expand_celltype(page)
        row = "li.rc-tree-treenode:has(button:text-is('CD4 T cell'))"
        box = row + " .rc-tree-checkbox"
        log("  cd4 checkbox count", page.locator(box).count())
        page.locator(box).first.click(force=True)
        page.wait_for_timeout(4000)
        foot2 = tag(page, "hmfoot2", "8,090 cells × 16,285 genes, with")
        S(page, "04_cellset_uncheck_CD4_both_views.jpg",
          [pv("selection", "Y", f"Vitessce @vitessce 4.0.10 ({TODAY}): unticking CD4 T cell (40 cells) in Cell Sets drops it from both scatterplots and the heatmap"),
           pv("filters", "P", "a cell-set checkbox restricts every view, but cells are greyed, not hidden, and there is no table filter")],
          [(1, row, "CD4 T cell unticked"), (2, um, "UMAP"), (3, fa, "FA"), (4, foot2, "heatmap: cells selected")], minc=3)
        page.locator(box).first.click(force=True)
        page.wait_for_timeout(2500)
    step("uncheck", uncheck)

    def las():
        if lasso(page, um, ARM):
            S(page, "03_lasso_UMAP_highlights_FA.jpg",
              [pv("selection", "Y", f"Vitessce @vitessce 4.0.10 ({TODAY}): a lasso on the UMAP highlights the same cells in the FA plot and restricts the heatmap")],
              [(1, um, "lasso on UMAP"), (2, fa, "same cells in FA"), (3, "li.rc-tree-treenode:has(button:text-is('My Selections'))", "new set in Cell Sets"),
               (4, tag(page, "hmfoot3", "8,090 cells × 16,285 genes, with"), "heatmap restricted to the selection")], minc=3)
    step("lasso", las)


def matrix(page):
    openapp(page, "config_matrix.json")
    um = panel(page, "Scatterplot \\(UMAP\\)", "umap")
    if not lasso(page, um, [(0.30, 0.05), (0.70, 0.05), (0.75, 0.30), (0.60, 0.33), (0.32, 0.18), (0.30, 0.05)]):
        return
    ms = "li.rc-tree-treenode:has(button:text-is('My Selections'))"
    S(page, "m09_annotation_lasso_creates_set.jpg",
      [pv("annot", "P", f"Vitessce @vitessce 4.0.10 ({TODAY}): a lasso creates 'My Selections' > 'Selection 1' in the view state; the store is not written")],
      [(1, um, "lasso on UMAP"), (2, ms, "new set 'My Selections'"), (3, ".vega-embed >> nth=0", "Cell Set Sizes: the selection")], minc=2)
    page.locator(ms + " [aria-label='Open Node View Menu']").first.click(force=True)
    page.wait_for_timeout(1200)
    items = page.evaluate("()=>[...document.querySelectorAll('[role=menuitem], [role=menu] li, .MuiMenuItem-root')].map(e=>(e.innerText||e.textContent||'').trim()).filter(Boolean)")
    log("  set menu:", items)
    menu = tag(page, "setmenu", "^Rename", minh=60)
    S(page, "m09_annotation_set_menu.jpg",
      [pv("annot", "P", f"Vitessce @vitessce 4.0.10 ({TODAY}): the set menu offers Rename, Delete and Export; sets live in the view state, nothing is written back to the store"),
       pv("de", "N", "the set menu, where a comparison would start, has no differential-expression or compare item")],
      [(1, menu, "set menu: " + ", ".join(items[:5])[:80]), (2, ms, "My Selections")], minc=1)
    page.keyboard.press("Escape")


DATAHOSTS = ("data-1.vitessce.io", "vitessce-data.storage.googleapis.com")
CHUNK = re.compile(r"/(c/)?\d+([./]\d+)*$")   # zarr chunk keys: .../0, .../0.0, .../0/0/0, .../c/0/0


def short(path):
    """.../<store>.zarr/<array>/<key>: drop the bucket prefix, keep the store name and the key."""
    i = path.find(".zarr")
    return ".../" + path[path.rfind("/", 0, i) + 1:] if i > 0 else path[-90:]


def click_gene(p):
    """Click the first entries of the Gene List view; returns the gene names clicked."""
    gl = tag(p, "genelist", "^Gene List$", minh=150)
    try:
        p.locator(gl).first.scroll_into_view_if_needed(timeout=3000)
        p.wait_for_timeout(800)
    except Exception:
        pass
    pts = p.evaluate("""() => { const v = document.querySelector("[data-cap='genelist']"); if (!v) return [];
      const vb = v.getBoundingClientRect();
      return [...v.querySelectorAll('*')].filter(e => !e.children.length)
        .map(e => [(e.innerText || e.textContent || '').trim(), e.getBoundingClientRect()])
        .filter(([t, b]) => /^[A-Za-z0-9][A-Za-z0-9.\\-]{1,15}$/.test(t) && !/^(Search|Gene|List)$/.test(t) && b.width > 0 && b.height > 0
                && b.y > vb.y + 40 && b.y + b.height < innerHeight)
        .slice(0, 2).map(([t, b]) => [t, b.x + b.width / 2, b.y + b.height / 2]); }""")
    log("  gene list entries:", pts)
    done = []
    for t, x, y in pts[:2]:
        p.mouse.click(x, y)
        done.append(t)
        p.wait_for_timeout(6000)
    if not done:  # fallback: the first entry seen in the earlier run
        try:
            p.get_by_text("A2M", exact=True).first.click(timeout=4000)
            done.append("A2M")
            p.wait_for_timeout(6000)
        except Exception as e:
            log("  no gene clicked:", str(e)[:100])
    return done


def zoom(p):
    """Zoom into the spatial view: finer OME-zarr image levels are fetched tile by tile."""
    sp = tag(p, "spatial", "^Spatial$", minh=300)
    try:
        bb = p.locator(sp).first.bounding_box(timeout=3000)
        p.mouse.move(bb["x"] + bb["width"] * 0.5, bb["y"] + bb["height"] * 0.5)
        for _ in range(6):
            p.mouse.wheel(0, -400)
            p.wait_for_timeout(700)
        return True
    except Exception as e:
        log("  zoom failed:", str(e)[:100])
        return False


def remote(page):
    p = page.context.new_page()
    rows = []
    phase = ["load"]

    def onfin(req):
        try:
            u = urllib.parse.urlparse(req.url)
            if u.netloc not in DATAHOSTS:
                return
            r = req.response()
            try:
                n = req.sizes()["responseBodySize"]
            except Exception:
                n = None
            if not isinstance(n, int) or n < 0:   # 2026-10-04: some responses report a negative body size
                cl = r.headers.get("content-length") if r else None
                n = int(cl) if cl and cl.isdigit() else "?"
            rows.append({"phase": phase[0], "host": u.netloc, "method": req.method, "path": u.path, "range": req.headers.get("range", ""),
                         "status": r.status if r else "-", "bytes": n})
        except Exception:
            pass
    p.on("requestfinished", onfin)
    p.goto(LYMPH, timeout=90000)
    p.wait_for_timeout(25000)
    phase[0] = "gene"
    genes = click_gene(p)
    p.wait_for_timeout(4000)
    phase[0] = "zoom"
    zoomed = zoom(p)
    p.wait_for_timeout(8000)
    p.remove_listener("requestfinished", onfin)
    p.screenshot(path=SCRATCH + "vit_lymph_after_interaction.jpg", type="jpeg", quality=60)

    def is_chunk(r):
        return r["status"] in (200, 206) and (bool(CHUNK.search(r["path"])) or bool(r["range"]))
    count = {ph: sum(1 for r in rows if r["phase"] == ph and is_chunk(r)) for ph in ("load", "gene", "zoom")}
    nbytes = {ph: sum(r["bytes"] for r in rows if r["phase"] == ph and is_chunk(r) and isinstance(r["bytes"], int)) for ph in count}
    hosts = {}
    for r in rows:
        hosts[r["host"]] = hosts.get(r["host"], 0) + 1
    log("hosts:", hosts, "chunk reads per phase:", count, "genes clicked:", genes, "zoomed:", zoomed)
    for r in rows:
        log("  req", r["phase"], r["host"][:12], r["method"], short(r["path"]), r["range"], r["status"], r["bytes"])
    if not any(count.values()):
        log("no chunk reads seen: no shot")
        p.close()
        return
    keep, seen, meta = [], set(), 0
    for i, r in enumerate(rows):  # a few metadata reads, the first chunk of each array at load, then the reads after each interaction
        if is_chunk(r):
            arr = (r["host"], r["path"].rsplit("/", 1)[0])
            if r["phase"] == "load" and arr in seen:
                continue
            seen.add(arr)
            if r["phase"] == "load" and sum(1 for j in keep if rows[j]["phase"] == "load" and is_chunk(rows[j])) >= 8:
                continue
            if r["phase"] != "load" and sum(1 for j in keep if rows[j]["phase"] == r["phase"]) >= 8:
                continue
            keep.append(i)
        elif r["phase"] == "load" and meta < 4 and r["status"] == 200:
            meta += 1
            keep.append(i)
    show = [rows[i] for i in keep]
    hl = [i for i, r in enumerate(show) if is_chunk(r)]
    lab = {"load": "page load", "gene": "click " + "/".join(genes) if genes else "gene click", "zoom": "zoom spatial"}
    host = {"data-1.vitessce.io": "data-1.vitessce.io", "vitessce-data.storage.googleapis.com": "storage.googleapis.com"}
    summary = (f"{len(rows)} requests to the two data hosts; chunk reads: {count['load']} at page load ({nbytes['load'] / 1e3:,.0f} kB), "
               f"{count['gene']} after clicking {', '.join(genes) or 'no gene'} in the Gene List ({nbytes['gene'] / 1e3:,.0f} kB), "
               f"{count['zoom']} after zooming the spatial view ({nbytes['zoom'] / 1e3:,.0f} kB)")
    gi = [k for k, r in enumerate(show) if r["phase"] == "gene" and is_chunk(r)]
    zi = [k for k, r in enumerate(show) if r["phase"] == "zoom" and is_chunk(r)]
    li = [k for k, r in enumerate(show) if r["phase"] == "load" and is_chunk(r)]
    callouts = ([(1, f"#r{li[0]}", "chunk read at page load")] if li else []) + \
               ([(2, f"#r{gi[0]}", "after a gene click: new chunk reads")] if gi else []) + \
               ([(3, f"#r{zi[0]}", "after zooming: image tiles, chunk by chunk")] if zi else []) + [(4, ".sub", "chunk reads per step")]
    gaplib.table_shot(
        p, tool=TOOL, name="h03_remote_request_log_lymph_node_zarr.jpg",
        title="Request log: vitessce.io reads the lymph node demo's remote zarr stores chunk by chunk",
        sub=f"{SW}, human-lymph-node-10x-visium demo opened {TODAY} (Playwright request log: 25 s after load, then a Gene List click, then a zoom). {summary}.",
        header=["step", "host", "method", "path (zarr key)", "status", "bytes"],
        rows=[[lab[r["phase"]], host.get(r["host"], r["host"]), r["method"], short(r["path"]) + (f"  [{r['range']}]" if r["range"] else ""), r["status"], r["bytes"]] for r in show],
        hl=hl,
        note="Highlighted: zarr chunk reads (keys like .../0.0 or .../0/0/0) from the AnnData zarr on data-1.vitessce.io and the OME-zarr image on "
             "Google Cloud Storage. Each interaction fetches only the chunks it needs; nothing is downloaded whole or uploaded first.",
        proves=[pv("remote", "Y", f"request log, Vitessce @vitessce 4.0.10 ({TODAY}): the lymph node demo reads its AnnData zarr (data-1.vitessce.io) and OME-zarr image "
                                  f"(Google Cloud Storage) over HTTP chunk by chunk: {count['load']} chunk GETs at load, {count['gene']} more after a Gene List click, "
                                  f"{count['zoom']} after zooming")],
        callouts=callouts, software=SW, driver=DRV, data="human-lymph-node-10x-visium (Vitessce demo, remote zarr)", url=LYMPH)
    p.close()


def steps(page, S_):
    page.context.grant_permissions(["local-network-access"], origin="https://vitessce.io")
    page.set_default_timeout(20000)
    only = sys.argv[4:]  # _focus_run.py <tool> <port> <this file> [bm] [matrix] [remote]; none = all
    for name, f in (("bm", bm), ("matrix", matrix), ("remote", remote)):
        if not only or name in only:
            step(name, lambda: f(page))
    log("done")
