"""Second look at TissUUmaps 3.2.1.11: drive the marker dropdowns, open the settings, the "+" form,
the Regions/Layers tabs and the File menu; dump option lists and count WebGL points drawn.
Server on 127.0.0.1:8908 (started by the session script). Output: screenshots + texts in argv[1]."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, f"{_DEMO_ROOT}/_browser")
from probe_web import INIT  # WebGL draw-call hook: window.__gl.max = largest points in one call

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
DUMP = {}


def shot(p, name):
    p.screenshot(path=str(OUT / f"{name}.png"))


def selects(p):
    return p.evaluate("""() => [...document.querySelectorAll('select')].filter(s => s.offsetParent || s.id)
        .map(s => ({id: s.id, n: s.options.length, opts: [...s.options].slice(0, 40).map(o => o.text)}))""")


def pick(p, label_text, value):
    """Select2 dropdown following a label: open it, type, Enter."""
    box = p.locator(f"text={label_text}").locator("xpath=following::span[contains(@class,'select2')][1]").first
    box.click(); p.keyboard.type(value, delay=40); p.wait_for_timeout(1200); p.keyboard.press("Enter")


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    ctx = b.new_context(viewport={"width": 1400, "height": 900})
    ctx.add_init_script(INIT)
    p = ctx.new_page()
    p.goto("http://127.0.0.1:8908/bm_demo_csc.h5ad", timeout=120000); p.wait_for_timeout(8000)
    DUMP["bm_selects_initial"] = selects(p)
    try:
        pick(p, "Categorical observations", "highres_celltype"); p.wait_for_timeout(8000)
    except Exception as e:
        DUMP["pick_cat_error"] = str(e)[:200]
    DUMP["bm_gl_after_cat"] = p.evaluate("window.__gl")
    shot(p, "a_bm_celltype")
    try:
        pick(p, "Gene expression", "Mpo"); p.wait_for_timeout(8000)
    except Exception as e:
        DUMP["pick_gene_error"] = str(e)[:200]
    DUMP["bm_gl_after_gene"] = p.evaluate("window.__gl")
    shot(p, "b_bm_mpo")
    DUMP["bm_text_after"] = p.inner_text("#ISS_menu")[:3000] if p.locator("#ISS_menu").count() else p.inner_text("body")[:3000]
    for tab in ["Regions", "Layers"]:
        try:
            p.get_by_text(tab, exact=True).first.click(); p.wait_for_timeout(1500); shot(p, f"c_bm_tab_{tab}")
            DUMP[f"bm_tab_{tab}"] = p.inner_text("body")[:2500]
        except Exception as e:
            DUMP[f"tab_{tab}_error"] = str(e)[:200]
    try:
        p.locator(".nav-link i.fa-cog, .nav-link .bi-gear, a:has(i[class*='cog'])").first.click(); p.wait_for_timeout(1500)
        shot(p, "d_bm_settings"); DUMP["bm_settings"] = p.inner_text("body")[:3000]
    except Exception as e:
        DUMP["settings_error"] = str(e)[:200]
    try:
        p.get_by_text("Markers", exact=True).first.click(); p.wait_for_timeout(800)
        p.get_by_text("+", exact=True).first.click(); p.wait_for_timeout(2500)
        shot(p, "e_bm_plus_form"); DUMP["bm_plus_form"] = p.inner_text("body")[:4000]; DUMP["bm_selects_plus"] = selects(p)
    except Exception as e:
        DUMP["plus_error"] = str(e)[:200]
    try:
        p.locator("#a_menubar_File, #navbarDropdownMenuLink").first.click(); p.wait_for_timeout(800)
        shot(p, "f_bm_file_menu"); DUMP["file_menu"] = p.inner_text("#menubar_File") if p.locator("#menubar_File").count() else ""
        p.keyboard.press("Escape")
    except Exception as e:
        DUMP["file_menu_error"] = str(e)[:200]
    # spatial demo: spots over the image, edges from obsp/spatial_connectivities
    p.goto("http://127.0.0.1:8908/spatial_demo.h5ad", timeout=120000); p.wait_for_timeout(8000)
    DUMP["sp_selects"] = selects(p)
    try:
        pick(p, "Categorical observations", "leiden"); p.wait_for_timeout(8000)
    except Exception as e:
        DUMP["sp_pick_error"] = str(e)[:200]
    DUMP["sp_gl"] = p.evaluate("window.__gl")
    shot(p, "g_sp_leiden"); DUMP["sp_text"] = p.inner_text("body")[:3000]
    try:
        p.get_by_text("Layers", exact=True).first.click(); p.wait_for_timeout(1500); shot(p, "h_sp_layers")
    except Exception as e:
        DUMP["sp_layers_error"] = str(e)[:200]
    (OUT / "dump.json").write_text(json.dumps(DUMP, indent=1, default=str)[:200000])
    b.close()
