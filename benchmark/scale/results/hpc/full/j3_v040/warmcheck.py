#!/usr/bin/env python
"""Is the filer warm for this store? Time a seeded random sample of its chunk files, read from the FILER.

The node page cache is evicted for the sampled files first (posix_fadvise DONTNEED, verified with mincore), so the
read goes to the NFS filer; its speed then says whether the filer still caches those chunks. Run it before the
warm-up (sample A), after the warm-up (a disjoint sample B), and after the measured pass (sample C): B much faster
than A means the warm-up stuck; B close to A means the filer was already warm, or the store does not stay cached.

  warmcheck.py STORE LABEL OUT.tsv [--n 60] [--seed S]
"""
import argparse
import os
import random
import sys
import time

sys.path.insert(0, "$SCRATCH/annzarro-scale/paper-hpcbench/benchmark/hpc/scripts")
import benchlib as bl  # noqa: E402  (evict, resident_fraction)

ap = argparse.ArgumentParser()
ap.add_argument("store"); ap.add_argument("label"); ap.add_argument("out")
ap.add_argument("--n", type=int, default=60); ap.add_argument("--seed", type=int, default=20261005)
a = ap.parse_args()
files = []
for sub in ("X/data", "X/indices", "layers/counts_csr/data", "layers/counts_csr/indices"):
    d = os.path.join(a.store, sub)
    files += [os.path.join(d, f) for f in os.listdir(d) if not f.startswith(".")]
files.sort()
rng = random.Random(f"{a.seed}:{a.label}:{a.store}")   # disjoint-by-construction is not guaranteed; label varies the draw
pick = rng.sample(files, min(a.n, len(files)))
bl.evict(pick)
res_after = bl.resident_fraction(pick)
nb, times = 0, []
for f in pick:
    t0 = time.perf_counter()
    with open(f, "rb") as fh:
        b = fh.read()
    times.append(time.perf_counter() - t0); nb += len(b)
times.sort()
tot = sum(times)
row = dict(ts=time.strftime("%Y-%m-%dT%H:%M:%S%z"), store=os.path.basename(a.store), label=a.label, n=len(pick),
           bytes=nb, seconds=round(tot, 3), mb_per_s=round(nb / 1e6 / tot, 1), p50_s=round(times[len(times) // 2], 4),
           p95_s=round(times[int(len(times) * 0.95) - 1], 4), resident_after_evict=round(res_after, 4),
           host=os.uname().nodename)
new = not os.path.exists(a.out)
with open(a.out, "a") as fh:
    if new:
        fh.write("\t".join(row) + "\n")
    fh.write("\t".join(str(v) for v in row.values()) + "\n")
print(row, flush=True)
