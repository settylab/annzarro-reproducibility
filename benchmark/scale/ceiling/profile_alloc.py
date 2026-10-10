#!/usr/bin/env python
"""Where the renderer's memory goes when one Cell Plot draws N points.

Opens the same deep link as ceiling.py (one Cell Plot, subset null) with V8's
sampling heap profiler running (CDP HeapProfiler.startSampling, 64 KiB
interval) from before navigation until the plot is ready, and reports
allocation sites by bytes:

  live   objects still alive when the plot is ready (what the plot holds)
  total  everything allocated during the load, collected or not (churn;
         an upper bound on the transient peak)

The vendored Plotly bundle (plotly-2.20.0.min.js) is replaced through
page.route by the unminified plotly.js-dist 2.20.0 build of the same version
(--plotly), so Plotly frames carry function names and line numbers.

ArrayBuffer backing stores (typed arrays) are not on the V8 heap and do not
appear in the sampling profile; they are reported from
performance.measureUserAgentSpecificMemory where available and as the
difference between renderer RSS and the JS heap.
"""

from __future__ import annotations

import argparse
import collections
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from ceiling import HERE, Server, Sampler, STATE_JS, link, view


def walk(node, stack, out):
    cf = node["callFrame"]
    url = cf["url"].rsplit("/", 1)[-1]
    frame = f'{cf["functionName"] or "(anon)"} {url}:{cf["lineNumber"] + 1}' if url else cf["functionName"]
    st = stack + [frame]
    if node.get("selfSize"):
        out.append((node["selfSize"], st))
    for c in node.get("children", []):
        walk(c, st, out)


def summarise(profile, n, top=25):
    rows = []
    walk(profile["head"], [], rows)
    total = sum(s for s, _ in rows)
    by_site = collections.Counter()
    by_ctx = collections.Counter()
    for size, st in rows:
        by_site[st[-1]] += size
        # nearest AnnZarro frame (static/js) for context
        az = next((f for f in reversed(st) if ".js:" in f and "plotly" not in f), "-")
        by_ctx[(st[-1], az)] += size
    lines = [f"total sampled {total / 1e6:.0f} MB = {total / n:.1f} B/pt"]
    for (site, az), size in by_ctx.most_common(top):
        lines.append(f"{size / 1e6:9.1f} MB {size / n:7.1f} B/pt  {site}   <- {az}")
    return "\n".join(lines), total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("store")
    ap.add_argument("--color", default="gene")
    ap.add_argument("--exe", default=str(HERE / ".venv-base/bin/annzarro"))
    ap.add_argument("--port", type=int, default=8955)
    ap.add_argument("--plotly", default="")
    ap.add_argument("--mode", default="live", choices=["live", "total"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--args", default="")
    a = ap.parse_args()
    n = int(json.loads((Path(a.store) / "obs/_index/.zarray").read_text())["shape"][0])
    srv = Server(a.exe, str(Path(a.store).parent), a.port, HERE / "home" / f"p{a.port}")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chromium",
                                   args=["--enable-precise-memory-info"] + a.args.split())
            smp = Sampler(srv, 25)
            smp.start()
            page = b.new_page(viewport={"width": 1400, "height": 1000})
            if a.plotly:
                page.route("**/plotly-2.20.0.min.js",
                           lambda r: r.fulfill(path=a.plotly, content_type="application/javascript"))
            page.goto(srv.root + "/api/v1/config")
            cdp = page.context.new_cdp_session(page)
            cdp.send("HeapProfiler.enable")
            coll = a.mode == "total"
            cdp.send("HeapProfiler.startSampling", {"samplingInterval": 65536,
                                                    "includeObjectsCollectedByMajorGC": coll,
                                                    "includeObjectsCollectedByMinorGC": coll})
            t0 = time.perf_counter()
            page.goto(link(srv.root, a.store, view(a.color)))
            while True:
                st = page.evaluate(STATE_JS)
                if st["n"] >= n and st["busy"] == 0:
                    break
                if time.perf_counter() - t0 > 900 or smp.low:
                    raise SystemExit(f"not ready: {st}")
                time.sleep(0.2)
            time.sleep(2)
            t = time.perf_counter() - t0
            prof = cdp.send("HeapProfiler.stopSampling")["profile"]
            heap = page.evaluate("() => performance.memory.usedJSHeapSize")
            txt, total = summarise(prof, n)
            head = (f"{Path(a.store).name} color={a.color} mode={a.mode} ready {t:.1f}s  "
                    f"js_heap {heap / 1e9:.2f} GB ({heap / n:.0f} B/pt)  renderer RSS now "
                    f"{smp.cur['renderer'] / 1e9:.2f} GB peak {smp.peak['renderer'] / 1e9:.2f} GB "
                    f"({smp.peak['renderer'] / n:.0f} B/pt)  gpu peak {smp.peak['gpu'] / 1e9:.2f} GB")
            Path(a.out).write_text(head + "\n" + txt + "\n")
            Path(a.out).with_suffix(".heapprofile").write_text(json.dumps(prof))
            print(head)
            print(txt)
            smp.running = False
            b.close()
    finally:
        srv.stop()


if __name__ == "__main__":
    main()
