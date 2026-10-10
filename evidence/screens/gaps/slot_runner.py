#!/usr/bin/env python
"""RETIRED 2026-10-04 (coordinator: the clock time-share ended; run run_session2.py under the bench lock).

Run GUI capture jobs only in agreed :00 slots, never holding the shared GUI lock while waiting.

The shared lock ($DEMO_ROOT/.gui.lock) serialises GUI sessions between agents. Waiting
for a quiet gap while holding it blocks everyone (2026-10-04), so this runner:
  1. sleeps (without the lock) until :00 of the next hour listed in --hours;
  2. takes the lock with a short timeout (lockf -t 60); if another session holds it, skips the slot;
  3. runs the jobs through gap_run.sh (which logs the window for overlap marking), with a hard
     stop at :14:30 (run_session2.py also stops by itself at :14:30);
  4. releases the lock and goes back to sleep. Each step is logged.

Usage: slot_runner.py --hours 14,16,18 --jobs "code docs ucsc ..." [--jobs "scp kana ..."]
Each --jobs group takes one slot, in order.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shlex
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
LOCK = HOME / "annzarro_compare/.gui.lock"
GAP = HOME / "annzarro_compare/_browser/gap_run.sh"
SESSION = Path(__file__).resolve().parent / "run_session2.py"


def log(msg):
    print(f"{dt.datetime.now():%H:%M:%S} {msg}", flush=True)


def next_slot(hours):
    now = dt.datetime.now()
    for add in range(0, 48):
        t = (now + dt.timedelta(hours=add)).replace(minute=0, second=0, microsecond=0)
        if t.hour in hours and t >= now - dt.timedelta(seconds=30):
            return t
    raise SystemExit("no slot")


def run_slot(jobs, end):
    cmd = ["/usr/bin/lockf", "-t", "60", str(LOCK), "env", "GAP_LOCKED=1", "GAP_PARITY=0", str(GAP),
           "/usr/bin/python3", str(SESSION), *jobs]
    log("slot: " + " ".join(shlex.quote(c) for c in cmd))
    p = subprocess.Popen(cmd)
    while p.poll() is None:
        if dt.datetime.now() >= end:
            log("hard stop at the end of the slot")
            p.terminate()
            try:
                p.wait(20)
            except subprocess.TimeoutExpired:
                p.kill()
        time.sleep(5)
    log(f"slot ended rc={p.returncode} (75 = lock busy, slot skipped)")
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", required=True, help="comma-separated hours whose :00 slot is ours")
    ap.add_argument("--jobs", action="append", required=True)
    a = ap.parse_args()
    hours = {int(h) for h in a.hours.split(",")}
    queue = [j.split() for j in a.jobs]
    while queue:
        start = next_slot(hours)
        wait = (start - dt.datetime.now()).total_seconds()
        log(f"next slot {start:%H:%M}; sleeping {max(wait, 0) / 60:.0f} min without the lock")
        if wait > 0:
            time.sleep(wait)
        rc = run_slot(queue[0], start + dt.timedelta(minutes=14, seconds=30))
        if rc != 75:
            queue.pop(0)
        hours.discard(start.hour)
        if not hours and queue:
            log("out of slots with jobs left: " + "; ".join(" ".join(j) for j in queue))
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
