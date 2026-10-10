"""Vitessce re-capture, session A: focus shots 01-05, m00, m12 (config.json) and m07 (lymph node demo), each with a dom sidecar.
Run: notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
     demos/_focus_run.py vitessce 8904 demos/vitessce/recap_a.py"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import sys; sys.path.insert(0, f"{_REPO}/notes/comparison/demos/vitessce")
from _recap_lib import *
DRV = "notes/comparison/demos/vitessce/recap_a.py"
def panels(page):
    return (tag(page, "Scatterplot (UMAP)", "umap", 300), tag(page, "Scatterplot (FA)", "fa", 300))
def steps(page, S):
    page.context.grant_permissions(["local-network-access"], origin="https://vitessce.io")
    page.goto(APP + "config.json", timeout=90000); page.wait_for_timeout(15000)
    cs = tag(page, "Cell Sets", "cellsets", 150); gl = tag(page, "Gene List", "genelist", 150)
    um, fa = panels(page)
    snap(page, "01_loaded.jpg", [pv("focus", "N", "Cell Sets lists only obs columns and Gene List only var names; no obsp/varp relation can be chosen as a focus")],
         [(1, cs, "Cell Sets: obs columns only"), (2, gl, "Gene List: var names only")], DRV)
    snap(page, "m00_plots_render.jpg", [pv("cells", "N", "Only configured obs columns (Cell type, Age, Sample) and var names are offered; no obsp matrix"),
         pv("genes", "N", "No varp matrix offered anywhere"), pv("slots", "P", "No slot browser: views show what the config names (two obsm embeddings, three obs columns, X)")],
         [(1, um, "obsm X_umap"), (2, fa, "obsm X_draw_graph_fa"), (3, cs, "obs columns from the config"), (4, gl, "var names")], DRV)
    # 05 hover: expand Cell type, hover an Ery P cell at the bottom of the UMAP
    def hover():
        sw = page.locator("[class*=switcher]")
        if sw.count(): sw.first.click()
        else: page.locator("text=Cell type").first.locator("xpath=..").locator("svg, button, span").first.click()
        page.wait_for_timeout(1500)
        b = page.locator(um).bounding_box()
        for fx, fy in [(0.67, 0.92), (0.66, 0.88), (0.68, 0.95), (0.27, 0.18)]:
            page.mouse.move(b["x"] + b["width"] * fx, b["y"] + b["height"] * fy); page.wait_for_timeout(1500)
            if page.locator("text=Cell ID").count(): break
        tt = tag(page, "Cell ID", "tooltip", 60)
        print("  tooltip text:", page.locator(tt).first.inner_text(timeout=1000)[:120].replace("\n", " ") if page.locator(tt).count() else None)
        page.mouse.down(); page.mouse.up(); page.wait_for_timeout(1500)
        snap(page, "05_cell_hover_tooltip.jpg", [pv("focus", "N", "Single-cell click: hover shows a tooltip and a crosshair in the FA plot; a click adds no selection or focus")],
             [(1, tt, "hover tooltip (Cell ID, type, Age, Sample)"), (2, fa, "linked crosshair in FA"), (3, tag(page, "8,090 cells × 16,285 genes", "hmfoot", 0, False), "heatmap: all 8,090 cells still selected")], DRV)
    step("hover", hover)
    # 04 untick CD4 T cell
    def uncheck():
        page.mouse.move(1300, 880)
        row = tag(page, "CD4 T cell", "cd4row", 20)
        page.locator(row).locator("input[type=checkbox]").first.click(); page.wait_for_timeout(4000)
        snap(page, "04_cellset_uncheck_CD4_both_views.jpg", [pv("selection", "Y", "Unticking CD4 T cell (40 cells) in Cell Sets drops it from both scatterplots and the heatmap"),
             pv("filters", "P", "A cell-set checkbox restricts every view, but cells are greyed, not hidden, and there is no table filter")],
             [(1, row, "CD4 T cell unticked"), (2, um, "UMAP"), (3, fa, "FA"), (4, tag(page, "with 8,050 cells selected", "hmfoot2", 0, False), "heatmap: 8,050 cells selected")], DRV)
        page.locator(row).locator("input[type=checkbox]").first.click(); page.wait_for_timeout(2500)
    step("uncheck", uncheck)
    # 02 gene Mpo
    def g():
        gene(page, "Mpo")
        snap(page, "02_gene_Mpo_both_scatterplots.jpg", [pv("focus", "N", "Feature colouring (a2, not a relation focus): Mpo recolours both the UMAP and the FA scatterplot")],
             [(1, gl, "Mpo chosen in Gene List"), (2, um, "UMAP by Mpo"), (3, fa, "FA by Mpo")], DRV)
    step("gene", g)
    # m12 share: EDIT writes the live state into the URL; reopen with edit=false
    state = {"p": page}
    def share():
        page.get_by_role("button", name="Edit", exact=True).first.click(); page.wait_for_timeout(3000)
        import urllib.parse; u = page.url; print("  edit url len", len(u), "Mpo in url", "Mpo" in urllib.parse.unquote(u))
        snap(page, "m12_share_edit_config_with_live_state.jpg", [pv("share", "Y", "EDIT serialises the live view config (including the Mpo selection) into a data: URL")],
             [(1, "textarea, .monaco-editor, .cm-editor, pre", "config editor with the live state")], DRV)
        p2 = page.context.new_page(); p2.goto(u.replace("edit=true", "edit=false"), timeout=90000); p2.wait_for_timeout(15000)
        um2, fa2 = panels(p2)
        snap(p2, "m12_share_data_url_reopened.jpg", [pv("share", "Y", "The same URL with edit=false reopens both scatterplots coloured by Mpo")],
             [(1, um2, "UMAP by Mpo, restored"), (2, fa2, "FA by Mpo, restored")], DRV)
        state["p"] = p2
    step("share", share)
    # 03 lasso on the UMAP top (neutrophil) arm
    def las():
        p = state["p"]; um3, fa3 = panels(p)
        b = p.locator(um3).bounding_box(); x, y, w, h = b["x"], b["y"], b["width"], b["height"]
        pts = [(x + w * fx, y + h * fy) for fx, fy in [(0.43, 0.04), (0.82, 0.04), (0.95, 0.33), (0.80, 0.38), (0.43, 0.08), (0.43, 0.04)]]
        lasso(p, pts)
        snap(p, "03_lasso_UMAP_highlights_FA.jpg", [pv("selection", "Y", "A lasso on the UMAP highlights the same cells in the FA plot and restricts the heatmap")],
             [(1, um3, "lasso on UMAP"), (2, fa3, "same cells in FA"), (3, tag(p, "My Selections", "mysel", 0), "new set in Cell Sets"),
              (4, tag(p, "8,090 cells × 16,285 genes, with", "hmfoot3", 0, False), "heatmap restricted to the selection")], DRV)
    step("lasso", las)
    # m07 lymph node demo
    def lymph():
        p = state["p"].context.new_page(); p.goto(LYMPH, timeout=90000); p.wait_for_timeout(25000)
        cv = p.locator("canvas"); big = [i for i in range(cv.count()) if (cv.nth(i).bounding_box() or {}).get("width", 0) > 300]
        cl = [(i + 1, f"canvas >> nth={j}", f"Spatial view {i+1}: spots on H&E") for i, j in enumerate(big[:2])]
        snap(p, "m07_spatial_lymph_node_spots_on_he.jpg", [pv("spatial", "Y", "Lymph node demo: 3,861 spots in tissue coordinates in two Spatial views"),
             pv("image", "Y", "H&E image drawn under the spots; Spatial Layers has an Image layer toggle")],
             cl + [(3, tag(p, "Spatial Layers", "layers", 100), "Spatial Layers: Image layer")], DRV, data="human-lymph-node-10x-visium (Vitessce demo, remote zarr)")
    step("lymph", lymph)
