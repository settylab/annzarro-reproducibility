"""iSEE gap shots (evidence-curator, 2026-10-04). Run under notes/comparison/demos/scale_probe/gap_run.sh with
benchmark/scale/ceiling/.venv/bin/python <this file>

Starts the local demo ($DEMO_ROOT/isee/start.sh: iSEE 2.18.0 on bm_demo_sce.rds, 127.0.0.1:8902),
and stops it at the end.
spatial N: Reduced dimension plot 1, "Type" dropdown open: reducedDims only, no spatial type.
spatial N, image N: Organization > Organize panels: the panel classes on offer, none spatial or image.
annot N, image N: Visual parameters of the same panel, every section shown: no label editing, no image layer.
"""
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaplib import SCRATCH, TODAY, log, pv, snap  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRIVER = "evidence/screens/gaps/capture_isee.py"
TOOL = "isee"
SW = "iSEE 2.18.0 (Bioc 3.20, R 4.4.3)"
DATA = "bm_demo_sce.rds (8,090 cells)"
URL = "http://127.0.0.1:8902"


def opts(p, sel):
    return p.evaluate(f"()=>{{const s=$('{sel}')[0]; return s&&s.selectize?Object.keys(s.selectize.options):(s?[...s.options].map(o=>o.value):null)}}")


os.makedirs(SCRATCH + "isee", exist_ok=True)
srv = subprocess.Popen(["$DEMO_ROOT/isee/start.sh"], stdout=open(SCRATCH + "isee/srv.log", "w"), stderr=subprocess.STDOUT)
try:
    for _ in range(150):
        try:
            urllib.request.urlopen(URL, timeout=2)
            break
        except Exception:
            time.sleep(1)
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, channel="chromium")
        p = b.new_page(viewport={"width": 1400, "height": 1000})
        p.goto(URL, timeout=120000)
        p.wait_for_timeout(25000)
        # spatial: Type dropdown
        try:
            types = opts(p, "#ReducedDimensionPlot1_Type")
            log("RD1 Type options:", types)
            p.locator("#heading_collapse_ReducedDimensionPlot1_DataBoxOpen a").click()
            p.wait_for_timeout(1500)
            p.locator("#ReducedDimensionPlot1_Type + .selectize-control").scroll_into_view_if_needed()
            p.evaluate("()=>$('#ReducedDimensionPlot1_Type')[0].selectize.open()")
            p.wait_for_timeout(1000)
            p.evaluate("()=>{const c=$('#ReducedDimensionPlot1_Type')[0].selectize.$dropdown[0]; c.setAttribute('data-gap','typedd');}")
            snap(p, TOOL, "g01_spatial_reduced_dim_type_dropdown.jpg",
                 [pv("spatial", "N", f"{SW} ({TODAY}): Reduced dimension plot 'Type' lists the reducedDims only ({', '.join(types or [])}); no spatial coordinate type, and no panel reads spatialCoords")],
                 [(1, "[data-gap='typedd']", "Type: " + ", ".join(types or [])), (2, "#ReducedDimensionPlot1_Type + .selectize-control", "Reduced dimension type")],
                 software=SW, driver=DRIVER, data=DATA, url=URL)
            p.evaluate("()=>$('#ReducedDimensionPlot1_Type')[0].selectize.close()")
        except Exception as e:
            log("FAIL type", str(e)[:200])
        # spatial / image: Organize panels modal
        try:
            p.evaluate("window.scrollTo(0,0)")
            p.locator("a.dropdown-toggle:has(i.fa-object-group)").first.click()
            p.wait_for_timeout(800)
            p.locator("#iSEE_INTERNAL_organize_panels").click()
            p.wait_for_timeout(2500)
            modal = p.locator(".modal-dialog").first
            log("modal text:", modal.inner_text()[:600].replace("\n", " | "))
            classes = p.evaluate("()=>{const s=[...document.querySelectorAll('.modal select')].map(x=>x.selectize?Object.values(x.selectize.options).map(o=>o.label||o.value):[...x.options].map(o=>o.text)); return s}")
            log("panel classes:", classes)
            try:
                p.evaluate("()=>{const x=[...document.querySelectorAll('.modal select')].find(s=>s.selectize); if(x){x.selectize.open(); x.selectize.$dropdown[0].setAttribute('data-gap','classes');}}")
                p.wait_for_timeout(1000)
            except Exception:
                pass
            flat = [c for c in (classes[0] if classes else []) if not c.split()[-1].isdigit()]
            snap(p, TOOL, "g02_spatial_image_organize_panels_classes.jpg",
                 [pv("spatial", "N", f"{SW} ({TODAY}): Organize panels offers the panel classes of iSEE ({', '.join(flat)}); none plots spatial coordinates"),
                  pv("image", "N", f"{SW} ({TODAY}): no panel class draws a tissue image layer")],
                 [(1, "[data-gap='classes']", "panel classes on offer"), (2, ".modal-dialog", "Organize panels")],
                 software=SW, driver=DRIVER, data=DATA, url=URL)
            p.keyboard.press("Escape")
            p.wait_for_timeout(500)
            for t in ["Apply settings", "Dismiss", "Close"]:
                bt = p.get_by_role("button", name=t)
                if bt.count() and bt.first.is_visible():
                    bt.first.click()
                    p.wait_for_timeout(1500)
                    break
        except Exception as e:
            log("FAIL organize", str(e)[:200])
        # annot / image: Visual parameters with every section on
        try:
            p.goto(URL, timeout=120000)
            p.wait_for_timeout(20000)
            p.set_viewport_size({"width": 1400, "height": 1400})
            p.locator("#heading_collapse_ReducedDimensionPlot1_VisualBoxOpen a").click()
            p.wait_for_timeout(1500)
            vals = p.eval_on_selector_all("input[name=ReducedDimensionPlot1_VisualChoices]", "els=>els.map(e=>e.value)")
            log("visual choices:", vals)
            for v in vals:
                cb = p.locator(f"input[name=ReducedDimensionPlot1_VisualChoices][value='{v}']")
                if not cb.is_checked():
                    cb.evaluate("e=>e.click()")
                    p.wait_for_timeout(700)
            p.wait_for_timeout(2500)
            vb = p.locator("#ReducedDimensionPlot1_VisualBoxOpen")
            vb.evaluate("e=>e.setAttribute('data-gap','visual')")
            vb.evaluate("e=>e.scrollIntoView({block:'start'})")
            p.wait_for_timeout(800)
            labels = p.locator("[data-gap='visual'] label").all_inner_texts()
            log("visual labels:", [l.strip() for l in labels if l.strip()][:60])
            snap(p, TOOL, "g03_annot_image_visual_parameters_all_sections.jpg",
                 [pv("annot", "N", f"{SW} ({TODAY}): Visual parameters with every section on ({', '.join(vals)}): colour, shape, size, point, facet, text and other settings; no control writes a label to colData"),
                  pv("image", "N", f"{SW} ({TODAY}): no image or tissue layer among the Visual parameters of the plot")],
                 [(1, "[data-gap='visual']", "Visual parameters, all sections shown"), (2, "input[name=ReducedDimensionPlot1_VisualChoices] >> xpath=ancestor::div[contains(@class,'shiny-input-checkboxgroup')][1]", "sections: " + ", ".join(vals))],
                 software=SW, driver=DRIVER, data=DATA, url=URL)
        except Exception as e:
            log("FAIL visual", str(e)[:200])
        b.close()
finally:
    subprocess.run(["$DEMO_ROOT/isee/stop.sh"])
    srv.terminate()
    log("iSEE stopped")
log("done")
