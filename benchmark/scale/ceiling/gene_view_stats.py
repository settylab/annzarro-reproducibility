#!/usr/bin/env python
"""Numbers behind the scale figure's gene panels (b, c): one gene's counts over every cell, and the
cells inside a shot's drawn region.

    python gene_view_stats.py STORE GENE CAP ZOOM_VIEW_JSON OUT_JSON

STORE is an AnnData zarr store (format 2) with X as csc_matrix and obs/cell_line_id categorical;
CAP is the colour scale's top; ZOOM_VIEW_JSON is a figures_tahoe.py view.json whose drawn range
(drawn.range_xy) is the zoomed region. Writes OUT_JSON: the share of all cells at or below CAP,
percentiles, and the zoomed region's cell count and cell lines.
"""
import json
import sys
from collections import Counter

import numpy as np
import zarr

CHUNK = 8_388_608


def main():
    store, gene, cap, zoom_view, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4], sys.argv[5]
    g = zarr.open_group(store, mode="r")
    genes = [str(x) for x in g["var/_index"][:]]
    j = genes.index(gene)
    X = g["X"]
    n = int(X.attrs["shape"][0])
    p = X["indptr"][j:j + 2]
    vals = np.zeros(n, dtype=np.float32)
    vals[np.asarray(X["indices"][p[0]:p[1]])] = np.asarray(X["data"][p[0]:p[1]])
    x0, x1, y0, y1 = json.loads(open(zoom_view).read())["drawn"]["range_xy"]
    u, codes = g["obsm/X_umap"], g["obs/cell_line_id/codes"]
    cats = [str(c) for c in g["obs/cell_line_id/categories"][:]]
    lines, inside = Counter(), []
    for s in range(0, n, CHUNK):
        a = u[s:s + CHUNK]
        m = (a[:, 0] >= x0) & (a[:, 0] <= x1) & (a[:, 1] >= y0) & (a[:, 1] <= y1)
        c, k = np.unique(np.asarray(codes[s:s + CHUNK])[m], return_counts=True)
        lines.update({cats[ci]: int(ki) for ci, ki in zip(c, k)})
        inside.append(vals[s:s + CHUNK][m])
    inside = np.concatenate(inside)
    top = lines.most_common(5)
    res = {"store": store, "gene": gene, "n_cells": n, "nonzero": int(p[1] - p[0]), "cap": cap,
           "pct_at_or_below_cap": round(100 * float((vals <= cap).mean()), 2),
           "percentiles": {str(q): float(np.percentile(vals, q)) for q in (50, 90, 99)},
           "zoom": {"view": zoom_view.split("/")[-1], "range_xy": [x0, x1, y0, y1], "n_cells": int(inside.size),
                    "median": float(np.median(inside)), "top_cell_lines": top,
                    "top_share_pct": round(100 * top[0][1] / inside.size, 1)}}
    open(out, "w").write(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res))


if __name__ == "__main__":
    main()
