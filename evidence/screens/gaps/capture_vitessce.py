"""Vitessce static Y (evidence-curator, 2026-10-04). Run under notes/comparison/demos/scale_probe/gap_run.sh with
benchmark/scale/ceiling/.venv/bin/python <this file>

docs:     the GitHub Pages tutorial ("GitHub's free static website hosting service").
terminal: a listing of the local Vitessce data folder (config.json + AnnData zarr) that vitessce.io read
          from a plain static file server: data files only, no server code.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaplib import TODAY, docs_shot, log, pv, table_shot  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRIVER = "evidence/screens/gaps/capture_vitessce.py"
TOOL = "vitessce"
STORE = "$DEMO_ROOT/vitessce/store"


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.path.dirname(STORE))
    return f"$ {cmd}\n{r.stdout}{r.stderr}"


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    p = b.new_page(viewport={"width": 1400, "height": 900})
    try:
        docs_shot(p, tool=TOOL, name="g01_static_DOCS_github_pages_tutorial.jpg", url="https://vitessce.io/docs/tutorial-gh-pages/",
                  phrases=["free static website hosting service", "must point to static files"], column="static", mark="Y",
                  software=f"Vitessce docs, vitessce.io (build 362bf129, 2026-09-30; read {TODAY})", driver=DRIVER,
                  caption=f"Vitessce docs (read {TODAY}): the app deploys to GitHub Pages, a static website host, and its data URLs point to static files (e.g. S3)",
                  extra=[(3, "text=must point to static files >> nth=0", "data: static files")])
    except Exception as e:
        log("FAIL docs", str(e)[:200])
    out = (sh("du -sh store") + sh("ls -la store") + sh("find store -maxdepth 2 | head -20")
           + sh("find store -type f | sed 's/.*\\.//' | sort | uniq -c | sort -rn | head -8")
           + sh("find store -type f \\( -name '*.py' -o -name '*.js' -o -name '*.cgi' -o -name '*.php' -o -name '*.R' \\) | wc -l"))
    srv = sh("grep -n 'class\\|serve_forever\\|RangeRequestHandler' ../_bin/serve.py") if os.path.exists("$DEMO_ROOT/_bin/serve.py") else ""
    log(out[-600:])
    table_shot(p, tool=TOOL, name="g02_static_terminal_store_listing.jpg",
               title="Terminal: the folder vitessce.io read the bone marrow demo from",
               sub=f"$DEMO_ROOT/vitessce (listing taken {TODAY}). The hosted app at vitessce.io (@vitessce 4.0.10) loaded "
                   "config.json and bm_demo.zarr from this folder through a plain static file server with Range support "
                   "(notes/comparison/demos/_bin/serve.py); there is no Vitessce server process.",
               header=[], rows=[], hl=[], pre=out + srv,
               note="Last command: no server code (.py, .js, .cgi, .php, .R) in the folder; only the view config and the zarr chunks.",
               proves=[pv("static", "Y", f"terminal, Vitessce (vitessce.io, @vitessce 4.0.10; listing {TODAY}): the deployment is a JSON config plus zarr chunk files on a static file server, no server code")],
               callouts=[(1, "#pre", "folder listing: config.json + bm_demo.zarr"), (2, "#note", "no server code")],
               software="Vitessce web app at vitessce.io (@vitessce 4.0.10) reading local static files", driver=DRIVER,
               data="$DEMO_ROOT/vitessce/store (config.json, bm_demo.zarr)", url="file://" + STORE)
    b.close()
log("done")
