#!/usr/bin/env python
"""Validate an HLCA AnnZarro store through annzarro's HTTP API against the source h5ad.

Starts `annzarro start` (the installed annzarro, e.g. 0.2.0) on 127.0.0.1 with the store's directory
as data dir, then for 3 random cells (seed 0, among the store's cells) and the genes SFTPC plus 2
random genes compares:
- /data/info: n_obs, n_vars;
- /data/obs (ann_level_1 and donor_id) at the 3 cells;
- /data/obsm/X_umap columns 0 and 1 at the 3 cells;
- /data/X gene columns: the value at the 3 cells, plus the stored-value count against the source;
- /data/layer/normalized_csr rows of the 3 cells;
- /data/obsp/connectivities rows of the 3 cells.
Each check records pass/fail and a short excerpt of the raw response. Output: <store>.validate.json.

  validate_hlca.py --store hlca_full.zarr --src HLCA.h5ad [--port 8911]
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import h5py
import numpy as np
import requests
import zarr

API = "/api/v1"


def row_of(f, key, r):
    ip = f[f"{key}/indptr"]
    s, e = int(ip[r]), int(ip[r + 1])
    return f[f"{key}/indices"][s:e].astype(np.int64), f[f"{key}/data"][s:e].astype(np.float32)


def dense_row(f, key, r, width):
    idx, val = row_of(f, key, r)
    out = np.zeros(width, np.float32)
    out[idx] = val
    return out


def as_array(resp):
    """A numeric response as a flat array. Binary (format=f32, annzarro core/array_response.py): headers
    X-Annzarro-Shape / -Dtype / -Encoding / -Nnz; dense = prod(shape) values, sparse = nnz values then nnz
    uint32 flat row-major positions. JSON otherwise (nested anywhere under 'data')."""
    ct = resp.headers.get("Content-Type", "")
    if "octet-stream" in ct:
        shape = [int(x) for x in resp.headers["X-Annzarro-Shape"].split(",")]
        dt = np.dtype("<f4" if resp.headers.get("X-Annzarro-Dtype", "float32") == "float32" else "<f8")
        size = int(np.prod(shape))
        if resp.headers.get("X-Annzarro-Encoding", "dense") == "sparse":
            nnz = int(resp.headers["X-Annzarro-Nnz"])
            vals = np.frombuffer(resp.content, dtype=dt, count=nnz)
            pos = np.frombuffer(resp.content, dtype="<u4", count=nnz, offset=nnz * dt.itemsize)
            out = np.zeros(size, dt)
            out[pos] = vals
            return out
        return np.frombuffer(resp.content, dtype=dt, count=size)
    j = resp.json()
    d = j.get("data", j) if isinstance(j, dict) else j
    while isinstance(d, dict) and len(d) == 1:
        d = next(iter(d.values()))
    if isinstance(d, dict) and "values" in d:
        d = d["values"]
    return np.asarray(d, dtype=np.float32).ravel()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--port", type=int, default=8911)
    a = ap.parse_args()
    store = Path(a.store).resolve()
    g = zarr.open_group(str(store), mode="r", use_consolidated=True)
    n, G = g["X"].attrs["shape"]
    names = np.array([str(x) for x in g["var/_index"][:]], dtype=object)
    rng = np.random.default_rng(0)
    cells = sorted(int(x) for x in rng.choice(n, 3, replace=False))
    genes = [int(np.flatnonzero(names == "SFTPC")[0])] + [int(x) for x in rng.choice(G, 2, replace=False)]
    home = store.parent / f".validate_home_{store.name}"
    home.mkdir(exist_ok=True)
    env = dict(os.environ, ANNZARRO_HOME=str(home), ANNZARRO_HEADLESS="1")
    lf = open(home / "server.log", "w")
    p = subprocess.Popen([str(Path(sys.executable).with_name("annzarro")), "start", "--host", "127.0.0.1",
                          "--port", str(a.port), "--data-dir", str(store.parent), "--no-browser", "--auth-disabled"],
                         stdout=lf, stderr=subprocess.STDOUT, env=env, cwd=home, start_new_session=True)
    base = f"http://127.0.0.1:{a.port}{API}"
    t0 = time.time()
    while True:
        try:
            if requests.get(base + "/config", timeout=2).status_code == 200:
                break
        except requests.RequestException:
            pass
        if p.poll() is not None or time.time() - t0 > 300:
            sys.exit(f"server did not start; see {home / 'server.log'}")
        time.sleep(0.2)
    ds = {"dataset_path": str(store)}
    checks = []

    def check(name, ok, detail, resp=None, seconds=None):
        excerpt = "" if resp is None else resp.text[:300] if "json" in resp.headers.get("Content-Type", "") else f"<{len(resp.content)} bytes {resp.headers.get('Content-Type','')}>"
        checks.append({"check": name, "pass": bool(ok), "detail": detail, "seconds": seconds, "response": excerpt})
        print(("PASS " if ok else "FAIL ") + name, detail, flush=True)

    def get(ep, params):
        t = time.perf_counter()
        r = requests.get(base + ep, params={**ds, **params}, timeout=1800)
        return r, round(time.perf_counter() - t, 3)

    try:
        with h5py.File(a.src, "r") as f:
            r, s = get("/data/info", {})
            j = r.json() if r.ok else {}
            txt = json.dumps(j)
            check("info", r.ok and str(n) in txt and str(G) in txt, f"expects n_obs={n} n_vars={G}", r, s)
            src_obs = {}
            import anndata as ad
            for col in ("ann_level_1", "donor_id"):
                src = ad.io.read_elem(f[f"obs/{col}"])
                want = [str(src[c]) for c in cells]
                r, s = get("/data/obs", {"columns": col, "rows": ",".join(map(str, cells))})
                got = r.json().get("data", {}).get(col) if r.ok else None
                if isinstance(got, list) and got and isinstance(got[0], (int, np.integer)):
                    cats = r.json().get("categories", {}).get(col, [])
                    got = [cats[int(x)] for x in got]
                check(f"obs/{col}", got is not None and [str(x) for x in got] == want, f"want {want} got {got}", r, s)
            for c in (0, 1):
                want = np.asarray(f["obsm/X_umap"][cells, c], np.float32)
                r, s = get("/data/obsm/X_umap", {"column_name": str(c), "rows": ",".join(map(str, cells)), "format": "f32"})
                got = as_array(r) if r.ok else None
                check(f"obsm/X_umap[:, {c}]", got is not None and np.allclose(got, want), f"want {want.tolist()} got {None if got is None else got.tolist()}", r, s)
            for gi in genes:
                r, s = get("/data/X", {"cols": str(gi), "format": "f32"})
                col = as_array(r) if r.ok else None
                want = np.array([dense_row(f, "X", c, G)[gi] for c in cells], np.float32)
                got = None if col is None or len(col) != n else col[cells]
                nz_store = int(np.diff(g["X/indptr"][gi:gi + 2])[0])
                ok = got is not None and np.array_equal(got, want) and int((col != 0).sum()) <= nz_store
                if col is not None and len(col) == n:   # also 3 cells where the store's column is non-zero
                    nzc = np.flatnonzero(col)
                    if nzc.size:
                        pick = sorted(int(x) for x in rng.choice(nzc, min(3, nzc.size), replace=False))
                        want_nz = np.array([dense_row(f, "X", c, G)[gi] for c in pick], np.float32)
                        ok_nz = np.array_equal(col[pick], want_nz)
                        check(f"X gene {names[gi]} non-zero cells", ok_nz, f"at {pick}: want {want_nz.tolist()} got {col[pick].tolist()}", r, s)
                check(f"X gene {names[gi]} (col {gi})", ok, f"at cells {cells}: want {want.tolist()} got {None if got is None else got.tolist()}; "
                      f"len {None if col is None else len(col)}; nonzero {None if col is None else int((col != 0).sum())} <= stored {nz_store}", r, s)
            for c in cells:
                want = dense_row(f, "X", c, G)
                r, s = get("/data/layer/normalized_csr", {"rows": str(c), "format": "f32"})
                got = as_array(r) if r.ok else None
                check(f"layers/normalized_csr row {c}", got is not None and len(got) == G and np.array_equal(got, want),
                      f"len {None if got is None else len(got)}, nonzero want {int((want != 0).sum())} got {None if got is None else int((got != 0).sum())}", r, s)
                wantp = dense_row(f, "obsp/connectivities", c, n_all := int(f["obsp/connectivities"].attrs["shape"][0]))[:n]
                r, s = get("/data/obsp/connectivities", {"rows": str(c), "format": "f32"})
                got = as_array(r) if r.ok else None
                check(f"obsp/connectivities row {c}", got is not None and len(got) == n and np.allclose(got, wantp),
                      f"len {None if got is None else len(got)}, nonzero want {int((wantp != 0).sum())} got {None if got is None else int((got != 0).sum())}", r, s)
    finally:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(30)
        lf.close()
    res = {"store": str(store), "src": a.src, "cells": cells, "genes": [str(names[x]) for x in genes],
           "n_pass": sum(c["pass"] for c in checks), "n_checks": len(checks), "checks": checks}
    (store.parent / (store.name + ".validate.json")).write_text(json.dumps(res, indent=1, default=str))
    print(f"{res['n_pass']}/{res['n_checks']} checks passed")


if __name__ == "__main__":
    main()
