"""Loupe Browser gap shots (evidence-curator, 2026-10-04): 10x documentation pages, not the app (no 10x account
may be created, so the app was never installed). Run under notes/comparison/demos/scale_probe/gap_run.sh with
benchmark/scale/ceiling/.venv/bin/python <this file>

focus N:  interface page: clicking a gene name colours the projection (feature colouring, no pairwise row).
slots N:  LoupeR page: what the converter carries into a .cloupe (counts, clusters, projections).
subset Y: Reanalyze page: re-clustering on a chosen barcode subset (hard cap 100,000 cells).
cells N, genes N: the docs say nothing (na: visual in loupe.yaml).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaplib import TODAY, docs_shot, log  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRIVER = "evidence/screens/gaps/capture_loupe.py"
TOOL = "loupe"
LB = "https://www.10xgenomics.com/support/software/loupe-browser/latest/"
SW = f"Loupe Browser 9.1.0 DOCS PAGE (10x website, read {TODAY}), not the app"
KIND = "docs, not the app"
JOBS = [
    ("g01_focus_DOCS_gene_click_colours_projection.jpg", LB + "tutorials/introduction/lb-sc-interface-and-navigation",
     ["Click on a different feature in your imported list to view the distribution of that feature", "Clicking on the gene name"], "focus", "N",
     "Loupe Browser 9.1.0 docs: clicking a feature shows that feature's distribution on the projection (feature colouring, which does not count); nothing describes a stored pairwise row re-driving linked panels"),
    ("g02_slots_DOCS_louper_converts_counts_clusters_projections.jpg", LB + "tutorials/introduction/lb-louper",
     ["count matrix", "counts matrix", "projections", "clusters", "Seurat object"], "slots", "N",
     "Loupe Browser 9.1.0 docs (LoupeR): a .cloupe carries counts, cluster factors and 2-D projections only; no AnnData slots (layers, obsp, varp, varm)"),
    ("g03_subset_DOCS_reanalyze_barcode_subset.jpg", LB + "tutorials/assay-analysis/lb-sc-recluster",
     ["hard cap at 100,000 cells", "100,000 cells", "Reanalyze"], "subset", "Y",
     "Loupe Browser 9.1.0 docs: Reanalyze re-runs PCA, clustering and t-SNE/UMAP on a user-chosen subset of barcodes (up to 100,000 cells)"),
]

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    p = b.new_page(viewport={"width": 1400, "height": 900})
    for name, url, phrases, col, mark, cap in JOBS:
        try:
            ph = docs_shot(p, tool=TOOL, name=name, url=url, phrases=phrases, column=col, mark=mark, software=SW, driver=DRIVER,
                           kind=KIND, caption=f"{cap} (read {TODAY})", wait=6,
                           banner_text=f"10x DOCS PAGE, not the app (Loupe Browser was not run): {url}")
            log(name, "phrase:", ph)
        except Exception as e:
            log("FAIL", name, str(e)[:200])
    b.close()
log("done")
