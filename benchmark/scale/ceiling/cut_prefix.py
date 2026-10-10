#!/usr/bin/env python
"""First-N-cell stores cut from a zarr v2 AnnData store with a CSC X (the real
Tahoe-100M panel store, tahoe_panel_95.6M_plot.zarr), for the release-0.3 rerun.

- Every array whose first axis is the cells (obs/*, obsm/*): its first
  ceil(N / chunk) chunk files are hard-linked and the shape set to N. The edge
  chunk then holds cells past N, which zarr ignores (v2 stores full edge chunks).
- Every other array (var, categories, uns): all files hard-linked.
- X (CSC): rewritten. Within a column the row indices are ascending, so the
  first N cells of a column are a prefix of its segment (checked per column).
  The source is read once and every N is written in the same pass, with the
  source's chunking and compressors. X/.zattrs keeps its attributes with
  shape [N, n_vars].
- .zmetadata (consolidated) is rebuilt from the written files.

Usage: cut_prefix.py SRC OUTDIR N [N ...]  ->  OUTDIR/tahoe95_first{N}.zarr
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numcodecs
import numpy as np

POOL = ThreadPoolExecutor(12)


def meta(p: Path) -> dict:
    return json.loads((p / ".zarray").read_text())


class Reader:
    def __init__(self, p: Path):
        self.p, self.m = p, meta(p)
        self.c = self.m["chunks"][0]
        self.dt = np.dtype(self.m["dtype"])
        self.codec = numcodecs.get_codec(self.m["compressor"])

    def _chunk(self, k):
        f = self.p / str(k)
        if not f.exists():
            return np.full(self.c, self.m["fill_value"] or 0, self.dt)
        return np.frombuffer(self.codec.decode(f.read_bytes()), self.dt)

    def get(self, a: int, b: int) -> np.ndarray:
        if b <= a:
            return np.empty(0, self.dt)
        k0, k1 = a // self.c, (b - 1) // self.c
        parts = list(POOL.map(self._chunk, range(k0, k1 + 1)))
        return np.concatenate(parts)[a - k0 * self.c: b - k0 * self.c]


class Writer:
    """Append values; full chunks are encoded and written as they fill."""

    def __init__(self, p: Path, src_meta: dict):
        p.mkdir(parents=True)
        self.p, self.m = p, dict(src_meta)
        self.c = self.m["chunks"][0]
        self.dt = np.dtype(self.m["dtype"])
        self.codec = numcodecs.get_codec(self.m["compressor"])
        self.buf, self.nbuf, self.k, self.n, self.fut = [], 0, 0, 0, []

    def _write(self, k, arr):
        (self.p / str(k)).write_bytes(self.codec.encode(np.ascontiguousarray(arr)))

    def add(self, x: np.ndarray):
        if len(x) == 0:
            return
        self.buf.append(x.astype(self.dt, copy=False))
        self.nbuf += len(x)
        self.n += len(x)
        if self.nbuf >= self.c:
            allb = np.concatenate(self.buf)
            full = (len(allb) // self.c) * self.c
            for s in range(0, full, self.c):
                self.fut.append(POOL.submit(self._write, self.k, allb[s:s + self.c].copy()))
                self.k += 1
            rest = allb[full:].copy()
            self.buf, self.nbuf = ([rest] if len(rest) else []), len(rest)
            self.fut = [f for f in self.fut if not f.done() or f.result()]

    def close(self):
        if self.nbuf:
            last = np.zeros(self.c, self.dt)
            tail = np.concatenate(self.buf)
            last[:len(tail)] = tail
            self._write(self.k, last)
        for f in self.fut:
            f.result()
        self.m["shape"] = [self.n]
        (self.p / ".zarray").write_text(json.dumps(self.m, indent=1))


def link_tree(src: Path, dst: Path, n: int, n_total: int):
    """Hard-link src (no X) into dst; cell-axis arrays cut to n."""
    for root, dirs, files in os.walk(src):
        r = Path(root)
        rel = r.relative_to(src)
        if rel.parts[:1] == ("X",):
            continue
        (dst / rel).mkdir(parents=True, exist_ok=True)
        if ".zarray" in files:
            m = meta(r)
            if m["shape"] and m["shape"][0] == n_total and rel.parts[0] in ("obs", "obsm"):
                m["shape"] = [n] + m["shape"][1:]
                (dst / rel / ".zarray").write_text(json.dumps(m, indent=1))
                nk = math.ceil(n / m["chunks"][0])
                sep = m.get("dimension_separator", ".")
                for f in files:
                    if f.startswith("."):
                        if f != ".zarray":
                            os.link(r / f, dst / rel / f)
                    elif int(f.split(sep)[0]) < nk:
                        os.link(r / f, dst / rel / f)
                continue
        for f in files:
            if f == ".zmetadata":
                continue
            os.link(r / f, dst / rel / f)


def consolidate(store: Path):
    md = {}
    for root, _, files in os.walk(store):
        for f in files:
            if f in (".zarray", ".zattrs", ".zgroup"):
                key = str((Path(root) / f).relative_to(store))
                md[key] = json.loads((Path(root) / f).read_text())
    (store / ".zmetadata").write_text(json.dumps({"zarr_consolidated_format": 1, "metadata": md}, indent=1))


def main():
    src, outdir, sizes = Path(sys.argv[1]), Path(sys.argv[2]), sorted(int(x) for x in sys.argv[3:])
    t0 = time.time()
    xattrs = json.loads((src / "X" / ".zattrs").read_text())
    n_total, n_vars = xattrs["shape"]
    stores = {n: outdir / f"tahoe95_first{n}.zarr" for n in sizes}
    for n, d in stores.items():
        if d.exists():
            sys.exit(f"{d} exists")
    for n, d in stores.items():
        link_tree(src, d, n, n_total)
        print(f"linked {d.name} {time.time() - t0:.0f}s", flush=True)
    ip = Reader(src / "X" / "indptr").get(0, n_vars + 1)
    ri, rd = Reader(src / "X" / "indices"), Reader(src / "X" / "data")
    wi = {n: Writer(d / "X" / "indices", ri.m) for n, d in stores.items()}
    wd = {n: Writer(d / "X" / "data", rd.m) for n, d in stores.items()}
    new_ip = {n: np.zeros(n_vars + 1, np.int64) for n in sizes}
    for j in range(n_vars):
        a, b = int(ip[j]), int(ip[j + 1])
        if b > a:
            idx = ri.get(a, b)
            if len(idx) > 1 and not np.all(idx[1:] > idx[:-1]):
                sys.exit(f"column {j}: row indices not strictly ascending")
            cnt = {n: int(np.searchsorted(idx, n)) for n in sizes}
            dat = rd.get(a, a + max(cnt.values()))
            for n in sizes:
                wi[n].add(idx[:cnt[n]])
                wd[n].add(dat[:cnt[n]])
        else:
            cnt = {n: 0 for n in sizes}
        for n in sizes:
            new_ip[n][j + 1] = new_ip[n][j] + cnt[n]
        if b > a:
            print(f"col {j} nnz {b - a} {time.time() - t0:.0f}s", flush=True)
    for n, d in stores.items():
        wi[n].close(); wd[n].close()
        assert wi[n].n == wd[n].n == new_ip[n][-1]
        w = Writer(d / "X" / "indptr", meta(src / "X" / "indptr"))
        w.add(new_ip[n]); w.close()
        (d / "X" / ".zattrs").write_text(json.dumps(dict(xattrs, shape=[n, n_vars]), indent=1))
        (d / "X" / ".zgroup").write_text((src / "X" / ".zgroup").read_text())
        consolidate(d)
        (outdir / f"{d.name}.build.json").write_text(json.dumps({
            "n_cells": n, "nnz": int(new_ip[n][-1]), "source": str(src), "script": "cut_prefix.py",
            "seconds": time.time() - t0}, indent=1))
        print(f"done {d.name} nnz {new_ip[n][-1]}", flush=True)


if __name__ == "__main__":
    main()
