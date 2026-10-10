"""Vitessce matrix check, part 2: per-gene zarr requests (config_matrix.json has no heatmap, so X is not
loaded whole) and lasso -> new cell set. Local store on 8904 through https://vitessce.io.
Run: gap_run.sh <venv python> /abs/demos/_focus_run.py vitessce 8904 /abs/demos/vitessce/matrix_check2.py"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
D = f"{_REPO}/notes/comparison/screens/vitessce/"
def shot(page, n): page.screenshot(path=D + n + ".jpg", type="jpeg", quality=70); print("shot", n)
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:250])
def steps(page, S):
    page.context.grant_permissions(["local-network-access"], origin="https://vitessce.io")
    reqs = []
    page.on("request", lambda r: reqs.append((r.url.split("8904/")[-1], r.headers.get("range"))) if "127.0.0.1:8904" in r.url else None)
    page.goto("https://vitessce.io/#?url=http://127.0.0.1:8904/config_matrix.json", timeout=90000); page.wait_for_timeout(15000)
    xs = [u for u, _ in reqs if "/X/" in u]
    print("X chunk requests at load:", len(xs), xs[:3])
    def gene():
        n0 = len(reqs)
        s = page.locator("input[placeholder*='Search']").first; s.click(); s.fill("Mpo"); page.wait_for_timeout(2500)
        page.locator("text=/^Mpo$/").first.click(); page.wait_for_timeout(6000)
        x = [u for u, _ in reqs[n0:] if "/X/" in u]
        print("after Mpo: requests", len(reqs) - n0, "X chunks", len(x), x[:4])
    step("gene", gene)
    def lasso():
        page.locator("[title='Select lasso']").first.click(); page.wait_for_timeout(600)
        pts = [(320, 125), (530, 125), (560, 260), (470, 270), (330, 190), (320, 125)]
        page.mouse.move(*pts[0]); page.mouse.down()
        for p in pts[1:]: page.mouse.move(*p, steps=25); page.wait_for_timeout(50)
        page.mouse.up(); page.wait_for_timeout(4000)
        print("My Selections:", page.get_by_text("My Selections").count())
        shot(page, "m09_annotation_lasso_creates_set")
        b = page.locator("text=My Selections").first
        if b.count():
            page.locator("text=My Selections >> xpath=following::*[name()='svg' or self::button][1]").first.click(timeout=3000); page.wait_for_timeout(1000)
            print("set menu:", page.evaluate("()=>[...document.querySelectorAll('[role=menuitem], .vitessce-popover li, li')].map(e=>e.innerText.trim()).filter(t=>t&&t.length<40).slice(0,15)"))
            shot(page, "m09_annotation_set_menu")
    step("lasso", lasso)
