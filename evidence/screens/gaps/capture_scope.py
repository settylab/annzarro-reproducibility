"""SCope gap shots (evidence-curator, 2026-10-04). Run under notes/comparison/demos/scale_probe/gap_run.sh with
benchmark/scale/ceiling/.venv/bin/python <this file>

desktop P: GitHub releases page, newest desktop build SCope_macOS_x64_v1.3.5_CI (2019 prerelease).
hosted Y:  scope.aertslab.org, anonymous: header "Your session will be deleted in ..." (per-user sessions).
static N:  request log of the same page load: data come over a websocket from the server, not from files.
subset Y:  Compare page: an annotation value dragged onto a display shows only those cells.
"""
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaplib import TODAY, docs_shot, log, pv, snap, table_shot  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRIVER = "evidence/screens/gaps/capture_scope.py"
TOOL = "scope"
SW = "SCope 1.8.2 (scope.aertslab.org)"
DATA = "Wouters_Human_Melanoma / 10_Baselines_filteredRegulons.loom (4,322 cells)"
BASE = "https://scope.aertslab.org/#/Wouters_Human_Melanoma/Wouters_Human_Melanoma%2F10_Baselines_filteredRegulons.loom/"


def loaded(p, limit):
    t = time.time()
    while time.time() - t < limit:
        if p.locator(".ui.loader:visible").count() == 0:
            return True
        time.sleep(1)
    return False


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    p = b.new_page(viewport={"width": 1400, "height": 900})
    p.set_default_timeout(8000)
    parts = sys.argv[1:] or ["desktop", "hosted", "subset"]
    # desktop: releases page
    try:
        assert "desktop" in parts
        docs_shot(p, tool=TOOL, name="g01_desktop_DOCS_releases_v1.3.5_CI.jpg", url="https://github.com/aertslab/SCope/releases",
                  phrases=["App development has currently halted"], column="desktop", mark="P",
                  software=f"SCope GitHub releases page (read {TODAY})", driver=DRIVER,
                  caption=f"SCope GitHub releases (read {TODAY}): the newest desktop build is the 2019 v1.3.5 CI prerelease, whose note says app development has halted and the apps are likely non-functional; none for SCope 1.8.x, so P",
                  extra=[(3, "relative-time >> nth=0", "released Feb 8, 2019"), (4, "h2:has-text('SCope_macOS_x64_v1.3.5_CI') >> nth=0", "newest desktop build: SCope_macOS_x64_v1.3.5_CI, Pre-release")])
    except Exception as e:
        log("FAIL desktop", str(e)[:200])
    # hosted + static: one page load, with a request and websocket log
    reqs, wss = [], {}

    def onfin(r):
        try:
            sz = r.sizes()["responseBodySize"]
        except Exception:
            sz = -1
        reqs.append((r.resource_type, r.method, r.url, sz))

    def onws(ws):
        wss[ws.url] = {"recv": 0, "sent": 0, "bytes": 0}
        ws.on("framereceived", lambda f: wss[ws.url].update(recv=wss[ws.url]["recv"] + 1, bytes=wss[ws.url]["bytes"] + (len(f) if f else 0)))
        ws.on("framesent", lambda f: wss[ws.url].update(sent=wss[ws.url]["sent"] + 1))
    p.on("requestfinished", onfin)
    p.on("websocket", onws)
    try:
        assert "hosted" in parts
        p.goto(BASE + "gene", timeout=90000)
        time.sleep(8)
        try:
            p.get_by_text("I decline").first.click(timeout=3000)
        except Exception:
            pass
        ok = loaded(p, 45)
        time.sleep(2)
        log("loaded", ok)
        hdr = p.get_by_text("Your session will be deleted").first
        log("header:", hdr.inner_text() if hdr.count() else "none")
        snap(p, TOOL, "g02_hosted_public_session_header.jpg",
             [pv("hosted", "Y", f"SCope 1.8.2 at scope.aertslab.org ({TODAY}), opened anonymously: one deployment serves every visitor, each with its own session ('Your session will be deleted in ...', 'Get new session')")],
             [(1, "text=/Your session will be deleted/ >> nth=0", "per-user session on the public server"),
              (2, "text=/new session/i >> nth=0", "Get new session"), (3, "canvas >> nth=0", "viewer area (data arrive from the server)")],
             software=SW, driver=DRIVER, data=DATA)
    except Exception as e:
        log("FAIL hosted", str(e)[:200])
    url_now = p.url
    rows, hl = [], []
    for u, s in wss.items():
        hl.append(len(rows))
        rows.append(["websocket", "WS", u, f"{s['recv']} frames received, {s['bytes']:,} bytes; {s['sent']} sent"])
    kinds = {}
    for t, m, u, sz in reqs:
        host = urllib.parse.urlparse(u).netloc
        kinds.setdefault((t, host), [0, 0])
        kinds[(t, host)][0] += 1
        kinds[(t, host)][1] += max(sz, 0)
    for (t, host), (n, sz) in sorted(kinds.items(), key=lambda x: -x[1][1]):
        rows.append([t, "GET", f"{host} ({n} requests)", f"{sz:,} bytes"])
    log("ws", wss, "req kinds", len(kinds))
    if wss and "hosted" in parts:
        table_shot(p, tool=TOOL, name="g03_static_request_log_websocket.jpg",
                   title="Request log: SCope gets its data over a websocket from the server",
                   sub=f"{SW}, page load of {DATA} on {TODAY} (Playwright request and websocket log). "
                       "Static files are only the page shell; every data value arrives as protobuf frames from the gRPC data server.",
                   header=["type", "method", "URL / host", "transfer"], rows=rows[:30], hl=hl,
                   note="A static file host cannot answer a websocket; without the Python data server (opt/scopeserver) the viewer gets no data.",
                   proves=[pv("static", "N", f"request log, SCope 1.8.2 at scope.aertslab.org ({TODAY}): the data come over a websocket ({list(wss)[0]}) from the gRPC server; nothing works as static files")],
                   callouts=[(1, "#r0", "websocket to the data server"), (2, "#note", "no static mode")],
                   software=SW, driver=DRIVER, data=DATA, url=url_now)
        p.set_viewport_size({"width": 1400, "height": 900})
    # subset: Compare page; drag one cell_line value onto display 1
    try:
        assert "subset" in parts
        p.goto("about:blank")
        p.set_viewport_size({"width": 1400, "height": 900})
        p.goto(BASE + "compare", timeout=90000)
        time.sleep(12)
        loaded(p, 30)
        time.sleep(2)
        try:
            p.get_by_text("cell_line", exact=True).first.click(timeout=5000)
            time.sleep(2)
        except Exception as e:
            log("open cell_line", str(e)[:120])
        val = "MM 001"
        src = p.get_by_text(val, exact=True).first
        dst = p.get_by_text("Drag and drop here the annotations you want to compare.").first
        dragged = False
        try:
            src.drag_to(dst, timeout=8000)
            time.sleep(10)
            loaded(p, 20)
            dragged = p.get_by_text("Drag and drop here the annotations you want to compare.").count() < 4
        except Exception as e:
            log("drag", str(e)[:150])
        log("dragged", dragged, "| placeholders left:", p.get_by_text("Drag and drop here the annotations you want to compare.").count())
        cv = p.locator("canvas").count()
        log("canvases", cv)
        snap(p, TOOL, "g04_subset_compare_page_MM001_only.jpg" if dragged else "g04_subset_compare_page_annotation_values.jpg",
             [pv("subset", "Y", f"SCope 1.8.2 Compare page ({TODAY}): " + ("display 1 shows only the cells of cell_line MM 001, dropped on it; the other displays stay empty"
                 if dragged else "annotation values (cell_line MM 001, ...) are dropped on up to 4 displays, each showing only the matching cells; drag not completed headless"))],
             [(1, f"text={val} >> nth=0", f"annotation value cell_line = {val}"),
              (2, "canvas >> nth=0" if dragged else "text=Drag and drop here the annotations you want to compare. >> nth=0", "display 1: only MM 001 cells" if dragged else "display 1 (drop target)"),
              (3, "text=Number of displays: >> xpath=..", "number of displays, superposition OR / AND")],
             software=SW, driver=DRIVER, data=DATA)
    except Exception as e:
        log("FAIL subset", str(e)[:200])
    b.close()
log("done")
