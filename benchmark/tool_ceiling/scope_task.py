#!/usr/bin/env python
"""SCope 1.8.2 (9ae5207) task, the same as every web tool's: open the UMAP of N cells, colour it by
cell line (the loom's cell_line_id annotation) and by MALAT1, and check that every cell is drawn.

SCope runs from the image built as in measured/scope (Dockerfile.final),
linux/amd64 under Docker's emulation on this arm64 laptop. The container is started fresh per rung with
only that rung's loom in its data folder; run-time configuration (not build changes): DATABASE_URL as in
SCope's opt/.env, and a config with localHostAddress 0.0.0.0 so Docker's published ports reach the servers.
The frontend is served from /app by python's http.server (the published setup puts Apache in front).

Client = Chromium on the host (memmon, as for every web tool). The server runs in Docker's Linux VM, so
memmon cannot see it; its memory is the container's cgroup usage from `docker stats`, sampled every 2 s,
reported separately (server_container_peak_gib) and labelled as such.

Every cell drawn: the viewer's PIXI ParticleContainer holds one sprite per cell; its child count and the
viewer's coordinate index length are read from the React component and must equal N.

Usage: scope_task.py LOOM OUT --n N [--image TAG] [--limit 1750]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

IMAGE = "scope:1.8.2-9ae5207-final"
DATA = Path("$DATA_ROOT/tool_ceiling_data/scope_serve")
COUNT = """() => { const c = document.querySelector('canvas'); if (!c) return null;
  const k = Object.keys(c).find(k => k.startsWith('__reactInternalInstance') || k.startsWith('__reactFiber'));
  let f = k ? c[k] : null;
  while (f) { const s = f.stateNode;
    if (s && s.mainLayer) return {children: s.mainLayer.children.length,
      idx: (s.state && s.state.coord && s.state.coord.idx) ? s.state.coord.idx.length : null,
      loading: s.state ? !!s.state.loading : null};
    f = f.return; }
  return null; }"""
GIB = 2 ** 30


def mem_bytes(s: str) -> float:
    m = re.match(r"([\d.]+)\s*([KMGT]?i?B)", s.strip())
    if not m:
        return 0.0
    v, u = float(m.group(1)), m.group(2)
    return v * {"B": 1, "KiB": 2**10, "MiB": 2**20, "GiB": 2**30, "TiB": 2**40,
                "kB": 1e3, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}.get(u, 1)


class Stats(threading.Thread):
    def __init__(self, name):
        super().__init__(daemon=True)
        self.name_, self.peak, self.halt = name, 0.0, threading.Event()

    def run(self):
        while not self.halt.is_set():
            r = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", self.name_],
                               capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                self.peak = max(self.peak, mem_bytes(r.stdout.split("/")[0]))
            self.halt.wait(2)


HEAP = {"fh": None, "cdp": None, "t0": time.time()}


def heap_sample(pg, phase):
    """One JS-heap sample (performance.memory and CDP Runtime.getHeapUsage), written as taken, so the last one
    before a renderer crash survives it (--heap-series)."""
    if not HEAP["fh"]:
        return
    rec = {"t": round(time.time() - HEAP["t0"], 2), "phase": phase}
    try:
        m = pg.evaluate("() => performance.memory ? [performance.memory.usedJSHeapSize, performance.memory.jsHeapSizeLimit] : null")
        if m:
            rec["pm_used"], rec["pm_limit"] = m
        h = HEAP["cdp"].send("Runtime.getHeapUsage")
        rec["cdp_used"], rec["cdp_total"] = h.get("usedSize"), h.get("totalSize")
    except Exception as e:
        rec["error"] = type(e).__name__
    HEAP["fh"].write(json.dumps(rec) + "\n")


def wait_draw(pg, n, limit, what):
    t0 = time.time()
    last = None
    while time.time() - t0 < limit:
        heap_sample(pg, what)
        c = pg.evaluate(COUNT)
        last = c
        if isinstance(c, dict) and c["children"] and not c["loading"] and c["children"] >= n:
            return time.time() - t0, c
        time.sleep(2)
    raise TimeoutError(f"waiting for {what}: last viewer state {last}")


def fit(pg):
    """Zoom the viewer out until the whole embedding is in view (mouse wheel over the canvas; SCope has no
    fit button), for the evidence shot only; the point count is read again afterwards."""
    box = pg.locator("canvas").first.bounding_box()
    if not box:
        return
    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    for _ in range(2):  # the default view crops the embedding at the right and top; zoom out about the centre
        pg.mouse.wheel(0, 120)
        time.sleep(0.7)
    time.sleep(2)


def pick(pg, query, label, kind):
    s = pg.locator("input[placeholder='Search...']").first
    s.click()
    s.fill("")
    s.type(query, delay=60)
    res = pg.locator(".results .result").filter(has_text=label)
    res.first.wait_for(timeout=120000)
    if kind == "annotation":  # the annotation result, not one of its values
        res = pg.locator(".results .category").filter(has_text="annotation").locator(".result").filter(has_text=label)
    res.first.click()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("loom")
    ap.add_argument("out")
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--image", default=IMAGE)
    ap.add_argument("--limit", type=float, default=1750)
    ap.add_argument("--heap-series", action="store_true", help="log JS-heap samples to OUT.heap.jsonl as taken")
    a = ap.parse_args()
    name = "scope-rung"
    data = DATA / "rung"
    shutil.rmtree(data, ignore_errors=True)
    for d in ("my-looms", "my-gene-sets", "my-aucell-rankings"):
        (data / d).mkdir(parents=True, exist_ok=True)
    loom = Path(a.loom)
    (data / "my-looms" / loom.name).hardlink_to(loom)
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    image_id = subprocess.run(["docker", "image", "inspect", a.image, "--format", "{{.Id}}"],
                              capture_output=True, text=True).stdout.strip()
    rec = {"tool": "scope", "variant": "default", "n_obs": a.n, "checks": {}, "image": a.image, "image_id": image_id,
           "versions": {"scope": "1.8.2 (9ae5207)", "image": image_id[:19]}, "ok": False}
    stats = Stats(name)
    t_start = time.time()
    try:
        subprocess.run(["docker", "run", "-d", "--name", name, "--platform", "linux/amd64",
                        "-p", "55850-55853:55850-55853", "-p", "8000:8000",
                        "-v", f"{data}:/root/.local/share/SCope", "-v", f"{DATA / 'config.json'}:/app/scope_config.json",
                        "-e", "SCOPE_CONFIG=/app/scope_config.json",
                        "-e", "DATABASE_URL=sqlite:////root/.local/share/SCope/scope.sqlite", a.image, "bash", "-c",
                        "cd /app && (/opt/conda/envs/scope/bin/python -m http.server 55850 --bind 0.0.0.0 "
                        ">/tmp/http.log 2>&1 &) ; cd /app/opt && poetry run hypercorn --bind 0.0.0.0 main:scope_api"],
                       check=True, capture_output=True)
        stats.start()
        import requests
        for _ in range(300):
            try:
                if requests.get("http://127.0.0.1:8000/echo/up", timeout=2).ok and \
                        requests.get("http://127.0.0.1:55850/", timeout=2).ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(2)
        time.sleep(20)  # the gRPC and websocket servers start after the API
        rec["server_ready_s"] = round(time.time() - t_start, 1)
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chromium", args=["--enable-precise-memory-info"] if a.heap_series else [])
            rec["versions"]["browser"] = "chromium " + b.version
            pg = b.new_page(viewport={"width": 1600, "height": 1100})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            if a.heap_series:
                HEAP["fh"] = open(a.out + ".heap.jsonl", "w", buffering=1)
                HEAP["cdp"] = pg.context.new_cdp_session(pg)
            pg.goto("http://127.0.0.1:55850/", timeout=120000)
            uuid = None
            for _ in range(120):  # the frontend puts its session UUID into the URL; the server also logs it
                m = re.search(r"#/([0-9a-f-]{36})/", pg.url) or re.search(
                    r"Using UUID ([0-9a-f-]{36}) from frontend",
                    subprocess.run(["docker", "logs", name], capture_output=True, text=True).stderr)
                if m:
                    uuid = m.group(1)
                    break
                time.sleep(2)
            if not uuid:
                raise TimeoutError("waiting for the session UUID")
            try:  # the cookie banner: decline (the most privacy-preserving choice), so it does not cover the plot
                pg.get_by_text("I decline").first.click(timeout=10000)
            except Exception:
                pass
            t0 = time.time()
            pg.goto(f"http://127.0.0.1:55850/#/{uuid}/{loom.name}/gene", timeout=120000)
            secs, c = wait_draw(pg, a.n, a.limit, "the embedding")
            rec["load_s"] = round(time.time() - t0, 1)
            for tag, (query, label, kind) in (("cat", ("cell_line_id", "cell_line_id", "annotation")),
                                              ("gene", ("MALAT1", "MALAT1", "gene"))):
                t1 = time.time()
                try:
                    pick(pg, query, label, kind)
                    time.sleep(3)
                    secs, c = wait_draw(pg, a.n, a.limit, f"colour by {label}")
                    fit(pg)
                    c2 = pg.evaluate(COUNT)
                    pg.screenshot(path=f"{a.out}_{tag}.png")
                    if isinstance(c2, dict):
                        c = c2
                    rec["checks"][tag] = {"status": "ok", "n_drawn": c["children"], "idx": c["idx"],
                                          "seconds": round(time.time() - t1, 1),
                                          "all_cells": c["children"] == a.n and c["idx"] == a.n}
                except Exception as e:
                    rec["checks"][tag] = {"status": "timeout" if isinstance(e, TimeoutError) or "Timeout" in type(e).__name__
                                          else "error", "error": str(e)[:300], "all_cells": False}
                    break
            rec["page_errors"] = errs[:10]
            b.close()
        rec["ok"] = len(rec["checks"]) == 2 and all(v.get("all_cells") for v in rec["checks"].values())
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"[:500]
    finally:
        stats.halt.set()
        rec["server_container_peak_gib"] = round(stats.peak / GIB, 3)
        rec["server_log_tail"] = subprocess.run(["docker", "logs", "--tail", "15", name], capture_output=True,
                                                text=True).stderr[-1500:]
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        if HEAP["fh"]:
            HEAP["fh"].close()
            hs = [json.loads(x) for x in Path(a.out + ".heap.jsonl").read_text().splitlines()]
            ok = [h for h in hs if "cdp_used" in h]
            rec["heap"] = {"samples": len(hs), "last": ok[-1] if ok else None,
                           "peak_cdp_used": max((h["cdp_used"] or 0 for h in ok), default=None),
                           "peak_pm_used": max((h.get("pm_used") or 0 for h in ok), default=None)}
        Path(a.out + ".json").write_text(json.dumps(rec, indent=1))
    raise SystemExit(0 if rec["ok"] else 3)


if __name__ == "__main__":
    main()
