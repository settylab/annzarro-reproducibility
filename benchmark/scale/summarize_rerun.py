#!/usr/bin/env python
"""Tables of the release-0.3 rerun (NOTES.md, "Results (release-0.3)").

In:  results/browser_rerun*.jsonl (ceiling/ceiling.py), results/http_rerun.csv (bench_http.py)
Out: results/browser_rerun_events.csv   one row per measured event
     results/browser_rerun_summary.csv  per (tag, n_cells, color, event): median, min, max
     results/http_rerun_summary.csv     per (n_cells, interaction, condition): median, min, max
Column meanings are in NOTES.md.
"""
import csv
import json
import re
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parent / "results"
GB = 1e9
FULL = 95624334

# Windows (UTC) in which the user live-tested AnnZarro on port 8810, or functional
# browser tests ran without the bench lock (coordinator, 2026-10-03). A row whose
# run interval [end - seconds, end] meets one is clean=False: its times are not
# used; its crash/ok outcome and memory limits still stand.
OVERLAP = [("2026-10-03T17:56:44", "2026-10-03T18:21:00"), ("2026-10-03T19:48:41", "2026-10-03T20:18:58"),
           ("2026-10-03T20:20:58", "2026-10-03T20:23:06"), ("2026-10-03T20:23:26", "2026-10-03T20:26:15"),
           ("2026-10-03T20:26:44", "2026-10-03T21:24:58")]
_WIN = [tuple(datetime.fromisoformat(t).replace(tzinfo=timezone.utc).timestamp() for t in w) for w in OVERLAP]


def clean_at(end: float, seconds: float = 0.0) -> bool:
    start = end - (seconds or 0.0)
    return not any(start <= b and end >= a for a, b in _WIN)


def n_of(store: str) -> int:
    m = re.search(r"first(\d+)", store)
    if m:
        return int(m.group(1))
    m = re.search(r"syn_(\d+)", store)
    if m:
        return int(m.group(1))
    return FULL if "95.6M" in store else -1


EV = ["clean", "tag", "n_cells", "store", "color", "rep", "event", "seq", "status", "seconds", "n_points", "large_mode",
      "js_heap_gb", "v8_used_peak_gb", "v8_backing_peak_gb", "renderer_rss_gb", "gpu_rss_gb", "browser_rss_gb",
      "server_rss_gb", "api_requests", "api_bytes", "api_ttfb_max_s", "browser", "flags", "time"]


def browser(paths):
    rows = []
    for p in paths:
        for line in open(p):
            d = json.loads(line)
            api = d.get("api") or []
            g = lambda k: round(d[k] / GB, 3) if isinstance(d.get(k), (int, float)) and d[k] >= 0 else ""
            rows.append({
                "tag": d.get("tag"), "n_cells": n_of(d["store"]), "store": d["store"], "color": d.get("color"),
                "rep": d.get("rep"), "event": d["event"], "seq": d.get("seq", ""), "status": d["status"],
                "seconds": round(d["seconds"], 3) if d.get("seconds") is not None else "",
                "n_points": d.get("n_points", ""),
                "large_mode": int(any("Large cell plot" in c for c in d.get("console") or [])) if d["event"] == "first_plot" else "",
                "js_heap_gb": g("js_heap"), "v8_used_peak_gb": g("v8_used_peak"),
                "v8_backing_peak_gb": g("v8_backing_peak"), "renderer_rss_gb": g("renderer_rss"),
                "gpu_rss_gb": g("gpu_rss"), "browser_rss_gb": g("browser_rss"), "server_rss_gb": g("server_rss"),
                "api_requests": len(api), "api_bytes": sum(max(r.get("bytes") or 0, 0) for r in api),
                "api_ttfb_max_s": round(max([(r.get("ttfb_ms") or 0) for r in api] or [0]) / 1000, 3),
                "browser": d.get("browser", ""), "flags": d.get("flags", ""), "time": round(d["time"]),
                # first_plot: the run began with the server start, a few s before navigation
                "clean": d.get("clean", True) and clean_at(d["time"], (d.get("seconds") or 0) + 30)})
    return rows


def agg(vals):
    v = [x for x in vals if x != "" and x is not None]
    return (round(st.median(v), 3), round(min(v), 3), round(max(v), 3)) if v else ("", "", "")


def summarize_browser(rows):
    grp = defaultdict(list)
    for r in rows:
        if r["clean"]:
            grp[(r["tag"], r["n_cells"], r["color"], r["event"])].append(r)
    out = []
    for (tag, n, color, ev), rs in sorted(grp.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3])):
        ok = [r for r in rs if r["status"] == "ok"]
        bad = sorted({r["status"] for r in rs if r["status"] != "ok"})
        sec = agg([r["seconds"] for r in ok])
        o = {"tag": tag, "n_cells": n, "color": color, "event": ev, "n_ok": len(ok), "n_total": len(rs),
             "fail_status": ";".join(bad), "seconds_median": sec[0], "seconds_min": sec[1], "seconds_max": sec[2],
             "large_mode": max([r["large_mode"] for r in rs if r["large_mode"] != ""] or [""])}
        for k in ("js_heap_gb", "v8_used_peak_gb", "v8_backing_peak_gb", "renderer_rss_gb", "gpu_rss_gb",
                  "server_rss_gb"):
            o[k.replace("_gb", "_max_gb")] = max([r[k] for r in rs if r[k] != ""] or [""])
        o["api_bytes_median"] = agg([r["api_bytes"] for r in ok])[0]
        out.append(o)
    return out


def summarize_http(path):
    grp = defaultdict(list)
    for r in csv.DictReader(open(path)):
        if clean_at(float(r["timestamp"]), float(r["latency_s"]) if r["latency_s"] not in ("", "nan") else 0):
            grp[(int(r["n_cells"]), r["interaction"], r["condition"])].append(r)
    out = []
    for (n, inter, cond), rs in sorted(grp.items()):
        ok = [r for r in rs if r["status"] == "200"]
        lat = agg([float(r["latency_s"]) for r in ok])
        out.append({"n_cells": n, "interaction": inter, "condition": cond, "n_ok": len(ok), "n_total": len(rs),
                    "fail_status": ";".join(sorted({r["status"] for r in rs if r["status"] != "200"})),
                    "latency_median_s": lat[0], "latency_min_s": lat[1], "latency_max_s": lat[2],
                    "bytes_median": agg([int(r["bytes"]) for r in ok])[0],
                    "server_rss_peak_max_gb": round(max([int(r["rss_peak"] or 0) for r in rs] or [0]) / GB, 3)})
    return out


def ceiling(paths, probe):
    """Every-cell first plots at and beyond 95.6M: ceiling.py runs (tags ceil_*) and probe.py verdicts."""
    rows = []
    for p in paths:
        for line in open(p):
            d = json.loads(line)
            if d["event"] == "first_plot" and str(d.get("tag", "")).startswith("ceil"):
                rows.append({"clean": clean_at(d["time"], (d.get("seconds") or 0) + 30),
                             "source": "ceiling.py", "tag": d["tag"], "n_cells": n_of(d["store"]), "color": d["color"],
                             "rep": d["rep"], "flags": d.get("flags", ""), "status": d["status"],
                             "seconds": round(d["seconds"], 2) if d.get("seconds") is not None else "",
                             "v8_used_peak_gb": round(d.get("v8_used_peak", 0) / GB, 3),
                             "v8_backing_peak_gb": round(d.get("v8_backing_peak", 0) / GB, 3),
                             "renderer_rss_peak_gb": round(d.get("renderer_rss", 0) / GB, 3),
                             "gpu_rss_peak_gb": round(d.get("gpu_rss", 0) / GB, 3),
                             "server_rss_peak_gb": round(d.get("server_rss", 0) / GB, 3)})
    for line in open(probe):
        d = json.loads(line)
        if d["kind"] != "verdict":
            continue
        pk = d["peak"]
        # probe.py lines before 2026-10-03 21:25Z carry no epoch; all of them ran 20:46-21:24Z
        rows.append({"clean": clean_at(d["epoch"], d.get("seconds", 0)) if "epoch" in d else False,
                     "source": "probe.py", "tag": d["tag"], "n_cells": d["n"], "color": d["color"],
                     "rep": d["tag"].rsplit("_r", 1)[-1] if "_r" in d["tag"] else "", "flags": d["flags"],
                     "status": d["status"], "seconds": "",   # probe.py times are not plot times
                     "v8_used_peak_gb": "", "v8_backing_peak_gb": "",
                     "renderer_rss_peak_gb": round(pk["renderer"] / GB, 3), "gpu_rss_peak_gb": round(pk["gpu"] / GB, 3),
                     "server_rss_peak_gb": round(pk["server"] / GB, 3)})
    # coordinator ruling (2026-10-04): crash/ok outcomes and memory (heap cap, bytes per point) are
    # deterministic per isolate and count from every row; times count only from clean rows
    for r in rows:
        r["clean_outcome"] = True
    return sorted(rows, key=lambda r: (r["n_cells"], r["source"], r["color"], str(r["tag"])))


def write(path, rows):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(path.name, len(rows))


if __name__ == "__main__":
    paths = sorted(p for p in R.glob("browser_rerun*.jsonl") if "probe" not in p.name)
    if paths:
        ev = browser(paths)
        write(R / "browser_rerun_events.csv", [{k: r[k] for k in EV} for r in ev])
        write(R / "browser_rerun_summary.csv", summarize_browser(ev))
    if (R / "browser_rerun_probe.jsonl").exists():
        write(R / "ceiling_rerun.csv", ceiling(paths, R / "browser_rerun_probe.jsonl"))
    if (R / "http_rerun.csv").exists():
        write(R / "http_rerun_summary.csv", summarize_http(R / "http_rerun.csv"))
    # release tags (v030: 3fb6826, v031: 1391357): the same tables from the release reruns (queue_v03*.sh)
    for tag in ("v030", "v031", "v040", "v041"):
        files = sorted(R.glob(f"browser_{tag}*.jsonl"))
        if files:
            ev = browser(files)
            write(R / f"browser_{tag}_events.csv", [{k: r[k] for k in EV} for r in ev])
            write(R / f"browser_{tag}_summary.csv", summarize_browser(ev))
        if (R / f"http_{tag}.csv").exists():
            write(R / f"http_{tag}_summary.csv", summarize_http(R / f"http_{tag}.csv"))
