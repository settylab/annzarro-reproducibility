#!/usr/bin/env python
"""Tables from the JSON lines of ceiling.py and harness.py (results/*.jsonl)."""
import json, sys, glob, statistics as st
from collections import defaultdict

def load(pat):
    rows = []
    for f in sorted(glob.glob(pat)):
        rows += [json.loads(l) for l in open(f)]
    return rows

def gb(x): return f"{x/1e9:.2f}" if isinstance(x, (int, float)) and x > 0 else "-"

def ceiling_table(pat):
    rows = load(pat)
    by = defaultdict(dict)
    for d in rows:
        k = (d.get("tag"), d["store"], d["color"], d.get("rep"))
        by[k].setdefault("rec", [])
        if d["event"] == "first_plot":
            by[k]["fp"] = d
        elif d["event"] in ("recolour", "zoom", "drag"):
            by[k].setdefault(d["event"], []).append(d)
    print("| tag | N | colour | rep | status | first plot s | recolour s | zoom s | drag frame ms (median/p95) | GPU draw ms | V8 heap peak GB | ArrayBuffers GB | renderer RSS GB | GPU RSS GB | server RSS GB |")
    print("|" + "---|" * 15)
    for k, v in by.items():
        fp = v.get("fp")
        if not fp: continue
        n = fp.get("n") or fp.get("n_points") or 0
        rc = [r["seconds"] for r in v.get("recolour", []) if r["status"] == "ok"]
        zm = [r["seconds"] for r in v.get("zoom", []) if r["status"] == "ok"]
        dr = [r for r in v.get("drag", []) if r["status"] == "ok"]
        rss = max([fp.get("renderer_rss") or 0] + [r.get("renderer_rss") or 0 for r in v.get("recolour", [])])
        secs = f"{fp['seconds']:.1f}" if fp.get("seconds") is not None else "-"
        print(f"| {k[0]} | {n:,} | {k[2]} | {k[3]} | {fp['status']} | {secs} | "
              + (f"{st.median(rc):.2f}" if rc else "-") + " | "
              + (f"{st.median(zm):.2f}" if zm else "-") + " | "
              + (f"{st.median([r['median_ms'] for r in dr]):.0f}/{st.median([r['p95_ms'] for r in dr]):.0f}" if dr else "-") + " | "
              + (f"{st.median([r['gpu_draw_ms'] for r in dr]):.0f}" if dr else "-") + " | "
              + f"{gb(fp.get('v8_used_peak'))} | {gb(fp.get('v8_backing_peak'))} | {gb(rss)} | {gb(fp.get('gpu_rss'))} | {gb(fp.get('server_rss'))} |")

def harness_table(pat):
    print("| tag | N | traces | status | fetch ms | prep ms | newPlot ms | zoom (relayout) ms median | V8 used GB | ArrayBuffers GB | renderer RSS GB | GPU RSS GB | error |")
    print("|" + "---|" * 13)
    for d in load(pat):
        hu = d.get("heap_usage") or {}
        zm = [z["frame_ms"] for z in d.get("zoom", [])]
        print(f"| {d['tag']} | {d['store'].split('_')[1].split('.')[0]} | {d.get('traces','-')} | {d['status']} | "
              f"{d.get('fetch_ms',0):.0f} | {d.get('prep_ms',0):.0f} | {d.get('newplot_ms',0):.0f} | "
              + (f"{st.median(zm):.0f}" if zm else "-") +
              f" | {gb(hu.get('usedSize'))} | {gb(hu.get('backingStorageSize'))} | {gb(d.get('renderer_rss'))} | {gb(d.get('gpu_rss'))} | {(d.get('error') or '')[:80]} |")

if __name__ == "__main__":
    kind, pat = sys.argv[1], sys.argv[2]
    (harness_table if kind == "harness" else ceiling_table)(pat)
