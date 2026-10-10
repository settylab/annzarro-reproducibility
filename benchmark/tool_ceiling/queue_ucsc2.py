#!/usr/bin/env python
"""UCSC ladder from 5M after the tutorial fix: 5M as r2 (r0, r1 harness failures), then up."""
import queue_bisect as qb

for n, rep in ((5_000_000, 2), (10_000_000, 0), (20_000_000, 0), (50_000_000, 0), (95_624_334, 0)):
    if not qb.one("ucsc", "default", n, rep=rep):
        break
