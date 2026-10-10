"""Replicate scSVA's 2-D density binning (server.R L644-656, L720-723) on the bm_aging coords
offline, to quantify how far each cell is moved to its bin centre at grid 512.
This is a replication, not scSVA output. vaex binning: idx = floor((v-lo)/(hi-lo)*G), v in [lo,hi)."""
import sys, json, h5py, numpy as np
f, G = sys.argv[1], int(sys.argv[2])
win = [float(v) for v in sys.argv[3:7]] if len(sys.argv) >= 7 else None  # optional zoom window xlo xhi ylo yhi (no pad, as S#L1019-1028)
with h5py.File(f, "r") as h:
    x = h["X"][:].astype(float); y = h["Y"][:].astype(float)
def pad(lo, hi):  # sequential, as in server.R L644-647 (X[1] updated before X[2] uses it)
    lo = lo - (hi - lo) * 0.005; hi = hi + (hi - lo) * 0.005; return lo, hi
if win:
    X, Y = (win[0], win[1]), (win[2], win[3])
    m = (x >= X[0]) & (x < X[1]) & (y >= Y[0]) & (y < Y[1]); x, y = x[m], y[m]
else:
    X = pad(x.min(), x.max()); Y = pad(y.min(), y.max())
ix = np.floor((x - X[0]) / (X[1] - X[0]) * G).astype(int); iy = np.floor((y - Y[0]) / (Y[1] - Y[0]) * G).astype(int)
bw = ((X[1] - X[0]) / G, (Y[1] - Y[0]) / G)
cx = X[0] + bw[0] * (ix + 0.5); cy = Y[0] + bw[1] * (iy + 0.5)   # = X[1]+range*(i-.5) with 1-based i
d = np.hypot(x - cx, y - cy)
keys, counts = np.unique(ix * (G + 1) + iy, return_counts=True)
hist = {int(k): int(v) for k, v in zip(*np.unique(counts, return_counts=True))}
print(json.dumps({"file": f, "grid": G, "window": win, "single_cell_marks": hist.get(1, 0), "marks_by_cells_per_bin": hist, "n_cells": int(x.size), "bin_width_x": bw[0], "bin_width_y": bw[1],
  "nonempty_bins_drawn": int(keys.size), "cells_sharing_a_bin": int(counts[counts > 1].sum()),
  "max_cells_in_one_bin": int(counts.max()), "max_snap_distance": float(d.max()),
  "median_snap_distance": float(np.median(d)), "cells_moved_nonzero": int((d > 0).sum())}, indent=1))
