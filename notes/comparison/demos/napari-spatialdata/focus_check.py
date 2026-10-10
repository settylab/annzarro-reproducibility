import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import traceback
from spatialdata import read_zarr
from napari_spatialdata import Interactive
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Qt
MX = Qt.MatchFlag.MatchExactly
OUT = f"{_REPO}/notes/comparison/screens/napari-spatialdata/"
sdata = read_zarr(f"{_DEMO_ROOT}/napari-spatialdata/spatial_demo_sdata.zarr")
inter = Interactive(sdata, headless=True)
v = inter._viewer
app = QApplication.instance()
def pump(n=20):
    for _ in range(n): app.processEvents()
def shot(name):
    pump(); arr = v.screenshot(canvas_only=False)
    from PIL import Image; Image.fromarray(arr).convert("RGB").save(OUT + name, quality=75); print("saved", name)
try:
    v.window._qt_window.resize(1400, 900); v.window._qt_window.show()
    inter.add_element("cells", "global"); pump()
    print("layers", [l.name for l in v.layers])
    from napari_spatialdata._view import QtAdataViewWidget, QtAdataScatterWidget
    print("docks", list(v.window._dock_widgets.keys()))
    view = v.window._qt_window.findChild(QtAdataViewWidget)
    print("obs items", [view.obs_widget.item(i).text() for i in range(view.obs_widget.count())])
    print("obsm items", [view.obsm_widget.item(i).text() for i in range(view.obsm_widget.count())])
    print("var count", view.var_widget.count(), "| table has obsp:", list(sdata.tables["table"].obsp), "varp:", list(sdata.tables["table"].varp))
    # (a2) pick one gene in View: what recolours?
    try:
        view.var_widget._onAction(("Mbp",)); pump()
    except AttributeError as e:
        print("GENE PICK FAILS UNPATCHED:", e)
        import anndata as ad
        ad.AnnData._get_X = lambda self, layer=None: self.X if layer is None else self.layers[layer]   # shim for anndata>=0.12
        print("applied _get_X shim")
        view.var_widget._onAction(("Mbp",)); pump()
    print("colored by:", view.color_by.text())
    # add a second layer of the same element under a new name to see whether it follows the gene
    shot("01_view_gene_Mbp.jpg")
    # Scatter widget as a second view
    _, sc = v.window.add_plugin_dock_widget("napari-spatialdata", "Scatter"); pump()
    if not isinstance(sc, QtAdataScatterWidget): sc = v.window._qt_window.findChild(QtAdataScatterWidget)
    for w, comp in ((sc.x_widget, "0"), (sc.y_widget, "1")):
        w.selection_widget.setCurrentText("obsm"); pump()
        items = [w.widget.item(i).text() for i in range(w.widget.count())]
        it = w.widget.findItems("X_umap", MX)[0]; w.widget.setCurrentItem(it); w.widget.itemClicked.emit(it); pump()
        w.component_widget.setCurrentText(comp); pump()
        print("axis items", items, w.getFormattedLabel())
    sc.color_widget.selection_widget.setCurrentText("obs"); pump()
    it = sc.color_widget.widget.findItems("leiden", MX)[0]; sc.color_widget.widget.setCurrentItem(it); sc.color_widget.widget.itemClicked.emit(it); pump()
    sc.plot_button_widget.click(); pump(40)
    shot("02_scatter_umap_leiden_spatial_Mbp.jpg")
    # change gene in View again: does Scatter follow?
    view.var_widget._onAction(("Pcp2",)); pump()
    print("colored by after Pcp2:", view.color_by.text(), "| scatter colour:", sc.color_widget.getFormattedLabel())
    # single-cell click: select one shape in the layer
    lay = v.layers["cells"]
    lay.mode = "select"; lay.selected_data = {100}; pump()
    print("selected", lay.selected_data, "| colored by:", view.color_by.text(), "| scatter colour:", sc.color_widget.getFormattedLabel())
    shot("03_select_one_cell.jpg")
except Exception:
    traceback.print_exc()
finally:
    v.close(); print("closed")
