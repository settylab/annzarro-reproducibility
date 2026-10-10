#!/usr/bin/env python
"""Per tag and colour: medians (min-max) over reps of the first plot and where
its time goes, recolour, zoom, pan, memory. Reads ceiling.py JSON lines.

  names   /cells: server time to first byte + transfer and stream parse
  axes    the slowest x/y/colour request (ttfb + transfer), after names
  draw    large-plot console line: load / build / draw (ms), when present
"""
import json, re, sys, statistics as st
from collections import defaultdict


def med(xs, f="{:.2f}"):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "-"
    return f.format(st.median(xs)) + (f" ({f.format(min(xs))}-{f.format(max(xs))})" if len(xs) > 1 else "")


rows = defaultdict(lambda: defaultdict(list))
meta = {}
for path in sys.argv[1:]:
    for line in open(path):
        d = json.loads(line)
        k = (d["tag"], d["color"])
        r = rows[k]
        if d["event"] == "first_plot":
            if d["status"] != "ok":
                r["fail"].append(d["status"])
                continue
            r["first"].append(d["seconds"])
            api = d.get("api", [])
            cells = [x for x in api if x["url"].startswith("data/cells")]
            if cells:
                r["names_srv"].append(cells[0].get("ttfb_ms", 0) / 1e3)
                r["names_xfer"].append(cells[0].get("recv_ms", 0) / 1e3)
            axes = [x for x in api if re.match(r"data/(obsm|obs\?|layer)", x["url"])]
            if axes:
                r["axes"].append(max(x.get("ttfb_ms", 0) + x.get("recv_ms", 0) for x in axes) / 1e3)
            for c in d.get("console", []):
                m = re.search(r"load (\d+) ms, build (\d+) ms, draw (\d+) ms", c)
                if m:
                    r["load"].append(int(m[1]) / 1e3); r["build"].append(int(m[2]) / 1e3); r["draw"].append(int(m[3]) / 1e3)
            r["v8"].append((d.get("v8_used_peak") or 0) / 1e9)
            r["ab"].append((d.get("v8_backing_peak") or 0) / 1e9)
            r["rss"].append((d.get("renderer_rss") or 0) / 1e9)
            r["gpu"].append((d.get("gpu_rss") or 0) / 1e9)
            r["srv"].append((d.get("server_rss") or 0) / 1e9)
            meta[k] = (d.get("browser"), d.get("flags"), d.get("gl"), d.get("n_points"))
        elif d["event"] == "recolour" and d["status"] == "ok":
            r["recolour"].append(d["seconds"])
            r["rss"].append((d.get("renderer_rss") or 0) / 1e9)
        elif d["event"] == "zoom" and d["status"] == "ok":
            r["zoom"].append(d["seconds"])
        elif d["event"] == "drag" and d["status"] == "ok":
            r["pan_redraw"].append(d.get("gpu_draw_ms", 0) / 1e3)
            r["pan_settle"].append((d.get("relayout_after_up_ms") or 0) / 1e3)

print("| tag | colour | points | reps ok | first plot s | names server s | names transfer+parse s | slowest axis s | "
      "plot load/build/draw s | recolour s | zoom s | pan: one redraw s | pan: settle after release s | "
      "V8 heap GB | ArrayBuffers GB | renderer RSS GB | GPU RSS GB | server RSS GB | failures |")
print("|" + "---|" * 19)
for (tag, colour), r in rows.items():
    m = meta.get((tag, colour), (None, None, None, None))
    lbd = "-" if not r["load"] else f"{st.median(r['load']):.1f}/{st.median(r['build']):.1f}/{st.median(r['draw']):.1f}"
    print(f"| {tag} | {colour} | {m[3]:,} | {len(r['first'])} | {med(r['first'], '{:.1f}')} | {med(r['names_srv'], '{:.1f}')} | "
          f"{med(r['names_xfer'], '{:.1f}')} | {med(r['axes'])} | {lbd} | {med(r['recolour'])} | {med(r['zoom'])} | "
          f"{med(r['pan_redraw'])} | {med(r['pan_settle'], '{:.1f}')} | {med(r['v8'])} | {med(r['ab'])} | "
          f"{max(r['rss'] or [0]):.2f} | {max(r['gpu'] or [0]):.2f} | {max(r['srv'] or [0]):.1f} | {';'.join(r['fail']) or '-'} |"
          if m[3] else f"| {tag} | {colour} | - | 0 | - | | | | | | | | | | | | | | {';'.join(r['fail'])} |")
k = next(iter(meta))
print(f"\nbrowser: {meta[k][0]}; flags: {meta[k][1]}; WebGL: {meta[k][2]}")
