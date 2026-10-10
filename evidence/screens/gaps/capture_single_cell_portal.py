"""Single Cell Portal gap shots (evidence-curator, 2026-10-04). Run under notes/comparison/demos/scale_probe/gap_run.sh with
benchmark/scale/ceiling/.venv/bin/python <this file>

Public study SCP383 (1,306,127 cells), not signed in.
genes N:   two genes searched -> the plot tabs (Correlation = two genes' expression, no stored gene x gene matrix).
hosted Y:  the same page served to an anonymous visitor ("Sign in" in the header).
static N + lazy Y: request log of the Explore load: views filled from the Rails JSON API; one gene fetched on demand.
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaplib import TODAY, log, pv, snap, table_shot  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRIVER = "evidence/screens/gaps/capture_single_cell_portal.py"
TOOL = "single-cell-portal"
SW = "Single Cell Portal 1.20.0 (singlecell.broadinstitute.org)"
S = "https://singlecell.broadinstitute.org/single_cell/study/"
DATA = "SCP383, 10X 1.3M brain cells E18 (1,306,127 cells)"

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    p = b.new_page(viewport={"width": 1400, "height": 1000})
    reqs = []

    def onfin(r):
        if "/api/v1" in r.url:
            try:
                sz = r.sizes()["responseBodySize"]
            except Exception:
                sz = -1
            reqs.append((time.time(), r.method, r.url.split("/single_cell")[-1], sz))
    p.on("requestfinished", onfin)
    try:
        p.goto(S + "SCP383#study-visualize", timeout=90000)
        time.sleep(22)
        n_load = len(reqs)
        if sys.argv[1:] == ["hosted"]:
            p.evaluate("window.scrollTo(0,0)")
            time.sleep(1)
            log("header links:", [t.strip() for t in p.locator("header a, nav a").all_inner_texts() if t.strip()][:20])
        # hosted: page top, with the header and its sign-in link
        p.evaluate("window.scrollTo(0,0)")
        time.sleep(1)
        snap(p, TOOL, "g01_hosted_anonymous_explore.jpg",
             [pv("hosted", "Y", f"Single Cell Portal 1.20.0 ({TODAY}): one deployment serves this public study's Explore view to an anonymous visitor; 'Sign in' is optional")],
             [(1, "a:has-text('Sign in') >> nth=0", "not signed in: 'Sign in'"), (2, ".js-plotly-plot >> nth=0", "Explore view served to an anonymous visitor"),
              (3, "text=/total cells/ >> nth=0", "public study, 1,306,127 cells")],
             software=SW, driver=DRIVER, data=DATA)
        if sys.argv[1:] == ["hosted"]:
            raise SystemExit
        # lazy: search one gene, log its request
        t_gene = time.time()
        p.goto(S + "SCP383?genes=Sox2#study-visualize", timeout=90000)
        time.sleep(20)
        gene_reqs = [r for r in reqs if r[0] >= t_gene]
        # genes: two genes -> plot tabs
        p.goto(S + "SCP383?genes=Sox2%2CPax6#study-visualize", timeout=90000)
        time.sleep(22)
        tabs = [t.strip() for t in p.locator("[role=tab], .nav-tabs a, .study-plot-tabs a").all_inner_texts() if t.strip()]
        log("tabs with two genes:", tabs)
        try:
            p.get_by_text("Correlation", exact=True).first.click(timeout=4000)
            time.sleep(12)
        except Exception as e:
            log("correlation tab", str(e)[:120])
        snap(p, TOOL, "g02_genes_two_gene_tabs_no_gene_matrix.jpg",
             [pv("genes", "N", f"Single Cell Portal 1.20.0 ({TODAY}): with two genes searched the tabs offer plots of their expression (Correlation = gene A vs gene B per cell); no stored gene x gene matrix can be shown")],
             [(1, "text=Correlation >> nth=0 >> xpath=../..", "plot tabs for a multi-gene search: " + ", ".join(tabs[:8])),
              (2, ".js-plotly-plot >> nth=0", "Correlation: two genes' expression, computed per cell")],
             software=SW, driver=DRIVER, data=DATA + "; genes Sox2, Pax6")
    except SystemExit:
        b.close()
        log("done (hosted only)")
        sys.exit(0)
    except Exception as e:
        log("FAIL app", type(e).__name__, str(e)[:250])
    rows, hl = [], []
    for i, (t, m, u, sz) in enumerate(reqs[:60]):
        path = u.split("?")[0]
        if "/clusters/" in path or "/explore" in path or "Sox2" in u:
            hl.append(len(rows))
        rows.append([m, (u[:150] + "...") if len(u) > 150 else u, f"{sz:,} B" if sz >= 0 else "?"])
    gtxt = "; ".join(f"{u.split('?')[0][-60:]} {sz:,} B" for _, _, u, sz in reqs if "Sox2" in u)[:200]
    log("api requests", len(reqs), "gene:", gtxt)
    if rows:
        p.set_viewport_size({"width": 1400, "height": 900})
        table_shot(p, tool=TOOL, name="g03_static_lazy_request_log_api.jpg",
                   title="Request log: Single Cell Portal fills every view from its server API",
                   sub=f"{SW}, {DATA}, recorded {TODAY} (Playwright log of /single_cell/api/v1 requests): first the default Explore view, "
                       "then the gene Sox2, then Sox2 + Pax6. Highlighted: per-view and per-gene requests.",
                   header=["method", "API request", "response body"], rows=rows[:34], hl=[h for h in hl if h < 34],
                   note=("Each view is computed by the Rails server per request (static N). A gene is fetched on its own when asked for "
                         f"(lazy Y): {gtxt or 'see highlighted rows'}."),
                   proves=[pv("static", "N", f"request log, Single Cell Portal 1.20.0 ({TODAY}): every view is filled from the Rails JSON API, so it cannot run as static files"),
                           pv("lazy", "Y", f"request log, Single Cell Portal 1.20.0 ({TODAY}): the server returns one gene on demand ({gtxt[:90] or 'gene request highlighted'})")],
                   callouts=[(1, f"#r{hl[0]}" if hl else "#r0", "Explore / cluster data from the API"),
                             (2, f"#r{[i for i, r in enumerate(rows) if 'Sox2' in r[1]][0]}" if any('Sox2' in r[1] for r in rows[:34]) else "#note", "one gene on demand"),
                             (3, "#note", "server-computed views")],
                   software=SW, driver=DRIVER, data=DATA, url=S + "SCP383")
    b.close()
log("done")
