"""CPU profile of Plotly.relayout zooms on the harness page (scattergl only)."""
import sys, json, time, collections
from pathlib import Path
from playwright.sync_api import sync_playwright
from ceiling import HERE, Server
store, chunk, mode = sys.argv[1], int(sys.argv[2]), sys.argv[3]
flags = sys.argv[4:]
srv = Server(str(HERE / ".venv-base/bin/annzarro"), "$DATA_ROOT/tahoe_scale_ceiling", 8961, HERE / "home" / "p8961")
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chromium", args=["--enable-precise-memory-info"] + flags)
        page = b.new_page(viewport={"width": 1400, "height": 1000})
        page.route("**/plotly-2.20.0.min.js", lambda r: r.fulfill(path=str(HERE / "plotly-2.20.0.js"), content_type="application/javascript"))
        page.route("**/ceiling.html", lambda r: r.fulfill(path=str(HERE / "harness.html"), content_type="text/html"))
        page.goto(srv.root + "/ceiling.html")
        r = page.evaluate("o => run(o)", dict(store=store, mode=mode, chunk=chunk, typed=True, hover=False))
        print({k: r[k] for k in ("traces", "newplot_ms", "fetch_ms")})
        cdp = page.context.new_cdp_session(page)
        cdp.send("Profiler.enable"); cdp.send("Profiler.setSamplingInterval", {"interval": 200}); cdp.send("Profiler.start")
        zs = [page.evaluate("d => zoom(d)", -1 if k % 2 == 0 else 1) for k in range(4)]
        prof = cdp.send("Profiler.stop")["profile"]
        print("zooms", [round(z["frame_ms"]) for z in zs])
        nodes = {n["id"]: n for n in prof["nodes"]}
        dt = collections.Counter()
        deltas = prof.get("timeDeltas", [])
        for s, d in zip(prof["samples"], deltas):
            cf = nodes[s]["callFrame"]
            dt[f'{cf["functionName"] or "(anon)"} {cf["url"].rsplit("/",1)[-1]}:{cf["lineNumber"]+1}'] += d
        tot = sum(dt.values())
        for k, v in dt.most_common(15):
            print(f"{v/1000:8.0f} ms {100*v/tot:5.1f}%  {k}")
        b.close()
finally:
    srv.stop()
