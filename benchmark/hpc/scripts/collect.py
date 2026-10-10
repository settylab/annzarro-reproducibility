#!/usr/bin/env python
"""Assemble benchmark/hpc/results/ from the run directory.

Per experiment it writes:
  results/<exp>_<http|raw>.csv
      Every request row ever measured for that experiment (first campaign and the post-#386
      rerun), with two flags:
        in_386_window   the row's timestamp falls in a a filer-load incident (2026-10-01) read-only window (below);
        basis           1 if the row backs the summary tables (measured after the windows,
                        and not on $DATA_ROOT), else 0.
  results/<exp>_<kind>_summary.csv
      median, q25, q75, IQR and n per (case, phase), from basis rows only.
  results/<exp>_<kind>_summary_386window.csv
      the same statistics for the rows that were taken inside a window, kept for the record.
  results/concurrency*.csv, results/canary.csv, results/environment.json

The #386 windows (PDT; from an incident report and the
a filer-load incident (2026-10-01) thread): the project tree's read-only bind detached on the agent host. Compute
nodes kept $DATA_ROOT mounted read-write throughout (see the per-job mounts in environment.json),
so the flag marks rows taken during a period of filer and host stress, not rows known to be wrong.

Usage: collect.py RUNS_DIR RESULTS_DIR
"""
import glob
import json
import os
import subprocess
import sys

import pandas as pd

WINDOWS = [  # (start, end), PDT
    ("2026-10-01T11:26:31-07:00", "2026-10-01T11:30:00-07:00"),
    ("2026-10-01T12:40:30-07:00", "2026-10-01T13:30:00-07:00"),
    ("2026-10-01T14:05:02-07:00", "2026-10-01T14:28:12-07:00"),
    ("2026-10-01T14:59:00-07:00", "2026-10-01T15:33:00-07:00"),
    ("2026-10-01T16:30:00-07:00", "2026-10-02T10:55:00-07:00"),
    # Post-10:55 project-bind losses (work/bindwatch/events.log BIND-LOST "1100->0000" -> SANDBOX-GONE),
    # found by the skeptic pass (skeptic-pass, 2026-10-03). bindwatch sampled continuously after
    # 17:16:59 to 2026-10-03T05:07 with the project bind present, so this list is complete for the runs.
    ("2026-10-02T11:45:51-07:00", "2026-10-02T12:19:25-07:00"),
    ("2026-10-02T16:45:31-07:00", "2026-10-02T16:48:42-07:00"),
    ("2026-10-02T17:09:42-07:00", "2026-10-02T17:16:59-07:00"),
]
# Whole runs excluded from the basis: the first post-window real-data $SCRATCH run (real http,
# real_rows) partly fell in W7/W8 and was rerun in full (jobs in runs/real_rerun_ids.txt), so no
# summary pools rows from two runs of the same case.
SUPERSEDED_JOBS = {"9987997", "9987998"}
WIN = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in WINDOWS]

runs, res = sys.argv[1], sys.argv[2]
os.makedirs(res, exist_ok=True)
for f in glob.glob(os.path.join(res, "*.csv")):  # results/ is fully generated: never leave a stale file
    os.remove(f)
here = os.path.dirname(os.path.abspath(__file__))
summ = os.path.join(here, "summarize.py")
EXPS = {  # experiment -> {kind: [csv paths relative to RUNS_DIR]}
    "smoke": {"http": ["smoke/smoke.csv"]},
    "real": {"http": ["real/real_fhfast.csv", "real/real_rows_fhfast.csv", "real/real_fhfast_rerun.csv",
                      "real_post/real_hpctemp.csv", "real_post/real_tmpfs.csv"]},
    "chunksweep": {"http": ["chunksweep/http.csv", "post/chunksweep/http.csv"],
                   "raw": ["chunksweep/raw.csv", "post/chunksweep/raw.csv"]},
    "fsarm": {"http": ["fsarm/http.csv", "post/fsarm/http.csv"],
              "raw": ["fsarm/raw.csv", "post/fsarm/raw.csv"]},
    "pairwise": {"http": ["pairwise/http_kernels.csv", "pairwise/http_dist_corr.csv", "post/pairwise/http.csv"],
                 "raw": ["pairwise/raw_kernels.csv", "pairwise/raw_dist_corr.csv", "post/pairwise/raw.csv"]},
    "atlas": {"http": ["atlas/http.csv", "atlas/http_aspect.csv", "post/atlas/http.csv"],
              "raw": ["atlas/raw.csv", "atlas/raw_aspect.csv", "post/atlas/raw.csv"]},
}


def flag(df):
    ts = pd.to_datetime(df["ts"], utc=True)
    inw = pd.Series(False, index=df.index)
    for a, b in WIN:
        inw |= (ts >= a) & (ts <= b)
    df["in_386_window"] = inw.astype(int)
    sup = df["job_id"].astype(str).isin(SUPERSEDED_JOBS) if "job_id" in df else pd.Series(False, index=df.index)
    df["superseded"] = sup.astype(int)
    df["basis"] = ((~inw) & (~sup) & (df["fs"] != "fhfast")).astype(int)
    return df


def summarize(df, kind, out):
    tmp = out + ".in.csv"
    (df.rename(columns={"proc_hwm_mb_cumulative": "proc_hwm_mb"}) if kind == "raw" else df).to_csv(tmp, index=False)
    subprocess.run([sys.executable, summ, tmp, "--out", out], check=True, stdout=subprocess.DEVNULL)
    os.remove(tmp)
    if kind == "raw":  # one long-lived process across cases: HWM is cumulative, not per case
        s = pd.read_csv(out).drop(columns=["peak_rss_mb_max"])
        s.to_csv(out, index=False)


for exp, kinds in EXPS.items():
    for kind, files in kinds.items():
        files = [os.path.join(runs, f) for f in files if os.path.exists(os.path.join(runs, f))]
        if not files:
            continue
        df = flag(pd.concat([pd.read_csv(f) for f in files], ignore_index=True))
        if kind == "raw":
            df = df.rename(columns={"proc_hwm_mb": "proc_hwm_mb_cumulative"})
        df.to_csv(os.path.join(res, f"{exp}_{kind}.csv"), index=False)
        for sel, suffix in ((df.basis == 1, ""), (df.in_386_window == 1, "_386window")):
            if sel.any():
                summarize(df[sel], kind, os.path.join(res, f"{exp}_{kind}_summary{suffix}.csv"))
conc =[os.path.join(runs, f) for f in ("concurrency/conc.csv", "post/concurrency/conc.csv")
        if os.path.exists(os.path.join(runs, f))]
if conc:
    d = pd.concat([pd.read_csv(f) for f in conc], ignore_index=True)
    d["fs"] = d["store_label"].str.rsplit("_", n=1).str[-1]
    d = flag(d)
    d.to_csv(os.path.join(res, "concurrency.csv"), index=False)
    for sel, suffix in ((d.basis == 1, ""), (d.in_386_window == 1, "_386window")):
        x = d[sel]
        if x.empty:
            continue
        g = x.groupby(["store_label", "concurrency"])
        per_rep_max = x.groupby(["store_label", "concurrency", "repeat"]).latency_s.max()
        pd.DataFrame({
            "latency_median_s": g.latency_s.median(),
            "latency_q25_s": g.latency_s.quantile(.25),
            "latency_q75_s": g.latency_s.quantile(.75),
            "slowest_request_median_s": per_rep_max.groupby(level=[0, 1]).median(),
            "wall_median_s": g.wall_s.median(),
            "n_requests": g.size(),
            "repeats": g.repeat.nunique(),
            "non200": g.status.apply(lambda s: int((s != 200).sum())),
        }).reset_index().to_csv(os.path.join(res, f"concurrency_summary{suffix}.csv"), index=False)
can = os.path.join(runs, "canary", "canary.csv")
if os.path.exists(can):
    pd.read_csv(can).to_csv(os.path.join(res, "canary.csv"), index=False)
def keep(f):  # runs/quarantine_*: measured under self-inflicted concurrent load, never used
    return "quarantine_" not in os.path.relpath(f, runs)


envs = {}
for f in sorted(filter(keep, glob.glob(os.path.join(runs, "*", "*env*.json"))
                       + glob.glob(os.path.join(runs, "*", "*", "*env*.json")))):
    e = json.load(open(f))
    envs[f"{e.get('slurm_job_id')}:{os.path.relpath(f, runs)}"] = e
specs = {}
for f in sorted(filter(keep, glob.glob(os.path.join(os.path.dirname(runs), "specs", "*.json"))
                       + glob.glob(os.path.join(runs, "*", "spec_*.json"))
                       + glob.glob(os.path.join(runs, "*", "*", "spec_*.json")))):
    specs[os.path.relpath(f, os.path.dirname(runs))] = json.load(open(f))
json.dump({"windows_386": WINDOWS, "jobs": envs, "specs": specs},
          open(os.path.join(res, "environment.json"), "w"), indent=1, sort_keys=True)
print("wrote", sorted(os.listdir(res)))
