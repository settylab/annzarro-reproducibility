#!/bin/sh
# napari-spatialdata (desktop GUI, not a server) on the paper's Visium spatial demo, wrapped as
# SpatialData by make_sdata.py. Opens a napari window; close the window to stop.
# Other data: ./start.sh /path/to/any_spatialdata.zarr
cd "$(dirname "$0")"
exec .venv/bin/python -c 'import sys; from spatialdata import read_zarr; from napari_spatialdata import Interactive; Interactive(read_zarr(sys.argv[1])).run()' "${1:-spatial_demo_sdata.zarr}"
