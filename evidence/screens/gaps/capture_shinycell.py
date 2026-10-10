"""ShinyCell gap shots (evidence-curator, 2026-10-04). Run under notes/comparison/demos/scale_probe/gap_run.sh with
benchmark/scale/ceiling/.venv/bin/python <this file>

Starts the local app ($DEMO_ROOT/shinycell/start.sh: ShinyCell 2.1.0 on bm_demo, 127.0.0.1:8907), stops it at the end.
share N:      page.url before and after changing the plot (cell info, gene, tab), drawn as a labelled overlay
              in the page (Playwright cannot see the browser's URL bar).
every_cell Y: the CellInfo plot plus the app's own cell-number table ("Toggle to show cell numbers / statistics");
              the overlay states the table's nCells total, read from the table in the page.
"""
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaplib import SCRATCH, TODAY, log, pv, snap  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRIVER = "evidence/screens/gaps/capture_shinycell.py"
TOOL = "shinycell"
SW = "ShinyCell 2.1.0 (local app)"
DATA = "bm_demo_sce.rds (8,090 cells)"
URL = "http://127.0.0.1:8907"


def sel(p, id_, v):
    p.evaluate("([i,v])=>{const s=$('#'+i)[0].selectize; if(!s.options[v]) s.addOption({value:v,label:v}); s.setValue(v);}", [id_, v])
    p.wait_for_timeout(300)


def overlay(p, html, top=True):
    p.evaluate("""([h,top])=>{let d=document.getElementById('gapurl'); if(!d){d=document.createElement('div');d.id='gapurl';document.body.appendChild(d);}
      d.style.cssText='position:fixed;'+(top?'top:0;':'bottom:0;')+'left:0;right:0;z-index:2147483647;background:#1d2733;color:#fff;font:14px/1.45 Menlo,monospace;padding:8px 12px;border-bottom:3px solid #d62728';
      d.innerHTML=h;}""", [html, top])


os.makedirs(SCRATCH + "shinycell", exist_ok=True)
srv = subprocess.Popen(["$DEMO_ROOT/shinycell/start.sh"], stdout=open(SCRATCH + "shinycell/srv.log", "w"), stderr=subprocess.STDOUT)
try:
    for _ in range(90):
        try:
            urllib.request.urlopen(URL, timeout=2)
            break
        except Exception:
            time.sleep(1)
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, channel="chromium")
        p = b.new_page(viewport={"width": 1400, "height": 1000})
        p.goto(URL, timeout=60000)
        p.wait_for_timeout(9000)
        # share N
        try:
            url0 = p.url
            sel(p, "sc1a1inp1", "Age")
            sel(p, "sc1a1inp2", "Mpo")
            p.wait_for_timeout(7000)
            url1 = p.url
            p.click("a:has-text('GeneExpr vs GeneExpr')")
            p.wait_for_timeout(2500)
            url2 = p.url
            p.click("a:has-text('CellInfo vs GeneExpr')")
            p.wait_for_timeout(3000)
            url3 = p.url
            nshare = p.locator("text=/bookmark|share|copy link|permalink/i").count()
            log("urls:", url0, url1, url2, url3, "share controls:", nshare)
            overlay(p, f"<b>page.url, recorded by the Playwright driver (the URL bar is not in headless screenshots)</b><br>"
                       f"<span id='u0'>before any change ............................ {url0}</span><br>"
                       f"<span id='u1'>after Cell information = Age, Gene = Mpo ..... {url1}</span><br>"
                       f"<span id='u2'>after switching to tab 'GeneExpr vs GeneExpr' {url2}</span><br>"
                       f"<span id='u3'>after switching back ......................... {url3}</span><br>"
                       f"elements matching bookmark / share / copy link / permalink on the page: {nshare}")
            p.wait_for_timeout(500)
            same = len({url0, url1, url2, url3}) == 1
            snap(p, TOOL, "g01_share_url_unchanged_overlay.jpg",
                 [pv("share", "N", f"{SW} ({TODAY}): the URL is {url0} before and after changing cell information, gene and tab ({'identical' if same else 'CHANGED'}); no bookmark, share or copy-link control")],
                 [(1, "#u0", "URL before"), (2, "#u1", "URL after changing the plot"), (3, "#sc1a1inp1 + .selectize-control", "plot changed: Cell information = Age"),
                  (4, "#sc1a1inp2 + .selectize-control", "Gene = Mpo")],
                 software=SW, driver=DRIVER, data=DATA, url=url3)
            p.evaluate("document.getElementById('gapurl').remove()")
        except Exception as e:
            log("FAIL share", str(e)[:200])
        # every_cell Y
        try:
            p.set_viewport_size({"width": 1400, "height": 1700})
            sel(p, "sc1a1inp1", "highres_celltype")
            p.wait_for_timeout(6000)
            p.click("#sc1a1tog9")
            p.wait_for_timeout(5000)
            # show every row of the DataTable, then sum nCells from the page
            try:
                p.evaluate("()=>{const t=$('#sc1a1\\\\.dt table').DataTable(); t.page.len(-1).draw();}")
                p.wait_for_timeout(1500)
            except Exception as e:
                log("page len", str(e)[:100])
            hdr = p.eval_on_selector_all("#sc1a1\\.dt thead th", "els=>els.map(e=>e.innerText.trim())")
            rows = p.eval_on_selector_all("#sc1a1\\.dt tbody tr", "els=>els.map(r=>[...r.cells].map(c=>c.innerText.trim()))")
            log("dt header", hdr, "rows", len(rows), rows[:3])
            ci = next((i for i, h in enumerate(hdr) if h.lower().startswith("ncells")), None)
            total = sum(int(float(r[ci].replace(",", ""))) for r in rows if ci is not None and len(r) > ci and r[ci]) if ci is not None else None
            log("nCells total", total)
            p.locator("#sc1a1oup1").first.scroll_into_view_if_needed()
            overlay(p, f"<span id='tot'>Sum of the app's nCells column over its {len(rows)} highres_celltype rows "
                       f"(read from the table on this page): <b>{total:,}</b> cells; bm_demo has 8,090.</span>" if total is not None
                       else "nCells column not found in the app's table", top=False)
            p.locator("#sc1a1oup1").first.evaluate("e=>e.scrollIntoView({block:'start'})")
            p.wait_for_timeout(800)
            snap(p, TOOL, "g02_every_cell_plot_and_cell_numbers.jpg",
                 [pv("every_cell", "Y", f"{SW} ({TODAY}): the CellInfo plot draws every cell; the app's own cell-number table sums to {total:,} of 8,090 cells" if total is not None
                     else f"{SW} ({TODAY}): the CellInfo plot with the app's cell-number table")],
                 [(1, "#sc1a1oup1", "UMAP, coloured by highres_celltype"), (2, "#sc1a1\\.dt", "app's cell numbers per group"), (3, "#tot", "total nCells")],
                 software=SW, driver=DRIVER, data=DATA, url=URL)
        except Exception as e:
            log("FAIL every_cell", str(e)[:200])
        b.close()
finally:
    subprocess.run(["$DEMO_ROOT/shinycell/stop.sh"])
    srv.terminate()
    log("ShinyCell stopped")
log("done")
