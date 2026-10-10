"""Vitessce re-capture, session B: m13 and m09 (config_matrix.json), m05 (config_lazy.json), each with a dom sidecar.
Run: notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
     demos/_focus_run.py vitessce 8904 demos/vitessce/recap_b.py"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import os, sys; sys.path.insert(0, f"{_REPO}/notes/comparison/demos/vitessce")
from _recap_lib import *
DRV = "notes/comparison/demos/vitessce/recap_b.py"
def steps(page, S):
    page.context.grant_permissions(["local-network-access"], origin="https://vitessce.io")
    reqs = []
    page.on("request", lambda r: reqs.append(r.url.split("8904/")[-1]) if "127.0.0.1:8904" in r.url else None)
    page.goto(APP + "config_matrix.json", timeout=90000); page.wait_for_timeout(15000)
    step("gene", lambda: gene(page, "Mpo")); page.wait_for_timeout(3000)
    vs = page.locator(".vega-embed"); print("  vega views", vs.count())
    snap(page, "m13_export_vega_views.jpg", [pv("export", "P", "The Vega views (Cell Set Sizes, Histogram, Expression by Cell Set) carry a '...' export menu; the deck.gl scatterplot has none")],
         [(i + 1, f".vega-embed >> nth={i}", lab) for i, lab in enumerate(["Cell Set Sizes", "Histogram (Mpo)", "Expression by Cell Set (Mpo)"][:vs.count()])], DRV)
    def menu():
        s = page.locator(".vega-embed summary"); s.first.hover(); s.first.click(); page.wait_for_timeout(1000)
        print("  vega actions:", page.evaluate("()=>[...document.querySelectorAll('.vega-actions a')].map(a=>a.innerText.trim())"))
        snap(page, "m13_export_vega_actions_menu.jpg", [pv("export", "P", "Vega '...' menu: Save as SVG, Save as PNG, View Source, View Compiled Vega, Open in Vega Editor")],
             [(1, ".vega-actions", "Save as SVG / PNG"), (2, ".vega-embed summary >> nth=0", "'...' button")], DRV)
        with page.expect_download(timeout=20000) as d: page.locator(".vega-actions a:has-text('PNG')").first.click()
        out = "/tmp/vitessce_vega.png"; d.value.save_as(out); print("  download:", d.value.suggested_filename, os.path.getsize(out), "bytes")
        page.keyboard.press("Escape"); page.mouse.click(1300, 60); page.wait_for_timeout(800)
    step("vega menu", menu)
    def las():
        lasso(page, [(320, 125), (530, 125), (560, 260), (470, 270), (330, 190), (320, 125)])
        um = tag(page, "Scatterplot (UMAP)", "umap", 300)
        snap(page, "m09_annotation_lasso_creates_set.jpg", [pv("annot", "P", "A lasso creates 'My Selections' > 'Selection 1' in view state; the store is not written")],
             [(1, um, "lasso on UMAP"), (2, tag(page, "My Selections", "mysel", 0), "new set 'My Selections'"), (3, ".vega-embed >> nth=0", "Cell Set Sizes: the selection")], DRV)
        page.locator("text=My Selections >> xpath=following::*[name()='svg' or self::button][1]").first.click(timeout=3000); page.wait_for_timeout(1000)
        print("  set menu:", page.evaluate("()=>[...document.querySelectorAll('[role=menuitem], li')].map(e=>e.innerText.trim()).filter(t=>t&&t.length<40).slice(0,8)"))
        snap(page, "m09_annotation_set_menu.jpg", [pv("annot", "P", "The set menu offers Rename, Delete, Export hierarchy (JSON, CSV); no write-back to the store")],
             [(1, tag(page, "Rename", "rename", 120), "Rename / Delete / Export hierarchy"), (2, tag(page, "My Selections", "mysel2", 0), "My Selections")], DRV)
    step("lasso", las)
    def lazy():
        nonlocal_page = page.context.new_page(); page.close()
        p = nonlocal_page; r2 = []
        p.on("request", lambda r: r2.append(r.url.split("8904/")[-1]) if "127.0.0.1:8904" in r.url else None)
        p.goto(APP + "config_lazy.json", timeout=90000); p.wait_for_timeout(12000)
        print("  X requests at load:", len([u for u in r2 if "/X/" in u])); n0 = len(r2)
        gene(p, "Mpo")
        print("  after Mpo: X requests", [u for u in r2[n0:] if "/X/" in u][:8])
        snap(p, "m05_lazy_scatter_genelist_mpo.jpg", [pv("lazy", "Y", "With only UMAP and Gene List, load fetches no X chunk; choosing Mpo fetches X/.zarray, X/.zattrs and one chunk")],
             [(1, tag(p, "Gene List", "gl", 150), "Mpo chosen"), (2, tag(p, "Scatterplot (UMAP)", "umap2", 300), "UMAP by Mpo")], DRV)
    step("lazy", lazy)
    # retry of session A's 04 (the cell-set checkbox is not an <input>)
    def uncheck():
        p = page.context.new_page(); p.bring_to_front(); p.goto(APP + "config.json", timeout=90000); p.wait_for_timeout(14000)
        sw = p.locator("[class*=switcher]")
        if sw.count(): sw.first.click()
        p.wait_for_timeout(1500)
        r = p.evaluate("""() => { const t = [...document.querySelectorAll('body *')].filter(e => e.children.length===0 && (e.textContent||'').trim()==='CD4 T cell')[0];
            if (!t) return 'no text'; let e = t;
            for (let i=0; i<8 && e; i++, e=e.parentElement) {
              const c = e.querySelector('input[type=checkbox], [role=checkbox], [class*=checkbox], [class*=Checkbox]');
              if (c) { c.setAttribute('data-recap','cd4box'); e.setAttribute('data-recap','cd4row'); return [i, c.tagName, c.className && c.className.baseVal !== undefined ? c.className.baseVal : c.className]; } }
            return 'no box'; }""")
        print("  cd4 box", r)
        p.locator("[data-recap='cd4box']").first.click(force=True); p.wait_for_timeout(4000)
        um = tag(p, "Scatterplot (UMAP)", "umap4", 300); fa = tag(p, "Scatterplot (FA)", "fa4", 300)
        snap(p, "04_cellset_uncheck_CD4_both_views.jpg", [pv("selection", "Y", "Unticking CD4 T cell (40 cells) in Cell Sets drops it from both scatterplots and the heatmap"),
             pv("filters", "P", "A cell-set checkbox restricts every view, but cells are greyed, not hidden, and there is no table filter")],
             [(1, "[data-recap='cd4row']", "CD4 T cell unticked"), (2, um, "UMAP"), (3, fa, "FA"), (4, tag(p, "8,090 cells × 16,285 genes, with", "hmfoot4", 0, False), "heatmap: 8,050 cells selected")],
             "notes/comparison/demos/vitessce/recap_b.py")
        # retry of session A's 03 (the lasso on a second tab drew nothing)
        p.locator("[data-recap='cd4box']").first.click(force=True); p.wait_for_timeout(2500)
        b = p.locator(um).bounding_box(); x, y, w, h = b["x"], b["y"], b["width"], b["height"]
        lasso(p, [(x + w * fx, y + h * fy) for fx, fy in [(0.43, 0.04), (0.82, 0.04), (0.95, 0.33), (0.80, 0.38), (0.43, 0.08), (0.43, 0.04)]])
        snap(p, "03_lasso_UMAP_highlights_FA.jpg", [pv("selection", "Y", "A lasso on the UMAP highlights the same cells in the FA plot and restricts the heatmap")],
             [(1, um, "lasso on UMAP"), (2, fa, "same cells in FA"), (3, tag(p, "My Selections", "mysel3", 0), "new set in Cell Sets"),
              (4, tag(p, "8,090 cells × 16,285 genes, with", "hmfoot5", 0, False), "heatmap restricted to the selection")], "notes/comparison/demos/vitessce/recap_b.py")
    step("uncheck", uncheck)
