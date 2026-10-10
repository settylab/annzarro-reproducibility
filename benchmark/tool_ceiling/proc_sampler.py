#!/usr/bin/env python
"""Per-process memory of an app's process tree, once a second, as JSON lines: pid, name,
RSS and phys_footprint (memmon.rusage). For the record next to memmon's group peak, e.g. to
see which Electron helper grows. Runs until UNTIL exists or no such process is left after it appeared.
Usage: proc_sampler.py NAME OUT.jsonl UNTIL"""
import json, os, sys, time
import psutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from memmon import rusage, tree

name, out, until = sys.argv[1:4]
seen = False
with open(out, "a", buffering=1) as f:
    while not os.path.exists(until):
        pids = [p.info["pid"] for p in psutil.process_iter(["pid", "name"]) if p.info["name"] == name]
        allp = sorted({q for p in pids for q in tree(p)})
        if allp:
            seen = True
        elif seen:
            break
        t = time.strftime("%H:%M:%S")
        for pid in allp:
            r = rusage(pid)
            try:
                nm = psutil.Process(pid).name()
            except psutil.Error:
                continue
            if r:
                f.write(json.dumps({"t": t, "pid": pid, "name": nm, "rss_gib": round(r[2] / 2**30, 3),
                                    "fp_gib": round(r[0] / 2**30, 3), "fp_lifetime_gib": round(r[1] / 2**30, 3)}) + "\n")
        time.sleep(1)
