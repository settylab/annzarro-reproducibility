#!/usr/bin/env python
"""Ceilings and the curve from results.csv.

The budget is on the CLIENT: for a web tool every Chromium process (renderer,
GPU, browser), with its server treated as remote and reported separately; for
a library (Scanpy, Seurat) the whole process, which is the client.

ceilings.csv: per tool x variant, the largest N with a successful run whose
peak client footprint stays within 8, 16 and 32 GB, the first N that failed
(and how), and the largest N that succeeded at all. Only measured rows count;
an N that was not run is never assumed.

ceiling_curve.png: peak client footprint (median over runs) against N, one
panel per tool, variants as lines; failures as crosses on the top edge.

Usage: summarize.py
"""
from __future__ import annotations

import csv
import json
import math
import re
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
LOCAL = ZoneInfo("America/Los_Angeles")
BUDGETS = (8, 16, 32)
TOOLS = ["annzarro", "cellxgene", "cirrocumulus", "vitessce", "ucsc", "isee", "shinycell", "scanpy", "seurat"]
NAMES = {"annzarro": "AnnZarro", "cellxgene": "CELLxGENE", "cirrocumulus": "Cirrocumulus", "vitessce": "Vitessce",
         "ucsc": "UCSC Cell Browser", "isee": "iSEE", "shinycell": "ShinyCell", "scanpy": "Scanpy",
         "seurat": "Seurat v5"}
# categorical slots 1-4 of the reference palette, in fixed order per panel
# tools that render images on the server and ship them to the page: the client
# footprint says nothing about their limit, so their server ceiling is reported
SERVER_RENDERED = {"isee", "shinycell"}
# AnnZarro variants of the cited release (v0.4.1); older builds are in HISTORY.md, not drawn
CURRENT_ANNZARRO = "v041"
COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7", "#c43b8a", "#6b737c"]
MARKERS = ["o", "s", "^", "D", "v", "P"]


# runs that failed because of the harness, not the tool (kept in results.csv,
# left out of every number): id -> reason
HARNESS_FAILURES = {
    "annzarro_v041_noguard_edge_run_225000000_r0": "drawn by gene; the category recolour failed in the page ('Error loading plot data: RangeError: Array buffer allocation failed', large-plot.js groupByKey) but the driver's recolour wait had no error check and ran to its limit, logged 'hang' (fixed; rerun as r1)",
    "annzarro_v041_noguard_run_250000000_r0": "the page reported 'plot data: failed to read -- Array buffer allocation failed' (RangeError in the tab); the driver did not read it and logged 'stalled' after 45 s (fixed; rerun as r1)",
    "annzarro_v041_noguard_run_300000000_r0": "the page reported 'plot data: failed to read -- Array buffer allocation failed' (RangeError in the tab); the driver did not read it and logged 'stalled' after 45 s (fixed; rerun as r1)",
    "annzarro_v041_noguard_run_500000000_r0": "the page reported 'plot data: failed to read -- Array buffer allocation failed' (RangeError in the tab); the driver did not read it and logged 'stalled' after 45 s (fixed; rerun as r1)",
    "annzarro_v041_syn_run_250000000_r0": "v0.4.1 refused the plot with its new reason ('250,000,000 points is above 200,000,000, the largest plot tested to draw'); the driver's guard pattern knew only the v0.4.0 wordings and logged 'stalled' (fixed; rerun as r1)",
    "cellxgene_backed_run_2000000_r0": "gene suggestion list missed the typed name (fixed by retries; rerun as r1)",
    "ucsc_default_run_1000000_r0": "waited for 'N visible cells loaded'; with WebGL the tool writes 'N cells loaded' (fixed; rerun as r1)",
    "ucsc_default_run_5000000_r0": "the first-visit tutorial opened after the Escape and covered the Gene tab (fixed: its close button is clicked; rerun as r1)",
    "ucsc_default_run_5000000_r1": "same as r0 (ran before the fix); rerun as r2",
    "kana_default_run_2000000_r0": "Kana showed 'EXPLORE ERROR RuntimeError: Aborted()' (a Wasm abort) within ~2 min; the driver did not read that panel and waited 30 min (fixed; rerun as r1)",
    "napari_allpoints_run_1000000_r0": "driver read the layer list before napari-spatialdata's worker thread had added the layer (fixed: waits for it); rerun as r1",
    "napari_sub100k_run_1000000_r0": "same driver bug as allpoints 1M r0; rerun as r1",
    "cellxgene_backed_run_16800000_r2": "port 8940 still held by the previous run's server ('The port selected 8940 is in use'); r0 and r1 at 16.8M passed",
    "tissuumaps_default_run_1000000_r0": "harness wait: TissUUmaps drew all 1,000,000 markers in instanced calls of 65,536, and the driver waited for one call of N (fixed: per-frame sum); not a tool hang",
    "napari_allpoints_run_1000000_r1": "harness: the run sat on the bench lock waiting for the screen lock (flat 1.9 GiB for 30 min); the screen lock is now tried for 120 s at most",
    "tissuumaps_default_run_20000000_r0": "the gene colour failed with an uncaught page error the driver did not record yet, so it waited (logged 'hang'); r1 records the error: 'Cannot convert a BigInt value to a number'",
    "annzarro_remote_606f0bc_run_1000000_r0": "ceiling.py read the remote store's metadata locally (fixed; rerun as r1)",
    "annzarro_v040_noguard_run_200000000_r1": "harness: ceiling.py's clean-tree guard refused to start (another agent's "
        "benchmark/scale/summarize_rerun.py uncommitted); nothing ran",
    "manivault_default_run_250000_r0": "input fault: the 0.25M h5ad was written with anndata 0.13.4/pandas 3, whose obs/var "
        "index is a nullable-string-array group; ManiVault's loader reads only a dataset index (notes/comparison/manivault.md). "
        "Rebuilt with anndata 0.11.4 like every other input; rerun as r1",
    "manivault_default_run_500000_r0": "harness: the desktop session quit ManiVault before writing drawn_ (its drawn_ reports "
        "500,000 points and both colourings), so the watcher logged app_exited; rerun as r1",
}


# comparison-auditor's GUI sessions (UTC). The rule reads the copy in logs/; if
# $TOOL_CEILING_WINDOWS_SRC names the live log, the copy is refreshed from it first.
WINDOWS_COPY = HERE / "logs/windows.log"
OTHERS = re.compile(r"pytest|ms-playwright|Chrome for Testing|npm (run )?test|vitest|jest")  # as memmon.OTHERS


def windows():
    """comparison-auditor's windows; a copy is kept in logs/ so the rule can be rerun from the repo."""
    out = []
    src = os.environ.get("TOOL_CEILING_WINDOWS_SRC")
    if src and Path(src).exists():
        WINDOWS_COPY.write_text(Path(src).read_text())
    if WINDOWS_COPY.exists():
        for line in WINDOWS_COPY.read_text().splitlines():
            parts = line.split()
            try:
                a, b = (datetime.fromisoformat(x).replace(tzinfo=timezone.utc) for x in parts[:2])
            except (ValueError, IndexError):
                continue
            out.append((a, b, line[:200]))
    # other sessions on the machine (e.g. the user's live tests), logged as
    # "<utc> OPEN <what>" ... "<utc> CLOSE <what>"; an open one runs to now
    sess = HERE / "logs/sessions.log"
    if sess.exists():
        start = None
        for line in sess.read_text().splitlines():
            t, kind, *what = line.split()
            t = datetime.fromisoformat(t.rstrip("Z")).replace(tzinfo=timezone.utc)
            if kind == "OPEN":
                start, label = t, " ".join(what)
            elif kind == "CLOSE" and start:
                out.append((start, t, f"session: {label}"))
                start = None
        if start:
            out.append((start, datetime.now(timezone.utc), f"session (open): {label}"))
    return out


def mark_overlaps(rows):
    """clean_time = False when a run's interval [end - wall, end] overlaps a
    logged comparison-auditor window. Row times are local (America/Los_Angeles).
    Memory peaks are not affected (the sessions open 8k-cell demos); times are."""
    ws = windows()
    for r in rows:
        end = datetime.fromisoformat(r["time"]).replace(tzinfo=LOCAL).astimezone(timezone.utc)
        start = end - timedelta(seconds=float(r["wall_s"] or 0))
        hits = [w[2] for w in ws if w[0] < end and w[1] > start]
        # another agent's tests or Playwright Chromium alive when the run started
        # (memmon others_at_start; older rows: the top-10 ps snapshot); time only
        mem = HERE / "raw" / f"{r['id']}.mem.json"
        if mem.exists():
            m = json.loads(mem.read_text())
            oth = m.get("others_at_start")
            if oth is None:
                oth = [ln for ln in m.get("ps_before", "").splitlines() if OTHERS.search(ln)]
            if oth:
                hits.append(f"others at start: {len(oth)} ({oth[0][:80]})")
        r["clean_time"] = not hits
        # a user session can hold a large dataset in a browser: memory pressure can
        # shift phys_footprint (compression), so those rows are unclean for memory too
        r["clean_memory"] = not any(h.startswith("session") for h in hits)  # others/windows: time only
        r["overlaps"] = hits
    return rows


# One ladder per build: AnnZarro v0.3.0-preview runs on the real prefixes up to
# 95.6M (v030p) continue on synthetic stores above it, either tiled Tahoe
# (v030p_synth, build_synth.py) or build_stores.py's (v030p_syn, at the edge).
# The data source stays in results.csv (variant); the ceilings do not split it.
MERGE = {("napari", "allpoints"): "default",  # every cell: POINT_THRESHOLD raised (the tool's own advice)
         ("annzarro", "v030p_synth"): "v030p", ("annzarro", "v030p_syn"): "v030p",
         ("annzarro", "v030_synth"): "v030", ("annzarro", "v030_syn"): "v030",
         ("annzarro", "v031_syn"): "v031",
         ("annzarro", "v040_syn"): "v040",
         ("annzarro", "v041_syn"): "v041"}
SOURCE = {"v030": "real Tahoe-100M prefix", "v030_synth": "synthetic: tiled Tahoe (build_synth.py)",
          "v030_syn": "synthetic: build_stores.py (50 blobs, 4 dense genes)"}
SOURCE.update({k.replace("v030", "v030p"): v for k, v in list(SOURCE.items())})
# v030p = v030-preview 12f93f8 (memory-guard double count; superseded, kept as a record);
# v030 = the v030-preview head with the guard fix (the figure's AnnZarro row)

# subset reach: runs that open with a subset (not every cell), and the figure row
# they belong to. A rung counts only if every subset variant at that N passed.
SUBSET_OF = {("annzarro", "v030_sub"): "v030", ("annzarro", "v030_sub1m"): "v030",
             ("annzarro", "v031_sub"): "v031", ("annzarro", "v031_sub1m"): "v031",
             ("annzarro", "v040_sub"): "v040", ("annzarro", "v040_sub1m"): "v040",
             ("annzarro", "v041_sub"): "v041", ("annzarro", "v041_sub1m"): "v041",
             ("napari", "sub100k"): "default"}
SUBSET_SIZE = {("annzarro", "v041"): "the app's default subset (100,000 cells above 200,000) and a 1,000,000-cell subset",
               ("annzarro", "v040"): "the app's default subset (100,000 cells above 200,000) and a 1,000,000-cell subset",
               ("annzarro", "v031"): "the app's default subset (100,000 cells above 200,000) and a 1,000,000-cell subset",
               ("annzarro", "v030"): "the app's default subset (100,000 cells above 200,000) and a 1,000,000-cell subset",
               ("napari", "default"): "napari-spatialdata's default random subsample of 100,000 points (POINT_THRESHOLD)"}

# rows from builds that are not the release (kept in results.csv and in
# ceilings_superseded.csv; never in ceilings.csv, so no figure can pick them up)
# tools removed from the paper (operator 2026-10-06: spatial-specific): their runs stay in results.csv and
# raw/; their rows go to ceilings_out_of_scope.csv (never ceilings.csv), and they leave overlaps.csv and
# the curve
OUT_OF_SCOPE = {"tissuumaps": "operator 2026-10-06: spatial-specific tool, removed from the paper",
                "napari": "operator 2026-10-06: spatial-specific tool, removed from the paper"}

SUPERSEDED = {
    ("annzarro", "default"): "d5be664 (tahoe95-run), development build",
    ("annzarro", "noprewarm"): "d5be664 (tahoe95-run), development build, prewarm blocked",
    ("annzarro", "remote_606f0bc"): "606f0bc on hpc-node-36 via the SOCKS tunnel, dry run",
    ("annzarro", "v030"): "v030-preview 120f322 (and the v0.3.0 tag server rerun): superseded by the full ladder on v0.3.1 1391357 (operator: one version, the latest release)",
    ("annzarro", "v030p"): "v030-preview 12f93f8: memory-guard double count and old-plot retention, fixed in 120f322",
    ("annzarro", "v031"): "v0.3.1 1391357: superseded by the full ladder on v0.4.0 (RC 3bdeb09 = tag 49e2a19; operator 2026-10-06: the paper moves to v0.4.0)",
    ("annzarro", "v040"): "v0.4.0 RC 3bdeb09 (tree of tag 49e2a19): superseded by the full ladder on the v0.4.1 tag 78c9da6 (the paper cites v0.4.1)",
    ("annzarro", "v040_noguard"): "v0.4.0 RC 3bdeb09 guard off: superseded by v041_noguard",
    ("annzarro", "v031_noguard"): "v0.3.1 1391357 guard off (160M only; the series was deferred): superseded by v040_noguard",
    ("isee", "default"): "operator 2026-10-05: the default in-memory SCE (dgCMatrix) is a conversion artifact; iSEE's input is the HDF5-backed SCE (variant hdf5, 7b)",
}

# failure modes fixed after the fact, from evidence outside the run's own files: id -> (status, mode)
OVERRIDES = {
    # Loupe 10M: the desktop recorded the window going blank white after "Features" (gene colouring), not an app exit;
    # in r1 the app was force-quit by the operator after 1.5 min of blank window, which memmon saw first
    "loupe_default_run_10000000_r0": ("fail", "renderer process exited at 4.0 GiB on gene colouring; window blank "
                                      "(blank in both attempts, cell_line_id drawn; the renderer was sampled in r1: 4.03 GiB, "
                                      "consistent with a Chromium per-renderer V8 heap cap, not established)"),
    "loupe_default_run_10000000_r1": ("fail", "renderer process exited at 4.0 GiB on gene colouring; window blank "
                                      "(Renderer helper peak 4.03 GiB phys_footprint, last sample 21:23:57; consistent "
                                      "with a Chromium per-renderer V8 heap cap, not established)"),
    # a format limit of the tool's input path, not a memory or client stop (kind_16gb "input path limit")
    "tissuumaps_default_run_20000000_r1": ("input_limit", "h5wasm cannot read int64 X/indptr above 2^31 stored values "
                                           "(2,231,856,797 at 20M); page error 'Cannot convert a BigInt value to a number'"),
    # nothing drawn: a failure whatever the cause; the guard's text was not captured (case-sensitive match,
    # fixed); r1 reruns record the mode
    **{f"annzarro_v030_{v}_run_{n}_r0": ("fail", "no plot (cause pending: probable guard refusal)")
       for v, n in (("syn", 160000000), ("syn", 167000000), ("syn", 175000000), ("synth", 200000000))},
    "annzarro_v030p_run_95624334_r0": ("guard_refusal", "cat: guard_refusal (inferred: the server log has no "
        "obs request after the gene plot, so the client refused the recolour before fetching; memory-guard "
        "reproduced this refusal on 12f93f8, a double count fixed in c9272e5)"),
}


def load_all():
    rows = [r for r in csv.DictReader(open(HERE / "results.csv")) if r["id"] not in HARNESS_FAILURES]
    for r in rows:
        r["n"] = int(r["n"])
    return rows


def merge_remote(rows):
    """Competitor rungs whose server ran on the HPC (variant remote_<v>) join the
    tool's <v> row; at an N measured there, a laptop row that failed only on the
    laptop's machine cap (status cap) drops out (the cap is the laptop's, not the tool's)."""
    remote_ok = {(r["tool"], r["variant"][7:], r["n"]) for r in rows
                 if r["variant"].startswith("remote_") and r["tool"] != "annzarro"}
    out = []
    for r in rows:
        if r["tool"] != "annzarro" and r["variant"].startswith("remote_"):
            r["variant"] = r["variant"][7:]
        elif r["status"] == "cap" and (r["tool"], r["variant"], r["n"]) in remote_ok:
            continue
        out.append(r)
    return out


def load():
    """Rows that count: no harness failure, not overlapping a user session (memory)."""
    rows = [r for r in csv.DictReader(open(HERE / "results.csv")) if r["id"] not in HARNESS_FAILURES]
    for r in rows:
        r["n"] = int(r["n"])
        r["source_variant"] = r["variant"]
        if r["id"] in OVERRIDES:
            r["status"], r["failure_mode"] = OVERRIDES[r["id"]]
        r["variant"] = MERGE.get((r["tool"], r["variant"]), r["variant"])
        web = bool(r["fp_client_gb"])
        r["fp"] = float(r["fp_client_gb"] if web else r["fp_total_gb"] or "nan")
        r["fp_server"] = float(r["fp_server_gb"]) if web and r["fp_server_gb"] else math.nan  # desktop apps: no server
        r["fp_total"] = float(r["fp_total_gb"] or "nan")
    return merge_remote([r for r in mark_overlaps(rows) if r["clean_memory"]])


def guard_text(rid: str) -> str:
    """The memory guard's own refusal text for a run, if it refused (raw task JSON)."""
    p = HERE / "raw" / f"{rid}.task.json"
    if not p.exists():
        return ""
    checks = json.loads(p.read_text()).get("checks", {})
    for c in (checks.values() if isinstance(checks, dict) else checks):
        for g in (c.get("guard") or []) if isinstance(c, dict) else []:
            t = str(g).split("GUARD: ", 1)[-1]
            return t[:300]
    return ""


# variants whose max_n_gene_drawn is derived: guard-off edge runs, where the category recolour can fail
# on a buffer allocation at a size whose gene plot still drew every cell (raw task JSON, checks.gene)
GENE_EDGE = {("annzarro", "v041_noguard_edge")}


def gene_drawn(rows, tool, variant):
    """Largest N whose counted attempts (at least 2) all drew every cell by gene, read from the raw task JSON."""
    by_n = defaultdict(list)
    for r in rows:
        if r["phase"] == "run" and r["tool"] == tool and r["variant"] == variant:
            p = HERE / "raw" / f"{r['id']}.task.json"
            g = (json.loads(p.read_text()).get("checks", {}).get("gene") or {}) if p.exists() else {}
            by_n[r["n"]].append(bool(g.get("all_cells")) and g.get("status") == "ok")
    good = sorted(n for n, x in by_n.items() if len(x) >= 2 and all(x))
    return good[-1] if good else ""


def subset_reach(rows, tool, variant):
    rs = [r for r in rows if r["phase"] == "run" and SUBSET_OF.get((r["tool"], r["variant"])) == variant
          and r["tool"] == tool]
    if not rs:
        return {}
    kinds = {r["variant"] for r in rs}
    by_n = defaultdict(list)
    for r in rs:
        by_n[r["n"]].append(r)
    ok_n = sorted(n for n, x in by_n.items() if {r["variant"] for r in x if r["status"] == "ok"} == kinds
                  and max(r["fp"] for r in x) <= 16)
    bad = sorted((r for r in rs if r["status"] != "ok" or r["fp"] > 16), key=lambda r: r["n"])
    b16 = ok_n[-1] if ok_n else ""
    srv = [r["fp_server"] for r in by_n.get(b16, []) if not math.isnan(r["fp_server"])] if b16 else []
    top = max(by_n)
    return {"max_n_subset_16gb": b16,
            "subset_first_fail_n": bad[0]["n"] if bad else "",
            "subset_first_fail": (f'{bad[0]["variant"]}: {bad[0]["status"]} {bad[0]["failure_mode"]}'.strip()
                                  if bad[0]["status"] != "ok" else f'{bad[0]["variant"]}: client over 16 GiB') if bad else "",
            "server_gb_at_max_n_subset": round(max(srv), 2) if srv else "",
            "subset_kind_16gb": ("lower bound: largest N tested" if b16 and b16 == top and not bad else
                                 "ceiling" if b16 else ""),
            "subset_size": SUBSET_SIZE.get((tool, variant), "")}


# the v0.3.0 tag rerun: server footprints and local-app totals at a few sizes (the
# client numbers are 120f322's, same static/); read from results.csv, not a ceilings row
TAG_RERUN = {("annzarro", "v030_tag"), ("annzarro", "v030_tag_sub"), ("annzarro", "v030_tag_sub1m")}


# The server budget (operator decision, 2026-10-05): a flat 32 GiB for the server, in
# phys_footprint like every server value here. Data preparation (generating or
# converting a tool's input) is NOT measured (operator, later the same day): every
# tool's input is assumed to exist in the format it needs; conversion rows live in
# conversions_superseded.csv only.
SERVER_BUDGET_GIB = 32.0


def server_budget(rows):
    return SERVER_BUDGET_GIB


PREP = {}  # no preparation stops (see above); prep_stop() stays for the record and returns None


def prep_stop(rows, key, budget):
    """(N, reason) of the first preparation step that failed or passed the budget, or None."""
    steps = PREP.get(key, [])
    bad = []
    for r in rows:
        if r["phase"] != "convert" or r["variant"] not in steps:
            continue
        gb = REMOTE_PREP.get((r["variant"], r["n"]))
        if gb is not None:
            g = gb * 1e9 / 2 ** 30
            bad.append((r["n"], f"{r['variant']} {g:.1f} GiB > budget {budget:.0f} GiB "
                                f"(HPC worker, process-tree RSS peak {gb} GB; laptop run hit the 48 GiB cap)"))
        elif r["status"] == "cap":
            bad.append((r["n"], f"{r['variant']} > 48 GiB machine cap (so > budget {budget:.0f} GiB)"))
        elif r["status"] != "ok":
            bad.append((r["n"], f"{r['variant']} failed: {r['failure_mode']}"))
        elif r["fp_total"] > budget:
            bad.append((r["n"], f"{r['variant']} {r['fp_total']:.2f} GiB > budget {budget:.0f} GiB"))
    return min(bad) if bad else None


REMOTE_SERVER = {("scope", "default", 1_000_000): (0.974, "SCope's server in Docker's VM: container cgroup memory (docker stats, every 2 s), not phys_footprint; memmon sees only the docker CLI"),
                 ("shinycell", "default", 10_000_000): (7.216, "HPC worker: server process-tree RSS peak 7.216 GiB at t=505 s (HWM sum 7.216); job 10080889 rc 0"),
                 ("shinycell", "default", 5_000_000): (3.722, "HPC worker: server process-tree RSS peak 3.722 GiB at t=338 s (HWM sum 3.871); job 10080457 rc 0"),
                 ("ucsc", "default", 20_000_000): (0.022, "HPC worker: static server process-tree RSS peak 0.022 GiB (HWM sum 0.022); 86 requests 200/206; job 10072482 rc 0"),
                 ("ucsc", "default", 50_000_000): (0.022, "HPC worker: static server process-tree RSS peak 0.018 GiB at load, 0.022 GiB during the session (HWM sum identical, one process); 85 requests 200/206; job 10094741 on hpc-node-24, Slurm COMPLETED 0:0"),
                 ("ucsc", "default", 95_624_334): (0.022, "HPC worker: static server process-tree RSS peak 0.018 GiB at load, 0.022 GiB during the session (HWM sum identical, one process); 85 requests 200/206; job 10100752 on hpc-node-22 (build job 10098747), Slurm COMPLETED 0:0"),
                 ("cirrocumulus", "prepared", 20_000_000): (33.85, "HPC worker: server process-tree RSS peak 33.851 GiB at t=774 s of our session (one process; HWM sum 33.851); job 10071716 COMPLETED 0:0; a ShinyCell 10M build shared the node, not in this process tree"),
                 ("cellxgene", "default", 20_000_000): (40_479_461_376 / 2 ** 30, "HPC worker: server process-tree RSS peak during our session, 37.70 GiB (per-process HWM sum 37.87 GiB); job 10068398")}
# sizes at which a tool cannot read (or build) its input in its own format; no browser run exists there
INPUT_LIMITS = {("shinycell", "default", 20_000_000):
                "makeShinyApp refuses the HDF5-backed SCE: 'too many elements (>= 2^31) selected along dimension 1 of array' "
                "(h5mread; 2,231,856,797 stored values; HPC job 10071874, job.log lines 42-45; R 4.4.1, ShinyCell 2.1.0 "
                "5c61db7, HDF5Array 1.32.0)"}
HANG_ATTEMPTS = 3  # hang rule: a size with at least this many (non-harness) hang attempts is not renderable


def apply_server_budget(rs, budget):
    """Rows over the server budget become failures ('server_budget'); hangs are
    labelled with their attempt count."""
    hangs = defaultdict(int)
    for r in rs:
        if r["status"] == "hang":
            hangs[r["n"]] += 1
    out = []
    for r in rs:
        r = dict(r)
        key = (r["tool"], r["variant"], r["n"])
        if key in REMOTE_SERVER and r["status"] == "ok":
            r["fp_server"], r["server_note"] = REMOTE_SERVER[key]
        elif "server on HPC" in r.get("note", "") and r["status"] == "ok":
            r["server_pending"] = True  # the HPC worker has not reported this rung's server peak yet
            r["fp_server"] = math.nan  # the laptop's "server" group holds nothing for a remote server
        if r["status"] in ("ok", "cap") and not math.isnan(r["fp_server"]) and r["fp_server"] > budget:
            # (a run killed at the machine cap with its server already past 32 GiB is a server stop too)
            capped = r["status"] == "cap"
            r["status"], r["failure_mode"] = "server_budget", (
                f"server {r['fp_server']:.2f} GiB > server budget {budget:.0f} GiB"
                + (f" ({r['server_note']})" if r.get("server_note") else "")
                + (" (run killed at the machine cap: a lower bound)" if capped else ""))
        if r["status"] == "hang":
            k = hangs[r["n"]]
            r["failure_mode"] = (f"hang ({k} attempts, no progress for {300} s)" if k >= HANG_ATTEMPTS
                                 else f"hang ({k} of {HANG_ATTEMPTS} attempts so far)")
        out.append(r)
    return out


# rows whose ladder is complete under the current rules (column row_status;
# anything else is "provisional")
FINAL = {("annzarro", "v041"): "final 2026-10-07: AnnZarro v0.4.1, the tag itself (78c9da6, tree 661a454f); one version for "
                               "the whole ladder: every cell up to 200M (150-200M synthetic, every rung drawn), memory-guard "
                               "refusal at 250M (above 200,000,000, the largest plot tested to draw); subset reach 1.5B "
                               "(default and 1M subsets); 250M r0 was a harness misread of the new refusal (r1)",
         ("annzarro", "v041_noguard"): "final 2026-10-07 (not in Fig. 1c): v0.4.1 tag 78c9da6 with ui.memory.enforce off: at "
                                       "250M, 300M and 500M the tab could not allocate the positions buffer ('Array buffer "
                                       "allocation failed', shown in the panel) with the renderer at 14.4-15.9 GiB RSS (client footprint 15.9-17.9 GiB); 200M draws with "
                                       "the guard on; r0 rows were a harness misread (r1)",
         ("annzarro", "v041_noguard_edge"): "final 2026-10-09 (not in Fig. 1c): v0.4.1 tag 78c9da6 with ui.memory.enforce off, the edge "
                                            "between 200M and 250M (rungs 210M, 215M, 220M, 225M, 230M, 235M, 240M): every cell drawn by "
                                            "gene and by category up to 220M (210M, 215M and 220M, renderer 13.1-14.6 GiB RSS, client "
                                            "footprint 17.5-18.4 GiB, above the 16 GiB budget); at 225M, 230M and 235M every cell is drawn by "
                                            "gene (3 of 3, 2 of 2, 2 of 2 attempts) but the category recolour fails on 'Array buffer "
                                            "allocation failed' (225M: r1-r3, r0 was a harness misread; 230M and 235M: 2 of 2); at 240M "
                                            "the first plot fails on the same allocation in 3 of 3 runs (renderer 14.3-14.5 GiB RSS): "
                                            "the guard-off maximum is 220M by category (max_n_ok) and 235M by gene (max_n_gene_drawn)",
         ("annzarro", "v040"): "final 2026-10-06: AnnZarro v0.4.0, run on release candidate 3bdeb09 (tree bb2ace6d), "
                               "identical tree to the v0.4.0 tag 49e2a19; one version for the whole ladder: every cell up to "
                               "150M, memory-guard refusal at 160M; subset reach 1.5B (default and 1M subsets); vendor "
                               "assets checked in the page (logs/vendor_check_v040_3bdeb09.json)",
         ("scanpy", "lazy_h5ad"): "final 2026-10-06: lazy read of an h5ad; 31.6M within 16 GiB (12.22 GiB, one run); 39.7M "
                                  "over by the median of 3 runs (15.985 / 16.097 / 16.258 GiB: one of three within): client "
                                  "stop at 31.6M (a size fits only if the median of its repeats does)",
         ("ucsc", "default"): "final 2026-10-06: Cell Browser 1.2.20 served from the HPC (static site; server process tree "
                             "0.02 GiB at every size); every cell drawn to the full Tahoe-100M, 95.6M (client 12.02 GiB): "
                             "lower bound, the largest real dataset; no synthetic sizes run",
         ("cellxgene", "default"): "final 2026-10-06: ladder 1M-14.1M within both budgets (14.1M: client 5.47, server 29.65 GiB); "
                                   "16.8M in 3 of 3 runs over the 32 GiB server budget (35.48-36.12 GiB); 20M on the HPC "
                                   "(server 37.70 GiB RSS): server stop at 14.1M",
         ("cellxgene", "backed"): "final 2026-10-06: --backed; 14.1M within both budgets (server 28.40 GiB); 16.8M over the "
                                  "server budget in 2 runs (34.14, 34.43 GiB; r2 a harness port clash): server stop at 14.1M",
         ("cirrocumulus", "default"): "final 2026-10-06: h5ad served directly; 10M within both budgets (server 30.30 GiB); "
                                      "14.1M in 3 of 3 runs over the 32 GiB server budget (43.30-43.59 GiB): server stop at 10M",
         ("scanpy", "default"): "final 2026-10-06: in-memory AnnData; 7.1M in 3 of 3 runs within 16 GiB (14.38 GiB); "
                                "8.4M in 3 of 3 over (16.48-16.56 GiB): client stop at 7.1M (Docker 16 GiB check: 8.4M fits, "
                                "10M OOM)",
         ("scanpy", "backed"): "final 2026-10-06: backed h5ad; 11.9M in 3 of 3 runs within 16 GiB (13.55 GiB); 14.1M in 3 of 3 "
                               "over (16.60 GiB): client stop at 11.9M",
         ("scanpy", "lazy_zarr"): "final 2026-10-06: lazy read of a zarr store; 20M within 16 GiB (14.62 GiB), "
                                  "50M over (24.10 GiB): client stop at 20M (no intermediate sizes run)",
         ("seurat", "default"): "final 2026-10-06: in-memory dgCMatrix; 2M within 16 GiB (9.60 GiB), 5M over (24.06 GiB): "
                                "client stop at 2M (Docker 16 GiB check: 2M fits, 5M OOM)",
         ("seurat", "bpcells"): "final 2026-10-06: BPCells on-disk matrix; 20M within 16 GiB (5.82 GiB), 50M over (18.29 GiB): "
                                "client stop at 20M (no intermediate sizes run)",
         ("vitessce", "default"): "final 2026-10-06: 16.8M in 3 of 3 runs within 16 GiB (15.53-15.65 GiB); 20M in 3 of 3 over "
                                  "(16.81-16.86 GiB): client stop at 16.8M",
         ("annzarro", "v040_noguard"): "final 2026-10-06 (not in Fig. 1c): v0.4.0 (3bdeb09 = tag 49e2a19) with ui.memory.enforce "
                                       "off: every cell to 175M (client 15.63 GiB, V8 heap peak 3.53 GB); 200M hangs in 3 of 3 "
                                       "attempts (the page stops answering about 4 s after load, at 1.6 GB used JS heap; client "
                                       "8.6 GiB): beyond the guard, the next limit is the page hanging, not the 16 GiB budget",
         ("annzarro", "v031"): "final 2026-10-05: AnnZarro v0.3.1 (1391357), one version for the whole ladder: every cell up to 150M, "
                               "memory-guard refusal at 160M; subset reach 1B (default and 1M subsets)",
         ("annzarro", "v030"): "final 2026-10-05: every cell 150M (client 14.2 GiB), memory-guard refusal at 160M; subset reach 1B "
                               "(default and 1M subsets); v0.3.0 static/ identical to 120f322; server numbers rerun on the tag (v030_tag); "
                               "preparation not measured (operator)",
         ("cirrocumulus", "prepared"): "final 2026-10-05: 10M (laptop, server 13.7 GiB); 20M on the HPC: client 6.19 GiB ok, server 33.851 GiB RSS > 32 GiB: server stop",
         ("isee", "hdf5"): "final 2026-10-05: HDF5-backed SCE; 10M passes (client 0.79, server 24.57 GiB); 20M completes at the "
                           "85 GiB cap with server 49.52 GiB (r1; r0 was killed at the old 48 GiB cap): server stop at 10M",
         ("shinycell", "default"): "final 2026-10-05: 2M laptop; 5M and 10M on the HPC (server 3.72 / 7.22 GiB RSS, client 0.79 / 0.80 GiB); "
                                   "20M: makeShinyApp cannot read the HDF5-backed SCE (>= 2^31 elements): input path limit",
         ("kana", "default"): "final 2026-10-05: 1M passes (10.6 GiB), 2M Wasm abort on r1 (r0 a harness miss)",
         ("tissuumaps", "default"): "final 2026-10-05: 10M passes (client 5.0 GiB); 20M: the category plot draws, the gene colour "
                                    "fails with 'Cannot convert a BigInt value to a number' (X/indptr must be int64 above 2^31 "
                                    "stored values, ~19.2M cells on this panel)",
         ("napari", "default"): "final 2026-10-05: every cell (POINT_THRESHOLD raised) 2M (15.5 GiB), 5M over 16 GiB; "
                                "default 100k subsample 2M (12.8 GiB), 5M 25.5 GiB",
         ("manivault", "default"): "final 2026-10-05: ManiVault Studio 1.5.0-dev desktop app, measured in a Claude desktop session "
                                   "(memmon attached to the app); shared input tahoe_first<N>.h5ad (anndata 0.11.4); every cell drawn "
                                   "at each size; 1M passes (12.73 GiB), 2M client over budget (24.35 GiB > 16). Load dialog "
                                   "defaults obs, obsm and obsp ticked, left ticked; status bar 'Failed to load DensityCompute "
                                   "shader' after the Scatterplot opened, points drawn regardless",
         # claims read this note: supp1.versions.loupe ('Loupe Browser 9.1.0 desktop app') and
         # supp1.versions.loupe_engine ('(engine Electron 28.3.2, Chromium 120.'); tell manuscript-writer before rewording
         ("scope", "default"): "final 2026-10-08: SCope 1.8.2 (9ae5207) web app, built from its repository with nine "
                               "build-environment changes and run under amd64 emulation (measured/scope/README.md); input .loom "
                               "from the shared h5ad (to_loom.py); every cell drawn at 1M (client 4.03 GiB); at 2M the Chromium "
                               "renderer crashed in 2 of 2 attempts while drawing the embedding (client 4.74 / 4.73 GiB, JS heap "
                               "49.8 MB at the last sample): a crash, not slowness, so ceiling 1M; server memory is the "
                               "container's (docker stats), 0.97 GiB at 1M",
         ("loupe", "default"): "final 2026-10-05: Loupe Browser 9.1.0 desktop app (engine Electron 28.3.2, Chromium 120.0.6099.291: "
                               "Electron Framework CFBundleVersion and the binary's UA string), measured in a Claude desktop session "
                               "(memmon attached to the app); inputs .cloupe built by LoupeR 1.1.5 create_loupe from the shared "
                               "tahoe_first<N>.h5ad (anndata 0.11.4), barcodes renamed cellid_<9 digits>; every cell drawn to 5M "
                               "(5.72 GiB); 10M: cell_line_id drew all 10,000,000 cells, then gene colouring (Features, MALAT1) "
                               "left the window blank white in both attempts; in r1 the Renderer helper exited at 4.03 GiB "
                               "phys_footprint (app tree 8.18 GiB), consistent with a Chromium per-renderer V8 heap cap (not "
                               "established); far under the 16 GiB budget, and the input is not the limit"}


def ceilings(rows):
    budget = server_budget(rows)
    by = defaultdict(list)
    for r in rows:
        if r["phase"] == "run" and (r["tool"], r["variant"]) not in SUBSET_OF and (r["tool"], r["variant"]) not in TAG_RERUN:
            by[(r["tool"], r["variant"])].append(r)
    conv = defaultdict(list)
    for r in rows:
        if r["phase"] == "convert":
            conv[r["tool"]].append(r)
    out = []
    for (tool, var), rs in sorted(by.items()):
        rs = apply_server_budget(rs, budget)
        for (t, v, n), why in INPUT_LIMITS.items():
            if (t, v) == (tool, var) and not any(r["n"] >= n for r in rs if r["status"] == "ok"):
                rs = rs + [{"n": n, "status": "input_limit", "failure_mode": why, "fp": math.nan, "fp_server": math.nan,
                            "id": "", "variant": var, "tool": tool}]
        ps = prep_stop(rows, (tool, var), budget)
        if ps:  # a run at or past a failed preparation size cannot count
            rs = [r for r in rs if r["n"] < ps[0]] + [{"n": ps[0], "status": "prep_stop", "failure_mode": ps[1],
                                                        "fp": math.nan, "fp_server": math.nan, "id": "", "variant": var}]
        rec = {"tool": tool, "variant": var, "server_budget_gib": round(budget, 2)}
        ok = [r for r in rs if r["status"] == "ok"]
        bad = sorted((r for r in rs if r["status"] != "ok"), key=lambda r: r["n"])
        # a size fits a budget only if the median of its ok repeats is within it (operator rule, 2026-10-06)
        med = {n: float(np.median([r["fp"] for r in ok if r["n"] == n])) for n in {r["n"] for r in ok}}
        for b in BUDGETS:
            fit = [n for n, v in med.items() if v <= b]
            rec[f"max_n_{b}gb"] = max(fit) if fit else ""
        rec["max_n_ok"] = max((r["n"] for r in ok), default="")
        rec["rendering"] = "server" if tool in SERVER_RENDERED else "client"
        smed = {n: float(np.median(v)) for n in {r["n"] for r in ok}
                if (v := [r["fp_server"] for r in ok if r["n"] == n and not math.isnan(r["fp_server"])])}
        sfit = [n for n, v in smed.items() if v <= budget]
        rec["max_n_server_budget"] = max(sfit) if sfit else ""
        srv = [r["fp_server"] for r in ok if r["n"] == rec["max_n_ok"]]
        rec["server_gb_at_max_n_ok"] = round(max(srv), 2) if srv and not math.isnan(max(srv)) else ""
        # what the 16 GB number means: a ceiling (the client passed 16 GB, or the
        # tool failed on its own), or only a lower bound (the server passed the
        # laptop's 48 GB cap first, or every N up to the full 95.6M fitted)
        over = [r["n"] for r in ok if r["fp"] > 16]
        b16 = rec["max_n_16gb"]
        conv_bad = sorted((r for r in conv.get(tool, []) if r["status"] != "ok" and r["n"] > max(x["n"] for x in rs)),
                          key=lambda r: r["n"])
        if bad and bad[0]["status"] == "server_budget":
            rec["kind_16gb"] = f"ceiling: server exceeded the {budget:.0f} GiB server budget at {bad[0]['n']:,}"
        elif bad and bad[0]["status"] == "input_limit":
            why = bad[0]["failure_mode"].split(";")[0]
            why = why[:why.index(" (h5mread")] if " (h5mread" in why else why  # keep parentheses balanced
            rec["kind_16gb"] = f"ceiling: input path limit at {bad[0]['n']:,} ({why})"
        elif bad and bad[0]["status"] == "prep_stop":
            rec["kind_16gb"] = f"ceiling: data preparation stopped at {bad[0]['n']:,} ({bad[0]['failure_mode']})"
        elif b16 and b16 == max(r["n"] for r in rs) and conv_bad:
            c = conv_bad[0]
            if "dgCMatrix" in c["failure_mode"]:
                rec["kind_16gb"] = (f"limit of the default input path: the in-memory SCE's dgCMatrix holds at most "
                                    f"2^31-1 values, reached between {b16:,} and {c['n']:,} on this panel "
                                    f"(~110 values/cell); ~1.46M cells at Tahoe's ~1,470 values/cell (arithmetic, "
                                    f"not measured); an HDF5/DelayedArray-backed SCE avoids it (not tested)")
            else:
                rec["kind_16gb"] = (f"lower bound: input build {c['variant']} failed at {c['n']:,} "
                                    f"({c['status']} {c['failure_mode']})".strip())
        elif b16 and b16 == max(r["n"] for r in rs):
            rec["kind_16gb"] = "lower bound: largest N tested"
        elif b16 and not over and bad and bad[0]["status"] == "cap" and \
                (bad[0]["fp_server"] > bad[0]["fp"] if not math.isnan(bad[0]["fp_server"]) else False):
            rec["kind_16gb"] = f"lower bound: server exceeded the machine cap at {bad[0]['n']:,}"
        else:
            rec["kind_16gb"] = "ceiling"
        # the value Fig. 1c shows (user decision X3): server-rendered tools get a
        # marker and their server memory, never a client value
        if rec["rendering"] == "server":
            srv_ok = [(r["n"], r["fp_server"]) for r in ok if not math.isnan(r["fp_server"])]
            n_top, gb = max(srv_ok) if srv_ok else ("", "")
            rec["figure_value"] = (f"server-rendered: server {gb:.1f} GiB at {n_top / 1e6:.3g}M "
                                   f"(server within the {budget:.0f} GiB budget up to "
                                   f"{rec['max_n_server_budget'] / 1e6:.3g}M)") if srv_ok and rec["max_n_server_budget"] else ""
        else:
            lb = rec["kind_16gb"].startswith("lower bound")
            rec["figure_value"] = (f"{'>=' if lb else ''}{rec['max_n_16gb'] / 1e6:.3g}M" if rec["max_n_16gb"] else "")
        rec["first_fail_n"] = bad[0]["n"] if bad else ""
        rec["first_fail_detail"] = next((t for t in (guard_text(r["id"]) for r in bad if r["n"] == bad[0]["n"]) if t),
                                        "") if bad else ""
        rec["first_fail"] = f'{bad[0]["status"]} {bad[0]["failure_mode"]}'.strip() if bad else ""
        same = [r for r in bad if r["n"] == bad[0]["n"]]
        if bad and len(same) > 1:  # a confirmed mode (e.g. a rerun with the guard text) beats a pending one
            best = next((r for r in same if "pending" not in r["failure_mode"] and "machine cap" not in r["failure_mode"]),
                        next((r for r in same if "pending" not in r["failure_mode"]), same[0]))
            rec["first_fail"] = f'{best["status"]} {best["failure_mode"]}'.strip()
        pend = [r for r in rs if r.get("server_pending") and r["n"] == rec["max_n_16gb"]]
        if pend:
            rec["kind_16gb"] += (f" (the {pend[0]['n'] / 1e6:g}M pass is conditional: server peak pending from the HPC worker; "
                                 f"above 32 GiB it becomes a server stop at the previous size)")
        rec["n_runs"] = len(rs)
        rec["row_status"] = FINAL.get((tool, var), "provisional")
        for k in ("max_n_subset_16gb", "subset_first_fail_n", "subset_first_fail", "server_gb_at_max_n_subset",
                  "subset_kind_16gb", "subset_size"):
            rec[k] = ""
        rec.update(subset_reach(rows, tool, var))
        rec["max_n_gene_drawn"] = gene_drawn(rows, tool, var) if (tool, var) in GENE_EDGE else ""
        out.append(rec)
    return out


def next_points(rows, budget=16, resolution=1.25):
    """Bisection: for each tool x variant, the geometric midpoint between the
    largest N that fits the budget and the smallest N that does not (over the
    budget or failed), until they are within `resolution` of each other."""
    by = defaultdict(list)
    for r in rows:
        if r["phase"] == "run":
            by[(r["tool"], r["variant"])].append(r)
    out = {}
    for key, rs in sorted(by.items()):
        lo = max((r["n"] for r in rs if r["status"] == "ok" and r["fp"] <= budget), default=None)
        hi = min((r["n"] for r in rs if r["status"] != "ok" or r["fp"] > budget), default=None)
        if lo and hi and hi > lo and hi / lo > resolution:
            out[key] = (lo, hi, int(round(math.sqrt(lo * hi), -5)))
    return out


# The static figure shows these variants only: the tool's default first, then at most one more. The interactive
# charts on the evidence site show every variant, the server lines and every run.
CURVE_VARIANTS = {"annzarro": ["v041", "v041_sub"], "cellxgene": ["default", "backed"],
                  "cirrocumulus": ["default", "prepared"], "vitessce": ["default"], "ucsc": ["default"],
                  "isee": ["hdf5"], "shinycell": ["default"], "scanpy": ["default", "lazy_h5ad"],
                  "seurat": ["default", "bpcells"]}
CURVE_NOTE = {"v041": "default", "v041_sub": "subset (opens a part)", "hdf5": "HDF5-backed"}


def curve(rows, path):
    """ceiling_curve.png: nine small multiples (3 x 3), one per tool, on shared log axes: cells (1M to 1B) and
    client peak memory (GiB). Client peak only, solid lines, for the tool's default variant and at most one more
    (CURVE_VARIANTS). AnnZarro is the current release (v0.4.1): its default plot and its default subset, one mark where
    the memory guard declines the plot, one where the guard-off maximum lies. A run that did not finish sits at a
    recorded memory value: a triangle for a stop at the machine's memory cap (client + server together), a cross
    for any other failure, at the run's recorded peak. Every mark drawn is in the legend below the grid.
    Sized for 1600 x 1400 px; type 7 to 9.5 pt at 200 dpi is 15 to 26 px native, 12 px or more at 1440."""
    from matplotlib.lines import Line2D
    ceil_rows = {(r["tool"], r["variant"]): r for r in csv.DictReader(open(HERE / "ceilings.csv"))}
    run = [r for r in rows if r["phase"] == "run"]
    fig, axes = plt.subplots(3, 3, figsize=(8, 7), sharex=True, sharey=True)
    ylo, yhi = 0.4, 100
    grey = "#5f6368"
    used = set()
    for ax, tool in zip(axes.flat, [t for t in TOOLS if t in CURVE_VARIANTS]):
        notes = []
        for k, var in enumerate(CURVE_VARIANTS[tool]):
            c = COLOURS[k]
            pts, marks = defaultdict(list), defaultdict(list)
            for r in run:
                if (r["tool"], r["variant"]) != (tool, var):
                    continue
                if r["status"] == "ok":
                    pts[r["n"]].append(r["fp"])
                elif "guard_refusal" in r["failure_mode"]:
                    pass                          # drawn once, below
                elif r["status"] == "cap":        # the cap is on client + server together
                    tot = r["fp_total"] if r["fp_total"] == r["fp_total"] else r["fp"]
                    marks["cap"].append((r["n"], max(tot, r["fp"])))
                elif r["fp"] == r["fp"] and r["fp"] > 0.05:
                    marks["fail"].append((r["n"], r["fp"]))
            ns = sorted(pts)
            ax.plot([n / 1e6 for n in ns], [float(np.median(pts[n])) for n in ns], color=c, lw=1.4, marker="o", ms=2.6)
            notes.append((CURVE_NOTE.get(var, var), c))
            style = {"fail": dict(marker="x", ms=5, mew=1.2), "cap": dict(marker="^", ms=5.5, mew=0.8)}
            for kind, pp in marks.items():
                ax.plot([n / 1e6 for n, _ in pp], [min(max(v, ylo * 1.05), yhi * 0.95) for _, v in pp], ls="none",
                        color=c, mfc=c if kind == "cap" else "none", **style[kind])
                used.add(kind)
        if tool == "annzarro":                    # ONE mark at the guard's stop, ONE at the guard-off maximum
            ref = [r for r in run if (r["tool"], r["variant"]) == ("annzarro", "v041") and "guard_refusal" in r["failure_mode"]]
            if ref:                               # a refusal has no memory value: a dashed line at its size, not a point
                n = ref[0]["n"] / 1e6
                ax.axvline(n, color=grey, lw=1, ls=(0, (3, 2)), zorder=1)
                ax.text(n * 0.9, ylo * 1.12, "guard declines", fontsize=7.5, color=grey, va="bottom", ha="right")
                used.add("declined")
            e = ceil_rows.get(("annzarro", "v041_noguard_edge"))
            if e and e["max_n_ok"]:
                n0 = int(e["max_n_ok"])
                ys = [r["fp"] for r in run if (r["tool"], r["variant"], r["n"], r["status"]) == ("annzarro", "v041_noguard_edge", n0, "ok")]
                if ys:
                    y0 = float(np.median(ys))
                    ax.plot([n0 / 1e6], [y0], ls="none", marker="D", ms=5, color=grey, mfc="none", mew=1.2)
                    ax.text(n0 / 1e6 * 0.97, y0 * 1.3, "guard off", fontsize=7.5, color=grey, ha="right", va="bottom")
                    used.add("off")
        ax.set_title(NAMES.get(tool, tool), fontsize=9.5, loc="left", fontweight="bold", pad=14)
        x0 = 0.0
        for txt, c in notes:                      # the variants drawn, on the line under the title, in the lines' colors
            t = ax.text(x0, 1.025, txt, transform=ax.transAxes, fontsize=7.5, color=c, ha="left", va="bottom")
            fig.canvas.draw()
            x0 = ax.transAxes.inverted().transform((t.get_window_extent().x1, 0))[0] + 0.05
        for b_ in BUDGETS:
            ax.axhline(b_, color="#d7d9dc", lw=0.8, ls=(0, (2, 2)), zorder=0)
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_ylim(ylo, yhi); ax.set_xlim(0.8, 2000)
        ax.set_yticks([1, 10, 100]); ax.set_yticklabels(["1", "10", "100"])
        ax.set_xticks([1, 10, 100, 1000]); ax.set_xticklabels(["1M", "10M", "100M", "1B"])
        ax.minorticks_off()
        ax.tick_params(labelsize=8, labelbottom=True, length=2.5, color="#9aa0a6", labelcolor=grey)
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)
        for s_ in ("left", "bottom"):
            ax.spines[s_].set_color("#9aa0a6")
    first = axes.flat[0]
    for b_ in BUDGETS:                            # labeled once, in the first panel
        first.text(0.03, b_, f"{b_} GiB", transform=first.get_yaxis_transform(), ha="left", va="bottom", fontsize=6.5,
                   color="#8a8f96")
    for ax in axes[:, 0]:
        ax.set_ylabel("client peak (GiB)", fontsize=8.5, color=grey, labelpad=2)
    for ax in axes[-1]:
        ax.set_xlabel("cells", fontsize=8.5, color=grey, labelpad=2)
    handles = [Line2D([], [], color=COLOURS[0], lw=1.4, marker="o", ms=2.6),
               Line2D([], [], color=COLOURS[1], lw=1.4, marker="o", ms=2.6),
               Line2D([], [], color="#b9bcc1", lw=0.9, ls=(0, (2, 2)))]
    labels = ["client peak of the tool's default variant", "client peak of a second variant (named under the panel title)",
              "client budgets: 8, 16 and 32 GiB"]
    if "cap" in used:
        handles.append(Line2D([], [], ls="none", marker="^", ms=5.5, color=grey)); labels.append("stopped at the machine's memory cap")
    if "fail" in used:
        handles.append(Line2D([], [], ls="none", marker="x", ms=5, mew=1.2, color=grey)); labels.append("failed run, at its recorded peak")
    if "declined" in used:
        handles.append(Line2D([], [], ls="none", marker=r"$\vdots$", ms=9, color=grey)); labels.append("AnnZarro memory guard declines the plot here (by design)")
    if "off" in used:
        handles.append(Line2D([], [], ls="none", marker="D", ms=5, mfc="none", mew=1.2, color=grey)); labels.append("guard off: largest draw of every cell")
    fig.suptitle("Peak client memory to draw a UMAP colored by cell line and by a gene (Tahoe-100M prefixes)",
                 fontsize=10, x=0.01, y=0.985, ha="left", va="top", fontweight="bold")
    fig.subplots_adjust(left=0.075, right=0.985, top=0.885, bottom=0.2, hspace=0.62, wspace=0.12)
    fig.legend(handles, labels, loc="lower left", bbox_to_anchor=(0.01, 0.0), ncol=2, fontsize=8, frameon=False,
               labelcolor=grey, handlelength=2.2, columnspacing=1.6, labelspacing=0.5)
    fig.savefig(path, dpi=200)


def main():
    rows = load()
    cs = ceilings(rows)
    keep = [c for c in cs if (c["tool"], c["variant"]) not in SUPERSEDED and c["tool"] not in OUT_OF_SCOPE]
    old = [dict(c, superseded_because=SUPERSEDED[(c["tool"], c["variant"])]) for c in cs
           if (c["tool"], c["variant"]) in SUPERSEDED]
    oos = [dict(c, out_of_scope_because=OUT_OF_SCOPE[c["tool"]]) for c in cs
           if c["tool"] in OUT_OF_SCOPE and (c["tool"], c["variant"]) not in SUPERSEDED]
    for name, part in (("ceilings.csv", keep), ("ceilings_superseded.csv", old), ("ceilings_out_of_scope.csv", oos)):
        with open(HERE / name, "w", newline="") as f:
            w = csv.DictWriter(f, list(part[0]))
            w.writeheader()
            w.writerows(part)
    for c in cs:
        print(" | ".join(str(c[k]) for k in c))
    with open(HERE / "overlaps.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "clean_time", "clean_memory", "windows"])
        for r in mark_overlaps(load_all()):
            if r["tool"] in OUT_OF_SCOPE:
                continue
            w.writerow([r["id"], r["clean_time"], r["clean_memory"], " | ".join(r["overlaps"])])
    curve(rows, HERE / "ceiling_curve.png")
    print("\nnext bisection points (16 GB): tool variant lo hi next")
    for (t, v), (lo, hi, nx) in next_points(rows).items():
        print(t, v, lo, hi, nx)


if __name__ == "__main__":
    main()
