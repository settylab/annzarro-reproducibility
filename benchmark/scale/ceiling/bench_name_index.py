#!/usr/bin/env python
"""Build time, memory and query time of AnnZarro's cell-name index (core/name_index.py).

Loads the obs names of a store the way the server does (reader
get_cell_gene_names), builds NameIndex from them, and times searches: an
exact hit, an exact miss, a typeahead prefix, a substring, and the empty
query. Memory is the process RSS (psutil) after loading the names, after the
build, and after dropping the loaded list (what the index itself keeps), plus
the peak (ru_maxrss). Run with the interpreter of the AnnZarro checkout to
measure (its name_index.py is the one imported).
"""
from __future__ import annotations

import argparse
import gc
import json
import resource
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import envcapture  # noqa: E402


def rss():
    return psutil.Process().memory_info().rss


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("store")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--chunked", action="store_true",
                    help="build from the reader's chunk iterator (no list of every name)")
    a = ap.parse_args()
    envcapture.require_clean_bench()
    envcapture.record(a.out, python=sys.executable, label=a.label, store=a.store, chunked=a.chunked)
    import annzarro
    from annzarro.core import name_index
    from annzarro.core.zarr_reader import ZarrReader
    rec = {"label": a.label, "store": a.store, "annzarro": annzarro.__file__}
    r0 = rss()
    reader = ZarrReader()
    if a.chunked:
        t = time.perf_counter()
        ix = name_index.NameIndex(name_index.NameChunks(reader.iter_cell_gene_name_chunks(a.store, "cells")))
        rec["load_s"] = 0.0
        rec["build_s"] = time.perf_counter() - t      # read + build, one chunk at a time
        rec["n"] = len(ix)
        r1 = r2 = rss()
        names = [ix.name(i) for i in (0, len(ix) // 3, len(ix) - 1)]
        names_full = None
    else:
        t = time.perf_counter()
        names_full = reader.get_cell_gene_names(a.store, "cells", use_cache=False)
        rec["load_s"] = time.perf_counter() - t
        rec["n"] = len(names_full)
        r1 = rss()
        t = time.perf_counter()
        ix = name_index.NameIndex(names_full)
        rec["build_s"] = time.perf_counter() - t
        r2 = rss()
        names = [names_full[i] for i in (0, len(names_full) // 3, len(names_full) - 1)]
    rec["index_struct_bytes"] = (sum(getattr(ix, k).nbytes for k in ("_starts", "_orig_off")
                                     if getattr(ix, k, None) is not None)
                                 + sum(sys.getsizeof(getattr(ix, k)) for k in ("_hay", "_orig")
                                       if getattr(ix, k, None) is not None)) if hasattr(ix, "_hay") and isinstance(ix._hay, bytes) else None
    probe = [str(x) for x in names]
    del names_full
    gc.collect()
    r3 = rss()
    rec.update(rss_start=r0, rss_names_loaded=r1, rss_index_built=r2, rss_index_only=r3,
               index_bytes=r3 - r0, peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    mid = probe[1]
    queries = {"exact_hit": (mid, "exact"), "exact_miss": (mid + "zz", "exact"),
               "typeahead_prefix": (mid[:8], "substring"), "typeahead_substring": (mid[3:10], "substring"),
               "typeahead_full": (mid, "substring"), "empty": ("", "substring")}
    rec["queries"] = {}
    for k, (q, mode) in queries.items():
        times = []
        for _ in range(3):
            t = time.perf_counter()
            res = ix.search(q, limit=100, mode=mode)
            times.append(time.perf_counter() - t)
        rec["queries"][k] = {"q": q, "mode": mode, "s": min(times), "matches": len(res["matches"]),
                             "truncated": res["truncated"],
                             "first": res["matches"][0] if res["matches"] else None}
    print(json.dumps(rec, indent=1))
    with open(a.out, "a") as f:
        f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
