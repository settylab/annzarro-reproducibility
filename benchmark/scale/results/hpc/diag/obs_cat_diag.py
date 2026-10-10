"""Why is warm /data/obs?columns=cell_line_id (all cells) 84 s at 95.6M? Measure, do not infer.
Part A, in-process: annzarro 0.2.0 ZarrReader with the server default cache (1000 MB), get_obs_var x3 on
the 50M and 95.6M panel stores, plus a control with a large cache budget; time, result type, cache state,
and json.dumps time. Part B, over HTTP: a fresh `annzarro --debug start` server per store, 3 timed requests,
and the cache-related lines of its debug log."""
import json, os, subprocess, sys, time, signal
from pathlib import Path
import requests
S = Path("$SCRATCH/annzarro-scale")
STORES = {"50M": S / "stores_panel/n50M/tahoe_panel_50M.zarr", "95.6M": S / "stores_panel/n95.6M/tahoe_panel_95.6M.zarr"}
out = {"A": [], "B": []}

def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)

from annzarro.core.zarr_reader import ZarrReader
for label, budget in [("50M", 1000), ("95.6M", 1000), ("95.6M", 200000)]:
    r = ZarrReader(max_memory_mb=budget)
    for rep in range(3):
        t0 = time.perf_counter()
        res = r.get_obs_var(entity="cells", dataset_path=str(STORES[label]), indices=None,
                            column_names=["cell_line_id"], include_categories=True)
        t_get = time.perf_counter() - t0
        col = res["data"]["cell_line_id"]
        est = r.cache._estimate_memory_usage(res)
        t0 = time.perf_counter(); s = json.dumps(res); t_json = time.perf_counter() - t0
        info = r.cache.get_cache_info()
        row = {"store": label, "cache_mb": budget, "rep": rep, "get_s": round(t_get, 3), "json_s": round(t_json, 3),
               "json_bytes": len(s), "value_type": type(col).__name__, "first": str(col[:2]) if hasattr(col, "__getitem__") else "",
               "estimate_mb": round(est, 1), "cache_usage_mb": round(r.cache.memory_usage_mb, 1),
               "cache_keys": sum(len(v) for v in r.cache._dataset_caches.values())}
        out["A"].append(row); log("A", row)
        del s, res, col

API = "/api"
for label in ["50M", "95.6M"]:
    home = S / f"diag/home_{label}"; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, ANNZARRO_HOME=str(home), ANNZARRO_HEADLESS="1")
    lf = open(home / "server_debug.log", "w")
    exe = Path(sys.executable).with_name("annzarro")
    p = subprocess.Popen([str(exe), "--debug", "start", "--host", "127.0.0.1", "--port", "8907", "--data-dir",
                          str(STORES[label].parent), "--no-browser", "--auth-disabled"], stdout=lf, stderr=subprocess.STDOUT,
                         env=env, cwd=home, start_new_session=True)
    base = None
    t0 = time.time()
    while time.time() - t0 < 180:
        for b in ("http://127.0.0.1:8907/api", "http://127.0.0.1:8907"):
            try:
                if requests.get(b + "/config", timeout=2).status_code == 200: base = b; break
            except requests.RequestException: pass
        if base: break
        time.sleep(0.2)
    log("server up", label, base)
    for rep in range(3):
        mark = (home / "server_debug.log").stat().st_size
        t0 = time.perf_counter()
        rr = requests.get(base + "/data/obs", params={"dataset_path": str(STORES[label]), "columns": "cell_line_id"}, timeout=1200)
        dt = time.perf_counter() - t0
        with open(home / "server_debug.log") as f:
            f.seek(mark); lines = [l.rstrip() for l in f if any(k in l for k in ("CACHE", "cache", "Evict", "Added"))]
        row = {"store": label, "rep": rep, "status": rr.status_code, "seconds": round(dt, 2), "bytes": len(rr.content),
               "cache_log": lines[-12:]}
        out["B"].append(row); log("B", {k: v for k, v in row.items() if k != "cache_log"}); [print("   ", l[:220]) for l in lines[-12:]]
    os.killpg(p.pid, signal.SIGTERM); p.wait(30); lf.close()
json.dump(out, open(S / "diag/obs_cat_diag.json", "w"), indent=1)
log("done")
