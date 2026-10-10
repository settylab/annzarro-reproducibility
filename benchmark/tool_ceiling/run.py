#!/usr/bin/env python
"""One measured run of a library tool: take the bench lock, run CMD inside
memmon.py, append one row to results.csv.

  run.py --tool scanpy --variant default --n 1000000 --run 0 [--phase run] -- CMD ...

While a pause file exists (PAUSE, PAUSE_SLOT, PAUSE_LOW for non-remote runs, ~/.annzarro-bench.pause),
a new run waits before asking for the lock. "{out}" in CMD is replaced by shots/<id> (the task writes <id>.json and PNGs
there). Raw files: raw/<id>.mem.json (memmon), raw/<id>.task.json (the task's
own record, copied), raw/<id>.log (stdout+stderr).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCK = "$HOME/.annzarro-bench.lock"
PY = str(HERE / ".venv/bin/python")
HANG_S = 300  # web runs: no progress (client + server CPU < memmon.HANG_CPU s) for this long ends the run as "hang"
# while any of these exists, no new run asks for the lock: the manual pause, the
# hourly GUI slot (slots.sh), and the shared one (other benchmarks)
PAUSE = (Path("$DATA_ROOT/tool_ceiling_data/PAUSE"), Path("$DATA_ROOT/tool_ceiling_data/PAUSE_SLOT"),
         Path("$HOME/.annzarro-bench.pause"))
# while this exists, only high-priority runs (the remote AnnZarro ladder) go ahead
PAUSE_LOW = Path("$DATA_ROOT/tool_ceiling_data/PAUSE_LOW")
COLS = ["id", "time", "tool", "variant", "phase", "n", "run", "status", "failure_mode", "all_cells", "wall_s",
        "fp_total_gb", "fp_lifetime_total_gb", "rss_total_gb", "fp_client_gb", "fp_server_gb", "versions", "note"]
OOM = re.compile(r"MemoryError|cannot allocate|bad_alloc|vector memory|Cannot allocate|memory exhausted|"
                 r"V8 javascript OOM|Fatal JavaScript out of memory", re.I)


def gb(x):
    return round(x / 2 ** 30, 3) if x is not None else ""


def append_row(row: dict):
    # conversions (phase convert) are not measured results (operator, 2026-10-05): their rows go to
    # conversions_superseded.csv, kept only as a record of what the builds cost
    p = HERE / ("conversions_superseded.csv" if row.get("phase") == "convert" else "results.csv")
    new = not p.exists()
    with open(p, "a", newline="") as f:
        w = csv.DictWriter(f, COLS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in COLS})


HIGH = any(x.startswith("remote_") for x in sys.argv)  # --variant remote_<sha>
PAUSE = PAUSE if HIGH else PAUSE + (PAUSE_LOW,)
PAUSED_SH = " || ".join(f"[ -e {p} ]" for p in PAUSE)
PAUSED_RC = 75


def wait_while_paused(force=False):
    """While paused, become a plain /bin/sh loop (no python *run.py in ps, so
    other benchmarks' quiet-machine checks do not count a paused run as timed),
    then exec this run.py again from the start."""
    if force or any(p.exists() for p in PAUSE):
        os.execv("/bin/sh", ["/bin/sh", "-c", f'while {PAUSED_SH}; do sleep 30; done; exec "$0" "$@"',
                             sys.executable] + sys.argv)


def classify(status: str, log: str, task: dict | None) -> str:
    """failure_mode from memmon's status, the task's own error and the log."""
    if status == "ok":
        return "" if (task or {}).get("ok", True) else "check_failed"
    if status in ("timeout", "cap", "hang"):
        return status
    err = (task or {}).get("error") or ""
    bad = {k: v.get("status") for k, v in ((task or {}).get("checks") or {}).items()
           if isinstance(v, dict) and v.get("status") not in (None, "ok")}
    if bad:  # the task's own per-step verdict (e.g. guard_refusal, timeout of one colouring)
        return "; ".join(f"{k}: {v}" for k, v in bad.items())
    if "TimeoutError" in err:  # the task's own 1750 s wait ran out (memmon kills at 1800 s)
        m = re.search(r"waiting for (.{0,80})", err)
        return "timeout: " + (m.group(1).strip() if m else "page wait")
    if OOM.search(log) or OOM.search(err):
        return "oom"
    if status == "killed":
        return "killed"
    if err:
        return "crash: " + err.splitlines()[0][:160]
    m = re.findall(r"^\S*(?:Error|error)\b[^\n]{0,160}", log, re.M)
    return "crash: " + (m[-1] if m else "unknown")


def reclassify():
    """Recompute failure_mode/status of every row from its raw files (after a
    classify() change); the measurements are not touched."""
    p = HERE / "results.csv"
    rows = list(csv.DictReader(open(p)))
    for r in rows:
        mem = HERE / "raw" / f"{r['id']}.mem.json"
        if not mem.exists():
            continue
        m = json.loads(mem.read_text())
        tj = HERE / "raw" / f"{r['id']}.task.json"
        task = json.loads(tj.read_text()) if tj.exists() else None
        log = (HERE / "raw" / f"{r['id']}.log").read_text(errors="replace")
        r["status"], r["failure_mode"] = m["status"], classify(m["status"], log, task)
        if r["status"] == "ok" and r["failure_mode"]:
            r["status"] = "fail"
        if r["failure_mode"].startswith("timeout"):
            r["status"] = "timeout"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows)


# builds whose queued runs must not start any more (superseded before they ran):
# such a run exits without a row
RETIRED = {"annzarro_v030p_12f93f8": "12f93f8 has the memory-guard double count (fixed in c9272e5); rerun on the fixed head"}


def main():
    if "--tool" in sys.argv and sys.argv[sys.argv.index("--tool") + 1] == "napari" and \
            "--variant" in sys.argv and sys.argv[sys.argv.index("--variant") + 1] == "default" and \
            "--phase" not in sys.argv:
        print("== skipped: napari variant 'default' replaced by allpoints/sub100k (queue_napari2.sh)", file=sys.stderr)
        sys.exit(0)
    for k, why in RETIRED.items():
        if any(k in x for x in sys.argv):
            print(f"== skipped: {k} retired ({why})", file=sys.stderr, flush=True)
            sys.exit(0)
    ap = argparse.ArgumentParser()
    for k in ("tool", "variant"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--run", type=int, default=0)
    ap.add_argument("--phase", default="run")
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--cap-gb", type=float, default=85)  # machine guard (48 until 2026-10-05)
    ap.add_argument("--note", default="")
    ap.add_argument("--web", action="store_true", help="CMD drives a browser (memmon --web)")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    rid = f"{a.tool}_{a.variant}_{a.phase}_{a.n}_r{a.run}"
    raw, shots = HERE / "raw", HERE / "shots"
    raw.mkdir(exist_ok=True)
    shots.mkdir(exist_ok=True)
    out = str(shots / rid)
    cmd = [c.replace("{out}", out) for c in cmd]
    mem = raw / f"{rid}.mem.json"
    # RUN_TIMED (the team's run-timed wrapper) instead of a bare lockf: it also raises the timing marker
    pre = [os.environ["RUN_TIMED"]] if os.environ.get("RUN_TIMED") else ["/usr/bin/lockf", "-k", LOCK]
    full = pre + [PY, str(HERE / "memmon.py"), "--out", str(mem),
            "--timeout", str(a.timeout), "--cap-gb", str(a.cap_gb)] + (["--web", "--hang-s", str(HANG_S)] if a.web else []) + ["--"] + cmd
    wait_while_paused()
    # re-check the pause once the lock is held: a run that waited on the lock
    # through a pause starts nothing, and goes back to waiting
    full[len(pre):len(pre)] = ["/bin/sh", "-c", f'{PAUSED_SH} && exit {PAUSED_RC}; exec "$0" "$@"']
    print(f"== {rid} waiting for lock", file=sys.stderr, flush=True)
    with open(raw / f"{rid}.log", "w") as lf:
        rc = subprocess.run(full, stdout=lf, stderr=subprocess.STDOUT).returncode
    if rc == PAUSED_RC and not mem.exists():
        print(f"== {rid} paused after the lock; waiting again", file=sys.stderr, flush=True)
        wait_while_paused(force=True)
    log = (raw / f"{rid}.log").read_text(errors="replace")
    m = json.loads(mem.read_text())
    task = None
    if Path(out + ".json").exists():
        task = json.loads(Path(out + ".json").read_text())
        shutil.copy(out + ".json", raw / f"{rid}.task.json")
    pk = m["peaks"]["total"]
    checks = (task or {}).get("checks", {})
    row = {"id": rid, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": a.tool, "variant": a.variant,
           "phase": a.phase, "n": a.n, "run": a.run, "status": m["status"],
           "failure_mode": classify(m["status"], log, task),
           "all_cells": all(c.get("all_cells") for c in checks.values()) if len(checks) == 2 else "",
           "wall_s": m["wall_s"], "fp_total_gb": gb(pk["fp_peak"]), "fp_lifetime_total_gb": gb(pk["fp_lifetime_sum"]),
           "rss_total_gb": gb(pk["rss_peak"]), "versions": json.dumps((task or {}).get("versions", {})),
           "fp_client_gb": gb(m["peaks"]["client"]["fp_peak"]) if a.web else "",
           "fp_server_gb": gb(m["peaks"]["server"]["fp_peak"]) if a.web else "",
           "note": a.note}
    if row["status"] == "ok" and row["failure_mode"]:
        row["status"] = "fail"
    if row["failure_mode"].startswith("timeout"):
        row["status"] = "timeout"
    append_row(row)
    print(f"== {rid}: {row['status']} {row['failure_mode']} {row['wall_s']}s fp={row['fp_total_gb']}GB",
          file=sys.stderr, flush=True)


if __name__ == "__main__":
    reclassify() if sys.argv[1:] == ["--reclassify"] else main()
