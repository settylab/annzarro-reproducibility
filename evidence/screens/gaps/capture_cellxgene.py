"""CELLxGENE static N (evidence-curator, 2026-10-04). Run under notes/comparison/demos/scale_probe/gap_run.sh with
benchmark/scale/ceiling/.venv/bin/python <this file>

Starts the local CELLxGENE Annotate 1.3.0 demo ($DEMO_ROOT/cellxgene/start.sh, bm_demo.h5ad,
127.0.0.1:8903), opens it, adds the gene Mpo, logs every request and stops the server. The page shell is
static, but schema, layouts, annotations and expression all come from the Python server's /api.
(A first try on the hosted Explorer, 2026-10-04 07:07, logged no data requests within 25 s headless.)
"""
import subprocess
import urllib.request
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaplib import TODAY, log, pv, table_shot  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRIVER = "evidence/screens/gaps/capture_cellxgene.py"
TOOL = "cellxgene"
SW = "CELLxGENE Annotate 1.3.0 (local)"
URL = "http://127.0.0.1:8903/"
srv = subprocess.Popen(["$DEMO_ROOT/cellxgene/start.sh"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(90):
    try:
        urllib.request.urlopen(URL + "api/v0.2/schema", timeout=2)
        break
    except Exception:
        time.sleep(1)

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    p = b.new_page(viewport={"width": 1400, "height": 900})
    reqs = []

    def onfin(r):
        try:
            sz = r.sizes()["responseBodySize"]
        except Exception:
            sz = -1
        reqs.append((r.resource_type, r.method, r.url, sz))
    p.on("requestfinished", onfin)
    p.goto(URL, timeout=90000)
    time.sleep(15)
    gene_ok = False
    try:
        g = p.locator("input[placeholder*='gene' i]").first
        g.click(force=True, timeout=8000)
        g.fill("Mpo")
        time.sleep(2)
        p.keyboard.press("Enter")
        time.sleep(6)
        gene_ok = any("/data/var" in r[2] for r in reqs)
    except Exception as e:
        log("gene", str(e)[:150])
    for r in reqs:
        log("REQ", r[0], r[2][:160], r[3])
    api = [r for r in reqs if "/api/" in r[2]]
    log("total requests", len(reqs), "api/fetch", len(api))
    rows, hl = [], []
    for t, m, u, sz in api[:32]:
        pu = urllib.parse.urlparse(u)
        path = pu.path
        if any(k in path for k in ("/schema", "/config", "/layout", "/annotations", "/data/", "/colors", "s3_uri", "dataset-metadata")):
            hl.append(len(rows))
        rows.append([t, m, pu.netloc, (path[-110:] + ("?" + pu.query[:40] if pu.query else "")), f"{sz:,} B" if sz >= 0 else "?"])
    if not api:
        log("no /api requests seen: no shot")
        b.close()
        subprocess.run(["$DEMO_ROOT/cellxgene/stop.sh"])
        srv.terminate()
        sys.exit(1)
    static_n = sum(1 for r in reqs if r[0] in ("script", "stylesheet", "image", "font", "document"))
    table_shot(p, tool=TOOL, name="g01_static_request_log_api_calls.jpg",
               title="Request log: CELLxGENE Annotate reads every dataset value from its Python server",
               sub=f"{SW}, bm_demo.h5ad (8,090 cells) opened on {TODAY}{', then the gene Mpo added' if gene_ok else ''} (Playwright request log). {static_n} static files (page, scripts, styles, fonts, images) "
                   f"and {len(api)} data requests to the Python server's /api; highlighted: schema, config, layouts, annotations{' and expression' if gene_ok else ''}.",
               header=["type", "method", "host", "path", "response"], rows=rows, hl=hl,
               note="Every data access is a call to the Python server behind /api; with static files alone the app shows no data.",
               proves=[pv("static", "N", f"request log, CELLxGENE Annotate 1.3.0 ({TODAY}): schema, layouts, annotations{' and expression' if gene_ok else ''} all come from the Python server's /api; it cannot run as static files")],
               callouts=[(1, f"#r{hl[0]}" if hl else "#r0", "data request to the API server"), (2, "#note", "no static mode")],
               software=SW, driver=DRIVER, data="bm_demo.h5ad (8,090 cells)", url=URL)
    b.close()
subprocess.run(["$DEMO_ROOT/cellxgene/stop.sh"])
srv.terminate()
log("done")
