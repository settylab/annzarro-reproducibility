#!/usr/bin/env python
"""Reruns of memory-unclean rows (overlapping a user session) that a reported
value depends on. Builds are rerun into scratch dirs (the ladder's sites stay)."""
import shutil
import subprocess
import queue_bisect as qb

D, C = qb.D, qb.C
qb.run("cirrocumulus", "default", 14_100_000, [qb.PY, "web_task.py", "cirrocumulus", "default",
       qb.h5ad(14_100_000), "{out}", "--n", 14_100_000, "--port", 8943], rep=1, web=True)
qb.one("ucsc", "default", 5_000_000, rep=3)
i, h = D / "ucsc_r1" / "in_10000000", D / "ucsc_r1" / "html_10000000"
shutil.rmtree(i, ignore_errors=True)
qb.run("ucsc", "cbImportScanpy", 10_000_000, [C / "ucsc-cell-browser/.venv/bin/cbImportScanpy", "-i",
       qb.h5ad(10_000_000), "-o", i, "-n", "first10000000", "--clusterField=cell_line_id", "--skipMarkers",
       "-f", "mtx"], phase="convert", rep=1, timeout=7200)
shutil.rmtree(i, ignore_errors=True)
shutil.rmtree(h, ignore_errors=True)
