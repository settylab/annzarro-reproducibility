#!/usr/bin/env python
"""Screenshots of one Cell Plot on a Tahoe store, every cell or a subset.

For figures/scale/: headless Chromium (new headless, GPU), viewport
1600x1000 at device scale factor 2, Plotly's modebar hidden. Per shot two
PNGs: the plot alone (<name>.png) and the whole panel with its notice
(<name>_panel.png), plus <name>.view.json (the deep-link view) and one
commands.txt line with the exact command. Shots:

  all_cat     every cell, coloured by --cat
  all_gene    every cell, coloured by the first --genes
  all_zoom    the all_cat view zoomed to --zoom-box (x0,x1,y0,y1 in data units)
  sub_cat     the server's default subset (no subset in the link), by --cat
  sub_gene    the same subset, by the gene

A viewport2D in --panel-extra opens the plot already zoomed; --constants-extra
adds view constants (e.g. focusedCell). Each view.json records the drawn axis
ranges, the marker size and opacity drawn, and whether a focused-cell trace was drawn.

Uses ceiling.py's server, deep link and readiness check. Point size and
opacity are the app's defaults unless --point-size / --opacity are given.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import ceiling
from ceiling import HERE, Server, STATE_JS, envcapture, link, view, n_cells, ABSENT, VIEW

DRAWN_JS = """() => {
  const g = document.querySelector('.tile[data-tile-id="cell-plot-A"] .js-plotly-plot');
  const L = g._fullLayout, d = g._fullData;
  const pts = d.filter(t => t.name !== 'Focused Cell' && !(t.marker && t.marker.showscale && t.x && t.x.length === 1));
  const m = pts.length ? pts[0].marker || {} : {};
  const f = d.filter(t => t.name === 'Focused Cell');
  return {range_xy: [...L.xaxis.range, ...L.yaxis.range], marker_size: m.size === undefined ? null : (Array.isArray(m.size) ? m.size[0] : m.size),
          opacity: m.opacity === undefined ? null : (Array.isArray(m.opacity) ? m.opacity[0] : m.opacity),
          trace_opacity: pts.length ? (pts[0].opacity ?? null) : null, traces: d.length,
          focus_traces: f.map(t => ({n: t.x ? t.x.length : 0, x: t.x ? Array.from(t.x).slice(0, 2) : null, y: t.y ? Array.from(t.y).slice(0, 2) : null}))};
}"""

HIDE = """.modebar-container, .modebar { display: none !important; }
#notification-container, .notification { display: none !important; }"""


def ready(page, n, limit=1800):
    t0 = time.time()
    while time.time() - t0 < limit:
        st = page.evaluate(STATE_JS)
        if st["n"] >= n and st["busy"] == 0:
            time.sleep(2)
            return time.time() - t0
        time.sleep(0.5)
    raise SystemExit(f"not ready after {limit}s: {st}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("store")
    ap.add_argument("--exe", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--emb", default="X_pca_2d")
    ap.add_argument("--cat", default="cell_line_id")
    ap.add_argument("--genes", required=True)
    ap.add_argument("--zoom-box", default="", help="x0,x1,y0,y1; default: 1/100 of each range at the centre")
    ap.add_argument("--point-size", default="default")
    ap.add_argument("--opacity", default="default")
    ap.add_argument("--panel-extra", default="{}", help="JSON merged into the panel config")
    ap.add_argument("--constants-extra", default="{}", help="JSON merged into the view constants")
    ap.add_argument("--shots", default="all_cat,all_gene,all_zoom,sub_cat,sub_gene")
    ap.add_argument("--port", type=int, default=8965)
    a = ap.parse_args()
    envcapture.require_clean_bench()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "commands.txt", "a") as f:
        f.write(" ".join(shlex.quote(x) for x in [sys.executable, *sys.argv]) + "\n")
    VIEW.update(emb=a.emb, cat=a.cat, genes=a.genes.split(","),
                point_size=None if a.point_size == "default" else float(a.point_size),
                opacity=None if a.opacity == "default" else float(a.opacity),
                panel_extra=json.loads(a.panel_extra))
    n_all = n_cells(a.store)
    srv = Server(a.exe, str(Path(a.store).parent), a.port, HERE / "home" / f"p{a.port}")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chromium", args=["--enable-precise-memory-info"])
            envcapture.record(out / f"{a.prefix}.view.json", exe=a.exe, server_root=srv.root,
                              browser={"channel": "chromium", "version": b.version,
                                       "flags": ["--enable-precise-memory-info"], "headless": True},
                              store=a.store, shots=a.shots)
            for shot in a.shots.split(","):
                every = shot.startswith("all")
                VIEW["subset"] = None if every else ABSENT
                colour = "gene" if shot.endswith("gene") else "cat"
                v = view(colour)
                v["constants"].update(json.loads(a.constants_extra))
                ctx = b.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
                page = ctx.new_page()
                page.goto(link(srv.root, a.store, v), timeout=1800000)
                secs = ready(page, n_all if every else min(n_all, 100000))
                if shot == "all_zoom":
                    box = a.zoom_box.split(",") if a.zoom_box else None
                    rng = page.evaluate("""(box) => {
                      const g = document.querySelector('.tile[data-tile-id="cell-plot-A"] .js-plotly-plot');
                      let [x0, x1] = g._fullLayout.xaxis.range, [y0, y1] = g._fullLayout.yaxis.range;
                      if (box) { [x0, x1, y0, y1] = box.map(Number); }
                      else { const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, hx = (x1 - x0) / 200, hy = (y1 - y0) / 200;
                             [x0, x1, y0, y1] = [cx - hx, cx + hx, cy - hy, cy + hy]; }
                      return Plotly.relayout(g, {'xaxis.range': [x0, x1], 'yaxis.range': [y0, y1]})
                        .then(() => [x0, x1, y0, y1]); }""", box)
                    time.sleep(3)
                    v = dict(v, zoom_range_xy=rng)
                page.add_style_tag(content=HIDE)
                page.mouse.move(1, 1)
                time.sleep(1)
                tile = page.locator('.tile[data-tile-id="cell-plot-A"]')
                tile.locator(".js-plotly-plot").screenshot(path=str(out / f"{a.prefix}_{shot}.png"))
                tile.locator(".tile-content").screenshot(path=str(out / f"{a.prefix}_{shot}_panel.png"))
                meta = {"view": v, "store": a.store, "n_cells_store": n_all, "ready_s": round(secs, 1),
                        "browser": f"chromium {b.version}", "dsf": 2, "viewport": [1600, 1000],
                        "gl": page.evaluate(ceiling.GL_JS),
                        "drawn": page.evaluate(DRAWN_JS),
                        "notice": page.evaluate("""() => { const e = document.querySelector('.mode-notice .coverage-notice__headline');
                                                         return e ? e.textContent : null; }""")}
                (out / f"{a.prefix}_{shot}.view.json").write_text(json.dumps(meta, indent=1, default=str))
                print(shot, round(secs, 1), "s", flush=True)
                ctx.close()
            b.close()
    finally:
        srv.stop()


if __name__ == "__main__":
    main()
