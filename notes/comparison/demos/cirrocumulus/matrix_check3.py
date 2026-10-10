"""Cirrocumulus matrix check, part 3 (DE: One vs. Rest on Age), local bm_demo on 8901.
Run: gap_run.sh <venv python> /abs/demos/_focus_run.py cirrocumulus 8901 /abs/demos/cirrocumulus/matrix_check3.py"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import os, glob
D = f"{_REPO}/notes/comparison/screens/cirrocumulus/"
def shot(page, n): page.screenshot(path=D + n + ".jpg", type="jpeg", quality=70); print("shot", n)
def steps(page, S):
    page.set_viewport_size({"width": 1400, "height": 1100})
    page.goto("http://127.0.0.1:8901/"); page.wait_for_timeout(8000)
    mc = page.locator("[data-testid=compare-meta-input] input, input[aria-label*='Metadata Categories']").first
    if mc.count() == 0: mc = page.get_by_label("Metadata Categories").first
    mc.click(); mc.type("Age", delay=100); page.wait_for_timeout(1500)
    print("options:", page.evaluate("()=>[...document.querySelectorAll('[role=option], li')].map(e=>e.innerText.trim()).filter(t=>t&&t.length<30).slice(0,10)"))
    page.keyboard.press("ArrowDown"); page.keyboard.press("Enter"); page.wait_for_timeout(800); page.keyboard.press("Escape")
    page.get_by_role("button", name="GO").click(); page.wait_for_timeout(1500)
    mi = page.locator("[role=menuitem]:visible")
    print("visible menu after GO:", [mi.nth(i).inner_text() for i in range(mi.count())], "| dialog:", page.locator("[role=dialog]:visible").count())
    if mi.count() and not page.locator("[role=dialog]:visible").count(): mi.first.click(); page.wait_for_timeout(1000)
    page.locator("[role=dialog]:visible input").first.fill("matrix_check_age_one_vs_rest"); page.get_by_role("button", name="Submit").click()
    page.wait_for_timeout(25000)
    shot(page, "m10_de_job_submitted")
    page.get_by_role("tab", name="Results").click(); page.wait_for_timeout(2000)
    shot(page, "m10_de_results_list")
    b = page.get_by_text("matrix_check_age_one_vs_rest")
    if b.count(): b.first.click(); page.wait_for_timeout(8000)
    shot(page, "m10_de_results")
    print("results files:", [(f, os.path.getsize(f)) for f in glob.glob(os.path.expanduser(f"{_DEMO_ROOT}/_data/results/**"), recursive=True) if os.path.isfile(f)][:5])
