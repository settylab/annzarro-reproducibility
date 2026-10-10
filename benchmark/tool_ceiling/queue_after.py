#!/usr/bin/env python
"""After the live-session pause: the UCSC ladder (1M as r1, its r0 was a
harness failure), then bisection and repeats for the web tools only (Scanpy
and Seurat are the baseline row and get no more runs).

Usage: queue_after.py
"""
from __future__ import annotations

import queue_bisect as qb

WEB = ["cellxgene:default", "cellxgene:backed", "cirrocumulus:default", "cirrocumulus:prepared", "vitessce:default",
       "ucsc:default", "isee:default", "shinycell:default"]


def main():
    for n in (1_000_000, 2_000_000, 5_000_000, 10_000_000, 20_000_000, 50_000_000, 95_624_334):
        if not qb.one("ucsc", "default", n, rep=1 if n == 1_000_000 else 0):
            break
    import sys
    sys.argv = ["queue_bisect.py", "--only", ",".join(WEB)]
    qb.main()


if __name__ == "__main__":
    main()
