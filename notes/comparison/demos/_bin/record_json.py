"""Drop-in for evidence.tools.annotate.record() in the Playwright venv, which lacks PyYAML and Pillow.
Same fields and box arithmetic as record(); writes the sidecar as JSON, which is valid YAML
(annotate.py loads it with yaml.safe_load). Image size = viewport x devicePixelRatio (full-viewport shots only).
Validate afterwards with: <python with yaml+PIL> evidence/tools/annotate.py check <sidecar>."""
import json
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]  # repository root

def _rel(driver):
    """A driver inside the repository is recorded repo-relative, so sidecars carry no home path."""
    try:
        return str(Path(driver).resolve().relative_to(_REPO))
    except (ValueError, TypeError, OSError):
        return driver

def record(page, shot, *, tool, proves, callouts, software, by, driver, data=None, url=None, pad=4):
    shot = Path(shot)
    dpr = page.evaluate("window.devicePixelRatio") or 1
    vp = page.viewport_size
    W, H = vp["width"] * dpr, vp["height"] * dpr
    out = []
    for n, sel, label in callouts:
        bb = page.locator(sel).first.bounding_box()
        if bb is None:
            raise RuntimeError(f"callout {n}: selector {sel!r} not visible")
        x, y = max(0, (bb["x"] - pad) * dpr), max(0, (bb["y"] - pad) * dpr)
        w, h = min(W - x, (bb["width"] + 2 * pad) * dpr), min(H - y, (bb["height"] + 2 * pad) * dpr)
        if w <= 0 or h <= 0:
            raise RuntimeError(f"callout {n}: selector {sel!r} outside the viewport")
        out.append({"n": n, "box": [round(x), round(y), round(w), round(h)], "label": label, "selector": sel})
    meta = {"version": 1, "image": shot.name, "tool": tool, "software": software, "data": data,
            "url": url or page.url, "captured": date.today().isoformat(), "by": by, "driver": _rel(driver),
            "source": "dom", "proves": proves, "callouts": out}
    side = shot.with_name(shot.stem + ".annot.yaml")
    side.write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    return side
