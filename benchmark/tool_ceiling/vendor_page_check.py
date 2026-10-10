#!/usr/bin/env python
"""What the browser actually loaded from static/vendor, against the release's pins.

Starts the given AnnZarro build on a scratch port, opens the app in Chromium, and checks
two things against WORKTREE/scripts/vendor-assets.json:
  1. every /static/vendor/ file the page fetched: its sha256 equals the pinned one, and the
     file is listed in the manifest;
  2. the runtime versions the libraries report (Plotly.version, jQuery.fn.jquery, ...) equal
     the manifest's component versions.
Prints a JSON report; exits 1 on any mismatch, unlisted file or missing library.

Usage: vendor_page_check.py EXE WORKTREE [--port 8951] [--out report.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

RUNTIME = {  # component name in the manifest -> JS expression for the version the library reports
    "Plotly.js": "window.Plotly && Plotly.version",
    "jQuery": "window.jQuery && jQuery.fn.jquery",
    "Bootstrap": "window.bootstrap && bootstrap.Tooltip && bootstrap.Tooltip.VERSION",
    "DataTables": "window.jQuery && jQuery.fn.dataTable && jQuery.fn.dataTable.version",
    "DataTables Buttons": "window.jQuery && jQuery.fn.dataTable && jQuery.fn.dataTable.Buttons && jQuery.fn.dataTable.Buttons.version",
    "DataTables SearchBuilder": "window.jQuery && jQuery.fn.dataTable && jQuery.fn.dataTable.SearchBuilder && jQuery.fn.dataTable.SearchBuilder.version",
    "DataTables Select": "window.jQuery && jQuery.fn.dataTable && jQuery.fn.dataTable.select && jQuery.fn.dataTable.select.version",
    "DataTables FixedHeader": "window.jQuery && jQuery.fn.dataTable && jQuery.fn.dataTable.FixedHeader && jQuery.fn.dataTable.FixedHeader.version",
    "chroma.js": "window.chroma && chroma.version",
    "Select2": "window.jQuery && jQuery.fn.select2 ? 'loaded' : null",  # Select2 exposes no version
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("worktree")
    ap.add_argument("--port", type=int, default=8951)
    ap.add_argument("--out")
    a = ap.parse_args()
    wt = Path(a.worktree)
    man = json.loads((wt / "scripts/vendor-assets.json").read_text())
    pinned = {f["path"]: (c["name"], f["sha256"]) for c in man["components"] for f in c["files"]}
    versions = {c["name"]: c["version"] for c in man["components"]}

    home = Path(tempfile.mkdtemp(prefix="vendorcheck_"))
    data = home / "data"
    data.mkdir()
    env = dict(os.environ, ANNZARRO_HOME=str(home), ANNZARRO_HEADLESS="1")
    srv = subprocess.Popen([a.exe, "start", "--host", "127.0.0.1", "--port", str(a.port), "--data-dir", str(data),
                            "--no-browser", "--auth-disabled"], env=env, cwd=home,
                           stdout=open(home / "server.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    root = f"http://127.0.0.1:{a.port}"
    try:
        for _ in range(120):
            try:
                if requests.get(root + "/api/v1/config", timeout=2).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.5)
        else:
            sys.exit("server did not come up (see %s)" % (home / "server.log"))
        fetched = {}
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chromium")
            pg = b.new_page()

            def on_resp(r):
                u = r.url
                if "/static/vendor/" in u:
                    rel = u.split("/static/vendor/", 1)[1].split("?")[0]
                    try:
                        fetched[rel] = (r.status, hashlib.sha256(r.body()).hexdigest())
                    except Exception as e:  # redirects and the like have no body
                        fetched[rel] = (r.status, f"no body: {type(e).__name__}")
            pg.on("response", on_resp)
            pg.goto(root + "/", wait_until="networkidle", timeout=120000)
            runtime = {name: pg.evaluate(f"() => {{ try {{ return {expr} || null; }} catch (e) {{ return null; }} }}")
                       for name, expr in RUNTIME.items()}
            b.close()
    finally:
        os.killpg(srv.pid, 15)

    files = []
    for rel, (status, sha) in sorted(fetched.items()):
        pin = pinned.get(rel)
        files.append({"path": rel, "status": status, "component": pin[0] if pin else None,
                      "ok": bool(pin) and status == 200 and sha == pin[1], "listed": bool(pin)})
    libs = []
    for name, got in runtime.items():
        want = versions.get(name)
        ok = got == "loaded" if name == "Select2" else (got is not None and want is not None and str(got) == want)
        libs.append({"component": name, "pinned": want, "runtime": got, "ok": ok})
    rep = {"exe": a.exe, "worktree": str(wt),
           "rev": subprocess.run(["git", "-C", str(wt), "rev-parse", "--short", "HEAD"], capture_output=True,
                                 text=True).stdout.strip(),
           "files_fetched": len(files), "files_ok": sum(f["ok"] for f in files), "files": files, "libraries": libs,
           "ok": bool(files) and all(f["ok"] for f in files) and all(x["ok"] for x in libs)}
    text = json.dumps(rep, indent=1)
    if a.out:
        Path(a.out).write_text(text)
    print(text)
    sys.exit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
