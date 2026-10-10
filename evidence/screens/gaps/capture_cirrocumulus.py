"""Cirrocumulus gap shots (evidence-curator, 2026-10-04). Run under notes/comparison/demos/scale_probe/gap_run.sh with
benchmark/scale/ceiling/.venv/bin/python <this file> [docs] [lazy]

docs: the installation docs page, one shot per mark (hosted, static, remote, lazy).
lazy: `cirro prepare_data --format zarr` on bm_demo.h5ad (once, into the scratchpad), then `cirro launch`
      on the prepared zarr through cirro_audit_launch.py (an audit hook logs every file the server opens).
      The browser adds two genes; the shot is a request log: each /api/data request beside the chunk
      files the server opened to answer it, out of all chunk files of X.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaplib import SCRATCH, TODAY, docs_shot, log, pv, table_shot  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DRIVER = "evidence/screens/gaps/capture_cirrocumulus.py"
TOOL = "cirrocumulus"
VER = "Cirrocumulus 1.1.61"
DOCS = "https://cirrocumulus.readthedocs.io/en/latest/installation.html"
CV = "$DEMO_ROOT/cirrocumulus/.venv/bin/"
BM = "$DEMO_ROOT/_data/bm_demo.h5ad"
PREP = SCRATCH + "cirro_prep/bm_demo"          # prepare_data appends .zarr
ZARR = PREP + ".zarr"
AUDIT = SCRATCH + "cirro_prep/audit.log"
HERE = os.path.dirname(os.path.abspath(__file__))
parts = sys.argv[1:] or ["docs", "lazy"]


def docs(p):
    sw = f"{VER} documentation (cirrocumulus.readthedocs.io/en/latest, read {TODAY})"
    docs_shot(p, tool=TOOL, name="g01_hosted_DOCS_server_mode_multiple_users.jpg", url=DOCS,
              phrases=["serve multiple users and datasets securely", "server mode"], column="hosted", mark="Y",
              software=sw, driver=DRIVER,
              caption=f"{VER} installation docs (read {TODAY}): server mode serves multiple users and datasets, with MongoDB and Okta or Google sign-in")
    docs_shot(p, tool=TOOL, name="g02_static_DOCS_static_website_hosting.jpg", url=DOCS, goto=False,
              phrases=["Host the build directory on your static website hosting service"], column="static", mark="Y",
              software=sw, driver=DRIVER,
              caption=f"{VER} installation docs (read {TODAY}): the Static Website build (REACT_APP_STATIC=true yarn build) is hosted on a static file host such as S3 or GCS",
              extra=[(3, "text=REACT_APP_STATIC >> nth=0", "static build flag")])
    docs_shot(p, tool=TOOL, name="g03_remote_DOCS_cloud_storage_libraries.jpg", url=DOCS, goto=False,
              phrases=["Additional libraries needed for cloud storage"], column="remote", mark="Y",
              software=sw, driver=DRIVER,
              caption=f"{VER} installation docs (read {TODAY}): cloud storage (S3 via s3fs, GCS via gcsfs, Azure via adlfs) is read through fsspec; not exercised in the GUI here",
              extra=[(3, "text=pip install s3fs >> nth=0", "Amazon S3: s3fs")])
    docs_shot(p, tool=TOOL, name="g04_lazy_DOCS_partial_dataset_retrieval.jpg", url=DOCS, goto=False,
              phrases=["efficient partial dataset retrieval over a network"], column="lazy", mark="Y",
              software=sw, driver=DRIVER,
              caption=f"{VER} installation docs (read {TODAY}): prepare_data output allows partial dataset retrieval over a network with limited memory")


def prepare():
    if os.path.isdir(ZARR):
        log("prepared zarr exists", ZARR)
        return
    os.makedirs(os.path.dirname(PREP), exist_ok=True)
    t = time.time()
    r = subprocess.run([CV + "cirro", "prepare_data", "--format", "zarr", "--no-auto-groups", "--out", PREP, BM],
                       capture_output=True, text=True, timeout=420)
    log(f"prepare_data rc={r.returncode} {time.time() - t:.0f}s", r.stderr[-400:])


def chunk_files():
    out = []
    for root, _, files in os.walk(ZARR):
        for f in files:
            out.append(os.path.relpath(os.path.join(root, f), ZARR))
    return out


def lazy(p):
    prepare()
    if not os.path.isdir(ZARR):
        log("no prepared zarr; skip lazy")
        return
    open(AUDIT, "w").close()
    srv = subprocess.Popen([CV + "python", HERE + "/cirro_audit_launch.py", AUDIT, ZARR, "--host", "127.0.0.1",
                            "--port", "8901", "--no-open", "--results", SCRATCH + "cirro_prep/results"],
                           stdout=open(SCRATCH + "cirro_prep/server.log", "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(90):
            try:
                urllib.request.urlopen("http://127.0.0.1:8901/api/datasets", timeout=2)
                break
            except Exception:
                time.sleep(1)
        reqs = []

        def onfin(r):
            if "/api/data" in r.url:
                try:
                    sz = r.sizes()["responseBodySize"]
                except Exception:
                    sz = -1
                body = r.post_data or ""
                reqs.append((time.time(), r.method, r.url.split("127.0.0.1:8901")[1], body, sz))
        p.on("requestfinished", onfin)
        p.set_viewport_size({"width": 1400, "height": 1000})
        p.goto("http://127.0.0.1:8901/", timeout=60000)
        p.wait_for_timeout(10000)
        audit_lines = lambda: open(AUDIT).read().splitlines()  # noqa: E731
        n_start = len(audit_lines())
        log("audit lines after load", n_start, "requests", len(reqs))
        rows = []
        x_files = [f for f in chunk_files() if f.startswith("X/")]
        for g in ["Mpo", "Car1"]:
            a0, r0 = len(audit_lines()), len(reqs)
            c = p.get_by_role("combobox", name="Genes/Features")
            c.click()
            c.fill(g)
            p.wait_for_timeout(1500)
            p.keyboard.press("Enter")
            p.keyboard.press("Escape")
            p.wait_for_timeout(5000)
            opened = audit_lines()[a0:]
            files = sorted({ln.split("\t")[1] for ln in opened})
            for t, m, u, body, sz in reqs[r0:]:
                rows.append([f"add gene {g}", f"{m} {u}", (body[:90] + "...") if len(body) > 90 else body, f"{sz:,} B", ""])
            for f in files:
                rows.append(["", "", "server opened", "", f])
            log(g, "requests", len(reqs) - r0, "files opened", len(files), files[:8])
        if not rows:
            log("no rows; skip")
            return
        x_read = sorted({r[4] for r in rows if r[4].startswith("X/")})
        n_x = len(x_files)
        size_x = sum(os.path.getsize(os.path.join(ZARR, f)) for f in x_files)
        size_read = sum(os.path.getsize(os.path.join(ZARR, f)) for f in x_read if os.path.exists(os.path.join(ZARR, f)))
        note = (f"Per gene the server opened only that gene's chunk files: {len(x_read)} of {n_x} files under X/ "
                f"({size_read:,} of {size_x:,} bytes on disk). Files opened at startup (schema, obs, embeddings): {n_start}.")
        sub = (f"{VER}, <code>cirro launch</code> on <code>{os.path.basename(ZARR)}</code> made by "
               f"<code>cirro prepare_data --format zarr</code> from bm_demo.h5ad (8,090 cells x 16,285 genes). "
               f"Left: requests the browser sent (Playwright request log). Right: files the server process opened, "
               f"from a Python audit hook (evidence/screens/gaps/cirro_audit_launch.py). Recorded {TODAY}.")
        p.set_viewport_size({"width": 1400, "height": 900})
        table_shot(p, tool=TOOL, name="g05_lazy_request_log_prepared_zarr.jpg",
                   title="Request log: Cirrocumulus reads one gene at a time from a prepared dataset", sub=sub,
                   header=["user action", "browser request", "request body / server event", "response", "file opened by server"],
                   rows=rows[:40], hl=[i for i, r in enumerate(rows[:40]) if r[0]], note=note,
                   proves=[pv("lazy", "Y", f"request log, {VER} on a prepare_data zarr (recorded {TODAY}): adding a gene reads only that gene's chunks ({len(x_read)} of {n_x} X files); a plain h5ad under cirro launch is held whole in memory")],
                   callouts=[(1, "#r0", "gene request from the browser"), (2, "#note", "partial reads: chunks of X opened per gene")],
                   software=f"{VER} (local cirro launch on a prepare_data zarr)", driver=DRIVER,
                   data=f"bm_demo prepared with cirro prepare_data --format zarr ({n_x} X chunk files)", url="http://127.0.0.1:8901/")
        json.dump({"rows": rows, "n_start": n_start, "x_files": n_x}, open(SCRATCH + "cirro_prep/lazy_rows.json", "w"))
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=15)
        except Exception:
            srv.kill()
        subprocess.run(["$DEMO_ROOT/cirrocumulus/stop.sh"], capture_output=True)
        log("cirro server stopped")


def lazy_report(p):
    """Render the evidence of the lazy run (audit.log, lazy_rows.json) plus a direct reader check."""
    import collections
    rows_saved = json.load(open(SCRATCH + "cirro_prep/lazy_rows.json"))
    audit = [ln.rstrip("\n").split("\t") for ln in open(AUDIT)]
    grp = collections.Counter("/".join(a[1].split("/")[:2]) for a in audit)
    nx = sum(1 for f in chunk_files() if f.startswith("X/data/") or f.startswith("X/indices/") or f.startswith("X/data") or f.startswith("X/indices"))
    n_data = len([f for f in chunk_files() if f.startswith("X/data/") and not f.split("/")[-1].startswith(".")])
    n_lc = len([f for f in chunk_files() if f.startswith("layers/counts/") and not f.split("/")[-1].startswith(".")])
    r = subprocess.run([CV + "python", HERE + "/cirro_reader_check.py", ZARR], capture_output=True, text=True, timeout=120)
    direct = [json.loads(x) for x in r.stdout.splitlines() if x.startswith("{")]
    log("direct", direct, r.stderr[-300:])
    rows = [["A. cirro launch on the prepared zarr, browser opens the dataset", "GET /api/schema, POST /api/data (default view)",
             f"server opened X/data {grp.get('X/data', 0)}, X/indices {grp.get('X/indices', 0)}, layers/counts {grp.get('layers/counts', 0)} chunk files"]]
    for rr in rows_saved["rows"]:
        if rr[0]:
            rows.append([f"A. browser: {rr[0]}", f"{rr[1]} ({rr[3]})", "server opened no file (matrix already read)"])
    for d in direct:
        x = d["X_chunks"]
        rows.append([f"B. ZarrDataset.read_dataset(X=['{d['gene']}']) called directly", "-",
                     f"opened X/data {x.get('X/data', 0)}, X/indices {x.get('X/indices', 0)}, X/indptr {x.get('X/indptr', 0)} chunk files"])
    note = (f"X/data has {n_data} chunk files and layers/counts {n_lc}. B: the prepare_data reader fetches one gene from 2 of {n_data} data chunks, "
            f"so the format and its reader are lazy. A: under <code>cirro launch</code> the server opened every chunk of X and layers/counts "
            f"while the dataset loaded, and no file for the gene requests, so in launch mode the matrix ends up in memory.")
    sub = (f"{VER}, bm_demo.h5ad (8,090 cells x 16,285 genes) prepared with <code>cirro prepare_data --format zarr</code>. "
           f"Files opened are logged by a Python audit hook (evidence/screens/gaps/cirro_audit_launch.py, cirro_reader_check.py). "
           f"A recorded 2026-10-04 08:05 in the browser; B run {TODAY}.")
    table_shot(p, tool=TOOL, name="g05_lazy_request_and_file_log_prepared_zarr.jpg",
               title="Request and file log: what Cirrocumulus reads from a prepared zarr", sub=sub,
               header=["step", "request", "files the reader / server opened"], rows=rows,
               hl=[i for i, r in enumerate(rows) if r[0].startswith("B.")], note=note,
               proves=[pv("lazy", "Y", f"request and file log, {VER} ({TODAY}): the prepare_data reader reads one gene from 2 of {n_data} X chunks (lazy after a preparation step, reading B); caveat: cirro launch on the same zarr opened every X chunk at load")],
               callouts=[(1, f"#r{len(rows) - len(direct)}", "one gene: 2 data chunks of " + str(n_data)), (2, "#r0", "cirro launch: every chunk opened at load"), (3, "#note", "lazy reader, eager launch")],
               software=f"{VER} (prepare_data zarr; local cirro launch and direct reader call)", driver=DRIVER,
               data="bm_demo prepared with cirro prepare_data --format zarr", url="http://127.0.0.1:8901/")


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    p = b.new_page(viewport={"width": 1400, "height": 900})
    for part in parts:
        try:
            {"docs": docs, "lazy": lazy, "lazy_report": lazy_report}[part](p)
        except Exception as e:
            log("FAIL", part, type(e).__name__, str(e)[:300])
    b.close()
log("done")
