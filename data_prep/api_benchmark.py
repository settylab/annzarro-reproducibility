#!/usr/bin/env python
"""Real-data latency/payload benchmark of the AnnZarro HTTP API against the
protocol store (counterpart to the synthetic benchmark in benchmark/).

Issues exactly the requests the browser front end issues (static/js/data-manager.js)
for the five protocol views, against a running local server.

Method per request type:
  cold  = first request after POST /cache/reset (OS page cache NOT dropped; macOS
          `purge` needs sudo), for the protocol's example index
  rand  = n requests for distinct random indices (never served from the reader cache)
  warm  = the example request repeated (reader cache hit where the reader caches)
Latency is client wall time on localhost (request -> full body received).

Usage:
    python data_prep/api_benchmark.py --base http://127.0.0.1:8010 \
        --dataset $PWD/data/bm_aging.zarr --out data/api_benchmark.json
"""
import argparse
import json
import statistics
import time

import numpy as np
import requests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8010")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--examples", default="data_prep/demo_panelsets/examples.json")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", default="data/api_benchmark.json")
    args = ap.parse_args()
    api = f"{args.base}/api/v1"
    ds = args.dataset
    ex = json.load(open(args.examples))
    keys = ex["keys"]
    s = requests.Session()

    struct = s.get(f"{api}/data/dataset_structure", params={"dataset_path": ds}).json()
    n_obs, n_vars = struct.get("n_obs"), struct.get("n_vars")
    if not n_obs:
        n_obs, n_vars = struct["shape"]
    rng = np.random.default_rng(1)

    gene_i = ex["genes"]["focus"]["index"]
    cell_i = ex["cells"]["HSC"]["index"]

    # (label, path, params builder taking an index, axis for random indices, example index)
    cases = [
        ("X gene column (CSC)", "/data/X", lambda i: {"cols": i}, n_vars, gene_i),
        ("X cell row (CSC -> full load)", "/data/X", lambda i: {"rows": i}, n_obs, cell_i),
        ("fold-change layer gene column (dense 1024^2)", f"/data/layer/{keys['FC_KEY']}", lambda i: {"cols": i}, n_vars, gene_i),
        ("fold-change layer cell row (dense 1024^2)", f"/data/layer/{keys['FC_KEY']}", lambda i: {"rows": i}, n_obs, cell_i),
        ("smoothed Old layer gene column", f"/data/layer/{keys['SMOOTH_KEYS'][1]}", lambda i: {"cols": i}, n_vars, gene_i),
        ("logged_counts layer gene column (CSR -> full load)", "/data/layer/logged_counts", lambda i: {"cols": i}, n_vars, gene_i),
        ("obsp row, dense diffusion walk (1024^2)", f"/data/obsp/{keys['WALK_KEY']}", lambda i: {"rows": i}, n_obs, cell_i),
        ("obsp row, sparse DM_Kernel (CSR)", "/data/obsp/DM_Kernel", lambda i: {"rows": i}, n_obs, cell_i),
        ("varp row, dense Spearman (1024^2)", "/data/varp/spearman_smoothed", lambda i: {"rows": i}, n_vars, gene_i),
    ]

    def hit(path, params):
        p = {"dataset_path": ds, **{k: str(v) for k, v in params.items()}}
        t = time.perf_counter()
        r = s.get(api + path, params=p)
        dt = (time.perf_counter() - t) * 1000
        r.raise_for_status()
        body = r.json()
        d = body.get("data")
        shape = np.shape(d) if isinstance(d, list) else None
        return dt, len(r.content), shape

    results = []
    for label, path, mk, n_axis, ex_i in cases:
        s.post(f"{api}/cache/reset")
        cold, nbytes, shape = hit(path, mk(ex_i))
        rand = [hit(path, mk(int(i)))[0] for i in rng.choice(n_axis, args.n, replace=False)]
        warm = [hit(path, mk(ex_i))[0] for _ in range(3)]
        row = dict(request=label, endpoint=path, cold_ms=round(cold, 1),
                   rand_median_ms=round(statistics.median(rand), 1),
                   rand_p90_ms=round(float(np.percentile(rand, 90)), 1),
                   warm_median_ms=round(statistics.median(warm), 1),
                   payload_bytes=nbytes, payload_shape=shape)
        results.append(row)
        print(json.dumps(row), flush=True)

    # volcano: two var columns for all genes
    cols = f"{keys['LFC_KEY']},{keys['MAHAL_KEY']}"
    s.post(f"{api}/cache/reset")
    cold, nbytes, _ = hit("/data/var", {"columns": cols})
    warm = [hit("/data/var", {"columns": cols})[0] for _ in range(5)]
    row = dict(request="var columns mean_lfc + mahalanobis (volcano)", endpoint="/data/var",
               cold_ms=round(cold, 1), rand_median_ms=None, rand_p90_ms=None,
               warm_median_ms=round(statistics.median(warm), 1), payload_bytes=nbytes, payload_shape=None)
    results.append(row)
    print(json.dumps(row))
    # obs columns used by the cell table / UMAP
    cols = f"highres_celltype,{keys['DA_Z_KEY']}"
    cold, nbytes, _ = hit("/data/obs", {"columns": cols})
    results.append(dict(request="obs columns celltype + DA z-score (table)", endpoint="/data/obs",
                        cold_ms=round(cold, 1), payload_bytes=nbytes))
    print(json.dumps(results[-1]))
    t = time.perf_counter()
    r = s.get(f"{api}/data/obsm/X_umap", params={"dataset_path": ds})
    results.append(dict(request="obsm X_umap (all cells)", endpoint="/data/obsm/X_umap",
                        cold_ms=round((time.perf_counter() - t) * 1000, 1), payload_bytes=len(r.content)))
    print(json.dumps(results[-1]))
    t = time.perf_counter()
    r = s.get(f"{api}/data/dataset_structure", params={"dataset_path": ds})
    results.append(dict(request="dataset_structure (open dataset)", endpoint="/data/dataset_structure",
                        cold_ms=round((time.perf_counter() - t) * 1000, 1), payload_bytes=len(r.content)))
    print(json.dumps(results[-1]))
    json.dump(dict(dataset=ds, n_obs=n_obs, n_vars=n_vars, n_random=args.n, results=results),
              open(args.out, "w"), indent=1)


if __name__ == "__main__":
    main()
