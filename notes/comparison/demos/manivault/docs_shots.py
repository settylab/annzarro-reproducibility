"""ManiVault docs screenshots for the desktop, hosted and static columns (documentation, not the app),
with DOM sidecars. Pages: the official macOS release page and the ManiVault Studio site."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import sys, time
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT = f"{_REPO}/notes/comparison/screens/manivault/"
SW = "ManiVault Studio docs (documentation pages, not the app)"
def pv(c, m, t): return {"column": c, "mark": m, "caption": t}
def snap(p, name, proves, callouts):
    path = OUT + name; p.screenshot(path=path, type="jpeg", quality=72)
    try: record(p, path, tool="manivault", software=SW, by="comparison-auditor", driver=__file__, data=None, proves=proves, callouts=callouts)
    except Exception as e:
        print("callout failed", str(e)[:120]); record(p, path, tool="manivault", software=SW, by="comparison-auditor", driver=__file__, data=None, proves=proves, callouts=[])
    print("shot", name, flush=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    p = b.new_context(viewport={"width": 1400, "height": 900}).new_page()
    p.goto("https://github.com/ManiVaultStudio/Releases/releases/tag/manivault_1.5.0_mac", timeout=60000); time.sleep(4)
    snap(p, "g01_desktop_DOCS_release_macos_installer.jpg", [pv("desktop", "Y", "Docs, not the app: the official ManiVault 1.5.0 macOS installer (dmg) on the project's releases page")],
         [(1, "text=manivault_1.5.0_mac.dmg", "macOS installer asset")])
    p.goto("https://www.manivault.studio/", timeout=60000); time.sleep(5)
    txt = p.inner_text("body"); print("site text:", txt[:600].replace("\n", " | "))
    snap(p, "g02_hosted_static_DOCS_site.jpg", [pv("hosted", "N", "Docs, not the app: ManiVault Studio is presented and distributed as a desktop application; no server or multi-user deployment is offered"),
                                                pv("static", "N", "Docs, not the app: no web or static-site export is offered")],
         [(1, "body", "ManiVault Studio site")])
    b.close()
