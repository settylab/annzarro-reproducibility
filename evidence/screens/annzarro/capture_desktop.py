#!/usr/bin/env python
"""Visual proof for AnnZarro's `desktop` mark: the released macOS app, launched and used.

Downloads nothing itself. Give it the unpacked release app (e.g. AnnZarro-0.3.0-macos-arm64.zip from
https://github.com/settylab/annzarro/releases, `ditto -x -k` into a scratch dir; not installed into
/Applications). It launches the app's own executable with Chromium's --remote-debugging-port so
Playwright can attach to the Electron window over CDP, then does what a user does:

  1. waits for the app's window to load the UI from the app's bundled server (no server set up by us);
  2. opens the Dataset picker and clicks bm_aging_showcase (a link to this repo's data/ store, placed in
     the app's data directory `<data dir>/datasets/`);
  3. clicks the Cell Plot card (defaults to obsm/X_umap) and sets Color = obs / highres_celltype;
  4. screenshots the window's page, with DOM boxes (evidence/tools/annotate.record), as
     24_desktop_app_showcase.png;
  5. closes the window (the app quits and stops its server).

The app's data directory and profile are redirected into the scratch dir with the app's own
environment hooks (ANNZARRO_DESKTOP_DATA_DIR, ANNZARRO_DESKTOP_USER_DATA, read by main.js), so the
user's ~/annzarro-data and app profile are not touched.

    notes/comparison/demos/scale_probe/gap_run.sh <playwright python> evidence/screens/annzarro/capture_desktop.py \
        --app $SCRATCH/app/AnnZarro.app --asset AnnZarro-0.3.0-macos-arm64.zip --sha256 <hex> --scratch $SCRATCH
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import capture as C  # noqa: E402
import capture_remote as R  # noqa: E402  (open_by_picker, add_cell_plot_coloured_by, axis_text)

C.BY = "evidence-curator"
C.DRIVER = "evidence/screens/annzarro/capture_desktop.py"
LOG = C.LOG
SHOT = "24_desktop_app_showcase"


def wait_cdp(port, proc, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2))
        except Exception:
            if proc.poll() is not None:
                sys.exit(f"app exited with {proc.returncode}")
            time.sleep(0.5)
    sys.exit("no CDP endpoint: the app did not accept --remote-debugging-port")


def app_page(p, endpoint, timeout=240):
    """(browser, page) once a window shows the AnnZarro UI (the bundled server is up).

    The app first shows loading.html, then navigates. A CDP connection made during the loading
    page did not see the navigation (2026-10-04: still loading.html after 240 s while the app
    log said "Interface loaded"), so reconnect every few seconds and ask each page for its
    location instead of trusting the cached URL."""
    t0, last = time.time(), []
    while time.time() - t0 < timeout:
        browser = p.chromium.connect_over_cdp(endpoint)
        last = []
        for ctx in browser.contexts:
            for pg in ctx.pages:
                try:
                    href = pg.evaluate("location.href")
                    last.append(href)
                    if href.startswith("http://127.0.0.1:") and pg.query_selector("#dataset-selector"):
                        return browser, pg
                except Exception as e:
                    last.append(f"{pg.url} ({type(e).__name__})")
        browser.close()
        time.sleep(4)
    raise RuntimeError(f"no UI page after {timeout}s: {last}")


def shoot_tall(page, name):
    """Whole window content with the plot in frame. The first capture (2026-10-04 09:00) cut the
    plot off below the panel controls: grow the window over CDP (macOS may clamp it to the
    screen), then take a full-page shot from scroll 0, so DOM boxes keep their coordinates."""
    try:
        cdp = page.context.new_cdp_session(page)
        win = cdp.send("Browser.getWindowForTarget")
        cdp.send("Browser.setWindowBounds", {"windowId": win["windowId"],
                                             "bounds": {"width": 1400, "height": 1800, "windowState": "normal"}})
        time.sleep(1.5)
    except Exception as e:
        LOG.append(f"setWindowBounds failed: {e}")
    page.evaluate("window.scrollTo(0, 0)")
    page.add_style_tag(content=C.CLEAN_CSS)
    time.sleep(0.5)
    path = C.OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return path


def instrument(page):
    page._inflight, page._requests = set(), []
    page.on("request", lambda r: (page._inflight.add(r), page._requests.append(r.url)))
    page.on("requestfinished", lambda r: page._inflight.discard(r))
    page.on("requestfailed", lambda r: page._inflight.discard(r))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", type=Path, required=True, help="the unpacked AnnZarro.app")
    ap.add_argument("--asset", required=True, help="release asset name it came from")
    ap.add_argument("--sha256", required=True, help="sha256 of that asset")
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--data", type=Path, default=REPO / "data")
    ap.add_argument("--cdp-port", type=int, default=9229)
    a = ap.parse_args()
    scratch = a.scratch.resolve()
    ddir, prof = scratch / "desktop_data", scratch / "desktop_profile"
    (ddir / "datasets").mkdir(parents=True, exist_ok=True)
    link = ddir / "datasets" / C.SHOWCASE
    if not link.exists():
        link.symlink_to((a.data / C.SHOWCASE).resolve())
    exe = a.app / "Contents/MacOS/AnnZarro"
    plist = a.app / "Contents/Info.plist"
    version = subprocess.run(["/usr/libexec/PlistBuddy", "-c", "Print :CFBundleShortVersionString", str(plist)],
                             capture_output=True, text=True).stdout.strip()
    C.A = SimpleNamespace(scratch=scratch, datadir=ddir / "datasets",
                          software=f"AnnZarro {version} desktop app (macOS arm64, Electron); release asset "
                                   f"{a.asset}, sha256 {a.sha256}; run unpacked from a scratch dir")
    env = {**os.environ, "ANNZARRO_DESKTOP_DATA_DIR": str(ddir), "ANNZARRO_DESKTOP_USER_DATA": str(prof)}
    proc = subprocess.Popen([str(exe), f"--remote-debugging-port={a.cdp_port}"], env=env,
                            stdout=open(scratch / "desktop_app.log", "w"), stderr=subprocess.STDOUT,
                            start_new_session=True)
    t0 = time.time()
    try:
        ver = wait_cdp(a.cdp_port, proc)
        LOG.append(f"CDP up after {time.time() - t0:.1f}s: {ver.get('Browser')} {ver.get('User-Agent')}")
        with sync_playwright() as p:
            browser, page = app_page(p, f"http://127.0.0.1:{a.cdp_port}")
            instrument(page)
            LOG.append(f"UI up after {time.time() - t0:.1f}s at {page.url}")
            page.wait_for_selector(R.PICKER, timeout=60000)
            time.sleep(1.0)
            info = page.evaluate("() => window.api ? window.api.getAppInfo() : null")
            ua = page.evaluate("navigator.userAgent")
            title = page.title()
            LOG.append(f"appInfo={info} ua={ua} title={title!r}")
            try:
                cells = R.open_by_picker(page, option="bm_aging_showcase")
                tid = R.add_cell_plot_coloured_by(page, "highres_celltype")
                axes = R.axis_text(page, tid)
                npts = C.npoints(page, tid)
                shot = shoot_tall(page, SHOT)
                electron = next((t for t in ua.split() if t.startswith("Electron/")), "Electron/?")
                appver = next((t for t in ua.split() if t.lower().startswith("annzarro")), f"AnnZarro/{version}")
                # the bundle-relative path only: where the app was unpacked is a local detail
                srv_cmd = re.sub(r"^.*/(?=[^/]+\.app/)", "", str(info.get("serverCommand", ""))) if info else "?"
                C.rec(page, shot, [
                    ("desktop", "Y", f"AnnZarro {version} desktop app (macOS) showing the 8,090-cell demo, "
                                     "no server set up by the user. The released app, launched from its bundle, "
                                     "started its own server; the store was picked in its Dataset menu and plotted.")],
                    [(1, ".app-title", f"window page of the Electron app: {appver} {electron}; "
                                       f"isPackaged={info.get('isPackaged') if info else '?'}"),
                     (2, "#dataset-selector >> xpath=..", "Dataset picker: bm_aging_showcase, clicked in the list "
                                                          "of the app's data directory"),
                     (3, "#dataset-stats", f"Cells {cells}, Genes {page.inner_text('#gene-count').strip()}; served by "
                                           f"the app's bundled server {srv_cmd} at {info.get('serverUrl') if info else page.url}"),
                     (4, C.row(tid, "color"), f"X = {axes['x']}; Y = {axes['y']}; Color = {axes['color']}"),
                     (5, C.tsel(tid, ".js-plotly-plot"), f"{npts:,} cells drawn")],
                    data=C.DATA_LABEL, url=page.url)
            except Exception:
                LOG.append(f"FAILED desktop flow:\n{traceback.format_exc()}")
                page.screenshot(path=str(scratch / "desktop_failure.png"))
            # quit the way a user does: closing the only window quits the app (main.js window-all-closed)
            try:
                page.evaluate("window.close()")
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
        for _ in range(30):
            if proc.poll() is not None:
                break
            time.sleep(0.5)
        LOG.append(f"app exit code after window close: {proc.poll()}")
    finally:
        if proc.poll() is None:
            LOG.append("app still running: SIGTERM")
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except Exception:
                os.killpg(proc.pid, signal.SIGKILL)
        left = subprocess.run(["pgrep", "-f", str(a.app)], capture_output=True, text=True).stdout.split()
        if left:
            LOG.append(f"leftover processes {left}: killed")
            for pid in left:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except Exception:
                    pass
    LOG.append(f"done in {time.time() - t0:.0f}s")
    (scratch / "capture_desktop.log").write_text("\n".join(LOG) + "\n")
    print("\n".join(LOG))


if __name__ == "__main__":
    main()
