#!/usr/bin/env python
"""First focus-by-name after opening every cell of a large store.

Opens the large-plot view (every cell, coloured by --cat), waits until it is
drawn, waits until --after seconds after navigation, then types a cell name
into the header's Focused Cell picker and times how long until the picker
lists it. The client (since #62 9cc9487) asks the server to build its name
index in the background once the plot is drawn; --no-prewarm blocks that
request (page.route) to measure the cold lookup instead. Server RSS is sampled
throughout (peak before the lookup and after it).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

from ceiling import HERE, Server, Sampler, STATE_JS, link, view, n_cells, VIEW


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("store")
    ap.add_argument("--exe", required=True)
    ap.add_argument("--emb", default="X_pca_2d")
    ap.add_argument("--cat", default="cell_line_id")
    ap.add_argument("--after", type=float, default=30)
    ap.add_argument("--row", type=int, default=12345678)
    ap.add_argument("--no-prewarm", action="store_true")
    ap.add_argument("--port", type=int, default=8966)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    VIEW.update(emb=a.emb, cat=a.cat, genes=["MALAT1"], subset=None, point_size=None, opacity=None)
    n = n_cells(a.store)
    srv = Server(a.exe, str(Path(a.store).parent), a.port, HERE / "home" / f"p{a.port}")
    try:
        name = requests.get(f"{srv.root}/api/v1/data/obs", params={"dataset_path": a.store, "columns": "_index",
                                                                   "rows": str(a.row)}).json()["data"]["_index"][0]
        rss0 = srv.rss()
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chromium")
            smp = Sampler(srv, 25)
            smp.start()
            page = b.new_page(viewport={"width": 1400, "height": 1000})
            names_reqs = []
            page.on("request", lambda r: names_reqs.append((time.perf_counter(), r.url)) if "/data/names" in r.url else None)
            if a.no_prewarm:
                page.route("**/data/names?*q=&*", lambda r: r.abort())
            t0 = time.perf_counter()
            page.goto(link(srv.root, a.store, view("cat")), timeout=600000)
            while page.evaluate(STATE_JS)["n"] < n:
                time.sleep(0.2)
            drawn = time.perf_counter() - t0
            rss_drawn = srv.rss()
            while time.perf_counter() - t0 < a.after:
                time.sleep(0.5)
            rss_before = srv.peak
            box = page.locator("#focused-cell")
            box.click()
            t1 = time.perf_counter()
            box.fill(name)
            page.wait_for_selector(f".name-picker-option:has-text('{name}')", timeout=600000)
            lookup = time.perf_counter() - t1
            time.sleep(10)
            rss_now = srv.rss()
            rec = dict(server_rss_10s_after_lookup=rss_now, store=Path(a.store).name, n=n, prewarm=not a.no_prewarm, plot_drawn_s=round(drawn, 2),
                       lookup_at_s=round(t1 - t0, 1), lookup_s=round(lookup, 2), name=name,
                       server_rss_idle=rss0, server_rss_drawn=rss_drawn, server_rss_peak_before_lookup=rss_before,
                       server_rss_peak_after=max(srv.peak, smp.server.peak),
                       names_requests=[(round(t - t0, 2), u.split("/api/v1/")[1][:120]) for t, u in names_reqs],
                       browser=b.version)
            smp.running = False
            print(json.dumps(rec), flush=True)
            with open(a.out, "a") as f:
                f.write(json.dumps(rec) + "\n")
            b.close()
    finally:
        srv.stop()


if __name__ == "__main__":
    main()
