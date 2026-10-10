"""One AnnZarro v0.3.0 server, 1B synthetic store: the default-subset requests one at a
time, server footprint sampled every 0.1 s: which request owns the peak, what stays."""
import json, os, subprocess, sys, threading, time, urllib.parse
sys.path.insert(0, "benchmark/tool_ceiling")
import psutil, requests
from memmon import rusage
EXE = os.environ.get("TC_EXE", "$ENVS_ROOT/annzarro_v030_3fb6826/.venv/bin/annzarro")
home = "$DATA_ROOT/tool_ceiling_data/probe/prof_home"
ST = "$DATA_ROOT/tahoe_scale_ceiling/syn_master_1000000000.zarr"
srv = subprocess.Popen([EXE, "start", "--host", "127.0.0.1", "--port", "8947", "--data-dir", "$DATA_ROOT/tahoe_scale_ceiling",
                        "--no-browser", "--auth-disabled"], env=dict(os.environ, ANNZARRO_HOME=home, ANNZARRO_HEADLESS="1"),
                       cwd=home, stdout=open("$DATA_ROOT/tool_ceiling_data/probe/subreq.server.log", "w"), stderr=subprocess.STDOUT)
B = "http://127.0.0.1:8947/api/v1/"
for _ in range(120):
    try:
        if requests.get(B + "config", timeout=2).ok: break
    except Exception: pass
    time.sleep(1)
def fp():
    return sum((rusage(p.pid) or (0, 0, 0))[0] for p in [psutil.Process(srv.pid)] + psutil.Process(srv.pid).children(True))
q = lambda **kw: urllib.parse.urlencode(dict(dataset_path=ST, **kw))
sub = json.dumps({"n": 100000, "seed": 0})
steps = [("subset=auto", "data/subset?" + q(subset="auto")),
         ("cells (names of the subset)", "data/cells?" + q(subset=sub)),
         ("obsm X_umap col 0", "data/obsm/X_umap?" + q(column_name=0, format="f32", subset=sub)),
         ("obsm X_umap col 1", "data/obsm/X_umap?" + q(column_name=1, format="f32", subset=sub)),
         ("layer X col 0", "data/layer/X?" + q(cols=0, format="f32", subset=sub)),
         ("obs cell_type", "data/obs?" + q(column_name="cell_type", subset=sub))]
try:
    print("idle", round(fp() / 2**30, 2), "GiB", flush=True)
    for name, url in steps:
        peak, done = [0], [False]
        def watch():
            while not done[0]:
                peak[0] = max(peak[0], fp()); time.sleep(0.1)
        th = threading.Thread(target=watch); th.start()
        t = time.time(); r = requests.get(B + url, timeout=600); dt = time.time() - t
        done[0] = True; th.join(); time.sleep(2)
        print(f"{name}: status {r.status_code}, {len(r.content)} B, {dt:.1f} s, peak {peak[0] / 2**30:.2f} GiB, "
              f"after {fp() / 2**30:.2f} GiB", flush=True)
finally:
    srv.terminate()
