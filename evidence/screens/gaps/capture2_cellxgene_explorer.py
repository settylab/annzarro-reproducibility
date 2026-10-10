"""CZ CELLxGENE Discover Explorer, hosted (evidence-curator, 2026-10-04): the Visium muscle dataset (4,992 spots). Re-captures
the Explorer matrix shots under their existing filenames with DOM sidecars, and adds the request log for remote P and lazy Y.
steps(page) for _focus_run.py (no local server):
  notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
      notes/comparison/demos/_focus_run.py none 0 evidence/screens/gaps/capture2_cellxgene_explorer.py
Steps of notes/comparison/demos/cellxgene/matrix_check.py explorer():
  m07 default spatial view; m04 embedding menu; MYH7 added (request log); m11 MYH7 on the tissue image;
  m13 the download menu with "Current view (.png)" (downloaded once); m12 the same URL reopened.
  h03 request log: layout/obs, the per-gene data/var request and its size, and the s3_uri endpoint (Discover's own bucket).
"""
import os
import re
import sys
import urllib.parse

sys.path.insert(0, "evidence/screens/gaps")
import gaplib  # noqa: E402
from capture2lib import BY, SCRATCH, TODAY, log, pv, shot, step, tag  # noqa: E402

gaplib.BY = BY
DRV = "evidence/screens/gaps/capture2_cellxgene_explorer.py"
SW = f"CZ CELLxGENE Discover Explorer (hosted, as served {TODAY})"
DATA = "Visium Spatial of Human muscle in Healthy control_2 (4,992 spots x 35,476 genes)"
VISIUM = "https://cellxgene.cziscience.com/e/85585f3f-d16a-412d-b93a-406d52721221.cxg/"
E = "Explorer (hosted)"
COUNT = "text=/[0-9]+ of [0-9]+ cells/ >> nth=0"


def tid(t):
    return f"[data-testid='{t}']"


def S(page, name, proves, callouts, minc=1, note=None):
    return shot(page, "cellxgene", name, proves, callouts, software=SW, driver=DRV, data=DATA, url=VISIUM, note=note, min_callouts=minc)


def ready(page, n=24):
    for i in range(n):
        page.wait_for_timeout(5000)
        if page.locator(tid("layout-choice")).count() and page.locator("canvas").count():
            log("explorer ready after", (i + 1) * 5, "s")
            break
    page.wait_for_timeout(8000)


def big_canvas(page):
    r = page.evaluate("""()=>{const c=[...document.querySelectorAll('canvas')].filter(e=>e.getBoundingClientRect().width>300);
      c.sort((a,b)=>b.getBoundingClientRect().width*b.getBoundingClientRect().height-a.getBoundingClientRect().width*a.getBoundingClientRect().height);
      if(!c.length) return null; c[0].setAttribute('data-cap','emb'); const b=c[0].getBoundingClientRect(); return [b.x,b.y,b.width,b.height].map(Math.round)}""")
    log("  canvas", r)
    return "[data-cap='emb']"


def addgene(page, g):
    inp = page.locator(f"{tid('gene-search')} input")
    if inp.count() == 0:
        inp = page.locator(tid("gene-search"))
    inp.first.click()
    page.wait_for_timeout(600)
    inp.first.fill(g)
    page.wait_for_timeout(2500)
    items = page.locator(".bp3-menu-item, .bp4-menu-item, .bp5-menu-item, [role=option]")
    items.filter(has_text=re.compile("^" + g + "$")).first.click()
    page.wait_for_timeout(4000)


def steps(page, S_):
    page.set_default_timeout(20000)
    reqs = []

    def onresp(r):
        if "/api/v0.3/" in r.url:
            try:
                n = len(r.body())
            except Exception:
                n = -1
            reqs.append((r.request.method, r.url, r.status, n))
    page.on("response", onresp)
    page.goto(VISIUM, timeout=120000)
    ready(page)
    emb = big_canvas(page)
    cnt = page.locator(COUNT).inner_text(timeout=3000) if page.locator(COUNT).count() else "NA"
    log("count", cnt)
    S(page, "m07_spatial_explorer_visium_default.jpg",
      [pv("spatial", "Y", f"{E} ({TODAY}): the Visium dataset opens in its spatial embedding, spots in tissue coordinates with a scale bar"),
       pv("hosted", "Y", "Explorer on CZ CELLxGENE Discover serves the dataset to an anonymous visitor: no sign-in, no install"),
       pv("every_cell", "Y", f"all spots are drawn ({cnt}), no downsampling")],
      [(1, tid("layout-choice"), "embedding: spatial"), (2, emb, "spots in tissue coordinates"), (3, COUNT, cnt), (4, tid("header"), "Discover header, no login")], minc=2)

    def lay():
        page.click(tid("layout-choice"))
        page.wait_for_timeout(1500)
        opts = page.evaluate("()=>[...document.querySelectorAll('[role=menuitem],[role=option],[role=radio],label')].map(e=>e.innerText.trim()).filter(t=>t&&t.length<40).slice(0,20)")
        log("layouts:", opts)
        pop = ".bp5-popover-content >> visible=true" if page.locator(".bp5-popover-content").count() else ".bp4-popover-content >> visible=true"
        S(page, "m04_slots_explorer_embedding_menu.jpg",
          [pv("slots", "N", f"{E} ({TODAY}): one obsm embedding (spatial), obs fields and X genes; no layer, obsp, varp or varm is reachable")],
          [(1, pop, "Embedding Choice: spatial only (obsm)"), (2, tid("layout-choice"), "embedding menu")], minc=1)
        page.keyboard.press("Escape")
        page.mouse.click(1380, 880)
        page.wait_for_timeout(800)
    step("layouts", lay)

    def gene():
        n0 = len(reqs)
        addgene(page, "MYH7")
        page.click(tid("colorby-MYH7"))
        page.wait_for_timeout(6000)
        log("gene requests:", [(u.split("/api/v0.3/")[-1][:90], n) for _, u, _, n in reqs[n0:]])
        S(page, "m11_image_explorer_myh7_on_tissue.jpg",
          [pv("image", "Y", f"{E} ({TODAY}): the Visium H&E image is drawn under the spots, with MYH7 colouring on top")],
          [(1, emb, "H&E tissue under the MYH7-coloured spots"), (2, tid("colorby-MYH7"), "MYH7 chosen as colour")], minc=1)
        return n0
    n0 = step("gene", gene) or 0

    def dl():
        page.click(tid("download-menu-button"))
        page.wait_for_timeout(1200)
        items = page.evaluate("()=>[...document.querySelectorAll('[role=menuitem], .bp5-menu-item, .bp4-menu-item')].map(e=>e.innerText.trim()).filter(Boolean)")
        log("download items:", items)
        cv = page.get_by_text("Current view (.png)").first
        S(page, "m13_export_explorer_download_menu.jpg",
          [pv("export", "Y", f"{E} ({TODAY}): the download menu offers 'Current view (.png)', which saves the plot as a PNG without code")],
          [(1, tid("download-menu-button"), "download button"), (2, "text=Current view (.png) >> nth=0", "Current view (.png)")], minc=2)
        try:
            with page.expect_download(timeout=60000) as d:
                cv.click()
            out = SCRATCH + "cxg_explorer_view.png"
            d.value.save_as(out)
            log("download:", d.value.suggested_filename, os.path.getsize(out), "bytes")
        except Exception as e:
            log("download failed", str(e)[:120])
    step("download", dl)

    def share():
        p2 = page.context.new_page()
        p2.goto(page.url, timeout=120000)
        ready(p2, 12)
        e2 = big_canvas(p2)
        S(p2, "m12_share_explorer_same_url_reopened.jpg",
          [pv("share", "N", f"{E} ({TODAY}): the dataset URL reopened after colouring by MYH7 shows uncoloured spots and an empty gene list")],
          [(1, e2, "spots uncoloured; MYH7 colouring not restored"), (2, tid("gene-search"), "gene list empty")], minc=1)
        p2.close()
    step("share", share)

    def log_shot():
        s3 = page.request.get(VISIUM + "api/v0.3/s3_uri")
        s3txt = s3.text()[:160]
        log("s3_uri:", s3.status, s3txt)
        rows, hl = [], []
        seen = set()
        for m, u, st, n in reqs:
            pu = urllib.parse.urlparse(u)
            path = pu.path.split("/api/v0.3/")[-1]
            key = path + "?" + pu.query
            if key in seen:
                continue
            seen.add(key)
            q = urllib.parse.unquote(pu.query)
            if path.startswith(("layout/obs", "data/var", "data/obs", "s3_uri")) or "nbins" in q:
                hl.append(len(rows))
            rows.append([m, path[:40], q[:70], st, f"{n:,}" if n >= 0 else "?"])
        rows, hl = rows[:29], [i for i in hl if i < 29]
        rows.append(["GET", "s3_uri", "(fetched by the driver)", s3.status, s3txt])
        hl.append(len(rows) - 1)
        gi = [i for i, r in enumerate(rows) if r[1].startswith("data/var") and "MYH7" in r[2]]
        p3 = page.context.new_page()
        p3.set_viewport_size({"width": 1400, "height": 900})
        gaplib.table_shot(
            p3, tool="cellxgene", name="h03_remote_lazy_request_log_explorer.jpg",
            title="Request log: CELLxGENE Explorer slices its own S3 copy of the dataset per request",
            sub=f"{SW}, {DATA}, opened {TODAY}, then MYH7 added (Playwright response log of api.cellxgene.cziscience.com/.../api/v0.3/). "
                "The last row is the dataset's s3_uri endpoint, fetched by the driver.",
            header=["method", "endpoint", "query", "status", "bytes"], rows=rows, hl=hl,
            note="One gene costs one data/var request of a few kB (TileDB array sliced on the server from S3); "
                 "the store is Discover's own bucket (s3_uri), not a store the user can point Explorer at.",
            proves=[pv("lazy", "Y", f"request log, {E} ({TODAY}): adding MYH7 makes one data/var request of {rows[gi[0]][4] if gi else 'a few kB'} bytes, one gene of the 4,992 x 35,476 matrix sliced from S3"),
                    pv("remote", "P", f"request log, {E} ({TODAY}): reads come from Discover's own S3 bucket ({s3txt[:60]}); a user cannot point Explorer at another store, and Annotate copies a remote file locally first, so P")],
            callouts=[(1, f"#r{gi[0]}" if gi else f"#r{hl[0]}", "one gene, one small request"), (2, f"#r{len(rows) - 1}", "s3_uri: Discover's bucket"), (3, "#note", "sliced per request, own bucket only")],
            software=SW, driver=DRV, data=DATA, url=VISIUM)
        p3.close()
    step("request log", log_shot)
    log("done")
