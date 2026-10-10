#!/usr/bin/env python
"""Per-request times of a run's first plot and category recolour, from ceiling.py's API records
(shots/<run id>.ceiling.jsonl: time to first byte and receive time per /api/v1 request, browser side).
Appends rows to subset_request_times.csv (run, event, request, ttfb_s, total_s, bytes); rows of a run
already in the file are not written again.

Usage: python request_times.py RUN_ID [RUN_ID ...]   e.g. annzarro_v041_sub_run_1000000000_r0
"""
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "subset_request_times.csv"
LABELS = [(r"^data/subset\?", "subset"), (r"^data/subset/locate\?", "subset locate"),
          (r"^data/fingerprint\?", "fingerprint"), (r"^data/cells\?", "cell names"),
          (r"^data/obsm/X_umap", "X_umap column"), (r"^data/layer/X", "X column"), (r"^data/obs\?", "obs column")]


def rows(rid):
    for line in open(HERE / "shots" / f"{rid}.ceiling.jsonl"):
        e = json.loads(line)
        if e["event"] not in ("first_plot", "recolour_cat"):
            continue
        for a in sorted(e.get("api") or [], key=lambda a: a.get("t_rel", 0)):
            label = next((n for p, n in LABELS if re.search(p, a["url"])), None)
            if label and a.get("ttfb_ms") is not None:
                yield [rid, e["event"], label, round(a["ttfb_ms"] / 1000, 1),
                       round((a["ttfb_ms"] + (a.get("recv_ms") or 0)) / 1000, 1), a.get("bytes")]


if __name__ == "__main__":
    have = {r["run"] for r in csv.DictReader(open(OUT))}
    with open(OUT, "a", newline="") as f:
        w = csv.writer(f)
        for rid in sys.argv[1:]:
            if rid in have:
                print(rid, "already in", OUT.name)
                continue
            new = list(rows(rid))
            w.writerows(new)
            print(rid, len(new), "rows")
