#!/usr/bin/env python
"""Concurrent cell-row requests against a live-like server (3 sync gunicorn workers).

For each store and each concurrency level N, repeated R times: evict the layer from the
page cache (verified), start a fresh 3-worker server, fire N simultaneous cell-row
requests for N distinct seeded rows, and record each request's latency and the
wall time until the last one returns. This tests whether the live instance's
23-26 s cold cell row can arise from several row requests contending (e.g. one
click requesting rows of several layers) rather than from one request alone.

Usage: bench_concurrency.py --out conc.csv STORE[=label] ...
"""
import argparse
import csv
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchlib as bl  # noqa: E402
from bench_http import Server  # noqa: E402

LAYER = "kompot_de_Xenium_smoothed"
FIELDS = ["run_id", "store_label", "dataset", "workers", "concurrency", "repeat", "request", "index",
          "latency_s", "wall_s", "status", "payload_bytes", "resident_after_evict", "ts", "node", "job_id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--levels", default="1,2,4,8")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("stores", nargs="+")
    a = ap.parse_args()
    venv = os.path.dirname(os.path.dirname(sys.executable))
    run_id = f"{os.environ.get('SLURM_JOB_ID', 'local')}_{int(time.time())}"
    logdir = os.path.join(os.path.dirname(os.path.abspath(a.out)), "logs", run_id)
    data_dir = os.path.join(logdir, "empty-data-dir")
    os.makedirs(data_dir, exist_ok=True)
    new = not os.path.exists(a.out)
    fh = open(a.out, "a", newline="")
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    if new:
        w.writeheader()
    rng = random.Random(20261001)
    for spec in a.stores:
        store, _, label = spec.partition("=")
        label = label or os.path.basename(store)
        files = bl.array_files(store, [f"layers/{LAYER}"])
        for n in [int(x) for x in a.levels.split(",")]:
            for r in range(a.repeats):
                rows = rng.sample(range(75000), n)
                bl.evict(files)
                res = bl.resident_fraction(files)
                srv = Server(venv, logdir, data_dir, f"conc_{label}_n{n}_r{r}", workers=a.workers)
                try:
                    def one(i):
                        t0 = time.perf_counter()
                        resp = requests.get(srv.base + f"/api/v1/data/layer/{LAYER}",
                                            params={"rows": str(i), "dataset_path": store}, timeout=1800)
                        return i, time.perf_counter() - t0, resp.status_code, len(resp.content)
                    ts = bl.now_iso()
                    t0 = time.perf_counter()
                    with ThreadPoolExecutor(max_workers=n) as ex:
                        out = list(ex.map(one, rows))
                    wall = time.perf_counter() - t0
                finally:
                    srv.stop()
                for k, (i, lat, st, nb) in enumerate(out):
                    w.writerow(dict(run_id=run_id, store_label=label, dataset=store, workers=a.workers,
                                    concurrency=n, repeat=r, request=k, index=i, latency_s=lat, wall_s=wall,
                                    status=st, payload_bytes=nb, resident_after_evict=res, ts=ts,
                                    node=os.uname().nodename, job_id=os.environ.get("SLURM_JOB_ID", "")))
                fh.flush()
                print(f"{bl.now_iso()} {label} N={n} r{r}: max={max(x[1] for x in out):.2f}s "
                      f"wall={wall:.2f}s", flush=True)
    fh.close()


if __name__ == "__main__":
    main()
