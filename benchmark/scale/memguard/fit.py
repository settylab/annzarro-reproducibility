#!/usr/bin/env python
"""Fit the memory guard's models (fixed + bytes per point) from memguard.jsonl.

For each step of a run it takes:
  resident  after.heap - (the previous step's after.heap)   on-heap kept
  backing   after.backing - previous                          ArrayBuffers kept
  peak      heap_peak - before.heap (None when no GC ran)     on-heap extra at its highest
  gpu       after.gpu - previous                              GPU-process RSS kept
and fits value = fixed + slope * n per (step kind, path, colour), least squares,
with the largest residual and the upper envelope (max of value/n over the
large n) beside it. Prints a table and writes memguard_fit.json.

Usage: fit.py results/memguard.jsonl
"""
import json
import sys
from collections import defaultdict

STORE_N = {"tahoe95_first1000000.zarr": 1_000_000, "tahoe95_first5000000.zarr": 5_000_000,
           "tahoe95_first20000000.zarr": 20_000_000, "tahoe95_first50000000.zarr": 50_000_000,
           "tahoe_panel_95.6M_plot.zarr": 95_624_334}


def runs(path):
    # one run = consecutive steps from 'load'
    out, cur = [], []
    for line in open(path):
        r = json.loads(line)
        if r["step"] == "load" and cur:
            out.append(cur)
            cur = []
        cur.append(r)
    if cur:
        out.append(cur)
    return out


def path_of(r, n):
    thr = r.get("large_threshold")
    thr = 5_000_000 if thr is None else thr
    return "large" if n > thr else "regular"


def fit(points):
    """Least squares of y = a + b n; returns a, b, max |residual|."""
    if len(points) < 2:
        n, y = points[0]
        return 0.0, y / n if n else 0.0, 0.0
    ns = [p[0] for p in points]
    ys = [p[1] for p in points]
    mn, my = sum(ns) / len(ns), sum(ys) / len(ys)
    sxx = sum((x - mn) ** 2 for x in ns)
    if sxx == 0:
        return my, 0.0, 0.0
    b = sum((x - mn) * (y - my) for x, y in zip(ns, ys)) / sxx
    a = my - b * mn
    return a, b, max(abs(y - a - b * x) for x, y in zip(ns, ys))


def main():
    path = sys.argv[1]
    series = defaultdict(list)
    verdicts = []
    for run in runs(path):
        prev = None
        for r in run:
            n = STORE_N.get(r["store"])
            kind = r["step"].split(":")[0]
            if r["verdict"] != "ok":
                verdicts.append((r["tag"], r["store"], r["color"], r["step"], r["verdict"], r.get("error", "")[:80],
                                 r.get("user_chrome", {}).get("renderers")))
                break
            a = r.get("after") or {}
            if prev and n and kind != "load":
                key = (kind, path_of(r, n), r["color"])
                d = {"resident": a.get("heap", 0) - prev.get("heap", 0),
                     "backing": a.get("backing", 0) - prev.get("backing", 0),
                     "gpu": a.get("gpu", 0) - prev.get("gpu", 0)}
                if r.get("heap_peak") and r.get("before"):
                    d["peak"] = r["heap_peak"] - r["before"]["heap"]
                for k, v in d.items():
                    series[(*key, k)].append((n, v))
            prev = a
    res = {}
    print(f"{'step':12} {'path':8} {'colour':6} {'what':9} {'fixed MB':>9} {'B/pt':>8} {'max res MB':>10} {'n':>3}")
    for key in sorted(series):
        pts = series[key]
        a, b, res_ = fit(pts)
        res["|".join(key)] = {"fixed": a, "per_point": b, "max_residual": res_, "points": pts}
        print(f"{key[0]:12} {key[1]:8} {key[2]:6} {key[3]:9} {a / 1e6:9.1f} {b:8.1f} {res_ / 1e6:10.1f} {len(pts):3}")
    print("\nnot ok:")
    for v in verdicts:
        print("  ", v)
    json.dump({"fits": res, "not_ok": verdicts}, open(path.replace(".jsonl", "_fit.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
