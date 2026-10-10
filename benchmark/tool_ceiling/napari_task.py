#!/usr/bin/env python
"""The napari-spatialdata task: open the SpatialData store (to_sdata.py) with
napari_spatialdata.Interactive, add the "cells" element in the global
coordinate system, colour it by cell_line_id and then by MALAT1 through the
plugin's View widget (what a user clicks), screenshot each. A desktop app: the
whole Python process is the client (measured by memmon.py). The window is
shown (napari draws with OpenGL, which needs a real window on macOS).

Every cell drawn: the points layer holds N points. By default
napari-spatialdata draws a random 100,000-point subsample of a larger points
element (constants.config.POINT_THRESHOLD); --all-points raises the threshold
(variant allpoints, every cell); without it the run measures the tool's
default subsample (variant sub100k).

Usage: napari_task.py SDATA.zarr OUTPREFIX --n N   (napari-spatialdata's env)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from importlib.metadata import version


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sdata")
    ap.add_argument("out")
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--all-points", action="store_true",
                    help="raise napari_spatialdata's POINT_THRESHOLD (default 100,000 points, above which it draws a "
                         "random subsample) to N + 1, as its own log message says to")
    a = ap.parse_args()
    rec = {"tool": "napari-spatialdata", "n": a.n, "phases": {}, "checks": {},
           "versions": {p: version(p) for p in ("napari", "napari-spatialdata", "spatialdata", "anndata", "PyQt6")}}
    t0 = time.time()

    def mark(k):
        rec["phases"][k] = round(time.time() - t0, 2)
        print(f"[{rec['phases'][k]:8.1f}s] {k}", file=sys.stderr, flush=True)
        json.dump(rec, open(a.out + ".json", "w"), indent=1)

    import napari
    import napari_spatialdata
    for m in (napari, napari_spatialdata):  # never a stray napari*.py next to the script or in the cwd
        assert "site-packages" in m.__file__, f"{m.__name__} imported from {m.__file__}"
    rec["modules"] = {"napari": napari.__file__, "napari_spatialdata": napari_spatialdata.__file__}
    import anndata as ad
    if not hasattr(ad.AnnData, "_get_X"):  # napari-spatialdata 0.7.2 calls it; anndata >= 0.12 dropped it
        ad.AnnData._get_X = lambda self, layer=None: self.X if layer is None else self.layers[layer]
        rec["shim"] = "AnnData._get_X restored for napari-spatialdata 0.7.2 (anndata >= 0.12)"
    from napari_spatialdata import Interactive
    from napari_spatialdata.constants import config
    rec["point_threshold_default"] = config.POINT_THRESHOLD
    if a.all_points:
        config.POINT_THRESHOLD = a.n + 1
    expect = a.n if a.n < config.POINT_THRESHOLD else config.POINT_THRESHOLD
    rec["point_threshold"], rec["expect_drawn"] = config.POINT_THRESHOLD, expect
    from napari_spatialdata._view import QtAdataViewWidget
    from qtpy.QtWidgets import QApplication
    from spatialdata import read_zarr
    sdata = read_zarr(a.sdata)
    mark("read")
    inter = Interactive(sdata, headless=True)
    v = inter._viewer
    app = QApplication.instance()

    def pump(k=20):
        for _ in range(k):
            app.processEvents()

    # a visible window: hold the screen lock too (taken inside the bench lock, as every capture does)
    import fcntl
    screen = open("$HOME/.annzarro-screen.lock", "a")
    t_lock = time.time()
    while True:  # never sit on the bench lock for long waiting for the screen
        try:
            fcntl.flock(screen, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.time() - t_lock > 120:
                rec["error"] = "harness: screen lock busy for 120 s"
                mark("done")
                sys.exit(4)
            time.sleep(2)
    mark("screen_lock")
    v.window._qt_window.resize(1400, 900)
    v.window._qt_window.show()
    inter.add_element("cells", "global")
    # large elements are added from a worker thread: wait (pumping Qt events) until the layer exists
    t = time.time()
    while not len(v.layers) and time.time() - t < 1700:
        pump()
        time.sleep(0.05)
    if not len(v.layers):
        raise TimeoutError("no layer after add_element")
    pump()
    layer = v.layers[-1]
    layer.size = 0.1  # napari's default (6 data units) hides the UMAP; one user step, same per-point arrays
    pump()
    mark("first_plot")
    view = v.window._qt_window.findChild(QtAdataViewWidget)
    ok = True
    for tag, widget, key in (("cat", view.obs_widget, "cell_line_id"), ("gene", view.var_widget, "MALAT1")):
        widget._onAction((key,))
        pump(50)
        png = f"{a.out}_{tag}.png"
        from PIL import Image
        Image.fromarray(v.screenshot(canvas_only=False)).convert("RGB").save(png)
        n_drawn = len(layer.data)
        rec["checks"][tag] = {"n_drawn": n_drawn, "all_cells": n_drawn == a.n, "expected_drawn": expect,
                              "colored_by": view.color_by.text(), "png": png}
        ok &= n_drawn == expect and key in view.color_by.text()
        mark(f"plot_{tag}")
    rec["ok"] = bool(ok)
    mark("done")
    v.close()
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()
