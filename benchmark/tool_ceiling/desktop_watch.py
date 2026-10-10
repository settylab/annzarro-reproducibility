#!/usr/bin/env python
"""ManiVault Studio's ceiling, driven by a person or a Claude desktop session
through files in CHANNEL ($DEMO_ROOT/manivault/session_v031):

  watcher  next_<N>_<k>    get ready for size N, attempt k (the first is written at start)
  desktop  ready_<N>_<k>   ManiVault freshly opened, nothing imported
  watcher  go_<N>_<k>      bench and screen locks held, memmon sampling: import now
  desktop  drawn_<N>_<k>   coloured by cell_line_id, then MALAT1; key=value lines:
                           points=<Data Properties point count>, plus notes
           failed_<N>_<k>  what it saw; a first line "hang" counts as a hang
  watcher  stop            the ladder is over (reason inside)

memmon (--attach-name "ManiVault Studio") samples the app from go to drawn or
failed under both locks. A size passes when drawn, points == N, and the app's
peak phys_footprint is within the 16 GiB client budget; the ladder then goes to
the next size. It ends at the first size that fails, passes 16 GiB, hits the
85 GiB cap, or hangs three times. One row per attempt in results.csv (tool
manivault; client = the app; no server).

The same protocol runs Loupe Browser on .cloupe files (--tool loupe; inputs from
loupe_build.R, channel $DEMO_ROOT/loupe/session_v031).

Usage: desktop_watch.py [--tool manivault|loupe] [--sizes 250000,500000,...] [--channel DIR] [--app NAME]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from run import HERE, LOCK, PY, append_row, gb, wait_while_paused

SCREEN = "$HOME/.annzarro-screen.lock"
APP = {"manivault": "ManiVault Studio", "loupe": "Loupe Browser"}
CHANNEL = {"manivault": "annzarro_compare/manivault/session_v031", "loupe": "annzarro_compare/loupe/session_v031"}
SIZES = [250_000, 500_000, 1_000_000, 2_000_000, 5_000_000, 10_000_000, 20_000_000, 50_000_000, 95_624_334]
BUDGET = 16 * 2**30
VERSION = {"manivault": "1.5.0-dev (manivault_1.5.0_mac.dmg, sha256 06837bc1...aa77287)", "loupe": "9.1.0"}
TOOL = "manivault"
if os.environ.get("DESKTOP_WATCH_DRY"):  # dry run of the protocol: scratch locks and raw dir, no results.csv row
    _d = Path(os.environ["DESKTOP_WATCH_DRY"])
    LOCK, SCREEN, HERE = str(_d / "bench.lock"), str(_d / "screen.lock"), _d
    append_row = lambda row: print("DRY ROW", json.dumps(row), flush=True)  # noqa: E731


def h5ad(n: int) -> str:
    if TOOL == "loupe":
        return str(Path.home() / f"annzarro_compare/loupe/session_v031/cloupe/tahoe_first{n}.cloupe")
    return f"$DATA_ROOT/tool_ceiling_data/h5ad/tahoe_first{n}.h5ad"


def found(p: Path) -> Path | None:
    """p, or p.txt (TextEdit's plain-text save adds it)."""
    return next((q for q in (p, p.with_name(p.name + ".txt")) if q.exists()), None)


def wait_for(*paths: Path) -> Path:
    while True:
        for p in paths:
            if found(p):
                return found(p)
        time.sleep(2)


def say(ch: Path, name: str, text: str):
    (ch / (name + ".tmp")).write_text(text)
    (ch / (name + ".tmp")).rename(ch / name)  # whole file or nothing
    print(time.strftime("%H:%M:%S"), name, text.strip().replace("\n", " | "), flush=True)


def attempt(ch: Path, n: int, k: int, app: str) -> dict | None:
    """One attempt, run while this process holds the bench and screen locks:
    next_, the desktop's relaunch (ready_), memmon from go_ to drawn_/failed_, the row.
    None: it failed before any import (nothing measured, no row)."""
    say(ch, f"next_{n}_{k}", f"size={n}\nattempt={k}\nfile={h5ad(n)}\n")
    status_file(ch, f"locks held; next_{n}_{k} written; waiting for ready_{n}_{k}")
    if wait_for(ch / f"ready_{n}_{k}", ch / f"failed_{n}_{k}").name.startswith("failed"):
        return None
    raw = HERE / "raw"
    rid = f"{TOOL}_default_run_{n}_r{k - 1}"
    mem = raw / f"{rid}.mem.json"
    done = [str(ch / f"{e}_{n}_{k}{x}") for e in ("drawn", "failed") for x in ("", ".txt")]
    cmd = [PY, str(HERE / "memmon.py"), "--out", str(mem), "--attach-name", app, "--timeout", "7200", "--cap-gb", "85",
           "--started-file", str(ch / f"go_{n}_{k}"), "--until", *done]
    with open(raw / f"{rid}.log", "w") as lf:
        subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT)
    m = json.loads(mem.read_text())
    end = next((Path(d) for d in done if Path(d).exists()), None)
    text = end.read_text() if end else ""
    kv = dict(x.split("=", 1) for x in text.splitlines() if "=" in x)
    points = int(kv["points"]) if kv.get("points", "").strip().isdigit() else None
    pk = m["peaks"]["app"]
    drawn = end is not None and end.name.startswith("drawn")
    hang = end is not None and end.name.startswith("failed") and text.strip().lower().startswith("hang")
    over = pk["fp_peak"] > BUDGET
    status = m["status"] if m["status"] != "ok" else "ok" if drawn else "hang" if hang else "fail"
    mode = ("" if drawn and points == n and not over else
            f"client over budget ({gb(pk['fp_peak'])} GiB > 16)" if drawn and points == n else
            f"drawn {points} of {n} points" if drawn else
            "cap" if m["status"] == "cap" else
            f"{m['status']}" if m["status"] != "ok" else text.strip().splitlines()[0][:200] if text.strip() else "failed")
    row = {"id": rid, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": TOOL, "variant": "default",
           "phase": "run", "n": n, "run": k - 1, "status": "fail" if status == "ok" and mode else status,
           "failure_mode": mode, "all_cells": drawn and points == n, "wall_s": m["wall_s"],
           "fp_total_gb": gb(pk["fp_peak"]), "fp_lifetime_total_gb": gb(pk["fp_lifetime_sum"]),
           "rss_total_gb": gb(pk["rss_peak"]), "fp_client_gb": gb(pk["fp_peak"]), "fp_server_gb": "",
           "versions": json.dumps({TOOL: VERSION[TOOL]}),
           "note": f"desktop session; app {app!r}; input {Path(h5ad(n)).name}; "
                   f"{os.environ.get('DESKTOP_WATCH_ROW_NOTE', '')}{(text.strip().replace(chr(10), ' | '))[:300]}"}
    append_row(row)
    return row


def gap(ch: Path, n: int, k: int, limit: float = 5400):
    """Between two sizes: offer the gap to loupe_pipeline.sh (one .cloupe build, under the bench lock)
    and wait until it is used, so a build never competes with a size for the lock."""
    if TOOL != "manivault" or subprocess.run(["pgrep", "-f", "loupe_pipeline.sh"], capture_output=True).returncode != 0:
        return
    g = ch / f".gap_{n}_{k}"
    g.write_text(time.strftime("%H:%M:%S"))
    status_file(ch, f"size {n} attempt {k} done; one Loupe input build runs in this gap, then the next size")
    t0 = time.time()
    while g.exists() and time.time() - t0 < limit and \
            subprocess.run(["pgrep", "-f", "loupe_pipeline.sh"], capture_output=True).returncode == 0:
        time.sleep(2)
    g.unlink(missing_ok=True)


def status_file(ch: Path, text: str):
    note = os.environ.get("DESKTOP_WATCH_NOTE", "")  # e.g. what this run is, on every status line
    say(ch, "watcher_status.txt", f"{time.strftime('%Y-%m-%d %H:%M:%S %Z')} {text}\n" + (f"{note}\n" if note else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default=",".join(map(str, SIZES)))
    ap.add_argument("--tool", choices=sorted(APP), default="manivault")
    ap.add_argument("--channel")
    ap.add_argument("--app", help="process name (default: the tool's)")
    ap.add_argument("--first-attempt", type=int, default=1,
                    help="attempt number of the first size (a retry after a retired attempt keeps its ids apart)")
    ap.add_argument("--wait-inputs", action="store_true",
                    help="inputs still being built: wait for each size's input (and its .done marker) before next_")
    ap.add_argument("--one", nargs=2, type=int, metavar=("N", "K"), help=argparse.SUPPRESS)  # one attempt, under the locks
    a = ap.parse_args()
    global TOOL
    TOOL = a.tool
    app = a.app or APP[a.tool]
    a.channel = a.channel or str(Path.home() / CHANNEL[a.tool])
    ch = Path(a.channel)
    (ch / "shots").mkdir(parents=True, exist_ok=True)
    if a.one:
        n, k = a.one
        row = attempt(ch, n, k, app)
        (ch / f".result_{n}_{k}.json").write_text(json.dumps(row))
        return
    sizes = [int(x) for x in a.sizes.split(",")]
    for n in sizes:
        if not Path(h5ad(n)).exists() and not a.wait_inputs:
            sys.exit(f"missing input {h5ad(n)}")
    for i, n in enumerate(sizes):
        k0 = a.first_attempt if i == 0 else 1
        while a.wait_inputs and not (Path(h5ad(n)).exists() and Path(h5ad(n) + ".done").exists()):
            status_file(ch, f"size {n}: its input file is still being built; next_{n}_{k0} follows when it is ready")
            time.sleep(30)
        for k in range(k0, k0 + 3):
            wait_while_paused()
            status_file(ch, f"size {n} attempt {k}: waiting for the bench and screen locks; next_{n}_{k} follows")
            # the whole cycle (relaunch, import, colouring) inside the exclusive window; released between sizes
            subprocess.run(["/usr/bin/lockf", "-k", LOCK, "/usr/bin/lockf", "-k", SCREEN, PY, str(Path(__file__).resolve()),
                            "--tool", TOOL, "--channel", str(ch), "--app", app, "--one", str(n), str(k)], check=True)
            row = json.loads((ch / f".result_{n}_{k}.json").read_text())
            if row is None:
                say(ch, "stop", f"size={n}\nreason=failed before import: {found(ch / f'failed_{n}_{k}').read_text()[:300]}\n")
                return
            print(json.dumps(row), flush=True)
            status_file(ch, f"size {n} attempt {k} recorded: {row['status']} {row['failure_mode']}; locks released")
            ended = not (row["status"] == "hang" and k < k0 + 2) and bool(row["failure_mode"] or row["status"] != "ok")
            if not ended:
                gap(ch, n, k)
            if row["status"] == "hang" and k < k0 + 2:
                continue  # the hang rule: three attempts
            if ended:
                say(ch, "stop", f"size={n}\nreason={row['failure_mode'] or row['status']}\n")
                return
            break
    say(ch, "stop", "reason=ladder complete\n")


if __name__ == "__main__":
    main()
