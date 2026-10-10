#!/usr/bin/env python
"""Raw zarr read benchmark: the exact slicing call AnnZarro's dense path issues
(annzarro/core/zarr_reader.py `_get_dense_array`: `array[row_indices]` for a row,
`array[:, col_indices]` for a column), without Flask, JSON or HTTP.

Takes the SAME spec as bench_http.py and runs only its dense cases
(dense_layer_*, obsp_dense_row, varp_dense_row), with the SAME seeded indices,
so (raw, http) pairs differ only in the serving layer. Protocol per repeat r:
evict the array from the page cache (verified), open a fresh zarr handle,
phase=cold read, warm_repeats x phase=warm read of the same index, one
phase=newidx read of an untouched index.

Usage: bench_raw.py --spec cases.json --out raw.csv
"""
import argparse
import csv
import json
import os
import sys
import time
import zlib

import zarr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchlib as bl  # noqa: E402

DENSE = {"dense_layer_gene_col", "dense_layer_cell_row", "obsp_dense_row", "varp_dense_row"}
FIELDS = ["run_id", "experiment", "case_id", "kind", "dataset", "fs", "array", "op", "phase", "repeat",
          "first_touch", "index", "latency_s", "n_values", "proc_hwm_mb", "resident_before",
          "resident_after_evict", "ts", "node", "job_id"]


def array_path(route):
    tail = route.split("/api/v1/data/")[1]
    kind, name = tail.split("/", 1)
    return {"layer": "layers", "obsp": "obsp", "varp": "varp"}[kind] + "/" + name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    R, W, seed = spec.get("repeats", 5), spec.get("warm_repeats", 5), spec.get("seed", 20261001)
    run_id = f"{os.environ.get('SLURM_JOB_ID', 'local')}_{int(time.time())}"
    node = os.uname().nodename
    new = not os.path.exists(a.out)
    fh = open(a.out, "a", newline="")
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    if new:
        w.writeheader()
    only = set(a.only.split(",")) if a.only else None
    for case in spec["cases"]:
        if case["kind"] not in DENSE or (only and case["case_id"] not in only):
            continue
        arr = array_path(case["route"])
        op = "row" if "rows" in case["params"] else "col"
        cseed = seed + zlib.crc32(case.get("seed_key", case["case_id"]).encode())
        idx = bl.pick_indices(case["axis_len"], case.get("chunk", 1), 2 * R, cseed)
        files = bl.array_files(case["dataset"], [arr])
        base = dict(run_id=run_id, experiment=spec["experiment"], case_id=case["case_id"],
                    kind=case["kind"], dataset=case["dataset"], fs=case["fs"], array=arr, op=op,
                    node=node, job_id=os.environ.get("SLURM_JOB_ID", ""))

        def read(z, i):
            t0 = time.perf_counter()
            v = z[[i]] if op == "row" else z[:, [i]]
            dt = time.perf_counter() - t0
            return dt, int(v.size), bl.proc_status_mb(os.getpid())[1]

        for r in range(R):
            rb = bl.resident_fraction(files)
            bl.evict(files)
            ra = bl.resident_fraction(files)
            z = zarr.open_array(os.path.join(case["dataset"], arr), mode="r")
            common = dict(base, repeat=r, resident_before=rb, resident_after_evict=ra)
            rows = []
            for phase, i, ft in ([("cold", idx[r], int(r == 0))] + [("warm", idx[r], 0)] * W
                                 + [("newidx", idx[R + r], 0)]):
                ts = bl.now_iso()
                dt, nv, hwm = read(z, i)
                rows.append(dict(common, phase=phase, index=i, first_touch=ft, latency_s=dt,
                                 n_values=nv, proc_hwm_mb=hwm, ts=ts))
            for row in rows:
                w.writerow(row)
            fh.flush()
            print(f"{bl.now_iso()} RAW {case['case_id']} r{r}: cold={rows[0]['latency_s']:.3f}s "
                  f"warm={rows[1]['latency_s']:.3f}s new={rows[-1]['latency_s']:.3f}s "
                  f"resident {rb:.2f}->{ra:.2f}", flush=True)
    fh.close()


if __name__ == "__main__":
    main()
