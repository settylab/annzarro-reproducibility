"""First look at TissUUmaps 3.2.1.11 on the bone marrow and spatial demos: screenshots plus the visible
UI text, to plan the matrix checks. Assumes the server is running on 127.0.0.1:8908."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    p = b.new_context(viewport={"width": 1400, "height": 900}).new_page()
    reqs = []
    p.on("request", lambda r: reqs.append((r.url[-60:], r.headers.get("range"))))
    for name in ["bm_demo_csc", "spatial_demo"]:
        p.goto(f"http://127.0.0.1:8908/{name}.h5ad", timeout=120000)
        p.wait_for_timeout(15000)
        p.screenshot(path=str(OUT / f"x_{name}.png"))
        (OUT / f"x_{name}.txt").write_text(p.inner_text("body")[:6000])
        (OUT / f"x_{name}_reqs.txt").write_text("\n".join(f"{u} {r}" for u, r in reqs))
        reqs.clear()
    b.close()
