"""Render request logs as pages and screenshot them (visual proof for the lazy column, per the Columns-page rule
'an annotated request log'). TissUUmaps: the server's own werkzeug log lines for the h5ad (HTTP 206 = byte range).
VizIt: the API calls the hosted app made on one Gene View load (from the session's raw log)."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import html, json, re, sys
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from pathlib import Path
from record_json import record
from playwright.sync_api import sync_playwright
S = Path(f"{_SCRATCH}")
SCR = Path(f"{_REPO}/notes/comparison/screens")
def pv(c): return {"column": c, "mark": "?", "caption": "raw capture; verdict and caption pending review of the shot"}
tu = [re.sub(r"\x1b\[[0-9;]*m", "", l.strip()) for l in open(Path.home() / "annzarro_compare/tissuumaps/server_matrix.log", errors="ignore") if ".h5ad" in l and "GET" in l]
vz = json.load(open(S / "vz_dl/matrix_log.json"))["gene_api"]
pages = {
 "tissuumaps": ("TissUUmaps server request log: GET of bm_demo_csc.h5ad (476 MB file)", tu, "tissuumaps/l01_lazy_request_log.jpg"),
 "vizit": ("VizIt hosted API calls on one Gene View load (path, response bytes)", [f"{a}    {b:,} bytes" for a, b in vz], "vizit/l01_lazy_request_log.jpg"),
}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    p = b.new_context(viewport={"width": 1400, "height": 900}).new_page()
    for tool, (title, lines, out) in pages.items():
        body = "".join(f"<div class='l'>{html.escape(x)}</div>" for x in lines[:40])
        p.set_content(f"<html><body style='font:13px Menlo,monospace;margin:20px'><h3 style='font-family:sans-serif'>{html.escape(title)}</h3>"
                      f"<p style='font-family:sans-serif;color:#555'>{len(lines)} lines; rendered from the raw log of the 2026-10-05 session (not the app's own UI)</p>{body}</body></html>")
        path = SCR / out; p.screenshot(path=str(path), type="jpeg", quality=80)
        record(p, str(path), tool=tool, software=f"{tool} request log (rendered)", by="comparison-auditor", driver=__file__, data=None, proves=[pv("lazy")], callouts=[(1, ".l >> nth=0", "first request")], url="about:blank")
        print(tool, len(lines))
    b.close()
