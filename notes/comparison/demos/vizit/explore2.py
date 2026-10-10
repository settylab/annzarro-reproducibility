"""Second look at hosted VizIt (pd5d.yale.edu): the Gene, Cluster, Spatial Tx and XCheck views, with the
WebGL point-count hook, API request sizes and the visible text, to plan the matrix checks."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, f"{_DEMO_ROOT}/_browser")
from probe_web import INIT

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
D = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    ctx = b.new_context(viewport={"width": 1400, "height": 900}); ctx.add_init_script(INIT)
    p = ctx.new_page()
    reqs = []
    p.on("requestfinished", lambda r: reqs.append([r.method, r.url[:200], r.sizes().get("responseBodySize")]))
    for name in ["geneview", "clusters", "visiumview", "xcheck", "celltypes"]:
        reqs.clear()
        p.goto(f"https://pd5d.yale.edu/views/{name}", timeout=90000); p.wait_for_timeout(12000)
        p.screenshot(path=str(OUT / f"w_{name}.png"), full_page=True)
        D[name] = {"url": p.url, "text": p.inner_text("body")[:3500], "gl": p.evaluate("window.__gl"),
                   "api": [r for r in reqs if "/api/" in r[1]][:40],
                   "buttons": p.eval_on_selector_all("button,[role=button],a", "es=>es.map(e=>e.innerText.trim()).filter(t=>t&&t.length<40).slice(0,80)"),
                   "selects": p.eval_on_selector_all("input,select", "es=>es.map(e=>(e.placeholder||e.name||e.id||e.type)).slice(0,40)")}
    (OUT / "dump.json").write_text(json.dumps(D, indent=1, default=str))
    b.close()
