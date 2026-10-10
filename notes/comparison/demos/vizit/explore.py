"""First look at the hosted VizIt deployment (Parkinson's Cell Atlas, pd5d.yale.edu): screenshots, visible
text and the API requests per page, to plan the matrix checks."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    p = b.new_context(viewport={"width": 1400, "height": 900}).new_page()
    reqs = []
    p.on("requestfinished", lambda r: reqs.append(f"{r.method} {r.url[:140]} {r.sizes().get('responseBodySize')}"))
    p.goto("https://pd5d.yale.edu/", timeout=60000); p.wait_for_timeout(6000)
    p.screenshot(path=str(OUT / "v_home.png")); (OUT / "v_home.txt").write_text(p.inner_text("body")[:5000])
    links = p.eval_on_selector_all("a[href]", "els => [...new Set(els.map(e => e.href))]")
    (OUT / "v_links.txt").write_text("\n".join(links))
    for i, href in enumerate([l for l in links if "pd5d.yale.edu" in l][:8]):
        try:
            p.goto(href, timeout=60000); p.wait_for_timeout(7000)
            p.screenshot(path=str(OUT / f"v_{i:02d}.png")); (OUT / f"v_{i:02d}.txt").write_text(href + "\n" + p.inner_text("body")[:3000])
        except Exception as e:
            (OUT / f"v_{i:02d}.txt").write_text(f"{href} ERROR {e}")
    (OUT / "v_reqs.txt").write_text("\n".join(reqs))
    b.close()
