"""Run the evidence-curator drivers inside one GUI window (2026-10-04). Same rules as run_session.py:

  notes/comparison/demos/scale_probe/gap_run.sh /usr/bin/python3 evidence/screens/gaps/run_session2.py [job ...]

Since 2026-10-04 there are no clock slots: run under the bench lock, e.g.
  /usr/bin/lockf -k ~/.annzarro-bench.lock /usr/bin/python3 run_session2.py [job ...]
(optional RUN_DEADLINE_MIN=<minutes> skips jobs that would not fit). Jobs done are recorded in the state file, so a repeat call runs only what is left
(pass a job name with a trailing '!' to force it again). Logs: <scratch>/logs/<job>.log.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = "$TMPDIR/evidence/gap-capture-2/"
STATE = SCRATCH + "session_state.json"
PW = "benchmark/scale/ceiling/.venv/bin/python"
BPY = "$DEMO_ROOT/_browser/.venv/bin/python"
DEMOS = "notes/comparison/demos/"
FR = DEMOS + "_focus_run.py"
# name: (command, minimum seconds, maximum seconds, demo servers to stop afterwards)
JOBS = {
    "code": ([PW, HERE + "/capture2_code.py"], 120, 300, []),
    "code_scanpy": ([PW, HERE + "/capture2_code.py", "scanpy"], 70, 200, []),
    "code_isee": ([PW, HERE + "/capture2_code.py", "isee"], 40, 120, []),
    "code_small": ([PW, HERE + "/capture2_code.py", "napari", "shinycell"], 40, 120, []),
    "docs": ([PW, HERE + "/capture2_docs.py"], 60, 150, []),
    "ucsc": ([BPY, FR, "ucsc-cell-browser", "8906", HERE + "/capture2_ucsc.py"], 60, 150, ["ucsc-cell-browser"]),
    "vitessce": ([BPY, FR, "vitessce", "8904", HERE + "/capture2_vitessce.py"], 150, 300, ["vitessce"]),
    "cirro": ([BPY, FR, "cirrocumulus", "8901", HERE + "/capture2_cirrocumulus.py"], 120, 240, ["cirrocumulus"]),
    "isee_app": ([PW, HERE + "/capture2_isee.py"], 120, 240, ["isee"]),
    "shiny_app": ([BPY, FR, "shinycell", "8907", HERE + "/capture2_shinycell.py"], 60, 150, ["shinycell"]),
    "cxg_annotate": ([BPY, FR, "cellxgene", "8903", HERE + "/capture2_cellxgene.py", ], 150, 330, ["cellxgene"]),
    "cxg_explorer": ([BPY, FR, "none", "0", HERE + "/capture2_cellxgene_explorer.py"], 150, 400, []),
    "cxg_ts": ([BPY, FR, "none", "0", HERE + "/capture2_cellxgene_big.py", "ts"], 200, 420, []),
    "cxg_11m": ([BPY, FR, "none", "0", HERE + "/capture2_cellxgene_big.py", "big"], 200, 420, []),
    "scp": ([PW, HERE + "/capture2_scp.py"], 150, 400, []),
    "kana": ([BPY, HERE + "/capture2_kana.py"], 120, 300, []),
    # remaining marks (2026-10-04, second round): docs h04/h01, scanpy h04 selection, Annotate --backed RSS, Vitessce chunk log
    "docs_more": ([PW, HERE + "/capture2_docs.py", "cellxgene", "loupe"], 50, 120, []),
    "code_sel": ([PW, HERE + "/capture2_code.py", "select"], 40, 120, []),
    "cxg_backed": ([PW, HERE + "/capture2_cellxgene.py", "backed"], 120, 330, ["cellxgene"]),
    "vit_remote": ([BPY, FR, "none", "0", HERE + "/capture2_vitessce.py", "remote"], 90, 180, []),
}

want = sys.argv[1:] or list(JOBS)
state = json.load(open(STATE)) if os.path.exists(STATE) else {}
os.makedirs(SCRATCH + "logs", exist_ok=True)
t = time.localtime()
# The clock time-share ended on 2026-10-04 (coordinator): no slot deadline unless RUN_DEADLINE_MIN is set.
# Callers hold the bench lock (lockf -k ~/.annzarro-bench.lock) for the whole session.
_lim = os.environ.get("RUN_DEADLINE_MIN")
deadline = time.time() + float(_lim) * 60 if _lim else time.time() + 10 ** 9
print(time.strftime("%H:%M:%S"), "session start; deadline", time.strftime("%H:%M:%S", time.localtime(deadline)), flush=True)
for name in want:
    force = name.endswith("!")
    name = name.rstrip("!")
    if state.get(name) == "done" and not force:
        continue
    cmd, tmin, tmax, servers = JOBS[name]
    left = deadline - time.time()
    if left < tmin:
        print(time.strftime("%H:%M:%S"), f"skip {name}: {left:.0f}s left < {tmin}s", flush=True)
        continue
    t0 = time.time()
    with open(SCRATCH + f"logs/{name}.log", "a") as lg:
        lg.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(cmd)}\n")
        lg.flush()
        try:
            r = subprocess.run(cmd, stdout=lg, stderr=subprocess.STDOUT, timeout=min(tmax, left), cwd=HERE)
            rc = r.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    for s in servers:
        subprocess.run([f"$DEMO_ROOT/{s}/stop.sh"], capture_output=True)
    state[name] = "done" if rc == 0 else f"rc={rc}"
    json.dump(state, open(STATE, "w"), indent=1)
    print(time.strftime("%H:%M:%S"), f"{name}: rc={rc} in {time.time() - t0:.0f}s", flush=True)
for s in ["isee", "shinycell", "cirrocumulus", "cellxgene", "vitessce", "ucsc-cell-browser"]:
    subprocess.run([f"$DEMO_ROOT/{s}/stop.sh"], capture_output=True)
print(time.strftime("%H:%M:%S"), "session end", flush=True)
