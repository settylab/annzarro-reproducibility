#!/usr/bin/env python
"""The h5ad as a SpatialData store for napari-spatialdata: a points element
"cells" whose x/y are obsm/X_umap, annotated by the AnnData table (X, obs) via
instance_id. napari-spatialdata draws an element in a coordinate system and
colours it from its table, so the UMAP takes the place of the spatial layout.
Measured as a conversion run charged to napari-spatialdata.

Usage: to_sdata.py H5AD OUT.zarr   (napari-spatialdata's env)
"""
import sys

import anndata as ad
import numpy as np
import pandas as pd
from spatialdata import SpatialData
from spatialdata.models import PointsModel, TableModel

a = ad.read_h5ad(sys.argv[1])
n = a.n_obs
xy = a.obsm["X_umap"]
pts = PointsModel.parse(pd.DataFrame({"x": xy[:, 0], "y": xy[:, 1], "instance_id": np.arange(n)}),
                        instance_key="instance_id")
a.obs["region"] = pd.Categorical(["cells"] * n)
a.obs["instance_id"] = np.arange(n)
a.obs_names = a.obs_names.astype(str)
table = TableModel.parse(a, region="cells", region_key="region", instance_key="instance_id")
SpatialData(points={"cells": pts}, tables={"table": table}).write(sys.argv[2], overwrite=True)
print(n, "cells written to", sys.argv[2])
