#!/usr/bin/env python
"""Filer warm-up for one store: read every file once (4 threads), count read errors, and compare the bytes read with
the store's apparent size (the sum of st_size over the same walk = `du -b --apparent-size`). Appends one row to OUT.tsv:
rung, start, seconds, bytes_read, apparent_bytes, short_read_bytes, files, read_errors, mb_per_s, first_error.
  warmread.py STORE RUNG OUT.tsv"""
import os, sys, time
from concurrent.futures import ThreadPoolExecutor
store, rung, out = sys.argv[1:4]
paths, apparent = [], 0
for d, _, fs in os.walk(store):
    for f in fs:
        p = os.path.join(d, f); paths.append(p)
        try:
            apparent += os.lstat(p).st_size
        except OSError:
            pass
errs = []
def rd(p):
    n = 0
    try:
        with open(p, "rb", buffering=0) as fh:
            while True:
                b = fh.read(1 << 22)
                if not b:
                    return n
                n += len(b)
    except OSError as e:
        errs.append(f"{p}: {e}")
        return n
t0, ts = time.time(), time.strftime("%Y-%m-%dT%H:%M:%S%z")
with ThreadPoolExecutor(4) as ex:
    nb = sum(ex.map(rd, paths, chunksize=64))
dt = time.time() - t0
new = not os.path.exists(out)
with open(out, "a") as fh:
    if new:
        fh.write("rung\tstart\tseconds\tbytes_read\tapparent_bytes\tshort_read_bytes\tfiles\tread_errors\tmb_per_s\tfirst_error\n")
    fh.write(f"{rung}\t{ts}\t{dt:.0f}\t{nb}\t{apparent}\t{apparent - nb}\t{len(paths)}\t{len(errs)}\t{nb / 1e6 / max(dt, 1e-9):.1f}\t{errs[0] if errs else '-'}\n")
print(f"warm {rung}: {nb} of {apparent} B, {len(paths)} files, {len(errs)} errors, {dt:.0f} s", flush=True)
sys.exit(1 if errs or nb != apparent else 0)
