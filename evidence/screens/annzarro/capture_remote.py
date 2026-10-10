#!/usr/bin/env python
"""Visual proof for AnnZarro's `remote` mark on real cloud stores: s3:// and gs://, anonymous, read-only.

Shot 16 (capture.py) opened a store from an http:// URL on 127.0.0.1. This driver opens two PUBLIC
AnnData zarr stores the way a user does (Dataset picker -> type the URL -> Enter), adds a Cell Plot
(it defaults to obsm/X_umap) and sets its Color to one obs column through the plot's controls:

    22_remote_s3_store.png   s3://lamindata/.lamindb/CFcQxNjzSRzWZrVh.anndata.zarr
                             (LaminDB's public demo bucket on AWS S3; 46,086 cells, X CSC, obsm/X_umap)
    23_remote_gcs_store.png  gs://vitessce-demo-data/habib-2017/habib17.processed.h5ad.zarr
                             (Vitessce's public demo bucket on Google Cloud Storage; 13,067 cells)

Only the server's default policy is used: a loopback server with login off allows remote stores
(`remote_stores: auto`) with `remote_credentials: anonymous` (unsigned S3 requests, GCS token
'anon'); nothing is configured. Only the store's metadata, obs index, one obs column and X_umap are
read, a few MB in all.

    git -C <annzarro checkout> archive <ref> | tar -x -C $SCRATCH/annzarro_src
    uv venv $SCRATCH/.venv && uv pip install -p $SCRATCH/.venv/bin/python "$SCRATCH/annzarro_src[remote]"
    notes/comparison/demos/scale_probe/gap_run.sh <playwright python> evidence/screens/annzarro/capture_remote.py \
        --annzarro $SCRATCH/.venv/bin/annzarro --version 0.3.0 --sha <40-hex> --scratch $SCRATCH

The server binds 127.0.0.1:8930 (--port). Headless Chromium, 1400 x 900, deviceScaleFactor 1.
Boxes come from the DOM (evidence/tools/annotate.record via capture.rec).
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import traceback
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capture as C  # noqa: E402  (helpers: new_page, ready, shoot, rec, start, stop, wait_http)

C.BY = "evidence-curator"
C.DRIVER = "evidence/screens/annzarro/capture_remote.py"

STORES = [
    dict(shot="22_remote_s3_store", scheme="s3", url="s3://lamindata/.lamindb/CFcQxNjzSRzWZrVh.anndata.zarr",
         color="cell_type",
         data="s3://lamindata/.lamindb/CFcQxNjzSRzWZrVh.anndata.zarr (LaminDB public demo bucket on AWS S3, "
              "anonymous; AnnData zarr v2, 46,086 cells x 21,972 genes, X CSC, obsm/X_umap)",
         where="LaminDB's public demo bucket `lamindata` on AWS S3"),
    dict(shot="23_remote_gcs_store", scheme="gs", url="gs://vitessce-demo-data/habib-2017/habib17.processed.h5ad.zarr",
         color="CellType",
         data="gs://vitessce-demo-data/habib-2017/habib17.processed.h5ad.zarr (Vitessce public demo bucket on "
              "Google Cloud Storage, anonymous; AnnData zarr v2, 13,067 cells x 25,587 genes, obsm/X_umap)",
         where="Vitessce's public demo bucket `vitessce-demo-data` on Google Cloud Storage"),
]

PICKER = "#dataset-selector + .select2 .select2-selection"
LOG = C.LOG


def wait_counts(page, timeout=180):
    """Until the statistics bar shows numbers (the store's structure was read)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        cells = page.inner_text("#cell-count").strip()
        if re.fullmatch(r"[\d,]+", cells) and cells != "0":
            return cells
        time.sleep(0.5)
    raise RuntimeError(f"cell count still {page.inner_text('#cell-count')!r} after {timeout}s")


def open_by_picker(page, typed=None, option=None):
    """Open a dataset as a user does: click the Dataset picker, then type a URL + Enter or click an entry."""
    page.click(PICKER)
    page.wait_for_selector(".select2-container--open .select2-search__field", timeout=15000)
    if typed:
        page.fill(".select2-container--open .select2-search__field", typed)
        page.wait_for_selector(f'.select2-results__option:has-text("{typed}")', timeout=15000)
        page.keyboard.press("Enter")
    else:
        page.click(f'.select2-results__option:has-text("{option}")')
    return wait_counts(page)


def add_cell_plot_coloured_by(page, obs_column, timeout=180):
    """Welcome screen -> Cell Plot card (defaults to obsm/X_umap) -> Color = obs / <column> in its controls."""
    page.click('.tile-type-label:text-is("Cell Plot")')
    page.wait_for_selector('.tile[data-tile-id^="cell-plot"] .js-plotly-plot', timeout=timeout * 1000)
    C.ready(page, timeout=timeout)
    tid = page.get_attribute('.tile[data-tile-id^="cell-plot"]', "data-tile-id")
    typesel = C.tsel(tid, '.axis-type-select[data-axis="color"]')
    if not page.is_visible(typesel):
        page.click(C.tsel(tid, ".tile-toggle-controls"))
        page.wait_for_selector(typesel, state="visible", timeout=10000)
    page.select_option(typesel, "obs")
    keysel = C.tsel(tid, '.axis-key-select[data-axis="color"]')
    page.wait_for_function("""s => { const e = document.querySelector(s); return e && !e.disabled &&
                              [...e.options].length > 1; }""", arg=keysel, timeout=60000)
    # wait for this column's data, not just for quiet: on a remote store the recolour request can
    # start after the page looks settled (seen on v0.3.1 at S3 latency: legend title new, colours old)
    import urllib.parse
    with page.expect_response(lambda r: "/api/v1/data" in r.url and "obs" in r.url
                              and obs_column in urllib.parse.unquote(r.url), timeout=timeout * 1000):
        page.select_option(keysel, obs_column)
    time.sleep(1.0)
    C.ready(page, timeout=timeout)
    return tid


def axis_text(page, tid):
    return {a: C.selected(page, tid, a) for a in ("x", "y", "color")}


def s_store(browser, port, st):
    page = C.new_page(browser)
    page.goto(f"http://127.0.0.1:{port}/")
    page.wait_for_selector(PICKER, timeout=60000)
    t0 = time.time()
    cells = open_by_picker(page, typed=st["url"])
    t_open = time.time() - t0
    t1 = time.time()
    tid = add_cell_plot_coloured_by(page, st["color"])
    t_plot = time.time() - t1
    axes = axis_text(page, tid)
    npts = C.npoints(page, tid)
    shown = page.inner_text("#dataset-path").strip()
    picked = page.inner_text("#dataset-selector + .select2 .select2-selection__rendered").strip()
    data_calls = C.api_requests(page, 0)
    shot = C.shoot(page, st["shot"])
    scheme = {"s3": "s3:// (AWS S3, s3fs, unsigned requests)", "gs": "gs:// (Google Cloud Storage, gcsfs, token 'anon')"}[st["scheme"]]
    C.rec(page, shot, [
        ("remote", "Y", f"A public AnnData zarr store opened read-only and anonymously from {scheme}: "
                        f"{st['url']} ({st['where']}), typed into the Dataset picker; the UMAP is coloured by "
                        f"obs/{st['color']}, read from the bucket.")],
        [(1, "#dataset-selector >> xpath=..", f"Dataset picker: {picked}"),
         (2, "#dataset-stats", f"statistics bar: Cells {cells}, Genes {page.inner_text('#gene-count').strip()}, "
                               f"Dataset {shown}; structure read in {t_open:.1f} s"),
         (3, C.row(tid, "x"), f"X = {axes['x']}; Y = {axes['y']}"),
         (4, C.row(tid, "color"), f"Color = {axes['color']}"),
         (5, C.tsel(tid, ".js-plotly-plot"), f"{npts:,} cells drawn, {t_plot:.1f} s from adding the plot; "
                                              f"{len(data_calls)} /api/v1/data requests to the local server")],
        data=st["data"], url=page.url)
    LOG.append(f"{st['shot']}: open {t_open:.1f}s plot {t_plot:.1f}s cells={cells} npts={npts} axes={axes} calls={data_calls[:12]}")
    page.context.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--annzarro", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--port", type=int, default=8930)
    ap.add_argument("--only", choices=["s3", "gs"], default=None)
    a = ap.parse_args()
    scratch = a.scratch.resolve()
    data = scratch / "remote_data"           # empty: every store here is remote
    data.mkdir(parents=True, exist_ok=True)
    (scratch / "home").mkdir(exist_ok=True)
    C.A = SimpleNamespace(scratch=scratch, datadir=data,
                          software=f"AnnZarro {a.version} (settylab/annzarro@{a.sha[:7]}, "
                                   f"pip install '[remote]' from that commit)")
    log = scratch / "server_remote.log"
    srv = C.start([a.annzarro, "start", "--host", "127.0.0.1", "--port", str(a.port), "--data-dir", str(data),
                   "--no-browser"], log, C.annzarro_env())
    t0 = time.time()
    try:
        C.wait_http(f"http://127.0.0.1:{a.port}/", srv, "annzarro")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                for st in STORES:
                    if a.only and st["scheme"] != a.only:
                        continue
                    try:
                        s_store(browser, a.port, st)
                    except Exception:
                        LOG.append(f"FAILED {st['shot']}:\n{traceback.format_exc()}")
            finally:
                browser.close()
    finally:
        C.stop(srv)
    policy = [ln for ln in log.read_text().splitlines() if "Remote store policy" in ln]
    LOG.append(f"server policy line: {policy[:1]}")
    LOG.append(f"done in {time.time() - t0:.0f}s")
    (scratch / "capture_remote.log").write_text("\n".join(LOG) + "\n")
    print("\n".join(LOG))


if __name__ == "__main__":
    main()
