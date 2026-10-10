"""Re-capture helper: snap() = backup the old image, screenshot under the SAME name, write the dom sidecar.
Old image is copied to RECAP/prev/<tool>/<name> (scratchpad) so the caller can decide whether it needs a <stem>.prev.jpg.
If a callout selector is not visible, falls back to an empty callout list and prints a warning."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import os, shutil, sys
sys.path.insert(0, os.path.dirname(__file__))
from record_json import record
SCREENS = f"{_REPO}/notes/comparison/screens/"
RECAP = f"{_SCRATCH}/recap/prev/"
def pv(col, mark, cap): return {"column": col, "mark": mark, "caption": cap}
def snap(page, tool, name, proves, callouts, *, software, driver, data=None, url=None, full_page=False, by="comparison-auditor"):
    path = SCREENS + tool + "/" + name
    if os.path.exists(path):
        os.makedirs(RECAP + tool, exist_ok=True)
        bk = RECAP + tool + "/" + name
        if not os.path.exists(bk): shutil.copy2(path, bk)
    if full_page: page.evaluate("window.scrollTo(0,0)")
    page.screenshot(path=path, type="jpeg", quality=70, full_page=full_page)
    ok = []
    for c in callouts:
        try:
            bb = page.locator(c[1]).first.bounding_box(timeout=1500)
            vp = page.viewport_size
            if bb is None or bb["width"] <= 0 or bb["height"] <= 0: print("  callout not visible:", c[1][:80])
            elif bb["x"] >= vp["width"] or bb["y"] >= vp["height"] or bb["x"] + bb["width"] <= 0 or bb["y"] + bb["height"] <= 0:
                print("  callout outside viewport:", c[1][:80])
            else: ok.append(c)
        except Exception as e: print("  callout missing:", c[1][:80])
    record(page, path, tool=tool, software=software, by=by, driver=driver, data=data, url=url, proves=proves, callouts=ok)
    print("shot", tool, name, "callouts", len(ok), "/", len(callouts), flush=True)
