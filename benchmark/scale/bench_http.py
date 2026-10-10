#!/usr/bin/env python
"""Per-click cost of AnnZarro on the nested Tahoe-100M stores (HTTP, server side).

For every store (built by build_tahoe.py) and every repetition:

  1. make the store cold (see --cold), start a fresh ``annzarro start`` process
     (127.0.0.1, --no-browser --auth-disabled, default configuration);
  2. replay the requests the web client sends when it opens the dataset
     (``open_*_sub``: default subset in effect; ``open_*_all``: subset off, so
     the client also fetches every cell name), in the client's order;
  3. issue each click once (condition ``cold``), then twice more on the same
     process (``warm``: the same request again; page cache warm, and AnnZarro's
     in-process result cache may answer it), then for other genes/cells
     (``warm_new``: process warm, those columns/rows not read before);
  4. fire 8 concurrent gene-column requests for 8 different genes (``burst8``);
  5. stop the server.

Every numeric click uses the binary wire format (``format=f32``). Each
repetition has two sessions, each on its own fresh process and cold store, so
neither warms the other's caches: the default subset (``*_sub``: the
100,000-cell subset the client opens on above 200,000 cells) and every cell
(``*_all``).

Cold:
  clone    macOS: an APFS clone (``cp -c -R``) of the store; new vnodes, so
           nothing of it is in the unified buffer cache (``purge`` needs root).
  fadvise  Linux: posix_fadvise(DONTNEED) on every file of the store, which
           drops its pages from the local page cache without root (a network
           file system may still cache on its servers).
  none     no eviction (all ``cold`` rows are then only process-cold).

One row per request in --out (CSV). A request that errors or exceeds --timeout
is recorded with its status (or ``timeout``) and that click is not repeated
for larger stores in the same run (``skipped``).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import psutil
import requests
import zarr

import envcapture

API = "/api/v1"
FIELDS = ["site", "store", "n_cells", "rep", "phase", "interaction", "condition", "seq",
          "index", "status", "bytes", "latency_s", "rss_before", "rss_peak", "server_pid",
          "note", "timestamp"]
SUBSET_KEY = json.dumps({"n": 100000, "seed": 0}, separators=(",", ":"))
# What the client under test sends; main() sets these from --client/--exe/--emb.
# "2858fc5": the pre-#62/#63 client (the baseline). "0.3": release-0.3 (d5be664):
# genes from /data/layer/X, categorical obs as codes (categorical=codes), and
# a dataset open without the /data/names probes but with /data/subset/locate.
CLIENT = {"version": "2858fc5", "exe": "", "emb": "X_pca_2d"}
RUN = {}   # this invocation: results path, legacy environment, whether it was recorded


def tree_rss(proc: psutil.Process) -> int:
    total = 0
    for p in [proc] + proc.children(recursive=True):
        try:
            total += p.memory_info().rss
        except psutil.Error:
            pass
    return total


class Sampler(threading.Thread):
    def __init__(self, pid, interval=0.005):
        super().__init__(daemon=True)
        self.proc, self.interval, self.peak, self.running = psutil.Process(pid), interval, 0, True
        self.lock = threading.Lock()

    def run(self):
        while self.running:
            r = tree_rss(self.proc)
            with self.lock:
                self.peak = max(self.peak, r)
            time.sleep(self.interval)

    def reset(self):
        with self.lock:
            self.peak = tree_rss(self.proc)
            return self.peak

    def read(self):
        with self.lock:
            return max(self.peak, tree_rss(self.proc))


class Server:
    def __init__(self, data_dir: Path, port: int, home: Path, timeout: float):
        self.timeout = timeout
        exe = CLIENT["exe"] or Path(sys.executable).with_name("annzarro")
        self.exe = exe
        home.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, ANNZARRO_HOME=str(home), ANNZARRO_HEADLESS="1")
        self.log = open(home / "server.log", "a")
        t0 = time.perf_counter()
        self.proc = subprocess.Popen(
            [str(exe), "start", "--host", "127.0.0.1", "--port", str(port), "--data-dir", str(data_dir),
             "--no-browser", "--auth-disabled"],
            stdout=self.log, stderr=subprocess.STDOUT, env=env, cwd=home, start_new_session=True)
        self.base = f"http://127.0.0.1:{port}{API}"
        self.s = requests.Session()
        while True:
            if self.proc.poll() is not None:
                raise RuntimeError(f"server exited, see {home / 'server.log'}")
            try:
                if self.s.get(self.base + "/config", timeout=2).status_code == 200:
                    break
            except requests.RequestException:
                pass
            if time.perf_counter() - t0 > 120:
                raise RuntimeError("server did not start in 120 s")
            time.sleep(0.05)
        self.startup_s = time.perf_counter() - t0
        self.sampler = Sampler(self.proc.pid)
        self.sampler.start()
        time.sleep(0.3)
        self.rss_idle = self.sampler.reset()

    def get(self, endpoint, params, session=None):
        s = session or self.s
        before = self.sampler.reset() if session is None else tree_rss(self.sampler.proc)
        t0 = time.perf_counter()
        try:
            r = s.get(self.base + endpoint, params=params, timeout=self.timeout)
            body, status = r.content, r.status_code
            note = r.headers.get("X-Annzarro-Encoding", "") or r.headers.get("Content-Type", "")[:24]
        except requests.Timeout:
            body, status, note = b"", "timeout", ""
        except requests.RequestException as e:
            body, status, note = b"", "error", type(e).__name__
        dt = time.perf_counter() - t0
        time.sleep(0.01)
        return {"status": status, "bytes": len(body), "latency_s": dt, "rss_before": before,
                "rss_peak": self.sampler.read(), "server_pid": self.proc.pid, "note": note}, body

    def stop(self):
        self.sampler.running = False
        try:
            os.killpg(self.proc.pid, 15)
            self.proc.wait(20)
        except Exception:
            try:
                os.killpg(self.proc.pid, 9)
            except Exception:
                pass
            self.proc.wait()
        self.log.close()


# ------------------------------------------------------------------ cold
def make_cold(store: Path, mode: str, scratch: Path, tag: str) -> tuple[Path, float]:
    t0 = time.time()
    if mode == "clone":
        dst = scratch / f"cold_{tag}" / store.name
        if dst.parent.exists():
            shutil.rmtree(dst.parent)
        dst.parent.mkdir(parents=True)
        subprocess.run(["cp", "-c", "-R", str(store), str(dst)], check=True)
        return dst, time.time() - t0
    if mode == "fadvise":
        for root, _, files in os.walk(store):
            for f in files:
                try:
                    fd = os.open(os.path.join(root, f), os.O_RDONLY)
                    os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
                    os.close(fd)
                except OSError:
                    pass
    return store, time.time() - t0


def drop_cold(path: Path, store: Path, mode: str):
    if mode == "clone" and path != store:
        shutil.rmtree(path.parent)


# ------------------------------------------------------------------ requests
def pick(store: Path, n: int, rep: int):
    g = zarr.open_group(str(store), mode="r")
    cp = g["X/indptr"][:]
    nnz = np.diff(cp)
    order = np.argsort(-nnz, kind="stable")
    if "gene_order_full" in g["X"].attrs:   # gene-panel store: rank genes as in the all-gene store
        order = np.asarray(g["X"].attrs["gene_order_full"])
    rng = np.random.default_rng(1000 + rep)
    return {
        "gene_high": int(order[0]),                       # most-detected gene
        "gene_mid": int(order[1000]),                     # 1,000th most-detected gene
        "burst": [int(x) for x in order[2000:2008]],
        "gene_high_alt": [int(x) for x in order[1:3]],    # warm_new: 2nd, 3rd most detected
        "gene_mid_alt": [int(x) for x in order[1001:1003]],
        "cell": int(rng.integers(n)),
        "cell_alt": [int(x) for x in rng.integers(n, size=2)],
        "cell_sub": int(rng.integers(min(n, 100_000))),
        "cell_sub_alt": [int(x) for x in rng.integers(min(n, 100_000), size=2)],
        "nnz_high": int(nnz[order[0]]), "nnz_mid": int(nnz[order[1000]]),
    }


def open_sequence(sub):
    """The client's dataset-open requests (static/js/data-manager.js), in order.
    sub: the default subset is in effect; otherwise every cell (subset off)."""
    extra = {"subset": SUBSET_KEY} if sub else {}
    if CLIENT["version"] == "0.3":
        return [("open_datasets", "/datasets", {}), ("open_structure", "/data/dataset_structure", {}),
                ("open_subset", "/data/subset", {"subset": "auto" if sub else "all"}),
                ("open_cells", "/data/cells", dict(extra)), ("open_genes", "/data/genes", {})] + (
                [("open_locate", "/data/subset/locate", {"rows": 0, **extra})] if sub else [])
    return [("open_datasets", "/datasets", {}), ("open_structure", "/data/dataset_structure", {}),
            ("open_subset", "/data/subset", {"subset": "auto" if sub else "all"}),
            ("open_cells", "/data/cells", dict(extra)), ("open_genes", "/data/genes", {}),
            ("open_names_genes", "/data/names", {"entity": "genes", "q": "", "mode": "substring", "limit": 1}),
            ("open_names_cells", "/data/names",
             {"entity": "cells", "q": "", "mode": "substring", "limit": 1, **extra})]


def clicks(ix, sub):
    """(name, endpoint, params, index key, alternative indices for warm_new) of one session."""
    f = {"format": "f32"}
    if CLIENT["version"] == "0.3":
        s = {"subset": SUBSET_KEY, **f} if sub else dict(f)
        v = "sub" if sub else "all"
        return [
            (f"gene_high_{v}", "/data/layer/X", {"cols": ix["gene_high"], **s}, "cols", ix["gene_high_alt"]),
            (f"gene_mid_{v}", "/data/layer/X", {"cols": ix["gene_mid"], **s}, "cols", ix["gene_mid_alt"]),
            (f"obs_num_{v}", "/data/obs", {"columns": "total_counts", **s}, None, []),
            (f"obs_cat_{v}", "/data/obs", {"columns": "cell_line_id", "categorical": "codes", **s}, None, []),
            (f"emb_{v}", f"/data/obsm/{CLIENT['emb']}", {"column_name": "0", **s}, None, []),
        ]
    if sub:
        s = {"subset": SUBSET_KEY, **f}
        return [
            ("gene_high_sub", "/data/X", {"cols": ix["gene_high"], **s}, "cols", ix["gene_high_alt"]),
            ("gene_mid_sub", "/data/X", {"cols": ix["gene_mid"], **s}, "cols", ix["gene_mid_alt"]),
            ("cell_row_csr_sub", "/data/layer/counts_csr", {"rows": ix["cell_sub"], **s}, "rows",
             ix["cell_sub_alt"]),
            ("obs_num_sub", "/data/obs", {"columns": "total_counts", **s}, None, []),
            ("obs_cat_sub", "/data/obs", {"columns": "cell_line_id", **s}, None, []),
            ("emb_sub", "/data/obsm/X_pca_2d", {"column_name": "0", **s}, None, []),
        ]
    return [
        ("gene_high_all", "/data/X", {"cols": ix["gene_high"], **f}, "cols", ix["gene_high_alt"]),
        ("gene_mid_all", "/data/X", {"cols": ix["gene_mid"], **f}, "cols", ix["gene_mid_alt"]),
        ("cell_row_csr_all", "/data/layer/counts_csr", {"rows": ix["cell"], **f}, "rows", ix["cell_alt"]),
        ("obs_num_all", "/data/obs", {"columns": "total_counts", **f}, None, []),
        ("obs_cat_all", "/data/obs", {"columns": "cell_line_id", **f}, None, []),
        ("emb_all", "/data/obsm/X_pca_2d", {"column_name": "0", **f}, None, []),
        ("cell_row_cscscan_all", "/data/X", {"rows": ix["cell"], **f}, "rows", ix["cell_alt"][:1]),
    ]


# ------------------------------------------------------------------ main loop
def run_session(store: Path, n: int, rep: int, sub: bool, a, writer, skip: set):
    """One cold server process: open the dataset as the client does, then click."""
    v = "sub" if sub else "all"
    ix = pick(store, n, rep)
    path, cold_s = make_cold(store, a.cold, Path(a.scratch), f"{store.stem}_{v}_r{rep}")
    srv = Server(path.parent, a.port, Path(a.scratch) / "home", a.timeout)
    if not RUN.get("env_done"):   # once per invocation, with the first server
        envcapture.record(RUN["out"], exe=str(srv.exe), server_root=srv.base.rsplit("/api/", 1)[0],
                          harness_environment=RUN["legacy"])
        RUN["env_done"] = True
    base = dict(site=a.site, store=store.name, n_cells=n, rep=rep)

    def emit(phase, inter, cond, seq, index, res):
        writer(dict(base, phase=phase, interaction=inter, condition=cond, seq=seq, index=index,
                    timestamp=time.time(), **res))

    def srv_row(latency, note=""):
        return {"status": 200, "bytes": 0, "latency_s": latency, "rss_before": srv.rss_idle,
                "rss_peak": srv.sampler.read(), "server_pid": srv.proc.pid, "note": note}
    try:
        emit("server", f"startup_{v}", "cold", 0, "", dict(srv_row(srv.startup_s,
             f"cold prep {cold_s:.1f}s ({a.cold}); nnz_high={ix['nnz_high']} nnz_mid={ix['nnz_mid']}; "
             f"loadavg {os.getloadavg()[0]:.1f}"),
             rss_peak=srv.rss_idle))
        ds = {"dataset_path": str(path)}
        t_open = 0.0
        for name, ep, p in open_sequence(sub):
            res, _ = srv.get(ep, {**ds, **p})
            t_open += res["latency_s"]
            emit("open", f"{name}_{v}", "cold", 0, "", res)
        emit("open", f"open_total_{v}", "cold", 0, "", srv_row(t_open))
        for name, ep, p, key, alts in clicks(ix, sub):
            idx = p.get(key, "") if key else ""
            if name in skip:
                emit("click", name, "cold", 0, idx, {"status": "skipped", "bytes": 0, "latency_s": float("nan"),
                     "rss_before": 0, "rss_peak": 0, "server_pid": srv.proc.pid,
                     "note": "slow at a smaller N, or --skip"})
                continue
            # cold, then `warm` repeats of the same request, then warm_new: other indices
            plan = [("cold", p)] + [("warm", p)] * a.warm + [("warm_new", {**p, key: x}) for x in alts]
            for seq, (cond, pp) in enumerate(plan):
                res, _ = srv.get(ep, {**ds, **pp})
                emit("click", name, cond, seq, pp.get(key, "") if key else "", res)
                if res["status"] != 200 or res["latency_s"] > a.slow:
                    skip.add(name)
                    print(f"    {name}: {res['status']} {res['latency_s']:.1f}s -> not repeated", flush=True)
                    break
        # burst: 8 users each colour by a different gene at once
        bname = f"burst8_{v}"
        if bname not in skip:
            sessions = [requests.Session() for _ in ix["burst"]]
            srv.sampler.reset()
            t0 = time.perf_counter()

            def one(k):
                p = {**ds, "cols": ix["burst"][k], "format": "f32", **({"subset": SUBSET_KEY} if sub else {})}
                ep = "/data/layer/X" if CLIENT["version"] == "0.3" else "/data/X"
                return srv.get(ep, p, session=sessions[k])[0]
            with ThreadPoolExecutor(8) as ex:
                rs = list(ex.map(one, range(8)))
            ok = all(r["status"] == 200 for r in rs)
            emit("burst", bname, "cold", 0, "", dict(srv_row(time.perf_counter() - t0,
                 f"max single {max(r['latency_s'] for r in rs):.3f}"),
                 status=200 if ok else "error", bytes=sum(r["bytes"] for r in rs)))
        emit("server", f"rss_end_{v}", "warm", 0, "", srv_row(0, f"rss now {tree_rss(srv.sampler.proc)}"))
    finally:
        srv.stop()
        drop_cold(path, store, a.cold)
    print(f"  {store.name} {v} rep {rep} done (cold prep {cold_s:.1f}s)", flush=True)


def run_store(store: Path, a, writer, skip: set):
    """Per repetition two sessions, each on a fresh process and a cold store: the default
    subset (as the client opens a dataset over 200,000 cells) and every cell."""
    n = int(zarr.open_group(str(store), mode="r")["X"].attrs["shape"][0])
    for rep in range(a.rep_base, a.rep_base + a.reps):
        for sub in ([True, False] if n > 200_000 else [False]):
            run_session(store, n, rep, sub, a, writer, skip)


def environment(a, stores):
    def sh(cmd):
        try:
            return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception as e:
            return f"n/a ({e})"
    from importlib.metadata import version
    vers = {}
    for p in ["annzarro", "zarr", "numcodecs", "anndata", "numpy", "flask", "werkzeug", "playwright", "scipy"]:
        try:
            vers[p] = version(p)
        except Exception:
            vers[p] = None
    if CLIENT["exe"]:   # the server's own environment, not this harness's
        py = Path(CLIENT["exe"]).with_name("python")
        repo = Path(sh(f"{py} -c 'import annzarro; print(annzarro.__file__)'")).resolve().parents[1]
        vers["server"] = sh(f"{py} -c 'import annzarro, zarr, numcodecs, flask; "
                            f"print(annzarro.__version__, zarr.__version__, numcodecs.__version__, flask.__version__)'")
    else:
        import annzarro
        repo = Path(annzarro.__file__).resolve().parents[1]
    return {
        "site": a.site, "hostname": socket.gethostname(), "platform": platform.platform(),
        "python": sys.version, "packages": vers,
        "annzarro_commit": sh(f"git -C {repo} rev-parse HEAD"),
        "annzarro_branch": sh(f"git -C {repo} rev-parse --abbrev-ref HEAD"),
        "cpu": sh("sysctl -n machdep.cpu.brand_string") if sys.platform == "darwin" else sh("lscpu | head -20"),
        "n_cpu": os.cpu_count(), "ram_bytes": psutil.virtual_memory().total,
        "filesystem": sh(f"df -hT {stores[0]} 2>/dev/null || df -h {stores[0]}") + "\n" + sh(f"mount | grep -F \"$(df -P {stores[0]} | tail -1 | awk '{{print $6}}')\" | head -3"),
        "client": dict(CLIENT), "cold_mode": a.cold, "reps": a.reps, "warm": a.warm, "timeout_s": a.timeout, "slow_s": a.slow,
        "date": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stores", nargs="+", help="store paths, smallest first")
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cold", choices=["clone", "fadvise", "none"],
                    default="clone" if sys.platform == "darwin" else "fadvise")
    ap.add_argument("--scratch", required=True, help="directory for cold clones and the server's home")
    ap.add_argument("--port", type=int, default=8900)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--rep-base", type=int, default=0, help="number of the first rep (one rep per call)")
    ap.add_argument("--warm", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--slow", type=float, default=120, help="a click slower than this is not run at larger N")
    ap.add_argument("--skip", default="", help="comma-separated clicks not to run (recorded as skipped)")
    ap.add_argument("--client", choices=["2858fc5", "0.3"], default="2858fc5",
                    help="which client's requests to replay (see CLIENT)")
    ap.add_argument("--exe", default="", help="annzarro executable (default: next to this python)")
    ap.add_argument("--emb", default="X_pca_2d", help="obsm key of the embedding clicks")
    a = ap.parse_args()
    envcapture.require_clean_bench()
    CLIENT.update(version=a.client, exe=a.exe, emb=a.emb)
    stores = [Path(s).resolve() for s in a.stores]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    new = not out.exists()
    lock = threading.Lock()

    def writer(row):
        with lock, open(out, "a", newline="") as f:
            w = csv.DictWriter(f, FIELDS, extrasaction="ignore")
            w.writerow(row)
    if new:
        with open(out, "w", newline="") as f:
            csv.DictWriter(f, FIELDS).writeheader()
    RUN["out"], RUN["legacy"] = out, environment(a, stores)
    skip: set = set(x for x in a.skip.split(",") if x)
    for st in stores:
        print(f"{st.name}", flush=True)
        run_store(st, a, writer, skip)


if __name__ == "__main__":
    main()
