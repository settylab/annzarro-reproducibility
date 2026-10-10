#!/usr/bin/env python
"""The AnnZarro task, run by ../scale/ceiling/ceiling.py: a fresh server and
browser, one Cell Plot on obsm/X_umap with every cell ("subset": null, what
the user picks in the subset control; above 200,000 cells the app's default
view draws a 100,000-cell subset), coloured by MALAT1, then recoloured by
cell_line_id in the same session. Point size and opacity are the app's
defaults. ceiling.py checks that the panel holds N points after each step
(coloured by the 50 cell lines, ceiling.py reports N + 50 points at 1M, so
the check is >= N).

Variants: default (as released); noprewarm (ceiling.py --block-prewarm: the
harness aborts the client's background cell-name index request; AnnZarro has
no setting for it).

Remote server (--server-url URL --n N): ceiling.py runs in this process with
its Server replaced by the given URL (nothing started, no server memory
measured here), STORE is the dataset path as the remote server sees it, and
with --proxy (socks5://host:port) Chromium and the probe both go through
that SOCKS proxy. Before the run the network is probed: round-trip time of 20 GET /api/v1/config
and throughput of 6 GETs of one 4 MB vector of --probe-store (the first fills
the server's cache; the median of the other 5 is network-bound).

Run inside `memmon.py --web`; ceiling.py itself counts as harness.
Writes OUTPREFIX.json in the shape of the other tasks.

Usage: annzarro_task.py VARIANT STORE OUTPREFIX --exe ANNZARRO [--port 8933]
       annzarro_task.py VARIANT STORE OUTPREFIX --server-url URL --n N [--probe-store PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CEIL = HERE.parent / "scale/ceiling"


def probe(url: str, store: str, proxy: str | None) -> dict:
    import requests
    ses = requests.Session()
    if proxy:  # socks5h: the proxy resolves the host name, as Chromium does
        ses.proxies = {"http": proxy.replace("socks5://", "socks5h://"), "https": proxy.replace("socks5://", "socks5h://")}
    rtt = []
    for _ in range(20):
        t = time.perf_counter()
        ses.get(f"{url}/api/v1/config", timeout=30).raise_for_status()
        rtt.append((time.perf_counter() - t) * 1000)
    # a vector of the probe store; X_pca_2d where present (not drawn in the run), else X_umap column 0
    for key in ("X_pca_2d", "X_umap"):
        q = f"{url}/api/v1/data/obsm/{key}?dataset_path={quote(store, safe='')}&column_name=0&format=f32"
        if ses.get(q, timeout=300).status_code == 200:
            break
    rates, nbytes = [], 0
    for k in range(1, 6):  # the request above filled the server's cache
        t = time.perf_counter()
        r = ses.get(q, timeout=300)
        r.raise_for_status()
        dt = time.perf_counter() - t
        nbytes = len(r.content)
        rates.append(nbytes / dt / 1e6)
    return {"rtt_ms_median": round(statistics.median(rtt), 2), "rtt_ms_max": round(max(rtt), 2),
            "throughput_MBps_median": round(statistics.median(rates), 1), "probe_bytes": nbytes, "probe_store": store, "probe_url": q,
            "proxy": proxy}


GUARD_N = 9_000_000_000_000_000  # sentinel point count: the memory guard refused


class Remote:
    """Stands in for ceiling.Server: the server is already running elsewhere."""
    url = ""

    def __init__(self, *a, **k):
        self.root, self.peak = Remote.url, 0

    def rss(self):
        return 0

    def stop(self):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variant", choices=["default", "noprewarm"])
    ap.add_argument("store")
    ap.add_argument("out")
    ap.add_argument("--exe")
    ap.add_argument("--port", type=int, default=8933)
    ap.add_argument("--server-url")
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--probe-store", default="")
    ap.add_argument("--proxy", default="", help="remote mode: e.g. socks5://127.0.0.1:8767, for Chromium and the probe")
    ap.add_argument("--cat", default="cell_line_id", help="categorical obs column")
    ap.add_argument("--subset", default="null", help="ceiling.py --subset: null (every cell), absent (the "
                    "app's default subset), or a JSON spec such as {\"n\": 1000000, \"seed\": 0}")
    ap.add_argument("--gene", default="MALAT1")
    ap.add_argument("--inprocess", action="store_true", help="run ceiling.py in this process (memory-guard detection)")
    ap.add_argument("--version-label", default="remote", help="remote mode: the server's AnnZarro sha or tag")
    ap.add_argument("--guard-off", action="store_true", help="local server with ui.memory.enforce off (a site file "
                    "named by ANNZARRO_CONFIG); the run aborts unless /api/v1/config reports it")
    ap.add_argument("--heap-series", action="store_true", help="--inprocess: log every JS heap sample of the run "
                    "(performance.memory used and limit, CDP Runtime.getHeapUsage) to OUT.heap.jsonl, as taken")
    a = ap.parse_args()
    if a.guard_off:
        assert a.inprocess and not a.server_url, "--guard-off needs --inprocess and a local server"
        site = Path(a.out + ".config.yaml")
        site.write_text('ui:\n  memory:\n    enforce: "off"\n')  # quoted: YAML 1.1 reads a bare off as false
        os.environ["ANNZARRO_CONFIG"] = str(site.resolve())
    jl = Path(a.out + ".ceiling.jsonl")
    jl.unlink(missing_ok=True)
    cmd = [str(CEIL / ".venv/bin/python"), str(CEIL / "ceiling.py"), a.store, "--out", str(jl), "--exe", a.exe or "",
           "--port", str(a.port), "--subset", a.subset, "--colors", "gene", "--recolour", "0", "--recolour-cat", a.cat,
           "--cat", a.cat, "--genes", a.gene, "--emb", "X_umap", "--point-size", "default",
           "--opacity", "default", "--limit", "1750", "--shots", a.out + "_shots", "--tag", "tool_ceiling"]
    if a.variant == "noprewarm":
        cmd.append("--block-prewarm")
    net = None
    if a.server_url or a.inprocess:
        # ceiling.py in this process: lets the server be remote, and lets the
        # state probe also read the memory guard's refusal from the page
        sys.path.insert(0, str(CEIL))
        import ceiling
        # the memory guard's refusal (placeholder text, or a live plot's status tag
        # whose title holds the reason): logged once as a console warning (which
        # ceiling.py keeps), and reported as a sentinel state that ends the wait
        ceiling.STATE_JS = ceiling.STATE_JS.replace(
            "  const heap = performance.memory",
            "  const gsc = document.querySelector('.tile[data-tile-id=\"cell-plot-A\"]');\n"
            "  const gtxt = !gsc ? [] : (gsc.innerText.match(/Not drawn: [^\\n]*|[^\\n]*needs ~[^\\n]* of browser [^\\n]*|[^\\n]*the largest plot tested to draw[^\\n]*/gi) || [])\n"
            "      .concat([...gsc.querySelectorAll('[title]')].map(e => e.title)\n"
            "               .filter(t => /needs ~.* of browser|Not enough browser memory|the largest plot tested to draw/i.test(t)));\n"
            "  if (gtxt.length && !window.__guardLogged) { window.__guardLogged = 1;\n"
            "    console.warn('GUARD: ' + gtxt.join(' | ').slice(0, 600)); }\n"
            "  err.push(...gtxt.map(t => 'GUARD: ' + t.slice(0, 300)));\n"
            "  const heap = performance.memory").replace(
            "  return {busy, n, sig, heap, traces, err};",
            # first draw refused (no plot yet): no points, so ceiling.py reports "stalled" after 45 s and stops;
            # a recolour refused (a plot is there): the sentinel count ends ceiling.py's wait at once
            "  return gtxt.length ? {busy: 0, n: (g && g._fullData ? GUARD_N : -1), sig: 'GUARD', heap, traces, err}"
            " : {busy, n, sig, heap, traces, err};"
        ).replace("GUARD_N", str(GUARD_N))
        assert "GUARD_N" not in ceiling.STATE_JS and "sig: 'GUARD'" in ceiling.STATE_JS
        if a.heap_series:
            # every state probe and CDP heap reading, written as taken, so the last one before a renderer crash survives
            ceiling.STATE_JS = ceiling.STATE_JS.replace(
                "heap, traces, err}", "heap, heapLimit: performance.memory ? performance.memory.jsHeapSizeLimit : -1, traces, err}")
            assert ceiling.STATE_JS.count("heapLimit") == 2
            from playwright.sync_api import CDPSession, Page
            hs, t_hs = open(a.out + ".heap.jsonl", "w", buffering=1), time.time()
            ev0, send0 = Page.evaluate, CDPSession.send

            def evaluate(self, expression, *args, **kw):
                r = ev0(self, expression, *args, **kw)
                if expression == ceiling.STATE_JS:
                    hs.write(json.dumps({"t": round(time.time() - t_hs, 3), "src": "performance.memory", "n": r.get("n"),
                                         "used": r.get("heap"), "limit": r.get("heapLimit")}) + "\n")
                return r

            def send(self, method, params=None):
                r = send0(self, method, params)
                if method == "Runtime.getHeapUsage":
                    hs.write(json.dumps({"t": round(time.time() - t_hs, 3), "src": "Runtime.getHeapUsage",
                                         "used": r.get("usedSize"), "total": r.get("totalSize"),
                                         "backing": r.get("backingStorageSize")}) + "\n")
                return r
            Page.evaluate, CDPSession.send = evaluate, send
        sys.argv = cmd[1:2] + cmd[2:]
        if a.guard_off:
            class Unguarded(ceiling.Server):
                def __init__(self, *args, **kw):
                    super().__init__(*args, **kw)
                    import requests
                    got = requests.get(self.root + "/api/v1/config", timeout=30).json()["ui"]["memory"]["enforce"]
                    if got not in ("off", False):
                        self.stop()
                        print(f"--guard-off: the server reports ui.memory.enforce={got!r}", file=sys.stderr)
                        os._exit(2)  # no record: this is not a run
                    print("guard off: ui.memory.enforce =", repr(got), file=sys.stderr, flush=True)
            ceiling.Server = Unguarded
        if a.server_url:
            net = probe(a.server_url.rstrip("/"), a.probe_store or a.store, a.proxy or None)
            print("network", json.dumps(net), file=sys.stderr, flush=True)
            Remote.url = a.server_url.rstrip("/")
            ceiling.Server = Remote
            ceiling.n_cells = lambda store: a.n  # the store is on the remote machine
            sys.argv += ["--expect", str(a.n)]
            if a.proxy:
                sys.argv.append(f"--args=--proxy-server={a.proxy}")
        try:
            ceiling.main()
            rc = 0
        except SystemExit as e:
            rc = e.code or 0
    else:
        rc = subprocess.run(cmd).returncode
    ev = [json.loads(x) for x in jl.read_text().splitlines()] if jl.exists() else []
    n = ev[0]["n"] if ev else None  # with a subset: the subset's size (ceiling.py --subset)
    checks = {}
    for e in ev:
        tag = {"first_plot": "gene", "recolour_cat": "cat"}.get(e.get("event"))
        if tag:
            guard = [x for x in (e.get("ui_errors") or []) + (e.get("console") or []) if "GUARD: " in str(x)]
            refused = (e.get("n_points") or 0) >= GUARD_N or bool(guard and e.get("status") != "ok")
            # the page's own error for a buffer the tab could not allocate (v0.4.1, guard off, >= 250M points)
            alloc = "Array buffer allocation failed" in str(e.get("tile_text") or "") + str(e.get("console") or "")
            checks[tag] = {"status": "guard_refusal" if refused else "alloc_failed" if alloc and e.get("status") != "ok"
                           else e.get("status"),
                           "guard": guard[:3], "console": (e.get("console") or [])[:10],
                           "n_drawn": e.get("n_points"), "seconds": e.get("seconds"),
                           "all_cells": not refused and e.get("status") == "ok" and (e.get("n_points") or 0) >= n,
                           "renderer_rss": e.get("renderer_rss"), "gpu_rss": e.get("gpu_rss"),
                           "server_rss": e.get("server_rss")}
    if a.server_url:
        commit = a.version_label
    else:
        exe_dir = Path(a.exe).resolve().parents[2]
        commit = subprocess.run(["git", "-C", str(exe_dir), "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True).stdout.strip() or a.version_label
    rec = {"tool": "annzarro", "variant": a.variant, "store": a.store, "n_obs": n, "checks": checks,
           "versions": {"annzarro": commit, "browser": ev[0].get("browser") if ev else None},
           "ceiling_rc": rc, "server_url": a.server_url, "network": net, "events": [{k: e.get(k) for k in ("event", "status", "seconds", "n_points")} for e in ev]}
    if a.heap_series:
        hl = [json.loads(x) for x in Path(a.out + ".heap.jsonl").read_text().splitlines()]
        pm = [h for h in hl if h["src"] == "performance.memory" and (h["used"] or 0) > 0]
        cd = [h for h in hl if h["src"] == "Runtime.getHeapUsage"]
        rec["heap"] = {"file": a.out + ".heap.jsonl", "samples": len(hl), "last_pm": pm[-1] if pm else None,
                       "last_cdp": cd[-1] if cd else None, "peak_used_pm": max((h["used"] for h in pm), default=None),
                       "peak_used_cdp": max((h["used"] or 0 for h in cd), default=None)}
    rec["ok"] = len(checks) == 2 and all(c["all_cells"] for c in checks.values())
    Path(a.out + ".json").write_text(json.dumps(rec, indent=1))
    sys.exit(0 if rec["ok"] else 3)


if __name__ == "__main__":
    main()
