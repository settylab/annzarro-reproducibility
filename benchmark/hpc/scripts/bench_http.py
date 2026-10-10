#!/usr/bin/env python
"""End-to-end HTTP benchmark of a self-started AnnZarro server.

For each case and each repeat r (default 5):
  1. evict the touched arrays from the node's page cache (verified by mincore),
  2. start a FRESH gunicorn server (1 sync worker, 127.0.0.1, free port),
  3. phase=cold   : first request for index cold[r]
  4. phase=warm   : the same request again, warm_repeats times (process, app cache
                    and page cache warm)
  5. phase=newidx : one request for an untouched index new[r] in the same,
                    now-warm process (the "next click")
  6. stop the server.
Per request we log latency (time to last byte), time to headers, payload bytes,
the number of values in the decoded response (a correctness check), and the
server worker's VmRSS / VmHWM (peak RSS) read from /proc right after the request.

Usage: bench_http.py --spec cases.json --out results.csv [--env env.json]
"""
import argparse
import csv
import json
import os
import signal
import subprocess
import sys
import time
import zlib

import psutil
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchlib as bl  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIELDS = ["run_id", "experiment", "case_id", "kind", "dataset", "fs", "route", "phase", "repeat",
          "first_touch", "index", "latency_s", "ttfb_s", "payload_bytes", "n_values", "status",
          "server_rss_mb", "server_hwm_mb", "server_baseline_rss_mb", "startup_s",
          "resident_before", "resident_after_evict", "ts", "node", "job_id"]


def count_values(obj):
    if isinstance(obj, list):
        if obj and not isinstance(obj[0], (list, dict)):
            return len(obj)
        return sum(count_values(x) for x in obj)
    if isinstance(obj, dict):
        best = 0
        for k, v in obj.items():
            if k in ("dataset_path",):
                continue
            best = max(best, count_values(v))
        return best
    return 0


class Server:
    def __init__(self, venv, logdir, data_dir, tag, workers=1):
        self.port = bl.free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        env = dict(os.environ)
        env.update({
            "ANNZARRO_BENCH_PORT": str(self.port),
            "ANNZARRO_BENCH_DATA_DIR": data_dir,
            "ANNZARRO_BENCH_LOG": os.path.join(logdir, f"app_{tag}.log"),
            "PYTHONPATH": HERE,
        })
        self.log = open(os.path.join(logdir, f"gunicorn_{tag}.log"), "w")
        t0 = time.perf_counter()
        self.proc = subprocess.Popen(
            [os.path.join(venv, "bin", "gunicorn"), "--workers", str(workers), "--worker-class", "sync",
             "--bind", f"127.0.0.1:{self.port}", "--timeout", "1800", "--chdir", HERE,
             "--access-logfile", "-", "--access-logformat", '%(r)s %(s)s %(B)s %(D)s',
             "wsgi_bench:app"],
            stdout=self.log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        self.sess = requests.Session()
        deadline = time.time() + 180
        while True:
            if self.proc.poll() is not None:
                raise RuntimeError(f"gunicorn exited rc={self.proc.returncode}; see {self.log.name}")
            try:
                if self.sess.get(self.base + "/api/v1/datasets", timeout=5).status_code == 200:
                    break
            except requests.RequestException:
                pass
            if time.time() > deadline:
                self.stop()
                raise RuntimeError("server did not become ready in 180 s")
            time.sleep(0.2)
        self.startup_s = time.perf_counter() - t0
        kids = psutil.Process(self.proc.pid).children()
        if len(kids) != workers:
            self.stop()
            raise RuntimeError(f"expected {workers} gunicorn worker(s), found {len(kids)}")
        self.worker = kids[0].pid
        self.baseline_rss, _ = bl.proc_status_mb(self.worker)

    def get(self, route, params):
        t0 = time.perf_counter()
        r = self.sess.get(self.base + route, params=params, timeout=1800)
        body = r.content
        lat = time.perf_counter() - t0
        rss, hwm = bl.proc_status_mb(self.worker)
        nvals = -1
        if r.status_code == 200:
            nvals = count_values(json.loads(body))
        return dict(latency_s=lat, ttfb_s=r.elapsed.total_seconds(), payload_bytes=len(body),
                    status=r.status_code, n_values=nvals, server_rss_mb=rss, server_hwm_mb=hwm)

    def stop(self):
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(timeout=30)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.proc.wait()
        self.log.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--env", default=None)
    ap.add_argument("--venv", default=os.path.dirname(os.path.dirname(sys.executable)))
    ap.add_argument("--only", default=None, help="comma-separated case_ids to run")
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    R, W, seed = spec.get("repeats", 5), spec.get("warm_repeats", 5), spec.get("seed", 20261001)
    run_id = f"{os.environ.get('SLURM_JOB_ID', 'local')}_{int(time.time())}"
    outdir = os.path.dirname(os.path.abspath(a.out))
    logdir = os.path.join(outdir, "logs", run_id)
    os.makedirs(logdir, exist_ok=True)
    data_dir = os.path.join(logdir, "empty-data-dir")
    os.makedirs(data_dir, exist_ok=True)
    node = os.uname().nodename
    if a.env:
        bl.write_json(a.env, bl.environment(
            sorted({os.path.dirname(c["dataset"]) for c in spec["cases"]}),
            spec.get("annzarro_dir")))
    new = not os.path.exists(a.out)
    fh = open(a.out, "a", newline="")
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    if new:
        w.writeheader()
    only = set(a.only.split(",")) if a.only else None
    for case in spec["cases"]:
        if only and case["case_id"] not in only:
            continue
        cseed = seed + zlib.crc32(case.get("seed_key", case["case_id"]).encode())
        if case.get("axis_len"):
            idx = bl.pick_indices(case["axis_len"], case.get("chunk", 1), 2 * R, cseed)
        else:
            idx = [None] * (2 * R)
        cold_idx, new_idx = idx[:R], idx[R:]
        files = bl.array_files(case["dataset"], case.get("evict", []))
        base = dict(run_id=run_id, experiment=spec["experiment"], case_id=case["case_id"],
                    kind=case["kind"], dataset=case["dataset"], fs=case["fs"], route=case["route"],
                    node=node, job_id=os.environ.get("SLURM_JOB_ID", ""))

        def params_for(i):
            p = {"dataset_path": case["dataset"]}
            for k, v in case.get("params", {}).items():
                p[k] = v.replace("{idx}", str(i)) if isinstance(v, str) else v
            return p

        for r in range(R):
            res_before = bl.resident_fraction(files)
            bl.evict(files)
            res_after = bl.resident_fraction(files)
            srv = Server(a.venv, logdir, data_dir, f"{case['case_id']}_r{r}")
            try:
                common = dict(base, repeat=r, server_baseline_rss_mb=srv.baseline_rss,
                              startup_s=srv.startup_s, resident_before=res_before,
                              resident_after_evict=res_after)
                rows = []
                ts = bl.now_iso()
                rows.append(dict(common, phase="cold", first_touch=int(r == 0), index=cold_idx[r],
                                 ts=ts, **srv.get(case["route"], params_for(cold_idx[r]))))
                for k in range(W):
                    ts = bl.now_iso()
                    rows.append(dict(common, phase="warm", first_touch=0, index=cold_idx[r], ts=ts,
                                     **srv.get(case["route"], params_for(cold_idx[r]))))
                if case.get("axis_len"):
                    ts = bl.now_iso()
                    rows.append(dict(common, phase="newidx", first_touch=0, index=new_idx[r], ts=ts,
                                     **srv.get(case["route"], params_for(new_idx[r]))))
            finally:
                srv.stop()
            for row in rows:
                if row["status"] != 200 or (case.get("expect_len") and row["n_values"] != case["expect_len"]):
                    print(f"WARNING {case['case_id']} r{r} {row['phase']}: status={row['status']} "
                          f"n_values={row['n_values']} expected={case.get('expect_len')}", flush=True)
                w.writerow(row)
            fh.flush()
            print(f"{bl.now_iso()} {case['case_id']} r{r}: cold={rows[0]['latency_s']:.3f}s "
                  f"warm_med={sorted(x['latency_s'] for x in rows[1:1+W])[W//2]:.3f}s "
                  f"hwm={rows[-1]['server_hwm_mb']:.0f}MB resident {res_before:.2f}->{res_after:.2f}",
                  flush=True)
    fh.close()


if __name__ == "__main__":
    main()
