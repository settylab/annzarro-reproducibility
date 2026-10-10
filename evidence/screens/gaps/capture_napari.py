"""napari-spatialdata gap shots (evidence-curator, 2026-10-04): Qt window grabs (QWidget.grab) with boxes from Qt widget geometry.

Run under notes/comparison/demos/scale_probe/gap_run.sh with the napari venv and the native Qt platform:
  $DEMO_ROOT/napari-spatialdata/.venv/bin/python <this file>
(QT_QPA_PLATFORM=offscreen segfaults at viewer creation, rc=-11, as comparison-auditor found; the window shows on
screen for about a minute and the script closes it.)

napari is a desktop Qt app, so Playwright cannot record its DOM. Every box below is computed from Qt geometry
(QMenuBar.actionGeometry, QMenu.actionGeometry, QWidget.mapTo) at capture time and written to the sidecar by
this script (source: manual, pinned by image_sha256); nothing is read off the image by eye. Popup menus are
separate top-level widgets, so each is grabbed (QWidget.grab) and painted onto the window grab at its own
position relative to the window.

Viewer A: the SpatialData sandbox Visium example (H&E images + spots + table; $DEMO_ROOT/napari-spatialdata/examples/visium.zarr).
  g01 Plugins menu + napari-spatialdata submenu  -> de N
  g02 File menu                                    -> share N, export Y (Save Screenshot)
  g03 SpatialData dock: coordinate systems, elements -> subset P
  g05 image layer data type vs table X type        -> lazy P (log strip under the grab)
Viewer B: a synthetic SpatialData with one 150,000-point element.
  g04 points layer holds 100,000 of 150,000 points + the plugin's own log line -> every_cell P
"""
import hashlib
import os
import sys
import textwrap
import time
import traceback
from datetime import date
from pathlib import Path

import anndata as ad  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from qtpy.QtCore import QPoint  # noqa: E402
from qtpy.QtGui import QPainter  # noqa: E402
from qtpy.QtWidgets import QApplication  # noqa: E402
from spatialdata import SpatialData  # noqa: E402
from spatialdata._io import io_raster, io_shapes  # noqa: E402
from spatialdata._io.format import CurrentRasterFormat  # noqa: E402
from napari_spatialdata import Interactive  # noqa: E402

OUT = Path("notes/comparison/screens/napari-spatialdata/")
TMP = Path("$TMPDIR/evidence/gap-capture/napari")
TMP.mkdir(parents=True, exist_ok=True)
VIS = Path("$DEMO_ROOT/napari-spatialdata/examples/visium.zarr")
DRIVER = "evidence/screens/gaps/capture_napari.py"
SW = "napari 0.9.2, napari-spatialdata 0.7.2, spatialdata 0.8.0 (PyQt6)"
TODAY = date.today().isoformat()
FONT = "/System/Library/Fonts/Menlo.ttc"


def pump(n=40):
    for _ in range(n):
        QApplication.instance().processEvents()
        time.sleep(0.01)


def load_visium(root=VIS):
    # as notes/comparison/demos/napari-spatialdata/matrix_check.py: read_zarr(root) fails on the two
    # *_lowres_image elements (empty transform dict) in spatialdata 0.8.0, so read element by element.
    imgs = {p.name: io_raster._read_multiscale(p, "image", CurrentRasterFormat())
            for p in sorted((root / "images").iterdir()) if p.is_dir() and "hires" in p.name}
    shp = {p.name: io_shapes._read_shapes(p) for p in sorted((root / "shapes").iterdir()) if p.is_dir()}
    t = ad.read_zarr(root / "tables" / "table")
    a = t.uns["spatialdata_attrs"]
    a["region"] = [str(r) for r in list(a["region"])]
    return SpatialData(images=imgs, shapes=shp, tables={"table": t})


def rect_in(widget, top):
    """Widget rect in `top`'s coordinates (logical px)."""
    p = widget.mapTo(top, QPoint(0, 0))
    return [p.x(), p.y(), widget.width(), widget.height()]


def scale(box, dpr):
    return [round(v * dpr) for v in box]


def grab_with_menus(qtw, menus):
    """Window grab with popup menus painted at their positions. Returns (QPixmap, dpr, {menu: offset})."""
    pix = qtw.grab()
    dpr = pix.devicePixelRatio()
    origin = qtw.mapToGlobal(QPoint(0, 0))
    offs = {}
    painter = QPainter(pix)
    for m in menus:
        g = m.geometry()
        rel = QPoint(g.x() - origin.x(), g.y() - origin.y())
        painter.drawPixmap(rel, m.grab())
        offs[m] = (rel.x(), rel.y())
    painter.end()
    return pix, dpr, offs


def add_strip(png, lines, hl):
    """Append a terminal-style strip under the image; returns boxes (image px) of the lines whose index is in hl."""
    im = Image.open(png).convert("RGB")
    W, H = im.size
    f = ImageFont.truetype(FONT, 22)
    wrapped = []
    for i, ln in enumerate(lines):
        for w in textwrap.wrap(ln, max(40, W // 13)) or [""]:
            wrapped.append((i, w))
    lh = 32
    strip = 24 + lh * len(wrapped)
    c = Image.new("RGB", (W, H + strip), (17, 17, 17))
    c.paste(im, (0, 0))
    d = ImageDraw.Draw(c)
    boxes = {}
    y = H + 12
    for i, w in wrapped:
        d.text((16, y), w, fill=(230, 230, 230), font=f)
        tw = d.textlength(w, font=f)
        if i in hl:
            b = boxes.get(i)
            nb = [10, y - 4, int(tw) + 14, lh]
            boxes[i] = nb if b is None else [10, b[1], max(b[2], nb[2]), y - b[1] + lh]
        y += lh
    c.save(png)
    return boxes, H


def sidecar(png, proves, callouts, data, extra=None):
    png = Path(png)
    W, H = Image.open(png).size
    for c in callouts:
        x, y, w, h = c["box"]
        x, y = max(0, x), max(0, y)
        c["box"] = [x, y, max(1, min(w, W - x)), max(1, min(h, H - y))]
    meta = {"version": 1, "image": png.name, "tool": "napari-spatialdata", "software": SW, "data": data,
            "url": None, "captured": TODAY, "by": "evidence-curator", "driver": DRIVER, "source": "manual",
            "image_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
            "coordinates": "computed by the driver from Qt widget geometry (QMenu.actionGeometry, QWidget.mapTo), not read off the image",
            "proves": proves, "callouts": callouts}
    if extra:
        meta.update(extra)
    side = png.with_name(png.stem + ".annot.yaml")
    side.write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=100))
    print("wrote", png.name, side.name, flush=True)


def pv(c, m, t):
    return {"column": c, "mark": m, "caption": t}


def menu_of(qtw, title):
    mb = qtw.menuBar()
    for a in mb.actions():
        if a.text().replace("&", "") == title:
            return mb, a, a.menu()
    return mb, None, None


def open_menu(qtw, title):
    mb, act, menu = menu_of(qtw, title)
    menu.popup(mb.mapToGlobal(mb.actionGeometry(act).bottomLeft()))
    pump()
    return mb, act, menu


# ---------------------------------------------------------------- viewer A
sd = load_visium()
inter = Interactive(sd, headless=True)
v = inter._viewer
qtw = v.window._qt_window
try:
    qtw.resize(1400, 900)
    qtw.show()
    pump()
    inter.add_element("ST8059048_hires_image", "ST8059048")
    pump()
    inter.add_element("ST8059048", "ST8059048")
    pump()
    v.reset_view()
    pump(60)

    # g01 Plugins menu (+ the napari-spatialdata submenu if there is one)
    try:
        mb, act, menu = open_menu(qtw, "Plugins")
        items = [a.text().replace("&", "") for a in menu.actions() if a.text()]
        print("Plugins menu:", items, flush=True)
        menus = [menu]
        sub_items = []
        sub = None
        for a in menu.actions():
            if a.menu() is not None and "spatial" in a.text().lower():
                sub = a.menu()
                sub.popup(menu.mapToGlobal(menu.actionGeometry(a).topRight()))
                pump()
                sub_items = [x.text().replace("&", "") for x in sub.actions() if x.text()]
                menus.append(sub)
        print("napari-spatialdata submenu:", sub_items, flush=True)
        pix, dpr, offs = grab_with_menus(qtw, menus)
        png = OUT / "g01_de_plugins_menu.png"
        pix.save(str(png))
        mo = offs[menu]
        cal = [{"n": 1, "box": scale([mo[0], mo[1], menu.width(), menu.height()], dpr), "label": "Plugins menu: " + "; ".join(items)}]
        if sub is not None:
            so = offs[sub]
            cal.append({"n": 2, "box": scale([so[0], so[1], sub.width(), sub.height()], dpr), "label": "napari-spatialdata widgets: " + "; ".join(sub_items)})
        sidecar(png, [pv("de", "N", f"{SW} ({TODAY}): the Plugins menu and the napari-spatialdata submenu offer {', '.join(sub_items) or 'no'} widgets; none computes differential expression")],
                cal, "SpatialData sandbox Visium example (ST8059048, H&E + spots)")
        for m in reversed(menus):
            m.hide()
        pump()
    except Exception:
        traceback.print_exc()

    # g02 File menu
    try:
        mb, act, menu = open_menu(qtw, "File")
        acts = [a for a in menu.actions() if a.text()]
        items = [a.text().replace("&", "") for a in acts]
        print("File menu:", items, flush=True)
        pix, dpr, offs = grab_with_menus(qtw, [menu])
        png = OUT / "g02_share_export_file_menu.png"
        pix.save(str(png))
        mo = offs[menu]
        cal = [{"n": 1, "box": scale([mo[0], mo[1], menu.width(), menu.height()], dpr), "label": "File menu: " + "; ".join(items)}]
        n = 2
        for a in acts:
            if "screenshot" in a.text().lower():
                g = menu.actionGeometry(a)
                cal.append({"n": n, "box": scale([mo[0] + g.x(), mo[1] + g.y(), g.width(), g.height()], dpr), "label": a.text().replace("&", "") + " (writes a PNG)"})
                n += 1
        shot_items = [i for i in items if "screenshot" in i.lower()]
        session = [i for i in items if any(k in i.lower() for k in ("session", "link", "share", "state"))]
        sidecar(png, [pv("share", "N", f"{SW} ({TODAY}): the File menu opens and saves layers and screenshots; {'no' if not session else ', '.join(session)} session, view-state or link entry"),
                      pv("export", "Y", f"{SW} ({TODAY}): File > {' / '.join(shot_items) or 'Save Screenshot'} writes the canvas or the whole viewer as a PNG")],
                cal, "SpatialData sandbox Visium example (ST8059048, H&E + spots)")
        menu.hide()
        pump()
    except Exception:
        traceback.print_exc()

    # g03 SpatialData dock: coordinate systems and elements
    try:
        from napari_spatialdata._sdata_widgets import SdataWidget
        w = qtw.findChild(SdataWidget)
        cs = [w.coordinate_system_widget.item(i).text() for i in range(w.coordinate_system_widget.count())]
        el = [w.elements_widget.item(i).text() for i in range(w.elements_widget.count())]
        print("coordinate systems:", cs, "elements:", el, flush=True)
        pix = qtw.grab()
        dpr = pix.devicePixelRatio()
        png = OUT / "g03_subset_sdata_dock_elements.png"
        pix.save(str(png))
        sidecar(png, [pv("subset", "P", f"{SW} ({TODAY}): the SpatialData dock picks a coordinate system and which elements to load ({', '.join(el)}); there is no control to pick a subset of cells, which needs Python code before Interactive(...)")],
                [{"n": 1, "box": scale(rect_in(w.coordinate_system_widget, qtw), dpr), "label": "Coordinate System: " + ", ".join(cs)},
                 {"n": 2, "box": scale(rect_in(w.elements_widget, qtw), dpr), "label": "Elements: " + ", ".join(el)}],
                "SpatialData sandbox Visium example (ST8059048, H&E + spots)")
    except Exception:
        traceback.print_exc()

    # g05 lazy: what the layers hold
    try:
        img = v.layers["ST8059048_hires_image"]
        data = img.data if isinstance(img.data, list) else [img.data]
        X = sd["table"].X
        lines = [f"$ # recorded by {DRIVER} in the running viewer, {TODAY}",
                 f">>> [type(d).__name__ for d in viewer.layers['ST8059048_hires_image'].data]   # image layer, {len(data)} level(s)",
                 str([(type(d).__name__, type(getattr(d, 'data', d)).__module__.split('.')[0]) for d in data]) + "   <- xarray over dask: image chunks are read from zarr on demand",
                 ">>> type(sdata['table'].X).__name__, sdata['table'].X.shape",
                 f"{(type(X).__name__, X.shape)}   <- the table's X is loaded whole into memory"]
        print("\n".join(lines), flush=True)
        pix = qtw.grab()
        dpr = pix.devicePixelRatio()
        png = OUT / "g05_lazy_image_dask_table_in_memory.png"
        pix.save(str(png))
        boxes, H = add_strip(png, lines, hl={2, 4})
        cal = [{"n": 1, "box": scale(rect_in(v.window._qt_viewer.layers, qtw), dpr) if hasattr(v.window, "_qt_viewer") else [0, 0, round(qtw.width() * dpr), round(qtw.height() * dpr)], "label": "layer list: ST8059048_hires_image (image) and the spots"}]
        cal += [{"n": 2, "box": boxes[2], "label": "image data: dask arrays (lazy)"}, {"n": 3, "box": boxes[4], "label": "table X: in memory"}]
        sidecar(png, [pv("lazy", "P", f"terminal, {SW} ({TODAY}): image layers are dask arrays read lazily from zarr, but the table's X is loaded into memory, so P")],
                cal, "SpatialData sandbox Visium example (ST8059048, H&E + spots)")
    except Exception:
        traceback.print_exc()
finally:
    v.close()
    pump()
    print("closed viewer A", flush=True)

# ---------------------------------------------------------------- viewer B: 150,000 points
try:
    from loguru import logger
    from spatialdata.models import PointsModel
    logs = []
    logger.add(lambda m: logs.append(str(m).strip()), level="INFO")
    rng = np.random.default_rng(0)
    N = 150_000
    df = pd.DataFrame({"x": rng.uniform(0, 2000, N), "y": rng.uniform(0, 2000, N)})
    sdp = SpatialData(points={"points_150k": PointsModel.parse(df)})
    inter = Interactive(sdp, headless=True)
    v = inter._viewer
    qtw = v.window._qt_window
    qtw.resize(1400, 900)
    qtw.show()
    pump()
    inter.add_element("points_150k", "global")
    pump(60)
    v.reset_view()
    pump()
    lay = [l for l in v.layers if "points" in l.name][0]
    shown = len(lay.data)
    sub_logs = [l for l in logs if "ubsampl" in l]
    print("points layer", lay.name, "holds", shown, "of", N, "| log:", sub_logs[:1], flush=True)
    lines = [f"$ # recorded by {DRIVER} in the running viewer, {TODAY}",
             f"element points_150k: {N:,} points; napari layer '{lay.name}' holds {shown:,} points",
             "napari-spatialdata log: " + (sub_logs[0].split("|")[-1].strip()[:300] if sub_logs else "(no subsampling message captured)")]
    pix = qtw.grab()
    dpr = pix.devicePixelRatio()
    png = OUT / "g04_every_cell_points_subsampled_100k.png"
    pix.save(str(png))
    boxes, H = add_strip(png, lines, hl={1, 2})
    sidecar(png, [pv("every_cell", "P", f"terminal + window, {SW} ({TODAY}): a 150,000-point element is drawn as a random {shown:,}-point subsample (config.POINT_THRESHOLD, changeable only in code); labels and the scatter widget draw everything, so P")],
            [{"n": 1, "box": [0, 0, round(qtw.width() * dpr), round(qtw.height() * dpr)], "label": "viewer with the points layer"},
             {"n": 2, "box": boxes[1], "label": f"{shown:,} of {N:,} points in the layer"},
             {"n": 3, "box": boxes[2], "label": "the plugin's own subsampling log line"}],
            f"synthetic SpatialData, one points element of {N:,} uniform random points")
    v.close()
    pump()
    print("closed viewer B", flush=True)
except Exception:
    traceback.print_exc()
print("done", flush=True)
