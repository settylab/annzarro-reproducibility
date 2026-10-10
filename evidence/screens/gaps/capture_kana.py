"""Kana gap shots (evidence-curator, 2026-10-04). Run under notes/comparison/demos/scale_probe/gap_run.sh with
benchmark/scale/ceiling/.venv/bin/python <this file> [docs] [app]

docs: README (static Y, hosted P) and the wiki page "How to load datasets" (subset).
app:  live build kanaverse.org/kana with $DEMO_ROOT/_data/bm_demo.h5ad (read in the browser, not uploaded):
      New Analysis -> H5AD -> ADD DATASET -> "Subsetting by annotation" (subset Y);
      Explore mode -> the marker panel and its pickers (genes N: no gene x gene option).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaplib import TODAY, docs_shot, log, pv, snap  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRIVER = "evidence/screens/gaps/capture_kana.py"
TOOL = "kana"
SW = "Kana v3.2.0 (live build, kanaverse.org)"
BM = "$DEMO_ROOT/_data/bm_demo.h5ad"
DATA = "bm_demo.h5ad (8,090 cells)"
README = "https://github.com/kanaverse/kana"
WIKI = "https://github.com/kanaverse/kana/wiki/How-to-load-datasets"
parts = sys.argv[1:] or ["docs", "app"]


def docs(p):
    sw = f"Kana README, GitHub kanaverse/kana master (read {TODAY}; app v3.2.0)"
    docs_shot(p, tool=TOOL, name="g01_static_DOCS_readme_static_files.jpg", url=README,
              phrases=["Deployment is as easy as serving the static files", "just serve it as a static website"],
              column="static", mark="Y", software=sw, driver=DRIVER,
              caption=f"Kana v3.2.0 README (read {TODAY}): deployment is serving static files (GitHub Pages); no backend server")
    docs_shot(p, tool=TOOL, name="g02_hosted_DOCS_readme_client_side.jpg", url=README, goto=False,
              phrases=["the calculations are performed client-side", "performed client-side"],
              column="hosted", mark="P", software=sw, driver=DRIVER,
              caption=f"Kana v3.2.0 README (read {TODAY}): one public deployment, but every visitor computes on their own machine with their own data (no accounts or shared datasets), so P")
    docs_shot(p, tool=TOOL, name="g03_subset_DOCS_wiki_subset_of_cells.jpg", url=WIKI,
              phrases=["use this option to perform analysis only on a subset", "Perform analysis on a subset of cells"],
              column="subset", mark="Y", software=f"Kana wiki 'How to load datasets' (read {TODAY}; app v3.2.0)", driver=DRIVER,
              caption=f"Kana wiki (read {TODAY}): 'Perform analysis on a subset of cells' keeps cells by annotation before the analysis runs")


def app(p):
    p.set_viewport_size({"width": 1800, "height": 1000})
    # subset: New Analysis -> H5AD -> ADD DATASET -> Subsetting by annotation
    p.goto("https://www.kanaverse.org/kana/", timeout=120000)
    time.sleep(4)
    p.get_by_text("I want to analyze a new dataset").first.click()
    time.sleep(3)
    p.get_by_text("H5AD", exact=True).first.click()
    time.sleep(2)
    p.locator("input[type=file]").first.set_input_files(BM)
    time.sleep(3)
    p.get_by_role("button", name="ADD DATASET").first.click()
    for _ in range(30):
        time.sleep(2)
        if p.get_by_text("Subsetting by annotation").count():
            break
    time.sleep(3)
    co = p.get_by_text("Subsetting by annotation").first.locator("xpath=ancestor::div[contains(@class,'callout')][1]")
    sel = co.locator("select").first
    opts = sel.evaluate("s=>[...s.options].map(o=>o.text)")
    log("subset columns", opts)
    sel.select_option("highres_celltype")
    time.sleep(2)
    for lab in ["HSC", "LMPP"]:
        try:
            p.locator(".subset-section label", has_text=lab).first.click()
        except Exception as e:
            log("checkbox", lab, str(e)[:120])
    time.sleep(1)
    co.evaluate("e=>e.setAttribute('data-gap','subset')")
    co.evaluate("e=>e.scrollIntoView({block:'center'})")
    time.sleep(1)
    snap(p, TOOL, "g04_subset_new_analysis_subset_by_annotation.jpg",
         [pv("subset", "Y", f"Kana v3.2.0 (live build, {TODAY}), New Analysis: 'Subsetting by annotation' keeps the ticked highres_celltype groups (HSC, LMPP) for the whole downstream analysis")],
         [(1, "[data-gap='subset']", "Subsetting by annotation (New Analysis, H5AD)"), (2, ".subset-section", "groups to keep: HSC and LMPP ticked")],
         software=SW, driver=DRIVER, data=DATA)
    # genes: Explore mode marker panel
    p.goto("https://www.kanaverse.org/kana/", timeout=120000)
    time.sleep(4)
    p.get_by_text("I want to explore existing analysis results").click()
    time.sleep(3)
    p.locator("input[type=file]").first.set_input_files(BM)
    time.sleep(10)
    p.get_by_role("button", name="Explore", exact=True).first.click()
    for _ in range(20):
        time.sleep(4)
        if p.get_by_text("X_umap", exact=True).count():
            break
    time.sleep(6)
    sels = p.locator("select")
    allopts = sels.evaluate_all("els=>els.map(s=>[...s.options].map(o=>o.text).slice(0,20))")
    log("selects", allopts)
    tabs = p.locator("[role=tab]").all_inner_texts()
    log("tabs", tabs)
    try:
        sels.nth(2).select_option("highres_celltype")
        time.sleep(6)
        sels.nth(3).select_option("HSC")
        time.sleep(8)
    except Exception as e:
        log("marker selects", str(e)[:150])
    mk = p.locator("text=rowNames >> xpath=../..").first
    mk.evaluate("e=>e.setAttribute('data-gap','markers')")
    snap(p, TOOL, "g05_genes_marker_panel_no_gene_pairs.jpg",
         [pv("genes", "N", f"Kana v3.2.0 (live build, {TODAY}): the gene side offers marker tables per cluster, gene sets and cell-type labels; no varp is read and no gene x gene matrix is offered as colour or axis")],
         [(1, "select >> nth=2", "marker panel: annotation picker"), (2, "select >> nth=3", "cluster picker"),
          (3, "[data-gap='markers']", "marker table: one gene per row, no gene-pair view")],
         software=SW, driver=DRIVER, data=DATA)


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    p = b.new_page(viewport={"width": 1400, "height": 900})
    for part in parts:
        try:
            {"docs": docs, "app": app}[part](p)
        except Exception as e:
            log("FAIL", part, type(e).__name__, str(e)[:300])
    b.close()
log("done")
