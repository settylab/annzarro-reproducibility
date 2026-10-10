#!/usr/bin/env python
"""Measure AnnZarro per-interaction latency, payload size and server memory.

Every measurement goes through the real HTTP API of an AnnZarro server
(``python -m annzarro.server``, or ``annzarro start`` on builds without it; Flask/werkzeug, bound to 127.0.0.1) that this
script starts and stops itself.  Datasets come from ``generate_data.py``.

Conditions (column ``condition``)
---------------------------------
cold         First request to a freshly started server process on a fresh APFS
             clone of the store (``cp -c``).  A clone is a new file system
             object with no pages in the macOS unified buffer cache, so its
             chunks are read from the SSD.  One cold sample per server process;
             repeated ``--reps`` times with a new process and a new clone.
cold_new     Following requests on that same process and clone for *other*
             indices: process warm, data not yet in the page cache (unless the
             index shares a chunk with an earlier request).
warm_new     Server on the original store after all of its files were read once
             (page cache warm), one request per new random index.  This is the
             best case for "click another gene/cell".
warm_repeat  Same index requested again; hits AnnZarro's in-process result cache
             where that exists (obs, obsm, obsp/varp) and re-reads otherwise
             (X, layers: never cached, see FINDINGS.md).
warmup       Discarded first request of the warm phase (kept for completeness).

Experiments (sub-commands; each writes ``results/<experiment>.csv``)
-------------------------------------------------------------------
scale      scale/cells_<n>.zarr: layer gene column, layer cell row, obsm column,
           obs float column, sparse kNN obsp row, dataset open (structure, cell names)
sweep      sweep/n<n>/<tag>.zarr: layer gene column and cell row per chunk shape
obsp       pairwise/obsp_<n>.zarr: dense kernel row per chunk shape
varp       pairwise/varp_<g>.zarr: dense gene-correlation row per chunk shape
sparse     sparse/X_<n>_<csr|csc>.zarr: X gene column and X cell row
breakdown  in-process split of one request into zarr read, ndarray.tolist(),
           Flask jsonify and the remaining HTTP/werkzeug overhead
env        write results/environment.json only

Usage: ``python run_benchmark.py all`` or one experiment, e.g.
``python run_benchmark.py sweep --reps 5``.
"""

from __future__ import annotations

import argparse
import importlib.util
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
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import psutil
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent / "scale"))
import envcapture  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "data" / "bench"
RESULTS = HERE / "results"
COLD_DIR = ROOT / "_cold"
RUN_DIR = ROOT / "server_run"
# Checkout whose commit is recorded with each run; override with ANNZARRO_REPO.
ANNZARRO_REPO = Path(os.environ.get("ANNZARRO_REPO", HERE.parents[1].parent / "annzarro"))
PY = sys.executable          # the server's interpreter; --server-python (or ANNZARRO_PYTHON) overrides
API = "/api/v1"
# What the client asks for. "binary" (default) is what the web client sends since AnnZarro #44:
# format=f32 on every numeric slice and categorical=codes on obs/var columns (v0.3.1
# static/js/data-manager.js _fetchVector, utils/wire.js). "json" (--wire json) is the old JSON route.
WIRE = "binary"
BINARY_PREFIXES = ("/data/layer/", "/data/X", "/data/obsm/", "/data/obsp/", "/data/varp/", "/data/varm/",
                   "/data/obs", "/data/var")
SUFFIX = ""                    # --suffix: results/<experiment><suffix>.csv, environment<suffix>.json
TIMEOUT = 3600

FIELDS = [
    "experiment", "store", "family", "n_cells", "n_genes", "matrix", "layout", "chunk_tag",
    "chunks", "interaction", "condition", "rep", "seq", "index", "status", "bytes", "n_values",
    "latency_s", "rss_base_bytes", "rss_peak_bytes", "server_pid", "timestamp", "wire", "encoding",
]


# ------------------------------------------------------------------ server control
class RssSampler(threading.Thread):
    """Poll a process's RSS every ``interval`` seconds and track the peak."""

    def __init__(self, pid: int, interval: float = 0.002):
        super().__init__(daemon=True)
        self.proc = psutil.Process(pid)
        self.interval = interval
        self.peak = 0
        self.overall_peak = 0
        self.running = True
        self.lock = threading.Lock()

    def run(self):
        while self.running:
            try:
                rss = self.proc.memory_info().rss
            except psutil.Error:
                break
            with self.lock:
                self.peak = max(self.peak, rss)
                self.overall_peak = max(self.overall_peak, rss)
            time.sleep(self.interval)

    def current(self) -> int:
        return self.proc.memory_info().rss

    def reset(self) -> None:
        with self.lock:
            self.peak = self.current()

    def read_peak(self) -> int:
        with self.lock:
            return max(self.peak, self.current())


class Server:
    """An AnnZarro server subprocess on a free localhost port."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.port = s.getsockname()[1]
        s.close()
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        # The published runs used `python -m annzarro.server` (cache_memory_mb=1000, debug off).
        # AnnZarro PR #47 removed that entry point; `annzarro start` with the cache pinned to
        # the same 1000 MB reproduces it. Older checkouts still have the module.
        env = dict(os.environ, ANNZARRO_HEADLESS="1", ANNZARRO_SERVER_CACHE_MEMORY_MB="1000",
                   ANNZARRO_HOME=str(RUN_DIR / "annzarro_home"))
        self.log = open(RUN_DIR / "server_stdout.log", "w")
        has_module = subprocess.run([PY, "-c", "import importlib.util, sys; "
                                     "sys.exit(importlib.util.find_spec('annzarro.server.__main__') is None)"],
                                    cwd=RUN_DIR).returncode == 0   # the server interpreter's, not this one's
        if has_module:
            cmd = [PY, "-m", "annzarro.server", "--data-dir", str(data_dir), "--port", str(self.port)]
        else:
            cmd = [PY, "-m", "annzarro.cli", "start", "--host", "127.0.0.1", "--port", str(self.port),
                   "--data-dir", str(data_dir), "--no-browser", "--auth-disabled"]
        self.proc = subprocess.Popen(
            cmd,
            stdout=self.log, stderr=subprocess.STDOUT, cwd=RUN_DIR, env=env)
        self.base = f"http://127.0.0.1:{self.port}{API}"
        self.session = requests.Session()
        t0 = time.time()
        while True:
            if self.proc.poll() is not None:
                raise RuntimeError(f"server died, see {RUN_DIR / 'server_stdout.log'}")
            try:
                if self.session.get(self.base + "/datasets", timeout=2).status_code == 200:
                    break
            except requests.RequestException:
                pass
            if time.time() - t0 > 60:
                raise RuntimeError("server did not start within 60 s")
            time.sleep(0.05)
        time.sleep(0.2)
        self.sampler = RssSampler(self.proc.pid)
        self.sampler.start()
        self.rss_base = self.sampler.current()

    def get(self, endpoint: str, params: dict) -> dict:
        self.sampler.reset()
        t0 = time.perf_counter()
        r = self.session.get(self.base + endpoint, params=params, timeout=TIMEOUT)
        body = r.content
        dt = time.perf_counter() - t0
        time.sleep(0.01)  # let the sampler see post-response memory too
        out = {"status": r.status_code, "bytes": len(body), "latency_s": dt,
               "rss_peak_bytes": self.sampler.read_peak(), "rss_base_bytes": self.rss_base,
               "server_pid": self.proc.pid}
        if r.headers.get("Content-Type", "").startswith("application/octet-stream"):
            # binary reply (utils/wire.js): values = nnz (sparse) or prod(shape) (dense, categorical)
            enc = r.headers.get("X-Annzarro-Encoding", "dense")
            if r.headers.get("X-Annzarro-Categories-Bytes"):
                enc = "categorical"
            shape = [int(x) for x in r.headers.get("X-Annzarro-Shape", "0").split(",") if x]
            out["wire"], out["encoding"] = "binary", enc
            out["n_values"] = (int(r.headers.get("X-Annzarro-Nnz", 0)) if enc == "sparse"
                               else int(np.prod(shape)) if shape else -1)
        else:
            out["wire"], out["encoding"] = "json", ""
            try:
                out["n_values"] = _count_values(r.json())
            except ValueError:
                out["n_values"] = -1
        if r.headers.get("Content-Encoding"):
            out["content_encoding"] = r.headers["Content-Encoding"]
        return out

    def stop(self) -> None:
        self.sampler.running = False
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.log.close()


def _count_values(js) -> int:
    """Number of scalar values in the response's payload field."""
    d = js.get("data", js.get("cells", js)) if isinstance(js, dict) else js
    if isinstance(d, dict):
        return sum(_count_values({"data": v}) for v in d.values())
    if isinstance(d, list):
        if d and isinstance(d[0], list):
            return sum(len(x) for x in d)
        return len(d)
    return 1


# ------------------------------------------------------------------ store helpers
def clone_store(src: Path, tag: str) -> Path:
    """APFS clone (copy-on-write) of a store: new vnodes, no cached pages."""
    COLD_DIR.mkdir(parents=True, exist_ok=True)
    dst = COLD_DIR / f"{tag}_{src.name}"
    if dst.exists():
        shutil.rmtree(dst)
    subprocess.run(["cp", "-c", "-R", str(src), str(dst)], check=True)
    return dst


def prewarm(path: Path) -> float:
    """Read every file of a store once so that it sits in the page cache."""
    t0 = time.time()
    for f in path.rglob("*"):
        if f.is_file():
            with open(f, "rb") as fh:
                while fh.read(16 * 2**20):
                    pass
    return time.time() - t0


def manifest() -> dict:
    return json.loads((ROOT / "manifest.json").read_text())


# ------------------------------------------------------------------ interactions
@dataclass
class Interaction:
    """One user action that maps to one GET request."""
    name: str
    endpoint: str
    param: str | None          # query parameter that carries the index
    n_index: int               # size of the index space (1 = no index)
    extra: dict = field(default_factory=dict)
    matrix: str = ""

    def params(self, store: Path, idx: int) -> dict:
        p = {"dataset_path": str(store), **self.extra}
        if WIRE == "binary" and self.endpoint.startswith(BINARY_PREFIXES):
            p["format"] = "f32"
            if self.endpoint in ("/data/obs", "/data/var"):
                p["categorical"] = "codes"
        if self.param:
            p[self.param] = str(idx)
        return p


def pick_indices(n_index: int, k: int, seed: int) -> list[int]:
    rng = np.random.default_rng(seed)
    if n_index <= 1:
        return [0] * k
    if n_index < k:
        return list(rng.integers(0, n_index, k))
    return [int(i) for i in rng.choice(n_index, size=k, replace=False)]


@dataclass
class Target:
    """A store plus the interactions to measure on it."""
    store: Path
    meta: dict
    interactions: list[Interaction]


def measure_target(exp: str, tgt: Target, reps: int, n_cold_new: int, n_warm: int,
                   writer, skip_cold: bool = False) -> None:
    """Run cold, cold_new, warm_new and warm_repeat for every interaction of a store."""
    store = tgt.store
    seed0 = zlib.crc32(f"{exp}/{store.name}".encode())
    base = {k: tgt.meta.get(k, "") for k in ["family", "n_cells", "n_genes", "layout", "chunk_tag", "chunks"]}
    base.update(experiment=exp, store=str(store.relative_to(ROOT)))

    def emit(inter, cond, rep, seq, idx, res):
        row = dict(base, matrix=inter.matrix or inter.endpoint, interaction=inter.name, condition=cond,
                   rep=rep, seq=seq, index=idx, timestamp=time.time(), **res)
        if isinstance(tgt.meta.get("chunks_by_matrix"), dict):
            row["chunks"] = tgt.meta["chunks_by_matrix"].get(inter.matrix, row["chunks"])
            row["chunk_tag"] = tgt.meta.get("tags_by_matrix", {}).get(inter.matrix, row["chunk_tag"])
        writer(row)

    # ---- cold phases: fresh clone per rep, fresh server per interaction
    if not skip_cold:
        for rep in range(reps):
            t0 = time.time()
            clone = clone_store(store, f"r{rep}")
            clone_s = time.time() - t0
            for k, inter in enumerate(tgt.interactions):
                idxs = pick_indices(inter.n_index, 1 + n_cold_new, seed0 + 1000 * rep + k)
                srv = Server(clone.parent)
                try:
                    for seq, idx in enumerate(idxs):
                        res = srv.get(inter.endpoint, inter.params(clone, idx))
                        emit(inter, "cold" if seq == 0 else "cold_new", rep, seq, idx, res)
                        if inter.n_index <= 1:
                            break
                finally:
                    srv.stop()
            shutil.rmtree(clone)
            print(f"    cold rep {rep}: clone {clone_s:.1f}s", flush=True)

    # ---- warm phases: original store, page cache primed
    pw = prewarm(store)
    srv = Server(store.parent)
    try:
        for k, inter in enumerate(tgt.interactions):
            idxs = pick_indices(inter.n_index, 1 + n_warm, seed0 + 7 + k)
            res = srv.get(inter.endpoint, inter.params(store, idxs[0]))
            emit(inter, "warmup", 0, 0, idxs[0], res)
            if inter.n_index > 1:
                for seq, idx in enumerate(idxs[1:]):
                    res = srv.get(inter.endpoint, inter.params(store, idx))
                    emit(inter, "warm_new", 0, seq, idx, res)
            for seq in range(n_warm):
                res = srv.get(inter.endpoint, inter.params(store, idxs[0]))
                emit(inter, "warm_repeat", 0, seq, idxs[0], res)
    finally:
        srv.stop()
    print(f"    warm done (prewarm {pw:.1f}s)", flush=True)


class CsvWriter:
    def __init__(self, path: Path, fresh: bool):
        RESULTS.mkdir(exist_ok=True)
        self.path = path
        if fresh or not path.exists():
            with open(path, "w", newline="") as f:
                csv.DictWriter(f, FIELDS).writeheader()

    def __call__(self, row: dict) -> None:
        with open(self.path, "a", newline="") as f:
            csv.DictWriter(f, FIELDS, extrasaction="ignore").writerow(row)


# ------------------------------------------------------------------ experiments
def layer_interactions(n, g, matrix="fc"):
    return [
        Interaction("layer_gene", f"/data/layer/{matrix}", "cols", g, matrix=f"layers/{matrix}"),
        Interaction("layer_cell", f"/data/layer/{matrix}", "rows", n, matrix=f"layers/{matrix}"),
    ]


def targets_scale(man, sizes=None):
    out = []
    for key, m in sorted(man.items(), key=lambda kv: kv[1].get("n_cells", 0)):
        if m["family"] != "scale" or (sizes and m["n_cells"] not in sizes):
            continue
        n, g = m["n_cells"], m["n_genes"]
        inters = layer_interactions(n, g) + [
            Interaction("obsm_col", "/data/obsm/X_umap", "cols", 2, matrix="obsm/X_umap"),
            Interaction("obs_col", "/data/obs", None, 1, extra={"columns": "score"}, matrix="obs/score"),
            Interaction("obsp_knn_row", "/data/obsp/connectivities", "rows", n, matrix="obsp/connectivities"),
            Interaction("open_structure", "/data/dataset_structure", None, 1, matrix="structure"),
            Interaction("open_cells", "/data/cells", None, 1, matrix="obs_names"),
        ]
        meta = dict(m, layout="dense", chunks="x".join(map(str, m["layer"]["chunks"])))
        out.append(Target(ROOT / key, meta, inters))
    return out


def targets_sweep(man, sizes=None):
    out = []
    for key, m in sorted(man.items()):
        if m["family"] != "sweep" or (sizes and m["n_cells"] not in sizes):
            continue
        meta = dict(m, layout="dense", chunks="x".join(map(str, m["layer"]["chunks"])))
        out.append(Target(ROOT / key, meta, layer_interactions(m["n_cells"], m["n_genes"])))
    return out


def targets_pairwise(man, family, sizes=None):
    out = []
    for key, m in sorted(man.items(), key=lambda kv: kv[0]):
        if m["family"] != family:
            continue
        n = m.get("n_cells") or m.get("n_genes")
        if sizes and n not in sizes:
            continue
        inters, chunks_by, tags_by = [], {}, {}
        for info, tag in zip(m["arrays"], m["chunk_tags"]):
            slot, name = info["key"].split("/")
            inters.append(Interaction(f"{slot}_row", f"/data/{slot}/{name}", "rows", n, matrix=info["key"]))
            chunks_by[info["key"]] = "x".join(map(str, info["chunks"]))
            tags_by[info["key"]] = tag
        meta = dict(m, layout="dense", chunks_by_matrix=chunks_by, tags_by_matrix=tags_by,
                    n_cells=m.get("n_cells", 100), n_genes=m.get("n_genes", 100))
        out.append(Target(ROOT / key, meta, inters))
    return out


def targets_sparse(man, sizes=None):
    out = []
    for key, m in sorted(man.items()):
        if m["family"] != "sparse" or (sizes and m["n_cells"] not in sizes):
            continue
        n, g = m["n_cells"], m["n_genes"]
        inters = [Interaction("X_gene", "/data/X", "cols", g, matrix="X"),
                  Interaction("X_cell", "/data/X", "rows", n, matrix="X")]
        meta = dict(m, chunks="x".join(map(str, m["data_chunks"])), chunk_tag=m["layout"])
        out.append(Target(ROOT / key, meta, inters))
    return out


def run_http_experiment(exp, targets, args):
    out = RESULTS / f"{exp}{SUFFIX}.csv"
    writer = CsvWriter(out, args.fresh)
    envcapture.record(out, python=PY, wire=WIRE, experiment=exp, sizes=args.sizes, reps=args.reps)
    for tgt in targets:
        print(f"[{exp}] {tgt.store.relative_to(ROOT)}", flush=True)
        reps = args.reps
        measure_target(exp, tgt, reps, args.cold_new, args.warm, writer, skip_cold=args.skip_cold)


# ------------------------------------------------------------------ breakdown (Q6)
def run_breakdown(args):
    """Split a warm request into read / tolist / jsonify / HTTP remainder."""
    import zarr
    from flask import Flask, jsonify
    from annzarro.core.zarr_reader import ZarrReader

    reader = ZarrReader(enable_caching=False)
    app = Flask("breakdown")
    man = manifest()
    writer_path = RESULTS / "breakdown.csv"
    fields = ["store", "n_cells", "n_genes", "chunks", "interaction", "rep", "index", "t_open_s",
              "t_read_s", "t_tolist_s", "t_jsonify_s", "t_http_s", "bytes"]
    with open(writer_path, "w", newline="") as f:
        csv.DictWriter(f, fields).writeheader()

    jobs = []
    for t in targets_scale(man, args.sizes):
        jobs.append((t, ["layer_gene", "layer_cell", "obsm_col", "obsp_knn_row"]))
    for t in targets_sparse(man, args.sizes):
        jobs.append((t, ["X_gene", "X_cell"]))
    for t in targets_pairwise(man, "obsp", args.sizes):
        jobs.append((t, [i.name for i in t.interactions][:1]))

    for tgt, names in jobs:
        store = tgt.store
        sp = str(store)
        prewarm(store)
        srv = Server(store.parent)
        print(f"[breakdown] {store.relative_to(ROOT)}", flush=True)
        try:
            for inter in tgt.interactions:
                if inter.name not in names:
                    continue
                idxs = pick_indices(inter.n_index, args.reps + 1, 99)
                for rep, idx in enumerate(idxs):
                    t0 = time.perf_counter()
                    zarr.open_group(sp, mode="r")
                    t_open = time.perf_counter() - t0
                    rows = [idx] if inter.param == "rows" else None
                    cols = [idx] if inter.param == "cols" else None
                    t0 = time.perf_counter()
                    if inter.name.startswith("layer"):
                        data = reader.get_layer("fc", sp, rows, cols)
                    elif inter.name.startswith("X_"):
                        data = reader.get_X(sp, rows, cols)
                    elif inter.name == "obsm_col":
                        data = reader.get_obsm_varm(entity="cells", key="X_umap", dataset_path=sp,
                                                    indices=None, col_indices=cols)
                    else:  # obsp row (dense or sparse)
                        key = inter.endpoint.rsplit("/", 1)[1]
                        data = reader.get_obsp_varp(key=key, entity="cells", dataset_path=sp,
                                                    row_indices=rows, col_indices=None)
                    t_read = time.perf_counter() - t0
                    t0 = time.perf_counter()
                    lst = data.tolist()
                    t_tolist = time.perf_counter() - t0
                    t0 = time.perf_counter()
                    with app.app_context():
                        body = jsonify({"data": lst, "dataset_path": sp}).get_data()
                    t_json = time.perf_counter() - t0
                    res = srv.get(inter.endpoint, inter.params(store, idx))
                    if rep == 0:
                        continue  # discard first (warms code paths)
                    with open(writer_path, "a", newline="") as f:
                        csv.DictWriter(f, fields).writerow(dict(
                            store=str(store.relative_to(ROOT)), n_cells=tgt.meta.get("n_cells"),
                            n_genes=tgt.meta.get("n_genes"),
                            chunks=tgt.meta.get("chunks_by_matrix", {}).get(inter.matrix, tgt.meta.get("chunks")),
                            interaction=inter.name, rep=rep, index=idx, t_open_s=t_open, t_read_s=t_read,
                            t_tolist_s=t_tolist, t_jsonify_s=t_json, t_http_s=res["latency_s"],
                            bytes=len(body)))
        finally:
            srv.stop()


# ------------------------------------------------------------------ environment
def _sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"unavailable: {e}"


def write_environment():
    from importlib.metadata import version
    pkgs = {}
    for p in ["annzarro", "anndata", "zarr", "numcodecs", "numpy", "scipy", "flask", "werkzeug",
              "pandas", "psutil", "requests", "matplotlib"]:
        try:
            pkgs[p] = version(p)
        except Exception:  # noqa: BLE001
            pkgs[p] = None
    env = {
        "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "annzarro_commit": _sh(["git", "-C", str(ANNZARRO_REPO), "rev-parse", "HEAD"]),
        "annzarro_dirty": bool(_sh(["git", "-C", str(ANNZARRO_REPO), "status", "--porcelain", "--untracked-files=no"])),
        "paper_repo_commit": _sh(["git", "-C", str(HERE.parent), "rev-parse", "HEAD"]),
        "python": sys.version,
        "platform": platform.platform(),
        "os": f"{_sh(['sw_vers', '-productName'])} {_sh(['sw_vers', '-productVersion'])} ({_sh(['sw_vers', '-buildVersion'])})",
        "cpu": _sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "cpu_cores_logical": os.cpu_count(),
        "cpu_cores_performance": _sh(["sysctl", "-n", "hw.perflevel0.physicalcpu"]),
        "cpu_cores_efficiency": _sh(["sysctl", "-n", "hw.perflevel1.physicalcpu"]),
        "memory_bytes": psutil.virtual_memory().total,
        "disk": "internal Apple NVMe SSD",
        "filesystem": "APFS",
        "server": "python -m annzarro.server, or annzarro start on builds without it (Flask/werkzeug threaded server, debug off, cache_memory_mb=1000)",
        "client": "python requests, localhost, HTTP/1.0 (werkzeug), no gzip",
        "packages": pkgs,
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"environment{SUFFIX}.json").write_text(json.dumps(env, indent=2))
    print(json.dumps(env, indent=2))


# ------------------------------------------------------------------ CLI
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("experiment", choices=["all", "scale", "sweep", "obsp", "varp", "sparse", "breakdown", "env"])
    p.add_argument("--sizes", type=int, nargs="*", help="restrict to these n_cells / n_genes")
    p.add_argument("--reps", type=int, default=5, help="cold repetitions (fresh process + clone)")
    p.add_argument("--cold-new", type=int, default=3, help="extra new-index requests per cold process")
    p.add_argument("--warm", type=int, default=10, help="warm_new and warm_repeat requests each")
    p.add_argument("--fresh", action="store_true", help="overwrite the experiment's CSV instead of appending")
    p.add_argument("--skip-cold", action="store_true")
    p.add_argument("--wire", choices=["binary", "json"], default="binary",
                   help="binary: format=f32 (+ categorical=codes on obs/var), as the web client; json: the old JSON route")
    p.add_argument("--server-python", default=os.environ.get("ANNZARRO_PYTHON", sys.executable),
                   help="interpreter of the AnnZarro under test (default: this one)")
    p.add_argument("--suffix", default="", help="results/<experiment><suffix>.csv, e.g. _v031")
    a = p.parse_args()
    global WIRE, PY, SUFFIX
    WIRE, PY, SUFFIX = a.wire, a.server_python, a.suffix
    envcapture.require_clean_bench()
    dirty = _sh(["git", "-C", str(HERE.parent), "status", "--porcelain", "--untracked-files=all", "--",
                 "benchmark/run_benchmark.py", "benchmark/generate_data.py", "benchmark/sweep_1m.sh"])
    if dirty and not dirty.startswith("unavailable"):
        sys.exit("refusing to run: benchmark scripts differ from the commit:\n" + dirty)
    write_environment() if a.experiment in ("env", "all") else None
    man = manifest() if a.experiment != "env" else {}
    exps = ["sweep", "scale", "sparse", "breakdown"] if a.experiment == "all" else [a.experiment]
    for exp in exps:
        if exp == "env":
            continue
        if exp == "breakdown":
            run_breakdown(a)
            continue
        tg = {"scale": lambda: targets_scale(man, a.sizes),
              "sweep": lambda: targets_sweep(man, a.sizes),
              "obsp": lambda: targets_pairwise(man, "obsp", a.sizes),
              "varp": lambda: targets_pairwise(man, "varp", a.sizes),
              "sparse": lambda: targets_sparse(man, a.sizes)}[exp]()
        run_http_experiment(exp, tg, a)


if __name__ == "__main__":
    main()
