"""Wrap the paper's spatial demo AnnData (data/spatial_demo.zarr) as a SpatialData store.

Cells become circles at obsm['spatial'] and the AnnData is the annotating table, so
napari-spatialdata can colour them by obs columns and genes. There is no tissue image in the
source store, so none is added. Writes spatial_demo_sdata.zarr next to this script.
"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
from pathlib import Path

import anndata as ad
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from spatialdata import SpatialData
from spatialdata.models import ShapesModel, TableModel

HERE = Path(__file__).parent
a = ad.read_zarr(f"{_REPO}/data/spatial_demo.zarr")
xy = np.asarray(a.obsm["spatial"])[:, :2]
from scipy.spatial import cKDTree
d = float(np.median(cKDTree(xy).query(xy, k=2)[0][:, 1])) * 0.45  # spot radius: just under half the spot pitch
cells = gpd.GeoDataFrame({"radius": np.full(len(xy), d)}, geometry=[Point(x, y) for x, y in xy],
                         index=a.obs_names.astype(str))
cells = ShapesModel.parse(cells)
a.obs["region"] = "cells"
a.obs["region"] = a.obs["region"].astype("category")
a.obs["instance_id"] = a.obs_names.astype(str)
table = TableModel.parse(a, region="cells", region_key="region", instance_key="instance_id")
sd = SpatialData(shapes={"cells": cells}, tables={"table": table})
sd.write(HERE / "spatial_demo_sdata.zarr", overwrite=True)
print(sd, "radius", d)
