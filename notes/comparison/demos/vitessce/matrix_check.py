"""Matrix-mark screenshots for Vitessce (hosted app at vitessce.io).
A: local bone marrow store via ?url=http://127.0.0.1:8904/config.json (served by $DEMO_ROOT/vitessce/start.sh)
B: same store, config_matrix.json (adds the Vega statistical views: obsSetSizes, featureValueHistogram, violin)
C: public demo human-lymph-node-10x-visium (spatial, H&E image, remote GCS/HTTP zarr)
config_matrix.json and config_lazy.json are config.json with coordinationSpace {"embeddingType": {"A": "UMAP"}} and
layout replaced by (x, y, w, h on the 12-column grid):
  config_matrix: scatterplot(A) 0,0,6,6; obsSets 6,0,3,6; featureList 9,0,3,6; obsSetSizes 0,6,4,4;
                 featureValueHistogram 4,6,4,4; obsSetFeatureValueDistribution 8,6,4,4
  config_lazy:   scatterplot(A) 0,0,6,6; featureList 6,0,6,6
Run (starts and stops the local data server):
  notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
      demos/_focus_run.py vitessce 8904 demos/vitessce/matrix_check.py
"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import os, re, urllib.parse
D = f"{_REPO}/notes/comparison/screens/vitessce/"
APP = "https://vitessce.io/#?url=http://127.0.0.1:8904/"
LYMPH = "https://vitessce.io/#?dataset=human-lymph-node-10x-visium"
def shot(page, n): page.screenshot(path=D + n + ".jpg", type="jpeg", quality=70); print("shot", n)
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:250])
def gene(page, g):
    s = page.locator("input[placeholder*='Search']").first; s.click(); s.fill(g); page.wait_for_timeout(2500)
    page.locator(f"text=/^{g}$/").first.click(); page.wait_for_timeout(5000)

def local(page, reqs):
    page.goto(APP + "config.json", timeout=90000); page.wait_for_timeout(15000)
    shot(page, "m00_plots_render")
    def g():
        n0 = len(reqs); gene(page, "Mpo")
        x = [(u, r) for u, r in reqs[n0:] if "/X/" in u]
        print("requests after clicking Mpo:", len(reqs) - n0, "X chunk requests:", x[:6])
    step("gene", g)
    def ann():
        page.locator("[title='Select lasso']").first.click(); page.wait_for_timeout(500)
        cv = [b for b in (page.locator("canvas").nth(i).bounding_box() for i in range(page.locator("canvas").count())) if b and b["width"] > 300]
        b = sorted(cv, key=lambda b: (b["y"], b["x"]))[0]
        cx, cy, w, h = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, b["width"], b["height"]
        pts = [(cx - w * .3, cy - h * .4), (cx + w * .1, cy - h * .4), (cx + w * .1, cy - h * .05), (cx - w * .3, cy - h * .05), (cx - w * .3, cy - h * .4)]
        page.mouse.move(*pts[0]); page.mouse.down()
        for p in pts[1:]: page.mouse.move(*p, steps=12)
        page.mouse.up(); page.wait_for_timeout(4000)
        shot(page, "m09_annotation_lasso_creates_set")
        print("obsSets text:", page.locator("text=My Selections").count(), page.evaluate("()=>[...document.querySelectorAll('[title]')].map(e=>e.getAttribute('title')).filter(t=>/[Ss]et|[Dd]ownload|[Ee]xport|[Ii]mport|[Rr]ename|[Uu]nion|[Ii]ntersect/.test(t)).slice(0,20)"))
    step("annotation", ann)
    def share():
        page.get_by_role("button", name="Edit", exact=True).first.click(); page.wait_for_timeout(3000)
        u = page.url; print("edit url length:", len(u), "| contains Mpo:", "Mpo" in urllib.parse.unquote(u))
        shot(page, "m12_share_edit_config_with_live_state")
        u2 = u.replace("edit=true", "edit=false")
        p2 = page.context.new_page(); p2.goto(u2, timeout=90000); p2.wait_for_timeout(15000)
        p2.screenshot(path=D + "m12_share_data_url_reopened.jpg", type="jpeg", quality=70); print("shot m12 reopened")
        p2.close()
    step("share", share)

def vega(page):
    page.goto(APP + "config_matrix.json", timeout=90000); page.wait_for_timeout(15000)
    step("gene", lambda: gene(page, "Mpo"))
    page.wait_for_timeout(4000)
    shot(page, "m13_export_vega_views")
    def menu():
        s = page.locator(".vega-embed summary, details summary")
        print("vega action buttons:", s.count())
        if s.count():
            s.first.hover(); s.first.click(); page.wait_for_timeout(1000)
            print("vega actions:", page.evaluate("()=>[...document.querySelectorAll('.vega-actions a')].map(a=>a.innerText.trim())"))
            shot(page, "m13_export_vega_actions_menu")
            with page.expect_download(timeout=30000) as d:
                page.locator(".vega-actions a:has-text('PNG')").first.click()
            dd = d.value; out = "/tmp/vitessce_vega.png"; dd.save_as(out); print("download:", dd.suggested_filename, os.path.getsize(out), "bytes")
    step("vega menu", menu)

def lymph(page):
    hosts = set()
    page.on("request", lambda r: hosts.add(re.sub(r"^(https?://[^/]+/).*", r"\1", r.url)) if ("zarr" in r.url or ".zarray" in r.url or "ome" in r.url) else None)
    page.goto(LYMPH, timeout=90000); page.wait_for_timeout(25000)
    shot(page, "m07_spatial_lymph_node_spots_on_he")
    print("data hosts:", sorted(hosts))
    step("gene", lambda: gene(page, "CR2"))
    page.wait_for_timeout(5000)
    shot(page, "m11_image_lymph_node_gene_on_he")

def steps(page, S):
    page.context.grant_permissions(["local-network-access"], origin="https://vitessce.io")
    reqs = []
    page.on("request", lambda r: reqs.append((r.url.split("8904/")[-1], r.headers.get("range"))) if "127.0.0.1:8904" in r.url else None)
    step("local", lambda: local(page, reqs))
    step("vega", lambda: vega(page))
    step("lymph", lambda: lymph(page))
