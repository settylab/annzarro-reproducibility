#!/usr/bin/env python
"""One every-cell first plot, observed from outside so that a failure leaves a record.

ceiling.py hung at 200M points: the page's renderer process vanished without a
Playwright crash event and the next CDP call never returned. This probe uses the
async API with a timeout on every browser call, and writes a timeline line every
0.5 s (renderer, GPU and browser RSS, server RSS, free memory, last page state)
plus every console message, crash, request and response as it happens, to
--out (JSON lines). The last line is the verdict:

  ok             the panel holds N points and the page is idle
  crash          Playwright's page 'crash' event
  renderer_gone  the page's renderer process exited without a crash event
  unresponsive   page.evaluate did not return for --stall seconds
  timeout        no plot within --limit seconds
  low_memory     system free memory below --min-free percent (run stopped)

Usage: probe.py STORE --exe ANNZARRO --color gene|cat [--cat cell_type --gene GENE0] --out F
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import psutil
from playwright.async_api import async_playwright

from ceiling import HERE, STATE_JS, VIEW, Server, envcapture, free_pct, link, n_cells, view


def chromium_rss(me: psutil.Process) -> dict:
    out = {"renderer": 0, "renderer_pid": None, "gpu": 0, "browser": 0}
    for p in me.children(recursive=True):
        try:
            cmd = " ".join(p.cmdline())
            if "annzarro" in cmd:
                continue
            rss = p.memory_info().rss
            if "--type=renderer" in cmd:
                if rss > out["renderer"]:
                    out["renderer"], out["renderer_pid"] = rss, p.pid
            elif "--type=gpu-process" in cmd:
                out["gpu"] = max(out["gpu"], rss)
            elif "--type=" not in cmd and "chrom" in cmd.lower():
                out["browser"] = max(out["browser"], rss)
        except psutil.Error:
            pass
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("store")
    ap.add_argument("--exe", required=True)
    ap.add_argument("--color", default="gene")
    ap.add_argument("--cat", default="cell_type")
    ap.add_argument("--gene", default="GENE0")
    ap.add_argument("--emb", default="X_umap")
    ap.add_argument("--args", default="", help="extra browser flags")
    ap.add_argument("--port", type=int, default=8966)
    ap.add_argument("--limit", type=float, default=900)
    ap.add_argument("--stall", type=float, default=120)
    ap.add_argument("--call-timeout", type=float, default=5, help="per page.evaluate / CDP call (s)")
    ap.add_argument("--min-free", type=int, default=15)
    ap.add_argument("--tag", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    envcapture.require_clean_bench()
    VIEW.update(emb=a.emb, cat=a.cat, genes=[a.gene], subset=None, point_size=None, opacity=None, panel_extra={})
    n = n_cells(a.store)
    flags = ["--enable-precise-memory-info"] + a.args.split()
    out = open(a.out, "a")
    t0 = time.perf_counter()
    base = {"tag": a.tag, "store": Path(a.store).name, "n": n, "color": a.color, "flags": " ".join(flags)}

    def log(kind, **kw):
        out.write(json.dumps({**base, "t": round(time.perf_counter() - t0, 2), "epoch": round(time.time(), 2), "kind": kind, **kw}) + "\n")
        out.flush()

    srv = Server(a.exe, str(Path(a.store).parent), a.port, HERE / "home" / f"p{a.port}")
    me = psutil.Process()
    state = {"page": None, "peak": {"renderer": 0, "gpu": 0, "browser": 0, "server": 0}, "crash": False,
             "renderer_pid": None, "gone": False, "low": False}

    async def sampler():
        while True:
            r = chromium_rss(me)
            s = srv.rss()
            f = free_pct()
            for k in ("renderer", "gpu", "browser"):
                state["peak"][k] = max(state["peak"][k], r[k])
            state["peak"]["server"] = max(state["peak"]["server"], s)
            # the page's renderer: the largest one once it passed 1 GB
            if r["renderer"] > 1e9 and state["renderer_pid"] is None:
                state["renderer_pid"] = r["renderer_pid"]
            if state["renderer_pid"] and not psutil.pid_exists(state["renderer_pid"]):
                state["gone"] = True
            state["low"] = f < a.min_free
            log("sample", renderer=r["renderer"], gpu=r["gpu"], browser=r["browser"], server=s, free_pct=f,
                page=state["page"], renderer_pid=r["renderer_pid"])
            await asyncio.sleep(0.5)

    verdict, info = "timeout", {}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=flags)
        log("browser", version=browser.version)
        envcapture.record(a.out, exe=a.exe, server_root=srv.root,
                          browser={"channel": "bundled", "version": browser.version, "flags": flags, "headless": True},
                          tag=a.tag, store=a.store, color=a.color)
        task = asyncio.create_task(sampler())
        try:
            ctx = await browser.new_context(viewport={"width": 1400, "height": 1000})
            page = await ctx.new_page()
            page.on("console", lambda m: log("console", type=m.type, text=m.text[:300]))
            page.on("pageerror", lambda e: log("pageerror", text=str(e)[:300]))
            page.on("crash", lambda *_: (state.__setitem__("crash", True), log("crash")))
            page.on("request", lambda r: log("request", url=r.url.split("/api/v1/")[-1][:120])
                    if "/api/" in r.url else None)
            page.on("requestfinished", lambda r: log("response", url=r.url.split("/api/v1/")[-1][:120])
                    if "/api/" in r.url else None)
            page.on("requestfailed", lambda r: log("requestfailed", url=r.url.split("/api/v1/")[-1][:120],
                                                   failure=str(r.failure)[:120]))
            cdp = await ctx.new_cdp_session(page)
            await asyncio.wait_for(page.goto(link(srv.root, a.store, view(a.color)), wait_until="commit"), 60)
            last_ok = time.perf_counter()
            while True:
                if state["crash"]:
                    verdict = "crash"; break
                if state["gone"]:
                    verdict = "renderer_gone"; break
                if state["low"]:
                    verdict = "low_memory"; break
                if time.perf_counter() - t0 > a.limit:
                    verdict = "timeout"; break
                try:
                    st = await asyncio.wait_for(page.evaluate(STATE_JS), a.call_timeout)
                    hu = await asyncio.wait_for(cdp.send("Runtime.getHeapUsage"), a.call_timeout)
                    last_ok = time.perf_counter()
                    state["page"] = {"n": st["n"], "busy": st["busy"], "heap": st["heap"],
                                     "v8_used": hu.get("usedSize"), "v8_backing": hu.get("backingStorageSize")}
                    if st["n"] >= n and st["busy"] == 0:
                        verdict = "ok"; break
                except asyncio.TimeoutError:
                    if time.perf_counter() - last_ok > a.stall:
                        verdict = "unresponsive"; break
                except Exception as e:
                    info["error"] = f"{type(e).__name__}: {str(e)[:200]}"
                    verdict = "crash" if state["crash"] else "renderer_gone" if state["gone"] else "eval_error"
                    break
                await asyncio.sleep(0.5)
        finally:
            await asyncio.sleep(1)   # one more sample after the verdict
            task.cancel()
            log("verdict", status=verdict, seconds=round(time.perf_counter() - t0, 2), peak=state["peak"],
                last_page=state["page"], **info)
            try:
                await asyncio.wait_for(browser.close(), 20)
            except Exception:
                for p in me.children(recursive=True):
                    try:
                        if "annzarro" not in " ".join(p.cmdline()):
                            p.kill()
                    except psutil.Error:
                        pass
            srv.stop()
    print(json.dumps({"store": base["store"], "color": a.color, "status": verdict,
                      "seconds": round(time.perf_counter() - t0, 1), "peak_gb": {k: round(v / 1e9, 2)
                      for k, v in state["peak"].items()}, "last_page": state["page"]}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
