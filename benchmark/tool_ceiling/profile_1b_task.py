"""1B synthetic store, AnnZarro v0.3.0 server under tracemalloc, the default-subset
task driven against it; then a tracemalloc dump and the footprint."""
import json, os, signal, subprocess, sys, time
sys.path.insert(0, "benchmark/tool_ceiling")
import psutil, requests
from memmon import rusage
EXE = os.environ.get("TC_EXE", "$ENVS_ROOT/annzarro_v030_3fb6826/.venv/bin/annzarro")
OUT = os.environ.get("TC_OUT", "$DATA_ROOT/tool_ceiling_data/probe/prof1b")
home = "$DATA_ROOT/tool_ceiling_data/probe/prof_home"; os.makedirs(home, exist_ok=True)
env = dict(os.environ, ANNZARRO_HOME=home, ANNZARRO_HEADLESS="1", TC_PROF_OUT=OUT + ".prof",
           PYTHONPATH="$DATA_ROOT/tool_ceiling_data/probe/site")
srv = subprocess.Popen([EXE, "start", "--host", "127.0.0.1", "--port", "8946", "--data-dir",
                        "$DATA_ROOT/tahoe_scale_ceiling", "--no-browser", "--auth-disabled"], env=env, cwd=home,
                       stdout=open(OUT + ".server.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
for _ in range(120):
    try:
        if requests.get("http://127.0.0.1:8946/api/v1/config", timeout=2).status_code == 200: break
    except Exception: pass
    time.sleep(1)
tc = "benchmark/tool_ceiling"
rc = subprocess.run([tc + "/.venv/bin/python", tc + "/annzarro_task.py", "default",
                     "$DATA_ROOT/tahoe_scale_ceiling/syn_master_1000000000.zarr", OUT, "--server-url", "http://127.0.0.1:8946",
                     "--n", "1000000000", "--probe-store", "$DATA_ROOT/tahoe_scale_ceiling/syn_1000000.zarr",
                     "--version-label", os.environ.get("TC_VER", "3fb6826"), "--cat", "cell_type", "--gene", "GENE0", "--subset", "absent"], cwd=tc).returncode
procs = [psutil.Process(srv.pid)] + psutil.Process(srv.pid).children(recursive=True)
fp = {p.pid: rusage(p.pid) for p in procs}
print("task rc", rc, "server footprint (cur, lifetime max, rss) GiB:",
      {k: tuple(round(x / 2**30, 2) for x in v) for k, v in fp.items() if v})
for p in procs:
    try: os.kill(p.pid, signal.SIGUSR1)
    except Exception as e: print("sig", e)
time.sleep(90)
os.killpg(srv.pid, signal.SIGTERM)
print(open(OUT + ".json").read()[:400])
