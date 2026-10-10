# Kana focus re-capture (one session, <3 min): live build https://www.kanaverse.org/kana/ (v3.2.0), Explore mode with
# $DEMO_ROOT/_data/bm_demo.h5ad. Writes screens/kana/01-05 (same names as before) + dom .annot.yaml sidecars.
# Run: notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python demos/kana/focus_recap.py
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import time, os, sys
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from recap import snap as _snap, pv
from playwright.sync_api import sync_playwright
BM = os.path.expanduser(f"{_DEMO_ROOT}/_data/bm_demo.h5ad")
SW = "Kana v3.2.0 (live build, kanaverse.org)"; DATA = "bm_demo.h5ad (8,090 cells)"; DRV = "notes/comparison/demos/kana/focus_recap.py"
T0 = time.time()
def snap(p, name, proves, callouts):
    try: _snap(p, "kana", name, proves, callouts, software=SW, driver=DRV, data=DATA)
    except Exception as e: print("SNAP FAIL", name, str(e)[:200])
    print(f"  [{time.time()-T0:.0f}s]", flush=True)
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:250])
TAG_JS = """([txt, tag, minh, exact]) => {
  const all = [...document.querySelectorAll('body *')].filter(e => e.getClientRects().length);
  let c = all.filter(e => { const t = (e.innerText || e.textContent || '').trim(); return exact ? t === txt : t.startsWith(txt); });
  if (!c.length) return null;
  c.sort((a, b) => a.getBoundingClientRect().width * a.getBoundingClientRect().height - b.getBoundingClientRect().width * b.getBoundingClientRect().height);
  let e = c[0];
  while (e.parentElement && e.getBoundingClientRect().height < minh) e = e.parentElement;
  e.setAttribute('data-recap', tag); const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height].map(Math.round);
}"""
def tag(p, txt, name, minh=0, exact=True):
    try: r = p.evaluate(TAG_JS, [txt, name, minh, exact])
    except Exception: r = None
    print("  tag", name, r); return f"[data-recap='{name}']"
def tagpt(p, fx, fy, name, minw, minh):
    r = p.evaluate("""([fx, fy, name, minw, minh]) => { let e = document.elementFromPoint(innerWidth*fx, innerHeight*fy);
        while (e && e.parentElement && (e.getBoundingClientRect().width < minw || e.getBoundingClientRect().height < minh)) e = e.parentElement;
        if (!e) return null; e.setAttribute('data-recap', name); const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height].map(Math.round); }""", [fx, fy, name, minw, minh])
    print("  tagpt", name, r); return f"[data-recap='{name}']"
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium", args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    p = b.new_context(viewport={"width": 1800, "height": 950}).new_page(); p.set_default_timeout(20000)
    p.goto("https://www.kanaverse.org/kana/", timeout=120000); time.sleep(4)
    p.get_by_text("I want to explore existing analysis results").click(); time.sleep(3)
    p.locator("input[type=file]").first.set_input_files(BM); time.sleep(8)
    p.get_by_role("button", name="Explore", exact=True).first.click()
    for i in range(15):
        time.sleep(4)
        if p.get_by_text("X_umap", exact=True).count(): break
    time.sleep(5); print(f"loaded [{time.time()-T0:.0f}s]")
    p.get_by_text("X_umap", exact=True).first.click(); time.sleep(4)
    p.locator("select").first.select_option("highres_celltype"); time.sleep(3)
    opts = p.locator("select").first.evaluate("s=>[...s.options].map(o=>o.text)"); print("annotation options", opts)
    tabs = "button:has-text('X_diffusion') >> xpath=.."
    snap(p, "01_loaded_umap_celltype.jpg", [pv("focus", "N", "Embedding tabs offer only obsm keys and 'Choose annotation' only obs columns; no obsp (connectivities, distances, diffusion_distance) can be chosen as a focus")],
         [(1, tabs, "embedding tabs: obsm keys only"), (2, "select >> nth=0", "Choose annotation: obs columns only"), (3, "canvas >> nth=0", "the one live embedding")])
    def click():
        p.get_by_role("button", name="Pan").first.click(); time.sleep(1)
        p.mouse.click(720, 500); time.sleep(3)
        snap(p, "04_cell_click_no_visible_change.jpg", [pv("focus", "N", "Single-cell click under Pan on a dense GMP region: no visible change, no per-cell focus")],
             [(1, "canvas >> nth=0", "clicked at a GMP cell: no change"), (2, "button:has-text('Pan')", "Pan mode")])
    step("click", click)
    def gene():
        s = p.locator("input[placeholder*='Search gene']").first; s.click(); s.fill("Mpo"); time.sleep(3)
        r = p.evaluate("""() => { const c = [...document.querySelectorAll('body *')].filter(e => e.children.length===0 && (e.textContent||'').trim()==='Mpo');
             for (const t of c) { let e = t; for (let i=0;i<6 && e;i++, e=e.parentElement) { const bs = e.querySelectorAll('button, [role=button]'); if (bs.length>=2) { bs[bs.length-1].setAttribute('data-recap','drop'); e.setAttribute('data-recap-row','mpo'); return bs.length; } } } return 0; }""")
        print("  Mpo row buttons", r)
        p.locator("[data-recap='drop']").first.click(); time.sleep(4)
        snap(p, "02_gene_Mpo_main_only.jpg", [pv("focus", "N", "Feature colouring (a2): Mpo recolours the one live embedding only; the gallery snapshots do not change")],
             [(1, "[data-recap-row='mpo']", "Mpo: 'Visualize this gene's expression'"), (2, "canvas >> nth=0", "main embedding by Mpo"), (3, tag(p, "Gradient for", "grad", 30, False), "gradient 0.0 to 3.2"), (4, tagpt(p, 0.92, 0.5, "gal", 250, 500), "gallery unchanged")])
        try:
            p.locator("[data-recap='grad'] button, [data-recap='grad'] [class*=remove]").first.click(timeout=3000); time.sleep(2)
        except Exception as e: print("  gradient remove failed", str(e)[:80])
        p.locator("select").first.select_option("highres_celltype"); time.sleep(3)
    step("gene", gene)
    def lasso():
        p.get_by_role("button", name="Selection").first.evaluate("e=>e.click()"); time.sleep(1)
        pts = [(380, 255), (545, 255), (550, 470), (380, 470), (380, 255)]
        p.mouse.move(*pts[0]); p.mouse.down()
        for x, y in pts[1:]: p.mouse.move(x, y, steps=12)
        p.mouse.up(); time.sleep(4)
        print("  SELTXT", p.locator("text=/cells selected/").all_inner_texts()[:2])
        snap(p, "03_lasso_main_view_only.jpg", [pv("selection", "P", "A lasso greys the cells outside it in the one embedding; the gallery snapshots stay unchanged")],
             [(1, "canvas >> nth=0", "lasso in the embedding"), (2, tag(p, "cells selected", "nsel", 0, False), "N cells selected"), (3, "[data-recap='gal']", "gallery unchanged")])
        p.get_by_role("button", name="Save", exact=True).first.click(); time.sleep(6)
        snap(p, "05_saved_selection_listed.jpg", [pv("selection", "P", "'Save' lists the lasso as 'Selection 1' under Custom Selections, usable as a marker group")],
             [(1, tag(p, "Custom Selections", "cust", 60), "Custom Selections"), (2, "text=Selection 1", "Selection 1")])
    step("lasso", lasso)
    print(f"elapsed {time.time()-T0:.0f}"); b.close()
