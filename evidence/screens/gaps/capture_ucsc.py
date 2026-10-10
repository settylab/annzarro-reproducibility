"""UCSC Cell Browser static Y (evidence-curator, 2026-10-04). Run under notes/comparison/demos/scale_probe/gap_run.sh with
benchmark/scale/ceiling/.venv/bin/python <this file>

docs:     cellbrowser docs "Basic usage": "there is no backend server needed for a cell browser".
terminal: listing of the local cbBuild output ($DEMO_ROOT/ucsc-cell-browser/html): no server code.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaplib import TODAY, docs_shot, log, pv, table_shot  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRIVER = "evidence/screens/gaps/capture_ucsc.py"
TOOL = "ucsc-cell-browser"
ROOT = "$DEMO_ROOT/ucsc-cell-browser"


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=ROOT)
    return f"$ {cmd}\n{r.stdout}{r.stderr}"


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    p = b.new_page(viewport={"width": 1400, "height": 900})
    try:
        docs_shot(p, tool=TOOL, name="g01_static_DOCS_no_backend_server.jpg", url="https://cellbrowser.readthedocs.io/en/master/basic_usage.html",
                  phrases=["no backend", "static web server"], column="static", mark="Y",
                  software=f"UCSC Cell Browser docs, cellbrowser.readthedocs.io/en/master (read {TODAY}; cellbrowser 1.2.20)", driver=DRIVER,
                  caption=f"UCSC Cell Browser docs (read {TODAY}): no backend server is needed; the cbBuild output goes on any static web server")
    except Exception as e:
        log("FAIL docs", str(e)[:200])
    out = (sh("du -sh html") + sh("ls html") + sh("ls html/bm_demo | head -25")
           + sh("find html -type f | sed 's/.*\\.//' | sort | uniq -c | sort -rn")
           + sh("find html -type f \\( -name '*.py' -o -name '*.cgi' -o -name '*.php' -o -name '*.pl' -o -name '*.rb' -o -name '*.R' \\) | wc -l"))
    log(out[-500:])
    table_shot(p, tool=TOOL, name="g02_static_terminal_cbbuild_listing.jpg",
               title="Terminal: the cbBuild output folder of the bone marrow demo",
               sub=f"$DEMO_ROOT/ucsc-cell-browser (cellbrowser 1.2.20, cbBuild -o ../html; listing taken {TODAY}). "
                   "The local demo served this folder with a plain static file server with Range support (notes/comparison/demos/_bin/serve.py).",
               header=[], rows=[], hl=[], pre=out,
               note="Last command: no server code (.py, .cgi, .php, .pl, .rb, .R) anywhere in the build; the .js files are the browser client.",
               proves=[pv("static", "Y", f"terminal, UCSC Cell Browser cellbrowser 1.2.20 (listing {TODAY}): the cbBuild output is HTML, JS, JSON and binary matrix files with no server code")],
               callouts=[(1, "#pre", "cbBuild output: html, js, json, bin, gz"), (2, "#note", "no server code")],
               software="UCSC Cell Browser, cellbrowser 1.2.20 static build (local)", driver=DRIVER,
               data="bm_demo cbBuild output ($DEMO_ROOT/ucsc-cell-browser/html)", url="file://" + ROOT + "/html")
    b.close()
log("done")
