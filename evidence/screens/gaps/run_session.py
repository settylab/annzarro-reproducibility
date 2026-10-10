"""Run the evidence-curator drivers inside one GUI window (evidence-curator, 2026-10-04).

  notes/comparison/demos/scale_probe/gap_run.sh /usr/bin/python3 evidence/screens/gaps/run_session.py [job ...]

gap_run.sh starts sessions only at minutes :00-:11 and they must end by :15 (ceiling-benchmarker's timed runs resume
then). Each job runs as a subprocess with a timeout that ends it by :14:30; a job that cannot get its minimum
time is skipped and left for the next session. Jobs done are recorded in the state file, so the next call
runs only what is left. Logs: <scratch>/logs/<job>.log.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = "$TMPDIR/evidence/gap-capture/"
STATE = SCRATCH + "session_state.json"
PW = "benchmark/scale/ceiling/.venv/bin/python"
PAPER = ".venv/bin/python"
NAPARI = "$DEMO_ROOT/napari-spatialdata/.venv/bin/python"
# name: (command, minimum seconds, maximum seconds)
JOBS = {
    "scanpy": ([PAPER, HERE + "/capture_scanpy_seurat.py"], 40, 120),
    "ucsc": ([PW, HERE + "/capture_ucsc.py"], 30, 90),
    "vitessce": ([PW, HERE + "/capture_vitessce.py"], 30, 90),
    "loupe": ([PW, HERE + "/capture_loupe.py"], 50, 120),
    "isee": ([PW, HERE + "/capture_isee.py"], 150, 240),
    "shinycell": ([PW, HERE + "/capture_shinycell.py"], 90, 180),
    "napari": ([NAPARI, HERE + "/capture_napari.py"], 90, 180),
    "cellxgene": ([PW, HERE + "/capture_cellxgene.py"], 50, 100),
    "scp": ([PW, HERE + "/capture_single_cell_portal.py"], 110, 180),
    "scope": ([PW, HERE + "/capture_scope.py"], 110, 180),
    "kana": ([PW, HERE + "/capture_kana.py"], 200, 300),
    "scope_fix": ([PW, HERE + "/capture_scope.py", "subset"], 70, 150),
    "scp_hosted": ([PW, HERE + "/capture_single_cell_portal.py", "hosted"], 50, 90),
    "cirro_docs": ([PW, HERE + "/capture_cirrocumulus.py", "docs"], 30, 90),
    "cirro_lazy_report": ([PW, HERE + "/capture_cirrocumulus.py", "lazy_report"], 40, 120),
    "cirro_lazy": ([PW, HERE + "/capture_cirrocumulus.py", "lazy"], 240, 480),
}

want = sys.argv[1:] or list(JOBS)
state = json.load(open(STATE)) if os.path.exists(STATE) else {}
os.makedirs(SCRATCH + "logs", exist_ok=True)
t = time.localtime()
deadline = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, 14, 30, 0, 0, -1))
print(time.strftime("%H:%M:%S"), "session start; deadline", time.strftime("%H:%M:%S", time.localtime(deadline)), flush=True)
for name in want:
    if state.get(name) == "done":
        continue
    cmd, tmin, tmax = JOBS[name]
    left = deadline - time.time()
    if left < tmin:
        print(time.strftime("%H:%M:%S"), f"skip {name}: {left:.0f}s left < {tmin}s", flush=True)
        continue
    t0 = time.time()
    env = None  # napari: native Qt platform; QT_QPA_PLATFORM=offscreen segfaults at viewer creation (notes/comparison/napari-spatialdata.md)
    with open(SCRATCH + f"logs/{name}.log", "a") as lg:
        lg.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(cmd)}\n")
        lg.flush()
        try:
            r = subprocess.run(cmd, stdout=lg, stderr=subprocess.STDOUT, timeout=min(tmax, left), env=env, cwd=HERE)
            rc = r.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    state[name] = "done" if rc == 0 else f"rc={rc}"
    json.dump(state, open(STATE, "w"), indent=1)
    print(time.strftime("%H:%M:%S"), f"{name}: rc={rc} in {time.time() - t0:.0f}s", flush=True)
# a timed-out job may leave a server behind: stop every demo port this session could have used
for stop in ["isee", "shinycell", "cirrocumulus"]:
    subprocess.run([f"$DEMO_ROOT/{stop}/stop.sh"], capture_output=True)
print(time.strftime("%H:%M:%S"), "session end", flush=True)
