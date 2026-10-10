#!/usr/bin/env python
"""Filesystem health canary: evict, then time whole-file reads of K seeded chunk files
of a fixed array, plus a metadata (stat) pass. Appends one row per run to a CSV, so
every measurement job carries a before/after health reading of the filesystem it used.

Usage: fs_canary.py --array DIR --label LABEL --out canary.csv [--k 40] [--when pre|post]
"""
import argparse
import csv
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchlib as bl  # noqa: E402

FIELDS = ["ts", "node", "job_id", "label", "when", "array", "k", "read_p50_s", "read_p95_s",
          "read_max_s", "mb_per_s_median", "stat_total_s", "resident_after_evict"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--array", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=int, default=40)
    ap.add_argument("--when", default="pre")
    ap.add_argument("--seed", type=int, default=20261002)
    a = ap.parse_args()
    files = sorted(f for f in bl.array_files(os.path.dirname(a.array), [os.path.basename(a.array)])
                   if not os.path.basename(f).startswith("."))
    pick = random.Random(a.seed).sample(files, min(a.k, len(files)))
    t0 = time.perf_counter()
    for f in files:
        os.stat(f)
    stat_s = time.perf_counter() - t0
    bl.evict(pick)
    res = bl.resident_fraction(pick)
    lat, rate = [], []
    for f in pick:
        t0 = time.perf_counter()
        with open(f, "rb") as fh:
            n = len(fh.read())
        dt = time.perf_counter() - t0
        lat.append(dt)
        rate.append(n / 1e6 / dt if dt > 0 else float("nan"))
    lat_sorted = sorted(lat)
    row = dict(ts=bl.now_iso(), node=os.uname().nodename, job_id=os.environ.get("SLURM_JOB_ID", ""),
               label=a.label, when=a.when, array=a.array, k=len(pick),
               read_p50_s=statistics.median(lat), read_p95_s=lat_sorted[int(0.95 * (len(lat) - 1))],
               read_max_s=lat_sorted[-1], mb_per_s_median=statistics.median(rate),
               stat_total_s=stat_s, resident_after_evict=res)
    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
    print("CANARY " + " ".join(f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}" for k, v in row.items()),
          flush=True)


if __name__ == "__main__":
    main()
