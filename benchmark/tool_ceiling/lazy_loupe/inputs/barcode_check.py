"""Why Loupe shows 999,966 barcodes for 1,000,000 cells: count the cells with zero MALAT1 in each input h5ad.
Loupe's legend under the gene coloring says "999966 barcodes found"; both inputs hold 1,000,000 unique cells
(loupe_build.R passes all of them to LoupeR, the build log says 1000000 cells), of which 34 have no MALAT1 count.
Usage: barcode_check.py DIR   (DIR holds tahoe_first1000000_{g200,g2000}.h5ad; output: barcode_check.txt)"""
import sys
import h5py
import numpy as np

for s in ("g200", "g2000"):
    f = h5py.File(f"{sys.argv[1]}/tahoe_first1000000_{s}.h5ad")
    ix = f["var/_index"]
    names = [n.decode() if isinstance(n, bytes) else n for n in (ix["values"][:] if isinstance(ix, h5py.Group) else ix[:])]
    j = names.index("MALAT1")
    n = int(f["X"].attrs["shape"][0])
    v = f["X/data"][:][f["X/indices"][:] == j]
    nnz = np.diff(f["X/indptr"][:])
    print(f"{s}: {n} cells, {len(names)} genes, {len(set(f['obs/_index'][:]))} unique barcodes; "
          f"cells with MALAT1 > 0: {len(v)}; cells with MALAT1 = 0: {n - len(v)}; "
          f"cells with no stored value at all: {int((nnz == 0).sum())}; max MALAT1 count {v.max():.0f}, log2(1+max) {np.log2(1 + v.max()):.2f}")
