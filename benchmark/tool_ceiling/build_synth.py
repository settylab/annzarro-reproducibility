#!/usr/bin/env python
"""SYNTHETIC AnnData zarr stores larger than Tahoe-100M, tiled from the real
95.6M panel store, for AnnZarro's ceiling past 95.6M cells.

Cell i of a synthetic store of N cells is a copy of real cell (i mod S),
S = 95,624,334, in tile t = i // S:

- obs: every column copied from the source cell (categoricals keep the source
  categories, e.g. cell_line_id with 50 cell lines); obs names get "-syn<t>"
  appended for t >= 1, so they stay unique.
- obsm (X_umap, X_pca_2d): the source coordinates; for t >= 1 plus Gaussian
  jitter, sd JITTER (0.05) in each coordinate, seeded by (SEED, array, chunk),
  so a tiled cell does not sit exactly on its source cell.
- X (CSC, the same 5,000-gene var with values in the same 200 panel genes,
  MALAT1 included): column j of tile t is the source column j with its row
  indices shifted by t * S. So the values per cell, the stored values per
  cell (~110) and the per-gene distributions are exactly Tahoe's.
- var, uns, categories: hard links to the source.

Tile 0 is the real store unchanged: the first 95,624,334 cells of every
synthetic store are Tahoe-100M itself. Layout as the source (zarr format 2,
the same chunking and compressors, consolidated metadata).

Usage: build_synth.py SRC OUTDIR N [N ...]  ->  OUTDIR/synth_tahoe_{N}.zarr
"""
from __future__ import annotations

import json
import math
import os
import zlib
import sys
import time
from pathlib import Path

import numcodecs
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scale/ceiling"))
from cut_prefix import POOL, Reader, Writer, consolidate, meta  # noqa: E402

SEED = 20261004
JITTER = 0.05
VLEN = numcodecs.VLenUTF8()


def src_rows(n_src: int, a: int, b: int):
    """Source row slices for synthetic rows [a, b): [(src_a, src_b, tile), ...]."""
    out, i = [], a
    while i < b:
        t, r = divmod(i, n_src)
        e = min(b, (t + 1) * n_src)
        out.append((r, r + (e - i), t))
        i = e
    return out


class CellArray:
    """A cell-axis array of the source, read whole (obs/obsm are small next to X)."""

    def __init__(self, p: Path):
        import zarr
        self.p, self.m = p, meta(p)
        self.arr = zarr.open_array(p, mode="r")[...]


def write_cell_array(src: Path, dst: Path, rel: Path, n_src: int, n: int):
    ca = CellArray(src / rel)
    m = dict(ca.m)
    c = m["chunks"][0]
    m["shape"] = [n] + m["shape"][1:]
    (dst / rel).mkdir(parents=True, exist_ok=True)
    (dst / rel / ".zarray").write_text(json.dumps(m, indent=1))
    for f in (".zattrs",):
        if (src / rel / f).exists():
            os.link(src / rel / f, dst / rel / f)
    comp = numcodecs.get_codec(m["compressor"])
    is_str = bool(m.get("filters")) and m["filters"][0]["id"] == "vlen-utf8"
    sep = m.get("dimension_separator", ".")
    is_obsm = rel.parts[0] == "obsm"
    salt = zlib.crc32(str(rel).encode())

    def chunk(k):
        a, b = k * c, min((k + 1) * c, n)
        parts = []
        for sa, sb, t in src_rows(n_src, a, b):
            x = ca.arr[sa:sb]
            if is_str:
                x = np.asarray(x, dtype=object)
            if t >= 1:
                if is_str:
                    x = np.array([f"{s}-syn{t}" for s in x], dtype=object)
                elif is_obsm:
                    rng = np.random.default_rng([SEED, salt, k, t])
                    x = (x + rng.normal(0, JITTER, x.shape)).astype(x.dtype)
            parts.append(x)
        x = np.concatenate(parts)
        if is_str:
            full = np.full(c, "", dtype=object)
            full[:len(x)] = x
            raw = VLEN.encode(full)
        else:
            full = np.zeros((c,) + tuple(m["shape"][1:]), dtype=x.dtype)
            full[:len(x)] = x
            raw = np.ascontiguousarray(full)
        name = sep.join([str(k)] + ["0"] * (len(m["shape"]) - 1))
        (dst / rel / name).write_bytes(comp.encode(raw))

    list(POOL.map(chunk, range(math.ceil(n / c))))


def build_tree(src: Path, dst: Path, n_src: int, n: int):
    for root, dirs, files in os.walk(src):
        r = Path(root)
        rel = r.relative_to(src)
        if rel.parts[:1] == ("X",):
            continue
        if ".zarray" in files:
            m = meta(r)
            if m["shape"] and m["shape"][0] == n_src and rel.parts[0] in ("obs", "obsm"):
                write_cell_array(src, dst, rel, n_src, n)
                continue
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for f in files:
            if f != ".zmetadata":
                os.link(r / f, dst / rel / f)


def main():
    src, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    sizes = sorted(int(x) for x in sys.argv[3:])
    t0 = time.time()
    xattrs = json.loads((src / "X" / ".zattrs").read_text())
    n_src, n_vars = xattrs["shape"]
    assert max(sizes) < 2 ** 31, "int32 row indices"
    stores = {n: outdir / f"synth_tahoe_{n}.zarr" for n in sizes}
    for d in stores.values():
        if d.exists():
            sys.exit(f"{d} exists")
    for n, d in stores.items():
        build_tree(src, d, n_src, n)
        print(f"obs/obsm/var {d.name} {time.time() - t0:.0f}s", flush=True)
    ip = Reader(src / "X" / "indptr").get(0, n_vars + 1)
    ri, rd = Reader(src / "X" / "indices"), Reader(src / "X" / "data")
    wi = {n: Writer(d / "X" / "indices", ri.m) for n, d in stores.items()}
    wd = {n: Writer(d / "X" / "data", rd.m) for n, d in stores.items()}
    new_ip = {n: np.zeros(n_vars + 1, np.int64) for n in sizes}
    for j in range(n_vars):
        a, b = int(ip[j]), int(ip[j + 1])
        cnt = {n: 0 for n in sizes}
        if b > a:
            idx, dat = ri.get(a, b), rd.get(a, b)
            for n in sizes:
                for t in range(math.ceil(n / n_src)):
                    off = t * n_src
                    k = len(idx) if off + n_src <= n else int(np.searchsorted(idx, n - off))
                    wi[n].add((idx[:k].astype(np.int64) + off).astype(np.int32))
                    wd[n].add(dat[:k])
                    cnt[n] += k
            print(f"col {j} nnz {b - a} {time.time() - t0:.0f}s", flush=True)
        for n in sizes:
            new_ip[n][j + 1] = new_ip[n][j] + cnt[n]
    for n, d in stores.items():
        wi[n].close()
        wd[n].close()
        assert wi[n].n == wd[n].n == new_ip[n][-1]
        w = Writer(d / "X" / "indptr", meta(src / "X" / "indptr"))
        w.add(new_ip[n])
        w.close()
        (d / "X" / ".zattrs").write_text(json.dumps(dict(xattrs, shape=[n, n_vars], synthetic=True), indent=1))
        (d / "X" / ".zgroup").write_text((src / "X" / ".zgroup").read_text())
        attrs = json.loads((src / ".zattrs").read_text())
        (d / ".zattrs").unlink()
        (d / ".zattrs").write_text(json.dumps(dict(attrs, synthetic={
            "source": str(src), "tiles": math.ceil(n / n_src), "seed": SEED, "jitter_sd": JITTER,
            "recipe": "benchmark/tool_ceiling/build_synth.py"}), indent=1))
        consolidate(d)
        (outdir / f"{d.name}.build.json").write_text(json.dumps({
            "n_cells": n, "nnz": int(new_ip[n][-1]), "source": str(src), "script": "build_synth.py",
            "synthetic": True, "seed": SEED, "jitter_sd": JITTER, "seconds": round(time.time() - t0)}, indent=1))
        print(f"done {d.name} nnz {new_ip[n][-1]} {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
