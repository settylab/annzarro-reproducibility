#!/usr/bin/env python
"""Bisection and repeats after the ladders (queue_*.sh).

1. While summarize.next_points() names a point (16 GB client budget, until the
   bracketing Ns are within 1.25x), build that N's inputs and run it.
2. Then run two more repeats (r1, r2) of the largest N that fits 16 GB and of
   the smallest N that does not, for every tool x variant with a crossing.

Inputs per N: h5ad from to_h5ad.py; AnnData zarr prefixes for N off the ladder
from ../scale/ceiling/cut_prefix.py (one pass for all such N); tool builds
(cirro prepare_data, cbImportScanpy + cbBuild, to_sce.R, makeShinyApp,
BPCells write) as measured conversion runs. Every run goes through run.py,
which takes the bench lock and honours the PAUSE file.

Usage: queue_bisect.py [--only TOOL:VARIANT,...] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import summarize  # noqa: E402

D = Path("$DATA_ROOT/tool_ceiling_data")
C = Path("$DEMO_ROOT")
M = Path("$DATA_ROOT/tahoe_scale/stores/n95.6M_plot/tahoe_panel_95.6M_plot.zarr")
P = Path("$DATA_ROOT/tahoe_scale/stores/rerun_prefix")
PY = str(HERE / ".venv/bin/python")
RT = str(C / "_mamba/envs/rtools/bin/Rscript")
RC = "$ENVS_ROOT/rceiling/bin/Rscript"
EXE = "$ANNZARRO_SRC/.venv-test/bin/annzarro"
LADDER = {1_000_000, 2_000_000, 5_000_000, 10_000_000, 20_000_000, 50_000_000}
DRY = False


def sh(*cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    if DRY:
        return 0
    return subprocess.run([str(c) for c in cmd], cwd=HERE).returncode


def done(rid: str) -> str | None:
    """Status of a run id already in results.csv, else None."""
    p = HERE / "results.csv"
    for r in csv.DictReader(open(p)):
        if r["id"] == rid:
            st = r["status"]
    return locals().get("st")


def run(tool, variant, n, cmd, phase="run", rep=0, web=False, timeout=None):
    rid = f"{tool}_{variant}_{phase}_{n}_r{rep}"
    st = done(rid)
    if st is not None:
        return st == "ok"
    extra = ["--web"] if web else []
    if timeout:
        extra += ["--timeout", str(timeout)]
    sh(PY, "run.py", "--tool", tool, "--variant", variant, "--phase", phase, "--n", n, "--run", rep, *extra, "--", *cmd)
    return done(rid) == "ok"


def h5ad(n):
    f = D / "h5ad" / f"tahoe_first{n}.h5ad"
    if not f.exists():
        run("input_h5ad", "to_h5ad", n, [str(HERE / ".venv-conv/bin/python"), "to_h5ad.py", M, n, f], phase="convert")
    return f


def zstore(n):
    if n == 95_624_334:
        return M
    if n in LADDER:
        return P / f"tahoe95_first{n}.zarr"
    return D / "zarr" / f"tahoe95_first{n}.zarr"


def cut_zarr(ns):
    """One cut_prefix.py pass for every off-ladder N that has no store yet."""
    need = sorted(n for n in ns if not zstore(n).exists())
    if need:
        (D / "zarr").mkdir(exist_ok=True)
        run("input_zarr", "cut_prefix", need[0],
            [PY, str(HERE.parent / "scale/ceiling/cut_prefix.py"), M, D / "zarr", *need], phase="convert",
            timeout=7200)


def one(tool, variant, n, rep=0):
    """Build what (tool, variant) needs at n, then run it once."""
    conv = dict(phase="convert", timeout=7200)
    if tool == "scanpy":
        src = zstore(n) if variant == "lazy_zarr" else h5ad(n)
        return run(tool, variant, n, [PY, "scanpy_task.py", variant, src, "{out}"], rep=rep)
    if tool == "seurat":
        f = h5ad(n)
        if variant == "bpcells":
            bp = D / "bpcells" / f"first{n}"
            if not bp.exists() and not run("seurat", "bpcells_write", n,
                                            [RC, "seurat_task.R", "bpcells_write", f, "{out}", bp], **conv):
                return False
            return run(tool, variant, n, [RC, "seurat_task.R", "bpcells", f, "{out}", bp], rep=rep)
        return run(tool, variant, n, [RC, "seurat_task.R", variant, f, "{out}"], rep=rep)
    if tool == "annzarro":
        return run(tool, variant, n, [PY, "annzarro_task.py", variant, zstore(n), "{out}", "--exe", EXE], rep=rep,
                   web=True)
    web = [PY, "web_task.py", tool, variant]
    tail = ["{out}", "--n", n, "--port", 8940]
    if tool == "vitessce":
        d = D / "vitessce" / f"first{n}"
        sh(PY, "vitessce_config.py", zstore(n), d, 8940)
        return run(tool, variant, n, web + [d] + tail, rep=rep, web=True)
    if tool == "cirrocumulus" and variant == "prepared":
        out = D / "cirro" / f"first{n}.zarr"
        if not out.exists() and not run("cirrocumulus", "prepare_data", n,
                                         [C / "cirrocumulus/.venv/bin/cirro", "prepare_data", "--format", "zarr",
                                          "--no-auto-groups", "--out", out, h5ad(n)], **conv):
            return False
        return run(tool, variant, n, web + [out] + tail, rep=rep, web=True)
    if tool == "ucsc":
        i, h = D / "ucsc" / f"in_{n}", D / "ucsc" / f"html_{n}"
        if not (h / "index.html").exists():
            if not run("ucsc", "cbImportScanpy", n,
                       [C / "ucsc-cell-browser/.venv/bin/cbImportScanpy", "-i", h5ad(n), "-o", i, "-n", f"first{n}",
                        "--clusterField=cell_line_id", "--skipMarkers", "-f", "mtx"], **conv):
                return False
            if not run("ucsc", "cbBuild", n,
                       ["bash", "-c", f"cd {i} && exec {C}/ucsc-cell-browser/.venv/bin/cbBuild -o {h}"], **conv):
                return False
        return run(tool, variant, n, web + [h] + tail, rep=rep, web=True)
    if tool in ("isee", "shinycell"):
        rds = D / "sce" / f"first{n}.rds"
        if not rds.exists() and not run(tool, "to_sce", n, [RT, "to_sce.R", h5ad(n), rds], **conv):
            return False
        if tool == "isee":
            return run(tool, variant, n, web + [rds] + tail, rep=rep, web=True)
        app = D / "shinycell" / f"first{n}"
        if not (app / "sc1meta.rds").exists() and not run(tool, "makeShinyApp", n,
                                                          [RT, "shinycell_build.R", rds, app], **conv):
            return False
        return run(tool, variant, n, web + [app] + tail, rep=rep, web=True)
    return run(tool, variant, n, web + [h5ad(n)] + tail, rep=rep, web=True)


def main():
    global DRY
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    DRY = a.dry_run
    only = {tuple(x.split(":")) for x in a.only.split(",") if x}
    tried = set()
    while True:  # 1. bisection
        pts = {k: v for k, v in summarize.next_points(summarize.load()).items()
               if (not only or k in only) and (k, v[2]) not in tried}
        if not pts:
            break
        zs = [nx for (t, v), (_, _, nx) in pts.items() if t in ("vitessce", "annzarro") or v == "lazy_zarr"]
        cut_zarr(zs)
        for (t, v), (lo, hi, nx) in pts.items():
            tried.add(((t, v), nx))
            print(f"== bisect {t} {v}: {lo} .. {hi} -> {nx}", flush=True)
            one(t, v, nx)
        if DRY:
            break
    rows = summarize.load()  # 2. repeats at the bracketing points
    for key in sorted({(r["tool"], r["variant"]) for r in rows if r["phase"] == "run"}):
        if only and key not in only:
            continue
        rs = [r for r in rows if (r["tool"], r["variant"]) == key and r["phase"] == "run"]
        lo = max((r["n"] for r in rs if r["status"] == "ok" and r["fp"] <= 16), default=None)
        hi = min((r["n"] for r in rs if r["status"] == "ok" and r["fp"] > 16), default=None)
        for n in (lo, hi):
            if n:
                for rep in (1, 2):
                    one(*key, n, rep=rep)


if __name__ == "__main__":
    main()
