"""Part B (corrected): the server as bench_http starts it (annzarro start, default = production config),
GET /api/v1/cache/info for the effective budget, then /data/obs?columns=cell_line_id (format f32, as the
bench) x3 on the 50M and 95.6M panel stores, cache info after each request."""
import json, os, subprocess, sys, time, signal
from pathlib import Path
import requests
S = Path("$SCRATCH/annzarro-scale")
STORES = {"50M": S / "stores_panel/n50M/tahoe_panel_50M.zarr", "95.6M": S / "stores_panel/n95.6M/tahoe_panel_95.6M.zarr"}
out = []
def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
for label in ["50M", "95.6M"]:
    home = S / f"diag/homeB_{label}"; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, ANNZARRO_HOME=str(home), ANNZARRO_HEADLESS="1")
    lf = open(home / "server.log", "w")
    exe = Path(sys.executable).with_name("annzarro")
    p = subprocess.Popen([str(exe), "start", "--host", "127.0.0.1", "--port", "8907", "--data-dir", str(STORES[label].parent),
                          "--no-browser", "--auth-disabled"], stdout=lf, stderr=subprocess.STDOUT, env=env, cwd=home,
                         start_new_session=True)
    base = "http://127.0.0.1:8907/api/v1"; t0 = time.time()
    while time.time() - t0 < 180:
        try:
            if requests.get(base + "/config", timeout=2).status_code == 200: break
        except requests.RequestException: pass
        time.sleep(0.2)
    ci = requests.get(base + "/cache/info", timeout=30).json()
    log("cache/info at start", label, json.dumps(ci)[:600])
    for rep in range(3):
        t0 = time.perf_counter()
        rr = requests.get(base + "/data/obs", params={"dataset_path": str(STORES[label]), "columns": "cell_line_id", "format": "f32"}, timeout=1200)
        dt = time.perf_counter() - t0
        ci = requests.get(base + "/cache/info", timeout=30).json()
        row = {"store": label, "rep": rep, "status": rr.status_code, "seconds": round(dt, 2), "bytes": len(rr.content),
               "content_type": rr.headers.get("Content-Type", ""), "cache_info_after": ci}
        out.append(row); log("B", label, rep, rr.status_code, round(dt, 2), len(rr.content), json.dumps(ci)[:500])
    os.killpg(p.pid, signal.SIGTERM); p.wait(30); lf.close()
json.dump(out, open(S / "diag/obs_cat_http.json", "w"), indent=1)
log("done")
