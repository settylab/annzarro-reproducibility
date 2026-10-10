"""napari-spatialdata matrix-mark screenshots (run with $DEMO_ROOT/napari-spatialdata/.venv/bin/python
under gap_run.sh). Part 1: SpatialData sandbox Visium example (H&E + spots; 66 MB, downloaded from
https://s3.embl.de/spatialdata/spatialdata-sandbox/visium_spatialdata_0.7.3a2.dev27+gde3ed360b.zip).
Part 2: the local Visium demo with obsp/varp (spatial_demo_sdata.zarr) for the slot lists.
Every viewer is headless and closed inside this script."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
_SCRATCH = _os.environ.get("SCRATCH", _tempfile.gettempdir())  # scratch outputs
import os, sys, time, traceback, logging
from pathlib import Path
import anndata as ad
from qtpy.QtWidgets import QApplication
from spatialdata import SpatialData, read_zarr
from spatialdata._io import io_raster, io_shapes
from spatialdata._io.format import CurrentRasterFormat
from napari_spatialdata import Interactive
from PIL import Image

OUT = f"{_REPO}/notes/comparison/screens/napari-spatialdata/"
S = f"{_SCRATCH}/napari_matrix"
os.makedirs(S, exist_ok=True)
VIS = Path(f"{_DEMO_ROOT}/napari-spatialdata/examples/visium.zarr")

def load_visium(root=VIS):
    # read_zarr(root) raises ValidationError in spatialdata 0.8.0: the two *_lowres_image elements have an
    # empty transform dict. Skip those two; read the hires images, spot shapes and table element by element.
    imgs = {p.name: io_raster._read_multiscale(p, "image", CurrentRasterFormat())
            for p in sorted((root / "images").iterdir()) if p.is_dir() and "hires" in p.name}
    shp = {p.name: io_shapes._read_shapes(p) for p in sorted((root / "shapes").iterdir()) if p.is_dir()}
    t = ad.read_zarr(root / "tables" / "table")
    a = t.uns["spatialdata_attrs"]; a["region"] = [str(r) for r in list(a["region"])]
    return SpatialData(images=imgs, shapes=shp, tables={"table": t})

app = None
def pump(n=30):
    for _ in range(n): QApplication.instance().processEvents(); time.sleep(0.01)
def shot(v, name):
    pump(); arr = v.screenshot(canvas_only=False)
    Image.fromarray(arr).convert("RGB").save(OUT + name, quality=70); print("saved", name, arr.shape)
def menu_items(v, title):
    for a in v.window._qt_window.menuBar().actions():
        if a.text().replace("&", "") == title:
            return [x.text().replace("&", "") for x in a.menu().actions() if x.text()]

# ---------------- part 1: Visium H&E + spots ----------------
try:
    r = read_zarr(VIS)
except Exception as e:
    print("read_zarr(visium.zarr) fails:", type(e).__name__, str(e).splitlines()[0][:160])
sd = load_visium()
inter = Interactive(sd, headless=True); v = inter._viewer
try:
    v.window._qt_window.resize(1400, 900); v.window._qt_window.show(); pump()
    print("coordinate systems:", sd.coordinate_systems)
    inter.add_element("ST8059048_hires_image", "ST8059048"); pump()
    inter.add_element("ST8059048", "ST8059048"); pump()
    print("layers:", [(l.name, type(l).__name__) for l in v.layers])
    img = v.layers["ST8059048_hires_image"]
    print("image layer data:", type(img.data).__name__, "multiscale" if getattr(img, "multiscale", False) else "single", [type(d).__name__ for d in (img.data if isinstance(img.data, list) else [img.data])][:3])
    print("table X type:", type(sd["table"].X).__name__, sd["table"].shape)
    from napari_spatialdata._view import QtAdataViewWidget
    view = v.window._qt_window.findChild(QtAdataViewWidget)
    v.layers.selection.active = v.layers["ST8059048"]; pump()
    print("View obs:", [view.obs_widget.item(i).text() for i in range(view.obs_widget.count())])
    print("View obsm:", [view.obsm_widget.item(i).text() for i in range(view.obsm_widget.count())], "| var count:", view.var_widget.count())
    try:
        view.var_widget._onAction(("Mbp",)); pump(); print("gene colour ok, colour by:", view.color_by.text())
    except Exception as e:
        print("gene colour fails unpatched:", type(e).__name__, e)
        view.obs_widget._onAction(("array_row",)); pump(); print("colour by obs instead:", view.color_by.text())
    v.reset_view(); pump()
    shot(v, "m00_m07_m11_visium_spots_over_HE.jpg")
    # column 13: File menu and the screenshot export
    fm = menu_items(v, "File"); print("File menu:", fm)
    f = f"{S}/napari_screenshot.png"; v.screenshot(path=f, canvas_only=False); print("export:", os.path.basename(f), os.path.getsize(f), "bytes")
    # column 9: draw a polygon, save it into the SpatialData object (what Shift+E does)
    disk_before = sorted(p.name for p in (VIS / "shapes").iterdir())
    import numpy as np
    sp = sd.shapes["ST8059048"].geometry; cx, cy = float(sp.x.median()), float(sp.y.median())
    poly = np.array([[cy - 1500, cx - 1500], [cy - 1500, cx + 1500], [cy + 1500, cx + 1500], [cy + 1500, cx - 1500]])
    sh = v.add_shapes([poly], shape_type="polygon", name="my_roi", edge_color="yellow", face_color="transparent", edge_width=40)
    v.layers.selection.active = sh; v.layers.selection = {sh}; pump()
    logs = []
    try:
        from loguru import logger as L; L.add(lambda m: logs.append(str(m).strip()), level="WARNING")
    except Exception: pass
    inter._sdata_widget.viewer_model._save_to_sdata(v); pump()
    print("save warnings:", [x[-90:] for x in logs][-3:])
    print("in memory shapes now:", list(sd.shapes.keys()))
    print("on disk shapes before/after:", disk_before, sorted(p.name for p in (VIS / "shapes").iterdir()))
    shot(v, "m09_roi_saved_in_memory.jpg")
except Exception:
    traceback.print_exc()
finally:
    v.close(); pump(); print("closed viewer 1")

# ---------------- part 2: local demo with obsp / varp ----------------
sd2 = read_zarr(f"{_DEMO_ROOT}/napari-spatialdata/spatial_demo_sdata.zarr")
inter = Interactive(sd2, headless=True); v = inter._viewer
try:
    v.window._qt_window.resize(1400, 900); v.window._qt_window.show(); pump()
    inter.add_element("cells", "global"); pump()
    from napari_spatialdata._view import QtAdataViewWidget
    view = v.window._qt_window.findChild(QtAdataViewWidget)
    t = sd2["table"]
    print("table slots: obsm", list(t.obsm), "| layers", list(t.layers), "| obsp", list(t.obsp), "| varp", list(t.varp), "| varm", list(t.varm), "| uns", list(t.uns)[:6])
    print("View obs:", [view.obs_widget.item(i).text() for i in range(view.obs_widget.count())])
    print("View obsm:", [view.obsm_widget.item(i).text() for i in range(view.obsm_widget.count())])
    lw = getattr(view, "var_widget", None)
    print("View layer choices:", [view.adata_layer_widget.itemText(i) for i in range(view.adata_layer_widget.count())])
    print("View labels:", [w.text() for w in view.findChildren(type(view.color_by)) if w.text()][:12])
    view.obs_widget._onAction(("leiden",)); pump()
    shot(v, "m04_view_dock_lists_no_obsp.jpg")
    print("Plugins menu:", menu_items(v, "Plugins"))
except Exception:
    traceback.print_exc()
finally:
    v.close(); pump(); print("closed viewer 2")
