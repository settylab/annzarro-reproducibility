#!/usr/bin/env python
"""Drive harness.html (Plotly scattergl alone on AnnZarro's binary responses).

Usage: harness.py STORE... --mode cat --chunk 99999 [--typed] [--hover] [--args FLAGS]
One fresh browser per store; JSON lines to --out.
"""
import argparse, json, time
from pathlib import Path
from playwright.sync_api import sync_playwright
from ceiling import HERE, Server, Sampler, GL_JS, envcapture

ap = argparse.ArgumentParser()
ap.add_argument("stores", nargs="+")
ap.add_argument("--mode", default="cat")
ap.add_argument("--chunk", type=int, default=0)
ap.add_argument("--bins", type=int, default=64)
ap.add_argument("--typed", action="store_true")
ap.add_argument("--hover", action="store_true")
ap.add_argument("--channel", default="chromium")
ap.add_argument("--args", default="")
ap.add_argument("--zoom", type=int, default=4)
ap.add_argument("--port", type=int, default=8956)
ap.add_argument("--out", required=True)
ap.add_argument("--tag", default="")
ap.add_argument("--exe", default=str(HERE / ".venv-base/bin/annzarro"))
a = ap.parse_args()
envcapture.require_clean_bench()
flags = ["--enable-precise-memory-info"] + a.args.split()
srv = Server(a.exe, "$DATA_ROOT/tahoe_scale_ceiling", a.port, HERE / "home" / f"p{a.port}")
try:
    with sync_playwright() as pw:
        for store in a.stores:
            kw = dict(args=flags)
            if a.channel != "bundled":
                kw["channel"] = a.channel
            b = pw.chromium.launch(**kw)
            if store == a.stores[0]:
                envcapture.record(a.out, exe=a.exe, server_root=srv.root,
                                  browser={"channel": a.channel, "version": b.version, "flags": flags, "headless": True},
                                  stores=a.stores)
            smp = Sampler(srv, 25); smp.start()
            page = b.new_page(viewport={"width": 1400, "height": 1000})
            crashed, logs = [], []
            page.on("crash", lambda *_: crashed.append(1))
            page.on("console", lambda m: logs.append(f"{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
            page.route("**/ceiling.html", lambda r: r.fulfill(path=str(HERE / "harness.html"), content_type="text/html"))
            page.goto(srv.root + "/ceiling.html")
            gl = page.evaluate(GL_JS)
            rec = dict(tag=a.tag, store=Path(store).name, mode=a.mode, chunk=a.chunk, typed=a.typed, hover=a.hover,
                       browser=f"{a.channel} {b.version}", flags=" ".join(flags), gl=gl)
            t0 = time.perf_counter()
            try:
                r = page.evaluate("o => run(o)", dict(store=store, mode=a.mode, chunk=a.chunk, typed=a.typed,
                                                      hover=a.hover, bins=a.bins))
                rec.update(r, status="ok", wall_s=time.perf_counter() - t0)
                cdp = page.context.new_cdp_session(page)
                rec["heap_usage"] = cdp.send("Runtime.getHeapUsage")
                page.screenshot(path=str(HERE / "shots" / f"h_{a.tag}_{Path(store).stem}.png"))
                zs = []
                for k in range(a.zoom):
                    zs.append(page.evaluate("d => zoom(d)", -1 if k % 2 == 0 else 1))
                rec["zoom"] = zs
                rec["heap_after_zoom"] = page.evaluate("() => performance.memory.usedJSHeapSize")
                rec["heap_usage_after_zoom"] = cdp.send("Runtime.getHeapUsage")
            except Exception as e:
                rec.update(status="crash" if crashed else "error", error=str(e)[:300], wall_s=time.perf_counter() - t0)
            rec.update(renderer_rss=smp.peak["renderer"], gpu_rss=smp.peak["gpu"], min_free=smp.min_free_seen,
                       console=logs[:10])
            smp.running = False
            print(json.dumps({k: v for k, v in rec.items() if k not in ("flags", "gl", "console")}), flush=True)
            with open(a.out, "a") as f:
                f.write(json.dumps(rec) + "\n")
            b.close()
            if rec["status"] != "ok":
                break
finally:
    srv.stop()
