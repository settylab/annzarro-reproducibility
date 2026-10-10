#!/usr/bin/env python
"""Is AnnZarro's cell subset stable at scale? Checks and cost through the HTTP API.

What the design promises (annzarro/core/subset.py, static/js/utils/subset.js)
--------------------------------------------------------------------------------
- A subset is a spec {n, seed, balance?, where?}. The server alone decides the
  cells; the browser only carries the spec in every cell-axis request.
- Every row gets a rank key splitmix64(splitmix64(seed) XOR row) and the
  subset is the n eligible rows with the smallest keys. That is a fixed
  function of (seed, row): the same spec names the same cells on every
  machine, process and numpy version (DETERMINISM), and a larger n with the
  same seed keeps every cell of a smaller n (NESTING in n).
- `where` conditions (AND) restrict the eligible rows first; a missing value
  passes no condition.
- `balance=<obs column>` splits n over the column's groups by water-filling:
  a group smaller than its equal share is taken whole, the rest get
  budget // k each and the remainder one extra each in group (sorted label)
  order; within a group the smallest keys win.
- The resolved indices are cached per (store path, store signature, spec).
- Nothing promises that a store's subset is the same as that of a smaller
  store whose rows are its prefix: the n smallest keys among 2N rows are not
  the n smallest among the first N. What follows from the design, and is
  checked here (ACROSS SIZES), is weaker: the cells the 2N-row subset takes
  from the first N rows are exactly the smallest-keyed cells of those N rows,
  so they are a subset of the N-row store's selection (about n * N / 2N of
  them for an unfiltered spec), and a spec of n cells on the larger store
  never contradicts the smaller one.

Checks per store (one CSV row per measurement; `pass` is the verdict)
--------------------------------------------------------------------------------
determinism  {n: N_MID, seed: 0} on --reps fresh server processes (cold store),
             each asked twice (cold, warm); sha256 of the returned cell names
             must be identical everywhere, and equal to an independent
             recomputation from the documented key function (--verify).
nesting      n in --n (e.g. 50k, 100k, 200k), seeds 0 and 1: each set must be
             contained in the next larger one.
balance      balance=<col> for each --balance column: the per-group counts
             the server reports ("groups") and the counts in the cells it
             returns must equal an independent water-filling of the group
             sizes.
where        {n: N_MID, seed: 0, where: [{col, op: in, values: [v]}]}: every
             returned cell has that value, and the count is
             min(n, cells with that value).
partition    {n: N_MID, seed: 0, part: j} and the same balanced by the first
             --balance column: every part when there are at most
             --partition-all parts, else parts 0, 1, k/2 and k-1. The parts
             must be disjoint; when all were fetched, their union must be
             every cell. With --verify each part's names must equal an
             independent recomputation: unbalanced, key ranks [j*n, (j+1)*n);
             balanced, per group the key ranks after the quotas of parts
             0..j-1 (water-filling repeated on the remaining counts).
across       after all stores (pass the stores smallest first, nested
             prefixes): for each pair, the larger store's determinism subset
             restricted to the smaller store's rows must be contained in the
             smaller store's subset; the overlap is reported.
cost         every request's wall time, server peak RSS (process tree, 5 ms
             sampling) and response bytes, cold (fresh process, cold store)
             and warm (same request again).

Cell identity is the cell name (obs index) returned by /data/cells?subset=...
The stores' names must be unique.

Usage
--------------------------------------------------------------------------------
  bench_subset.py STORE [STORE ...] --site laptop --out results/subset_laptop.csv \
      --scratch /tmp/x [--n 50000,100000,200000] [--balance cell_line_id,drug] \
      [--where-col moa_fine] [--verify] [--reps 3]
  bench_subset.py synth --out DIR --sizes 1000000,2000000     nested synthetic test stores

Failures (HTTP errors, timeouts, server exits) are recorded with the response
text in `detail`; the run continues with the next check.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np
import requests
import zarr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import envcapture  # noqa: E402
from bench_http import Server, drop_cold, environment, make_cold  # noqa: E402

FIELDS = ["site", "store", "n_cells", "check", "spec", "rep", "condition", "endpoint", "status",
          "seconds", "bytes", "rss_before", "rss_peak", "n_returned", "sha256", "pass", "detail",
          "timestamp"]
U64 = np.uint64


# ------------------------------------------------------------------ independent reference
def splitmix64(x):
    with np.errstate(over="ignore"):
        z = x + U64(0x9E3779B97F4A7C15)
        z = (z ^ (z >> U64(30))) * U64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> U64(27))) * U64(0x94D049BB133111EB)
        return z ^ (z >> U64(31))


def expected_rows(n_obs, n, seed, eligible=None):
    """Rows of {n, seed} recomputed from the documented key function."""
    salt = splitmix64(np.array([seed], dtype=U64))[0]
    rows = np.arange(n_obs, dtype=np.int64) if eligible is None else np.flatnonzero(eligible)
    if n >= len(rows):
        return rows
    keys = splitmix64(rows.astype(U64) ^ salt)
    return np.sort(rows[np.argpartition(keys, n - 1)[:n]])


def water_fill(sizes, budget):
    """Group quotas as the design describes (independent implementation)."""
    sizes = np.asarray(sizes, dtype=np.int64)
    quota = np.zeros(len(sizes), np.int64)
    budget = min(budget, int(sizes.sum()))
    remaining = sorted(range(len(sizes)), key=lambda g: (sizes[g], g))
    while remaining:
        share = budget // len(remaining)
        g = remaining[0]
        if sizes[g] <= share:
            quota[g] = sizes[g]; budget -= int(sizes[g]); remaining.pop(0)
            continue
        rest = sorted(remaining)
        quota[rest] = share
        for h in rest[:budget - share * len(rest)]:
            quota[h] += 1
        break
    return quota


def expected_part(n_obs, n, seed, part, labels=None):
    """Rows of part `part` of {n, seed[, balance]} from the documented design."""
    salt = splitmix64(np.array([seed], dtype=U64))[0]
    rows = np.arange(n_obs, dtype=np.int64)
    keys = splitmix64(rows.astype(U64) ^ salt)
    if labels is None:
        return np.sort(rows[np.argsort(keys)][part * n:(part + 1) * n])
    cats, gid = np.unique(labels, return_inverse=True)
    remaining = np.bincount(gid, minlength=len(cats)).astype(np.int64)
    first = np.zeros(len(cats), np.int64)
    for _ in range(part):
        q = water_fill(remaining, n)
        first += q
        remaining -= q
    quota = water_fill(remaining, n)
    out = []
    for g in range(len(cats)):
        r = rows[gid == g]
        out.append(r[np.argsort(keys[gid == g])][first[g]:first[g] + quota[g]])
    return np.sort(np.concatenate(out))


class StoreObs:
    """Direct zarr reads of obs, for the independent expectations."""

    def __init__(self, path):
        self.g = zarr.open_group(str(path), mode="r")
        o = self.g["obs"]
        self.index_key = o.attrs.get("_index", "_index")

    @property
    def n(self):
        return int(self.g["obs"][self.index_key].shape[0])

    def names_at(self, rows):
        arr = self.g["obs"][self.index_key]
        return [str(x) for x in arr.oindex[np.asarray(rows, dtype=np.int64)]] if len(rows) else []

    def labels(self, col):
        """Text labels per cell (categorical codes mapped; -1 = missing)."""
        node = self.g["obs"][col]
        if isinstance(node, zarr.Group) and "codes" in node:
            codes = node["codes"][:]
            cats = np.array([str(c) for c in node["categories"][:]] + ["(missing)"], dtype=object)
            return cats[np.where(codes < 0, len(cats) - 1, codes)]
        return np.array([str(v) for v in node[:]], dtype=object)


# ------------------------------------------------------------------ requests
def sha(names):
    return hashlib.sha256("\n".join(names).encode()).hexdigest()


def cell_names(body):
    js = json.loads(body)
    if isinstance(js, dict):
        for k in ("cells", "data", "names"):
            if k in js:
                return [str(x) for x in js[k]]
    return [str(x) for x in js]


class Session:
    """One fresh server process on a (cold) store, with logging of every request."""

    def __init__(self, store, a, rep, emit):
        self.store, self.a, self.rep, self.emit = store, a, rep, emit
        self.path, self.cold_s = make_cold(store, a.cold, Path(a.scratch), f"subset_{store.stem}_r{rep}")
        self.srv = Server(self.path.parent, a.port, Path(a.scratch) / "home_subset", a.timeout)
        self.seen = set()

    def get(self, check, spec, endpoint, params):
        key = json.dumps(spec, separators=(",", ":"))
        cond = "warm" if (endpoint, key, json.dumps(params, sort_keys=True)) in self.seen else "cold"
        self.seen.add((endpoint, key, json.dumps(params, sort_keys=True)))
        res, body = self.srv.get(endpoint, {"dataset_path": str(self.path), "subset": key, **params})
        row = dict(check=check, spec=key, rep=self.rep, condition=cond, endpoint=endpoint,
                   status=res["status"], seconds=res["latency_s"], bytes=res["bytes"],
                   rss_before=res["rss_before"], rss_peak=res["rss_peak"])
        if res["status"] != 200:
            row["detail"] = body[:400].decode("utf-8", "replace") if body else res.get("note", "")
            row["pass"] = False
            self.emit(**row)
            return None, row
        return body, row

    def subset(self, check, spec):
        """/data/subset then /data/cells for a spec; returns (describe, names)."""
        body, row = self.get(check, spec, "/data/subset", {})
        if body is None:
            return None, None
        info = json.loads(body)
        row["n_returned"] = info.get("n")
        self.emit(**row)
        body, row = self.get(check, spec, "/data/cells", {})
        if body is None:
            return info, None
        names = cell_names(body)
        row.update(n_returned=len(names), sha256=sha(names))
        self.emit(**row)
        return info, names

    def obs_labels(self, check, spec, col):
        body, row = self.get(check, spec, "/data/obs", {"columns": col})
        if body is None:
            return None
        js = json.loads(body)
        data = js.get("data", js)
        vals = data.get(col) if isinstance(data, dict) else data
        cats = (js.get("categories") or {}).get(col)
        if cats is not None and vals and isinstance(vals[0], (int, float)):
            vals = [cats[int(v)] if v is not None and int(v) >= 0 else "(missing)" for v in vals]
        row["n_returned"] = len(vals)
        self.emit(**row)
        return [str(v) for v in vals]

    def close(self):
        self.srv.stop()
        drop_cold(self.path, self.store, self.a.cold)


# ------------------------------------------------------------------ checks
def run_store(store, a, emit_base, keep):
    obs = StoreObs(store)
    n_obs = obs.n
    ns = [int(x) for x in a.n.split(",")]
    n_mid = ns[len(ns) // 2]

    def emit(**kw):
        emit_base(store=store.name, n_cells=n_obs, **kw)

    def verdict(check, spec, ok, detail="", **kw):
        emit(check=check, spec=json.dumps(spec, separators=(",", ":")), endpoint="(check)",
             condition="", rep=kw.pop("rep", ""), status="", **{"pass": bool(ok)}, detail=detail, **kw)
        print(f"    {check:<12} {json.dumps(spec, separators=(',', ':'))[:70]:<70} "
              f"{'PASS' if ok else 'FAIL'} {detail}", flush=True)

    det_spec = {"n": n_mid, "seed": 0}
    hashes = []
    expect_names = None
    if a.verify:
        rows = expected_rows(n_obs, n_mid, 0)
        expect_names = obs.names_at(rows)
    for rep in range(a.reps):
        s = Session(store, a, rep, emit)
        try:
            for _ in range(2):                                   # cold, then warm
                info, names = s.subset("determinism", det_spec)
                if names is not None:
                    hashes.append(sha(names))
                    if rep == 0 and keep is not None:
                        keep[store] = (n_obs, set(names))
            if rep > 0:
                continue
            # nesting, seeds 0 and 1
            for seed in (0, 1):
                sets = []
                for n in ns:
                    _, names = s.subset("nesting", {"n": n, "seed": seed})
                    sets.append(set(names) if names is not None else None)
                for (n1, s1), (n2, s2) in zip(zip(ns, sets), zip(ns[1:], sets[1:])):
                    ok = s1 is not None and s2 is not None and s1 <= s2
                    verdict("nesting", {"n": [n1, n2], "seed": seed}, ok,
                            "" if ok else f"{len(s1 - s2) if s1 and s2 else 'n/a'} cells of the smaller set missing",
                            n_returned=len(s1) if s1 else "")
            # balance
            for col in [c for c in a.balance.split(",") if c]:
                spec = {"n": n_mid, "seed": 0, "balance": col}
                info, names = s.subset("balance", spec)
                got = s.obs_labels("balance", spec, col) if names is not None else None
                if info is None or got is None:
                    continue
                labels = obs.labels(col)
                cats, sizes = np.unique(labels, return_counts=True)
                quota = water_fill(sizes, n_mid)
                exp = {str(c): int(q) for c, q in zip(cats, quota)}
                served = {g: v["shown"] for g, v in (info.get("groups") or {}).items()}
                if info.get("subset") is None:       # n >= cells: no subset, every cell is served
                    served = {str(c): int(k) for c, k in zip(cats, sizes)}
                gc, gn = np.unique(np.array(got, dtype=object), return_counts=True)
                counted = {str(c): int(k) for c, k in zip(gc, gn)}
                exp_nz = {k: v for k, v in exp.items() if v}
                served_nz = {k: v for k, v in served.items() if v}
                ok = served_nz == exp_nz and counted == exp_nz
                worst = max((abs(counted.get(k, 0) - v) for k, v in exp_nz.items()), default=0)
                verdict("balance", spec, ok,
                        f"{len(exp_nz)} groups, quota {min(exp_nz.values())}-{max(exp_nz.values())}, "
                        f"max |returned - expected| = {worst}; server groups {'match' if served_nz == exp_nz else 'DIFFER'}",
                        n_returned=len(got))
            # where
            if a.where_col:
                labels = obs.labels(a.where_col)
                cats, sizes = np.unique(labels, return_counts=True)
                value = a.where_value or str(cats[np.argsort(sizes)[len(sizes) // 2]])   # a mid-sized group
                spec = {"n": n_mid, "seed": 0, "where": [{"col": a.where_col, "op": "in", "values": [value]}]}
                info, names = s.subset("where", spec)
                got = s.obs_labels("where", spec, a.where_col) if names is not None else None
                if got is not None:
                    elig = labels == value
                    want = min(n_mid, int(elig.sum()))
                    ok = len(got) == want and set(got) == {value}
                    detail = f"{a.where_col} in [{value}]: {len(got)} cells, expected {want}"
                    if a.verify and ok:
                        exp = obs.names_at(expected_rows(n_obs, n_mid, 0, eligible=elig))
                        ok = exp == names
                        detail += "; names match the recomputation" if ok else "; names DIFFER from recomputation"
                    verdict("where", spec, ok, detail, n_returned=len(got))
            # partition: disjoint parts that cover every cell
            if a.partition_all >= 0:
                cols = [c for c in a.balance.split(",") if c][:1]
                for bal in [None] + cols:
                    base = {"n": n_mid, "seed": 0, **({"balance": bal} if bal else {})}
                    info, _ = s.subset("partition", base)
                    k = int((info or {}).get("parts", 1))
                    parts = list(range(k)) if k <= a.partition_all else sorted({0, 1, k // 2, k - 1})
                    seen, ok, notes = {}, True, []
                    labels = obs.labels(bal) if (bal and a.verify) else None
                    for j in parts:
                        spec = {**base, "part": j} if j else base
                        pinfo, names = s.subset("partition", spec)
                        if names is None:
                            ok = False
                            notes.append(f"part {j} failed")
                            continue
                        if (pinfo or {}).get("part", 0) != j:
                            ok = False
                            notes.append(f"part {j} reported as {pinfo.get('part')}")
                        seen[j] = set(names)
                        if a.verify:
                            exp = obs.names_at(expected_part(n_obs, n_mid, 0, j, labels))
                            if exp != names:
                                ok = False
                                notes.append(f"part {j} DIFFERS from the recomputation")
                    union = set().union(*seen.values()) if seen else set()
                    overlap = sum(len(v) for v in seen.values()) - len(union)
                    ok = ok and overlap == 0
                    if len(seen) == k:
                        ok = ok and len(union) == n_obs
                        notes.append(f"all {k} parts: {len(union)} distinct cells of {n_obs}")
                    else:
                        notes.append(f"{len(seen)} of {k} parts ({', '.join(map(str, parts))})")
                    notes.append(f"{overlap} cells in two parts")
                    if a.verify:
                        notes.append("each part equals the recomputation" if ok else "")
                    verdict("partition", base, ok, "; ".join(n for n in notes if n), n_returned=len(union))
        except Exception as e:
            emit(check="error", spec="", rep=rep, condition="", endpoint="", status="exception",
                 **{"pass": False}, detail=f"{type(e).__name__}: {e} | {traceback.format_exc()[-600:]}")
            print(f"    ERROR {type(e).__name__}: {e}", flush=True)
        finally:
            s.close()
    ok = len(hashes) == 2 * a.reps and len(set(hashes)) == 1
    detail = f"{len(hashes)} answers, {len(set(hashes))} distinct hashes"
    if a.verify and expect_names is not None and hashes:
        match = sha(expect_names) == hashes[0]
        ok = ok and match
        detail += "; equals the recomputation" if match else "; DIFFERS from the recomputation"
    verdict("determinism", det_spec, ok, detail, sha256=hashes[0] if hashes else "")


def across(keep, a, emit_base):
    stores = sorted(keep, key=lambda s: keep[s][0])
    ns = [int(x) for x in a.n.split(",")]
    n_mid = ns[len(ns) // 2]
    for small, big in zip(stores, stores[1:]):
        n_s, set_s = keep[small]
        n_b, set_b = keep[big]
        prefix_names = set(StoreObs(small).names_at(np.arange(n_s))) if n_s <= 5_000_000 else None
        if prefix_names is None:       # names of the big subset that lie in the small store's rows
            obs_b = StoreObs(big)
            rows = expected_rows(n_b, n_mid, 0)
            in_prefix = set(obs_b.names_at(rows[rows < n_s]))
            in_prefix &= set_b
        else:
            in_prefix = set_b & prefix_names
        ok = in_prefix <= set_s
        overlap = len(set_s & set_b)
        emit_base(store=f"{small.name} vs {big.name}", n_cells=n_b, check="across",
                  spec=json.dumps({"n": n_mid, "seed": 0}), rep="", condition="", endpoint="(check)", status="",
                  n_returned=overlap, **{"pass": ok},
                  detail=(f"{overlap} of {len(set_s)} cells shared; {len(in_prefix)} of the larger store's cells lie "
                          f"in the smaller store's rows (expected about {n_mid * n_s / n_b:.0f}), "
                          f"{'all' if ok else 'NOT all'} of them in the smaller store's subset"))
        print(f"    across {small.name} -> {big.name}: shared {overlap}, in-prefix {len(in_prefix)}, "
              f"{'PASS' if ok else 'FAIL'}", flush=True)


# ------------------------------------------------------------------ synthetic stores
def cmd_synth(argv):
    import anndata as ad
    import pandas as pd
    import scipy.sparse as sp
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--sizes", default="1000000,2000000")
    a = p.parse_args(argv)
    sizes = sorted(int(x) for x in a.sizes.split(","))
    n = sizes[-1]
    rng = np.random.default_rng(20261003)
    # skewed group sizes so balance exercises water-filling (several groups below the equal share)
    w = rng.pareto(1.2, 50) + 0.02
    cell_line = rng.choice(50, n, p=w / w.sum())
    drug = rng.integers(0, 380, n)
    moa = rng.choice(11, n, p=np.r_[0.4, np.full(10, 0.06)])
    obs = pd.DataFrame({
        "cell_line_id": pd.Categorical.from_codes(cell_line, [f"CVCL_{i:04d}" for i in range(50)]),
        "drug": pd.Categorical.from_codes(drug, [f"drug_{i:03d}" for i in range(380)]),
        "moa_fine": pd.Categorical.from_codes(moa, [f"moa_{i}" for i in range(11)]),
        "total_counts": rng.gamma(2, 1000, n).astype(np.float32),
    }, index=[f"c{i:09d}" for i in range(n)])
    emb = rng.normal(size=(n, 2)).astype(np.float32)
    ad.settings.zarr_write_format = 2
    for m in sizes:
        X = sp.random(m, 20, density=0.05, format="csc", dtype=np.float32, random_state=1)
        adata = ad.AnnData(X=X, obs=obs.iloc[:m].copy(), obsm={"X_pca_2d": emb[:m]},
                           var=pd.DataFrame(index=[f"g{j}" for j in range(20)]))
        label = f"{m // 1_000_000}M" if m % 1_000_000 == 0 else f"{m // 1000}k"
        path = Path(a.out) / f"n{label}" / f"synth_{label}.zarr"
        path.parent.mkdir(parents=True, exist_ok=True)
        adata.write_zarr(path)
        print(path)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "synth":
        return cmd_synth(sys.argv[2:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stores", nargs="+", help="stores, smallest first (nested prefixes for the across check)")
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--cold", choices=["clone", "fadvise", "none"],
                    default="clone" if sys.platform == "darwin" else "fadvise")
    ap.add_argument("--port", type=int, default=8902)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--n", default="50000,100000,200000", help="nesting sizes; the middle one is used elsewhere")
    ap.add_argument("--balance", default="cell_line_id,drug")
    ap.add_argument("--where-col", default="moa_fine")
    ap.add_argument("--where-value", default=None)
    ap.add_argument("--partition-all", type=int, default=30,
                    help="check every part when there are at most this many, else a sample; -1 skips the check")
    ap.add_argument("--verify", action="store_true",
                    help="also recompute the expected cells from the documented key function (reads obs names)")
    a = ap.parse_args()
    envcapture.require_clean_bench()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        with open(out, "w", newline="") as f:
            csv.DictWriter(f, FIELDS).writeheader()
    stores = [Path(s).resolve() for s in a.stores]
    env = environment(argparse.Namespace(site=a.site, cold=a.cold, reps=a.reps, warm=1, timeout=a.timeout,
                                         slow=a.timeout), stores)
    env["subset_checks"] = {"n": a.n, "balance": a.balance, "where_col": a.where_col, "verify": a.verify}
    envcapture.record(out, exe=str(Path(sys.executable).with_name("annzarro")), harness_environment=env)
    lock = threading.Lock()

    def emit(**kw):
        row = {"site": a.site, "timestamp": time.time(), **kw}
        with lock, open(out, "a", newline="") as f:
            csv.DictWriter(f, FIELDS, extrasaction="ignore").writerow(row)
    keep = {}
    for st in stores:
        print(st.name, flush=True)
        run_store(st, a, emit, keep)
    if len(keep) > 1:
        across(keep, a, emit)


if __name__ == "__main__":
    main()
