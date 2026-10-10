# Runtime facts of the AnnZarro demo deployment (measured 2026-10-01)

## Request

Request: server-side runtime facts for the AnnZarro instance served on hpc-demo-node port 8766 (http://hpc-demo-node:8766/), for a methods manuscript. Read-only please; do not restart, reconfigure or modify the service or its data. Please report, with the exact commands/paths used: 1. Process: command line, annzarro version / git commit, python version, uptime, launch config (annzarro.yaml or CLI flags, data-dir, auth mode, port, workers). 2. Resources: current RSS and peak memory of the server process(es), CPU count available, node hardware (RAM, CPU model). If possible, RSS sampled before and after a few typical requests (e.g. one gene expression vector, one obsp row, one obsm embedding). 3. Datasets served: list each zarr store with on-disk size, n_obs, n_vars, and the keys in obs, var, obsm, varm, obsp, varp, layers, uns (top level). Note zarr chunk shapes and compressor for X, the largest layers, and obsp/varp arrays. Flag which ones hold kompot results. 4. Logs: request log summary if available (most common endpoints, response sizes, latency distribution p50/p95, cache hit rates if logged), and any errors/warnings in recent logs. 5. Server-side cache: location, size on disk / in memory, eviction settings. 6. Anything notable about deployment (reverse proxy, sandbox, how it is kept running). Short tables are ideal.

## Details

Request: server-side runtime facts for the AnnZarro instance served on hpc-demo-node port 8766 (http://hpc-demo-node:8766/), for a methods manuscript. Read-only please; do not restart, reconfigure or modify the service or its data. Please report, with the exact commands/paths used: 1. Process: command line, annzarro version / git commit, python version, uptime, launch config (annzarro.yaml or CLI flags, data-dir, auth mode, port, workers). 2. Resources: current RSS and peak memory of the server process(es), CPU count available, node hardware (RAM, CPU model). If possible, RSS sampled before and after a few typical requests (e.g. one gene expression vector, one obsp row, one obsm embedding). 3. Datasets served: list each zarr store with on-disk size, n_obs, n_vars, and the keys in obs, var, obsm, varm, obsp, varp, layers, uns (top level). Note zarr chunk shapes and compressor for X, the largest layers, and obsp/varp arrays. Flag which ones hold kompot results. 4. Logs: request log summary if available (most common endpoints, response sizes, latency distribution p50/p95, cache hit rates if logged), and any errors/warnings in recent logs. 5. Server-side cache: location, size on disk / in memory, eviction settings. 6. Anything notable about deployment (reverse proxy, sandbox, how it is kept running). Short tables are ideal.

## Reply

# AnnZarro on hpc-demo-node:8766 — server-side runtime facts

Measured 2026-10-01 16:08–16:55 PDT on hpc-demo-node, READ-ONLY (no restart, no config change, no writes to the data dir).
`$A` = `$DATA_ROOT/annzarro` (the service workdir from `monitor/services.registry`).

## 1. Process

| fact | value | how |
|---|---|---|
| service row | `annzarro  $NEXUS_ROOT/work/annzarro  ./run-supervised.sh  curl -fsS … http://localhost:8766/  …/annzarro.log` | `grep annzarro monitor/services.registry` |
| process tree | supervisor `bash run-supervised.sh` pid 11519 → gunicorn master 11555 → sync workers 11722, 11734, 11780 | `monitor/svc.sh status`, `ps -o pid,ppid,… -p 11519 --ppid 11519`, `pgrep -P` |
| command line | `.venv-pilot/bin/python3 .venv-pilot/bin/gunicorn --workers 3 --worker-class sync --bind 0.0.0.0:8766 --timeout 180 --graceful-timeout 30 --keep-alive 5 --access-logfile - --error-logfile - --log-level info wsgi_pilot:app` | `tr '\0' ' ' < /proc/11555/cmdline` (workers identical) |
| uptime | started Thu Oct 1 15:33:35 2026 (≈34 min at measurement); this is the 4th supervisor start today | `ps -o lstart= -p 11555`; `grep 'starting supervisor' $A/annzarro.log` |
| annzarro version | 0.1.1 (`pyproject.toml`, `annzarro.__version__`); git `b3cd3040443001988efb1334ea8d9a6649646423` (2026-08-28), `git describe` = `v0.1.1-158-gb3cd304`; package code clean (only `served-data/README.md` modified; `wsgi_pilot.py`, `run-supervised.sh` untracked) | `git -C $A rev-parse HEAD`, `git -C $A describe --tags`, `git -C $A status --porcelain` |
| remote | `https://github.com/settylab/annzarro.git` | `git -C $A remote -v` |
| Python / libs | Python 3.11.6; gunicorn 26.0.0, Flask 3.1.3, zarr 3.1.6, numcodecs 0.16.5, numpy 2.4.6, pandas 3.0.3, h5py 3.16.0 (anndata NOT installed in the serving venv; reads go through annzarro's own zarr/h5 readers) | `$A/.venv-pilot/bin/python3 -V`; `import <mod>; <mod>.__version__` in that venv |
| launch config | NOT `annzarro.yaml` (that symlink → `config/base.yaml` is not read by this deployment). Config = `DEFAULT_CONFIG` + overrides in `$A/wsgi_pilot.py`: `host 0.0.0.0`, `port $ANNZARRO_PORT or 8766`, `data_dir $ANNZARRO_DATA_DIR or $A/served-data`, `auth_enabled False`, `cache_enabled True`, `cache_memory_mb $ANNZARRO_CACHE_MB or 8000`, `cache_dataset_limit $ANNZARRO_CACHE_DATASETS or 6`, `log_file $A/annzarro_app.log`, `log_level INFO` | `cat $A/wsgi_pilot.py`; `sed -n 20,60p $A/annzarro/server/core.py` |
| data dir | `$A/served-data` (env default in `run-supervised.sh`); browsable datasets = `served-data/datasets/` (33 symlinks into `work/lab-data/data/processed_zarr/`) | `cat $A/run-supervised.sh`; `ls -la $A/served-data/datasets` |
| auth mode | disabled (`auth_enabled: False`) | `wsgi_pilot.py` |
| port / workers | 8766, 3 gunicorn **sync** workers (1 request at a time each), timeout 180 s | cmdline above; `ss -ltnp \| grep 8766` |
| request limits in effect | DEFAULT_CONFIG: `max_cells_per_request 10000`, `max_genes_per_request 10000`, `max_response_elements 1000000`, `max_embedding_dims 50` | `annzarro/server/core.py:24-50` |

## 2. Resources and hardware

| process | RSS now (kB) | peak RSS VmHWM (kB) | VmPeak (virtual, kB) |
|---|---|---|---|
| master 11555 | 25,664 | 25,664 | 173,672 |
| worker 11722 | 751,124 | 906,824 | 4,096,260 |
| worker 11734 | 581,368 | 905,628 | 3,791,144 |
| worker 11780 | 710,280 | 915,900 | 4,093,984 |
| **total** | **≈2.07 GB** | per-worker peaks ≈0.9 GB each (since 15:33) | |

How: `grep -E 'VmRSS|VmHWM|VmPeak' /proc/<pid>/status` at 16:08:10 PDT. The supervisor bash (11519) is 3.3 MB RSS.

**Node:** hpc-demo-node, 2 × Intel Xeon Gold 6254 @ 3.10 GHz (18 cores/socket, no SMT ⇒ 36 logical CPUs), 754.6 GiB RAM (`MemTotal 791221208 kB`; `MemAvailable` 629 GiB at measurement); host uptime 135 days; load average 60–78 (shared node, oversubscribed). Workers' CPU affinity 0-35 (no cpuset), memory cgroup `/user.slice` (no per-service limit).
How: `nproc`; `grep 'model name\|physical id\|cpu cores\|siblings' /proc/cpuinfo`; `grep Mem /proc/meminfo`; `taskset -cp 11722`; `cat /proc/11722/cgroup`; `uptime`.

**RSS around typical requests.** All GET to localhost:8766, dataset `served-data/datasets/spatial-B.zarr` (75,000 × 18,345), cold for those keys. The access log shows no other client traffic in that window, so the deltas are attributable to these three requests:

| request | HTTP | bytes | wall time | Σ worker RSS after (kB) | Δ |
|---|---|---|---|---|---|
| (before, 16:13:27) | | | | 2,068,996 | |
| `GET /api/v1/data/X?dataset_path=…spatial-B…&cols=200` (one gene, all 75k cells) | 200 | 450,127 | 1.97 s | 2,070,580 | +1.6 MB |
| `GET /api/v1/data/obsp/context_fn_ls1?dataset_path=…&rows=4321` (one dense obsp row, 75k floats) | 200 | 1,338,318 | 0.89 s | 2,072,556 | +2.0 MB |
| `GET /api/v1/data/obsm/X_umap?dataset_path=…&column_name=0` (one embedding column) | 200 | 1,409,237 | 0.76 s | 2,073,700 | +1.1 MB |

How: `awk '/VmRSS/{print $2}' /proc/{11722,11734,11780}/status` before and after each `curl -sS -o /dev/null -w '%{http_code} %{size_download} %{time_total}'`. An earlier identical trio on `spatial-A` (16:12:45–49; X cols=100, obsp rows=12345, obsm X_umap col 0) returned 450,127 / 1,340,466 / 1,409,709 B in 1.21 / 2.36 / 0.08 s, but there was concurrent browser traffic, so I did not use its RSS. I also made two `GET /api/v1/cache/info` calls, so 9 GETs in total.

## 3. Datasets served (33 stores, all zarr v2, AnnData encoding 0.1.0)

How: one Python script reading ONLY metadata. For 31 stores it read the consolidated `.zmetadata`; for the 2 healthy-atlas stores, which have no `.zmetadata`, it walked `.zgroup`/`.zattrs`/`.zarray` and stopped at each array. No chunk was read. `n_obs`/`n_vars` = length of `obs/_index`/`var/_index`. Kompot flags come from key names: **DE** = `uns/kompot_de*`, `layers/kompot_de_*` or var `kde_*`/`kompot_de_*` columns; **DA** = `uns/kompot_da` or obs `kompot_da_*`; **smooth** = `layers/kompot_smooth_all_smoothed` or `*_smoothed`; **imputed** = `layers/kompot_imputed_crossassay`. Script: `$SCRATCH/fallback/reports-staging/annzinfo_2026-10-01_161443_annzarro-runtime-facts.meta.py` (metadata) and `$SCRATCH/fallback/reports-staging/annzinfo_2026-10-01_161443_annzarro-runtime-facts.logs.py` (log summary). On-disk size = `timeout 240 du -shL <store>`, run one store at a time.

**Encodings common to all stores:**
- **X:** always `csc_matrix`; `data`/`indices` chunked 1-D (chunk lengths in the table); compressor `blosc/lz4 clevel=5 shuffle=1`.
- **Sparse layers and obsp:** csc/csr, same `blosc/lz4 clevel=5 shuffle=1`.
- **Dense layers:** chunked `[n_obs, 4]` (blosc/lz4) or `[n_obs, 64]` (blosc/lz4 or blosc/zstd clevel 5), i.e. whole-column chunks, so one gene vector is one chunk.
- **Dense obsp (spatial stores):** 75,000 × 75,000 f4, chunked `[16, 75000]` (row blocks), blosc/zstd clevel 5. That is 21 GiB uncompressed each, 9 per spatial store, 99 in total.
- **Dense varp (spatial stores):** n_vars × n_vars f4, chunked `[64, n_vars]`, blosc/zstd clevel 5.
- **Totals:** 208 dense layer/obsp/varp arrays, together **≈2.8 TiB uncompressed**.

| store | du -shL | n_obs | n_vars | X enc/dtype | X nnz | X data chunk | consolidated | kompot |
|---|---|---|---|---|---|---|---|---|
| spatial-A.zarr | 168G | 75,000 | 18,345 | csc <f4 | 11,809,157 | 184,519 | yes | DE+DA+smooth+imputed |
| spatial-B.zarr | 168G | 75,000 | 18,345 | csc <f4 | 25,367,975 | 198,188 | yes | DE+DA+smooth+imputed |
| spatial-E.zarr | 169G | 75,000 | 18,345 | csc <f4 | 15,183,717 | 237,246 | yes | DE+DA+smooth+imputed |
| spatial-D.zarr | 164G | 75,000 | 10,279 | csc <f4 | 25,608,531 | 200,067 | yes | DE+DA+smooth+imputed |
| spatial-C.zarr | 166G | 75,000 | 14,239 | csc <f4 | 15,492,894 | 242,077 | yes | DE+DA+smooth+imputed |
| BR_2204_spatial_annzarro.zarr | 169G | 75,000 | 18,345 | csc <f4 | 31,868,392 | 248,972 | yes | DE+DA+smooth+imputed |
| BR_2328_spatial_annzarro.zarr | 167G | 75,000 | 15,556 | csc <f4 | 26,566,452 | 207,551 | yes | DE+DA+smooth+imputed |
| BR_2453_spatial_annzarro.zarr | 169G | 75,000 | 18,345 | csc <f4 | 13,120,239 | 205,004 | yes | DE+DA+smooth+imputed |
| GSE115469_harmonized.zarr | 2.0G | 8,444 | 16,996 | csc <f4 | 11,069,888 | 172,967 | yes | smooth |
| GSE124395_harmonized.zarr | 2.9G | 11,947 | 19,557 | csc <f8 | 17,130,537 | 133,833 | yes | smooth |
| GSE125449_harmonized.zarr | 2.5G | 8,966 | 18,293 | csc <f8 | 12,647,186 | 98,807 | yes | DE+DA+smooth |
| GSE136103_harmonized.zarr | 12G | 85,942 | 23,223 | csc <f8 | 111,782,663 | 218,326 | yes | DE+DA+smooth |
| GSE138709_harmonized.zarr | 5.5G | 31,195 | 19,813 | csc <f8 | 68,022,734 | 265,714 | yes | DE+DA+smooth |
| GSE140228_harmonized.zarr | 8.8G | 62,765 | 22,464 | csc <f8 | 74,032,117 | 289,188 | yes | DE+DA+smooth |
| GSE146409_spatial_lcm_harmonized.zarr | 32M | 63 | 34,029 | csc <f4 | 616,392 | 77,049 | yes | — |
| GSE149614_harmonized.zarr | 11G | 68,175 | 23,628 | csc <f8 | 136,742,914 | 267,077 | yes | DE+DA+smooth |
| GSE164522_harmonized.zarr | 82G | 257,843 | 24,222 | csc <f4 | 437,626,882 | 854,741 | yes | DE+DA+smooth |
| GSE178318_harmonized.zarr | 41G | 126,314 | 22,657 | csc <f8 | 148,469,785 | 289,981 | yes | DE+DA+smooth |
| GSE192741_harmonized.zarr | 25G | 159,141 | 26,715 | csc <f8 | 206,021,998 | 402,387 | yes | DE+DA+smooth |
| GSE197177_harmonized.zarr | 11G | 57,747 | 24,443 | csc <f8 | 124,250,453 | 242,677 | yes | DE+DA+smooth |
| GSE206552_spatial_mapped_harmonized.zarr | 272M | 9,712 | 10,305 | csc <f4 | 13,327,643 | 208,245 | yes | — |
| GSE225857_harmonized.zarr | 22G | 222,728 | 17,816 | csc <f8 | 243,102,188 | 237,405 | yes | DE+DA+smooth |
| GSE225857_spatial_mapped_harmonized.zarr | 551M | 21,739 | 11,428 | csc <i8 | 58,682,780 | 229,230 | yes | — |
| GSE235863_harmonized.zarr | 67G | 181,770 | 24,462 | csc <f8 | 297,924,575 | 290,942 | yes | DE+DA+smooth |
| GSE263733_harmonized.zarr | 12G | 65,537 | 25,365 | csc <f8 | 171,573,675 | 335,105 | yes | DE+DA+smooth |
| MH1_22-049K4_spatial_annzarro.zarr | 168G | 75,000 | 17,080 | csc <f4 | 37,626,173 | 293,955 | yes | DE+DA+smooth+imputed |
| PR_1812_spatial_annzarro.zarr | 166G | 75,000 | 13,180 | csc <f4 | 35,741,924 | 279,234 | yes | DE+DA+smooth+imputed |
| PR_2409_spatial_annzarro.zarr | 169G | 75,000 | 16,966 | csc <f4 | 19,547,974 | 305,438 | yes | DE+DA+smooth+imputed |
| healthy_liver_atlas_snRNA_harmonized.zarr | 2.5G | 67,700 | 18,129 | csc <f4 | 165,929,489 | 648,163 | no | — |
| healthy_liver_atlas_visiumHD_harmonized.zarr | 636M | 75,949 | 18,085 | csc <f4 | 27,235,321 | 212,776 | no | — |
| atlas-1.17M-raw.zarr | 21G | 1,165,934 | 12,731 | csc <f4 | 1,557,510,496 | 760,504 | yes | — |
| atlas-1.17M-scvi.zarr | 78G | 1,165,934 | 12,731 | csc <f4 | 1,557,510,496 | 760,504 | yes | DA+smooth |
| atlas-scPLM.zarr | n/a (no result in 240 s) | 460,337 | 33,538 | csc <f8 | 868,229,259 | 423,941 | yes | DA+smooth |


Sum of measured `du` (32 of 33 stores): ≈2.20 TiB on disk. `atlas-scPLM.zarr` returned no size (the 240 s `timeout` or an error; the pipeline masked which). The 10 spatial stores are 164–169 G each; their uncompressed content is dominated by the nine dense 75k×75k obsp arrays (≈189 GiB raw per store). `du` was run serially, one `timeout 240 du -shL` per store, from 16:10 PDT; the last store finished at 16:54 PDT.

### Largest dense arrays (uncompressed size from shape × itemsize)

| store | array | shape | chunks | compressor | GiB raw |
|---|---|---|---|---|---|
| atlas-scPLM | layers/kompot_smooth_all_smoothed | 460,337 × 33,538 f4 | [460337, 4] | blosc/lz4 c5 | 57.5 |
| atlas-1.17M-scvi | layers/kompot_smooth_all_smoothed | 1,165,934 × 12,731 f4 | [1165934, 4] | blosc/lz4 c5 | 55.3 |
| GSE164522_harmonized | 9 kompot layers (smooth_all + 2 DE contrasts × {2 smoothed, fold_change, fold_change_zscores}) | 257,843 × 24,222 f4 | [257843, 4] | blosc/lz4 c5 | 23.3 each |
| any *_spatial_annzarro (10 stores) | obsp/{context_diff_ls1,3,10; context_fn_ls1,3,10; dist_context_rows; dist_diffmap; dist_spatial} | 75,000 × 75,000 f4 | [16, 75000] | blosc/zstd c5 | 21.0 each |
| GSE225857_harmonized | layers/kompot_smooth_all_smoothed | 222,728 × 17,816 f4 | [222728, 4] | blosc/lz4 c5 | 14.8 |
| any *_spatial_annzarro | layers/{kompot_de_Flex_smoothed, kompot_de_Xenium_smoothed} (lz4); {kompot_de_fold_change, kompot_imputed_crossassay} (zstd) | 75,000 × n_vars f4 | [75000, 64] | blosc c5 | ≤5.1 each |
| any *_spatial_annzarro | varp/{gene_corr_pearson_lognorm, gene_corr_spearman_lognorm, gene_cosine_lognorm} | n_vars² f4 | [64, n_vars] | blosc/zstd c5 | ≤1.25 each |

The non-spatial obsp (`connectivities`, `distances`) are sparse CSR, blosc/lz4. The full per-store key lists (obs/var columns; obsm/varm/obsp/varp/layers/uns keys) are in the appendix below.

## 4. Logs

The access log is gunicorn's default format, which **does not record latency**, and the server **does not log cache hit/miss at INFO**: those are `logger.debug` lines (`annzarro/core/caching.py:554,560`) and the service runs at `log_level INFO`. So the log cannot give p50/p95 latency or a cache hit rate.

How: a Python pass over `$A/annzarro.log` (88 MB, 972,581 lines, 2026-06-06 → 2026-10-01). It excludes the 958,815 health-check lines (`127.0.0.1 "GET /" curl`, the registry's probe) and groups paths by route. Also `grep` on `$A/annzarro.log` and `$A/annzarro_app.log`.

| | value |
|---|---|
| client requests (excl. health checks) | 6,747 over 33 distinct days, 10 distinct client IPs |
| status | 200: 4,657 · 304: 1,916 · 404: 126 · 400: 29 · 500: 19 |
| response bytes, all requests | p50 4.3 kB · p95 1.56 MB · max 838 MB · total 10.2 GB |

| endpoint (GET) | count | p50 bytes | p95 bytes | max bytes |
|---|---|---|---|---|
| /static/* | 2,573 | 0 (304) | 0 | 207 |
| /api/v1/data/obsm/<key> | 726 | 1.38 MB | 4.81 MB | 10.2 MB |
| /api/v1/data/obs | 656 | 614 kB | 2.36 MB | 73.4 MB |
| /api/v1/data/obsp/<key> | 604 | 1.38 MB | 1.43 MB | 1.57 MB |
| /api/v1/data/layer/<key> | 509 | 150 kB | 4.83 MB | 838 MB |
| /api/v1/data/dataset_structure | 488 | 5.3 kB | 8.3 kB | 12.0 kB |
| /api/v1/data/cells | 225 | 664 kB | 18.9 MB | 36.2 MB |
| /api/v1/data/uns/<key> | 172 | 171 B | 365 B | 484 B |
| /api/v1/datasets | 131 | 5.6 kB | 8.0 kB | 8.0 kB |
| /api/v1/sessions/* | 110 | 278 B | 805 kB | 805 kB |
| /api/v1/data/genes | 95 | 154 kB | 372 kB | 372 kB |
| /api/v1/data/varp/<key> | 77 | 154 kB | 164 kB | 166 kB |

**Errors and warnings** (counts over the whole log; `grep -E '\[ERROR\]|\[WARNING\]|WORKER TIMEOUT|SIGKILL'`, digits normalised, `sort | uniq -c`):

| event | count | dates / note |
|---|---|---|
| `WORKER TIMEOUT` (180 s) | 30 | 06-06 ×2, 06-25, 07-16 ×5, 07-17 ×5, **09-18 ×16**, 09-21 |
| `Worker … was sent SIGKILL! Perhaps out of memory?` | 15 | 06-06 ×2, 07-16 ×5, 07-17 ×5, 09-18 ×2, 09-21 (dates coincide with the timeouts: consistent with gunicorn killing timed-out workers, not proven OOM) |
| `Connection in use` / `Address already in use` | 50 / 50 | port 8766 still held when the supervisor relaunched (restart races) |
| `Error processing categorical data: path=slice(None…) is not a string` | 38 | annzarro.core.zarr_reader |
| `h5ad_reader: Could not get h5ad metadata: 'Group' object has no attribute 'shape'` | 18 | app log |
| `Error getting shape for layers/{X_within,X_within_shared,counts}` (sparse layer read as array) | 3 each | spatial stores |
| `Invalid dataset path or format: BE_…` / 500 on `/datasets/BE_…/metadata` | 6 / 5 | relative-path requests |
| `Request Line is too large` | 2 | over-long GET query |
| gunicorn exits (supervisor restarted gunicorn) | 9 | |
| supervisor starts (whole service relaunched) | 47 (4 on 2026-10-01) | external restarts: sandbox restarts and the HPC worker service-health auto-restart |

## 5. Server-side cache

| fact | value | how |
|---|---|---|
| type | **in-process memory only**, no on-disk cache; `DatasetCache` with separate matrix, dataframe and metadata dicts | `annzarro/core/caching.py:15-50` |
| scope | **per gunicorn worker** (3 independent caches; a request hits whichever worker accepts it) | sync worker model; `configure_zarr_reader()` runs per process (`annzarro/core/__init__.py:31`) |
| limits | `cache_memory_mb = 8000` **per worker** (so ≤24 GB across 3 workers, by annzarro's own size estimate), `cache_dataset_limit = 6` | `wsgi_pilot.py`; confirmed in the app log (`Zarr reader configured with: cache_memory_mb=8000, cache_enabled=True, cache_dataset_limit=6`) |
| eviction | LRU by access timestamp: first whole datasets beyond the dataset limit (oldest last-access), then individual items until under the memory limit | `annzarro/core/caching.py:158-200` (`_manage_cache_size`) |
| current state (one worker) | 6/6 datasets, 17 items (8 matrix, 3 dataframe, 6 metadata), **55.8 MB of 8,000 MB (0.70%)**; unchanged after my request trio | `curl -s http://localhost:8766/api/v1/cache/info` (GET, read-only) at 16:12:45 and 16:12:49 |
| hit rate | not available (DEBUG-only logging) | see §4 |
| other memory | OS page cache on the node (NFS-backed `$DATA_ROOT`) is not attributable to the service | |

The service also exposes `POST /api/v1/cache/reset`. I did not call it.

## 6. Deployment

| fact | value | how |
|---|---|---|
| reverse proxy | **none**: gunicorn binds `0.0.0.0:8766` directly, plain HTTP, no TLS, no auth; reachable as `http://hpc-demo-node:8766/` on the campus network | `ss -ltnp \| grep 8766` (4 gunicorn pids on fd 3); cmdline |
| keep-alive layer 1 | `run-supervised.sh`, a bash restart loop around gunicorn (2 s backoff), launched setsid-detached; logs supervisor events + gunicorn stdout/stderr + access log to `$A/annzarro.log` | `cat $A/run-supervised.sh` |
| keep-alive layer 2 | HPC worker `services.registry` row with health check `curl -fsS -o /dev/null --max-time 3 http://localhost:8766/` (958,815 probe lines over ~117 days ≈ one every ~10 s on average); policy column omitted ⇒ default `auto-restart`; relaunched by the HPC worker watcher's service-health loop / `monitor/bootstrap-recover.sh` (e.g. after sandbox restarts) | `monitor/services.registry`; `monitor/services.registry.example:145-155` |
| sandbox | runs inside the operator's agent-sandbox (kernel-enforced filesystem confinement) on the shared interactive node hpc-demo-node, as user `user`; not a Slurm job | process lineage; `cat /proc/11722/cgroup` (`/user.slice`) |
| venv | `$A/.venv-pilot` (Python 3.11.6) | cmdline |
| sibling instance | a second, independent AnnZarro (`annzarro-xiulan`, :8768) runs from another workdir; not covered here | `monitor/svc.sh status` |
| data provenance | every served store is a symlink from `served-data/datasets/` to `work/lab-data/data/processed_zarr/*.zarr` (several to `*.kompot.zarr` / `*.decorated.zarr` variants) | `ls -la $A/served-data/datasets` |

## Caveats
- Uptime and peak RSS cover only the current incarnation (since 15:33:35); the service was restarted 4× today.
- "Kompot" flags are inferred from key names, not from reading values.
- The RSS deltas are one-shot and single-worker; they show that per-request working memory is small (MB) for these access patterns, not a distribution.
- The 838 MB max response was a `/data/layer` request; I did not identify which.


## Appendix: keys per store (obs/var: column counts; others: full key lists)

**spatial-A.zarr, spatial-B.zarr, spatial-E.zarr, spatial-D.zarr, spatial-C.zarr, BR_2204_spatial_annzarro.zarr, BR_2328_spatial_annzarro.zarr, BR_2453_spatial_annzarro.zarr, PR_1812_spatial_annzarro.zarr, PR_2409_spatial_annzarro.zarr**
- obs (22): origin, celltype, sample, x_centroid, y_centroid, cell_id, leiden_hires, cluster_celltype, cluster_label, celltype_transfer, kompot_da_Flex_to_Xenium_lfc, kompot_da_Flex_to_Xenium_lfc_zscore, kompot_da_Flex_to_Xenium_neg_log10_lfc_ptp, kompot_da_Flex_to_Xenium_lfc_direction, kompot_da_Flex_log_density, kompot_da_Xenium_log_density, sctx_log_density, sctx_nearest_landmark, sctx_is_start_cell, leiden_res1_0, leiden_res0_5, leiden_res0_25
- var (6): panel, kompot_de_Flex_to_Xenium_mahalanobis, kompot_de_Flex_to_Xenium_mean_lfc, kompot_de_Flex_to_Xenium_mahalanobis_local_fdr, kompot_de_Flex_to_Xenium_is_de, kompot_de_sv_Flex_to_Xenium_mean_lfc
- obsm: DM_EigenVectors, X_context_slices, X_pca_harmony, X_umap, X_umap_3d, spatial
- varm: —
- obsp: context_diff_ls1, context_diff_ls10, context_diff_ls3, context_fn_ls1, context_fn_ls10, context_fn_ls3, dist_context_rows, dist_diffmap, dist_spatial
- varp: gene_corr_pearson_lognorm, gene_corr_spearman_lognorm, gene_cosine_lognorm
- layers: X_within, X_within_shared, counts, kompot_de_Flex_smoothed, kompot_de_Xenium_smoothed, kompot_de_fold_change, kompot_imputed_crossassay
- uns: DM_EigenValues, better_embedding, imputed_crossassay_genes, kompot_augmented, kompot_da, kompot_da_Flex_to_Xenium_lfc_direction_colors, kompot_de_genes, kompot_de_smoothed_note, kompot_smooth, leiden_hires, leiden_hires_colors, leiden_res0_25_colors, leiden_res0_5_colors, leiden_res1_0_colors, neighbors, norm_chosen_name, panel_sizes, pipeline, sample, smF, smX, spatial_context

**GSE115469_harmonized.zarr**
- obs (19): patient, sample, site, condition, author_cluster, author_celltype, n_genes_by_counts, total_counts, total_counts_mt, pct_counts_mt, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, cell_type, cell_type_original, author_celltype_uni
- var (11): gene_symbol, mt, n_cells_by_counts, mean_counts, pct_dropout_by_counts, total_counts, n_cells, highly_variable, means, dispersions, dispersions_norm
- obsm: X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: hvg, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, preprocessing, umap

**GSE124395_harmonized.zarr**
- obs (20): sample, donor, gate, orig_cluster, n_genes_by_counts, total_counts, total_counts_mt, pct_counts_mt, pass_count_bounds, predicted_doublet, doublet_score, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, cell_type, cell_type_original, cell_type_fine
- var (10): mt, n_cells_by_counts, mean_counts, pct_dropout_by_counts, total_counts, n_cells, highly_variable, means, dispersions, dispersions_norm
- obsm: X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: hvg, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, umap

**GSE125449_harmonized.zarr**
- obs (25): sample, author_celltype, set, patient, disease, n_genes_by_counts, total_counts, total_counts_mt, pct_counts_mt, pass_count_bounds, n_genes, doublet_score, predicted_doublet, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, cell_type, cell_type_original, cnv_score, cnv_high, cell_type_fine, kompot_da_lfc
- var (24): gene_symbol, ensembl_id, mt, n_cells_by_counts, mean_counts, pct_dropout_by_counts, total_counts, n_cells, highly_variable, means, dispersions, dispersions_norm, chromosome, start, end, gene_id, gene_name, kde_HCC_to_iCCA_mahalanobis, kde_HCC_to_iCCA_mean_lfc, kde_HCC_to_iCCA_mahalanobis_local_fdr, kde_HCC_to_iCCA_is_de, kde_HCC_to_iCCA_mahalanobis_sample_var, kde_HCC_to_iCCA_refined, kde_HCC_to_iCCA_mahalanobis_effective
- obsm: X_cnv, X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: cnv, hvg, kompot_da, kompot_de, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, scrublet, umap

**GSE136103_harmonized.zarr**
- obs (21): sample, patient, compartment, condition, n_genes_by_counts, total_counts, total_counts_mt, pct_counts_mt, pass_count_bounds, n_genes, doublet_score, predicted_doublet, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, cell_type, cell_type_original, kompot_da_lfc
- var (19): gene_symbol, ensembl_id, mt, n_cells_by_counts, mean_counts, pct_dropout_by_counts, total_counts, n_cells, highly_variable, means, dispersions, dispersions_norm, kde_healthy_to_cirrhotic_mahalanobis, kde_healthy_to_cirrhotic_mean_lfc, kde_healthy_to_cirrhotic_mahalanobis_local_fdr, kde_healthy_to_cirrhotic_is_de, kde_healthy_to_cirrhotic_mahalanobis_sample_var, kde_healthy_to_cirrhotic_refined, kde_healthy_to_cirrhotic_mahalanobis_effective
- obsm: X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: cell_type_colors, compartment_colors, condition_colors, hvg, kompot_da, kompot_de, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, scrublet, umap

**GSE138709_harmonized.zarr**
- obs (23): sample, patient, tissue, n_genes_by_counts, total_counts, total_counts_mt, pct_counts_mt, pass_count_bounds, n_genes, doublet_score, predicted_doublet, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, cell_type, cell_type_original, cnv_score, cnv_high, cell_type_fine, kompot_da_lfc
- var (22): mt, n_cells_by_counts, mean_counts, pct_dropout_by_counts, total_counts, n_cells, highly_variable, means, dispersions, dispersions_norm, chromosome, start, end, gene_id, gene_name, kde_Adjacent_to_Tumor_mahalanobis, kde_Adjacent_to_Tumor_mean_lfc, kde_Adjacent_to_Tumor_mahalanobis_local_fdr, kde_Adjacent_to_Tumor_is_de, kde_Adjacent_to_Tumor_mahalanobis_sample_var, kde_Adjacent_to_Tumor_refined, kde_Adjacent_to_Tumor_mahalanobis_effective
- obsm: X_cnv, X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: cnv, hvg, kompot_da, kompot_de, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, scrublet, umap

**GSE140228_harmonized.zarr**
- obs (28): patient, site, tissue_sub, sample, histology, author_global, author_sub, n_genes_by_counts, total_counts, total_counts_mt, pct_counts_mt, pass_count_bounds, n_genes, doublet_score, predicted_doublet, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, cell_type, cell_type_original, c1q_score, mono_score, exhaustion_score, naive_score, kompot_da_lfc
- var (23): ensembl_id, gene_symbol, chromosome, start, end, biotype, mt, n_cells_by_counts, mean_counts, pct_dropout_by_counts, total_counts, n_cells, highly_variable, means, dispersions, dispersions_norm, kde_Normal_to_Tumor_mahalanobis, kde_Normal_to_Tumor_mean_lfc, kde_Normal_to_Tumor_mahalanobis_local_fdr, kde_Normal_to_Tumor_is_de, kde_Normal_to_Tumor_mahalanobis_sample_var, kde_Normal_to_Tumor_refined, kde_Normal_to_Tumor_mahalanobis_effective
- obsm: X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: hvg, kompot_da, kompot_de, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, scrublet, umap

**GSE146409_spatial_lcm_harmonized.zarr**
- obs (34): patient, zone, disease, zone_name, zone_ord, n_genes_by_counts, log1p_n_genes_by_counts, total_counts, log1p_total_counts, score_SPP1_TAM, score_CD8_T, score_HSC_CAF, score_CXCL12_CAF, score_Tumor_epithelium, prop_B_cell, prop_CD4_T, prop_CD8_T, prop_HSC_CAF, prop_Mast, prop_Monocyte_macrophage, prop_NK, prop_Naive_T, prop_Plasma, prop_Proliferating, prop_SPP1_TAM, prop_Treg, prop_Malignant_epithelium, prop_pDC, prop_Cholangiocyte, prop_DC, prop_Erythroid, prop_Hepatocyte, prop_Vascular_endothelial, leiden
- var (6): n_cells_by_counts, mean_counts, log1p_mean_counts, pct_dropout_by_counts, total_counts, log1p_total_counts
- obsm: X_pca, X_umap, celltype_props
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, lognorm
- uns: embedding_provenance, log1p, neighbors, pca, umap

**GSE149614_harmonized.zarr**
- obs (26): sample, site, patient, stage, virus, author_celltype, n_genes_by_counts, total_counts, total_counts_mt, pct_counts_mt, pass_count_bounds, n_genes, doublet_score, predicted_doublet, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, cell_type, cell_type_original, cnv_score, cnv_high, cell_type_fine, kompot_da_lfc
- var (22): mt, n_cells_by_counts, mean_counts, pct_dropout_by_counts, total_counts, n_cells, highly_variable, means, dispersions, dispersions_norm, chromosome, start, end, gene_id, gene_name, kde_Normal_to_Tumor_mahalanobis, kde_Normal_to_Tumor_mean_lfc, kde_Normal_to_Tumor_mahalanobis_local_fdr, kde_Normal_to_Tumor_is_de, kde_Normal_to_Tumor_mahalanobis_sample_var, kde_Normal_to_Tumor_refined, kde_Normal_to_Tumor_mahalanobis_effective
- obsm: X_cnv, X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: cnv, hvg, kompot_da, kompot_de, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, scrublet, umap

**GSE164522_harmonized.zarr**
- obs (44): site, tissue_code, patient, tissue, author_global, author_major, author_sub, author_louvain, n_genes_author, percent_mito_author, n_counts_author, sample, tcr_clonotype, tcr_clone_state, tcr_cdr3b, has_tcr, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, exhaustion_score, naive_score, _spp1, cell_type, cell_type_original, kompot_da_lfc, kde_blood_to_liver_met__blood_smoothed__score_cytotoxic, kde_blood_to_liver_met__blood_smoothed__score_exhaustion, kde_blood_to_liver_met__blood_smoothed__score_apoptosis, kde_blood_to_liver_met__liver_met_smoothed__score_cytotoxic, kde_blood_to_liver_met__liver_met_smoothed__score_exhaustion, kde_blood_to_liver_met__liver_met_smoothed__score_apoptosis, kde_blood_to_liver_met_fold_change__score_cytotoxic, kde_blood_to_liver_met_fold_change__score_exhaustion, kde_blood_to_liver_met_fold_change__score_apoptosis, kde_blood_to_liver_met_fold_change_zscores__score_cytotoxic, kde_blood_to_liver_met_fold_change_zscores__score_exhaustion, kde_blood_to_liver_met_fold_change_zscores__score_apoptosis, kde_primary_CRC_to_liver_met__primary_CRC_smoothed__score_spp1_tam, kde_primary_CRC_to_liver_met__liver_met_smoothed__score_spp1_tam, kde_primary_CRC_to_liver_met_fold_change__score_spp1_tam, kde_primary_CRC_to_liver_met_fold_change_zscores__score_spp1_tam
- var (27): mt, n_cells, highly_variable, means, dispersions, dispersions_norm, kde_liver_normal_to_liver_met_mahalanobis, kde_liver_normal_to_liver_met_mean_lfc, kde_liver_normal_to_liver_met_mahalanobis_local_fdr, kde_liver_normal_to_liver_met_is_de, kde_liver_normal_to_liver_met_mahalanobis_sample_var, kde_liver_normal_to_liver_met_refined, kde_liver_normal_to_liver_met_mahalanobis_effective, kde_blood_to_liver_met_mahalanobis, kde_blood_to_liver_met_mean_lfc, kde_blood_to_liver_met_mahalanobis_local_fdr, kde_blood_to_liver_met_is_de, kde_blood_to_liver_met_mahalanobis_sample_var, kde_blood_to_liver_met_refined, kde_blood_to_liver_met_mahalanobis_effective, kde_primary_CRC_to_liver_met_mahalanobis, kde_primary_CRC_to_liver_met_mean_lfc, kde_primary_CRC_to_liver_met_mahalanobis_local_fdr, kde_primary_CRC_to_liver_met_is_de, kde_primary_CRC_to_liver_met_mahalanobis_sample_var, kde_primary_CRC_to_liver_met_refined, kde_primary_CRC_to_liver_met_mahalanobis_effective
- obsm: X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: kompot_de_blood_to_liver_met__blood_smoothed, kompot_de_blood_to_liver_met__liver_met_smoothed, kompot_de_blood_to_liver_met_fold_change, kompot_de_blood_to_liver_met_fold_change_zscores, kompot_de_primary_CRC_to_liver_met__liver_met_smoothed, kompot_de_primary_CRC_to_liver_met__primary_CRC_smoothed, kompot_de_primary_CRC_to_liver_met_fold_change, kompot_de_primary_CRC_to_liver_met_fold_change_zscores, kompot_smooth_all_smoothed, logcounts
- uns: hvg, kompot_da, kompot_de, kompot_de_blood_to_liver_met, kompot_de_layers_blood_to_liver_met, kompot_de_layers_primary_CRC_to_liver_met, kompot_de_primary_CRC_to_liver_met, kompot_de_scores_blood_to_liver_met, kompot_de_scores_primary_CRC_to_liver_met, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, umap

**GSE178318_harmonized.zarr**
- obs (58): patient, site, sample, n_genes_by_counts, total_counts, total_counts_mt, pct_counts_mt, pass_count_bounds, n_genes, doublet_score, predicted_doublet, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, score_Hepatocytes, score_Cholangiocytes, score_LSEC, score_Vascular_endothelial, score_Kupffer_resident_macrophage, score_Monocyte_derived_macrophage_TAM, score_SPP1_TAM, score_TREM2_scar_macrophage, score_cDC1, score_cDC2, score_DC_mreg, score_pDC, score_HSC_fibroblast_CAF, score_T_cell, score_CD4_T, score_CD8_T, score_Treg, score_Exhausted_T, score_Naive_T, score_NK, score_B_cell, score_Plasma, score_Neutrophil, score_Mast, score_Tumor_epithelium_CRC, cell_type, cell_type_original, cnv_score, kompot_da_lfc, kde_blood_to_liver_met__blood_smoothed__score_cytotoxic, kde_blood_to_liver_met__blood_smoothed__score_exhaustion, kde_blood_to_liver_met__blood_smoothed__score_apoptosis, kde_blood_to_liver_met__liver_met_smoothed__score_cytotoxic, kde_blood_to_liver_met__liver_met_smoothed__score_exhaustion, kde_blood_to_liver_met__liver_met_smoothed__score_apoptosis, kde_blood_to_liver_met_fold_change__score_cytotoxic, kde_blood_to_liver_met_fold_change__score_exhaustion, kde_blood_to_liver_met_fold_change__score_apoptosis, kde_blood_to_liver_met_fold_change_zscores__score_cytotoxic, kde_blood_to_liver_met_fold_change_zscores__score_exhaustion, kde_blood_to_liver_met_fold_change_zscores__score_apoptosis
- var (29): ensembl_id, gene_symbol, mt, n_cells_by_counts, mean_counts, pct_dropout_by_counts, total_counts, n_cells, highly_variable, means, dispersions, dispersions_norm, chromosome, start, end, kde_primary_CRC_to_liver_met_mahalanobis, kde_primary_CRC_to_liver_met_mean_lfc, kde_primary_CRC_to_liver_met_mahalanobis_local_fdr, kde_primary_CRC_to_liver_met_is_de, kde_primary_CRC_to_liver_met_mahalanobis_sample_var, kde_primary_CRC_to_liver_met_refined, kde_primary_CRC_to_liver_met_mahalanobis_effective, kde_blood_to_liver_met_mahalanobis, kde_blood_to_liver_met_mean_lfc, kde_blood_to_liver_met_mahalanobis_local_fdr, kde_blood_to_liver_met_is_de, kde_blood_to_liver_met_mahalanobis_sample_var, kde_blood_to_liver_met_refined, kde_blood_to_liver_met_mahalanobis_effective
- obsm: X_cnv, X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_de_blood_to_liver_met__blood_smoothed, kompot_de_blood_to_liver_met__liver_met_smoothed, kompot_de_blood_to_liver_met_fold_change, kompot_de_blood_to_liver_met_fold_change_zscores, kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: cnv, hvg, kompot_da, kompot_de, kompot_de_blood_to_liver_met, kompot_de_layers_blood_to_liver_met, kompot_de_scores_blood_to_liver_met, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, rank_genes_groups, scrublet, umap

**GSE192741_harmonized.zarr**
- obs (23): patient, sample, typeSample, digest, diet, annot_author, cluster_author, n_genes_by_counts, total_counts, total_counts_mt, pct_counts_mt, pass_count_bounds, predicted_doublet, doublet_score, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, cell_type, cell_type_original, kompot_da_lfc
- var (18): gene_symbol, mt, n_cells_by_counts, mean_counts, pct_dropout_by_counts, total_counts, n_cells, highly_variable, means, dispersions, dispersions_norm, kde_Lean_to_Obese_mahalanobis, kde_Lean_to_Obese_mean_lfc, kde_Lean_to_Obese_mahalanobis_local_fdr, kde_Lean_to_Obese_is_de, kde_Lean_to_Obese_mahalanobis_sample_var, kde_Lean_to_Obese_refined, kde_Lean_to_Obese_mahalanobis_effective
- obsm: X_pca, X_pca_harmony, X_umap, X_umap_author
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: cell_type_colors, diet_colors, hvg, kompot_da, kompot_de, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, typeSample_colors, umap

**GSE197177_harmonized.zarr**
- obs (24): sample, patient, site, tissue, n_genes_by_counts, total_counts, total_counts_mt, pct_counts_mt, pass_count_bounds, n_genes, doublet_score, predicted_doublet, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, cell_type, cell_type_original, cnv_score, cnv_high, cell_type_fine, kompot_da_lfc
- var (24): gene_symbol, ensembl_id, mt, n_cells_by_counts, mean_counts, pct_dropout_by_counts, total_counts, n_cells, highly_variable, means, dispersions, dispersions_norm, chromosome, start, end, gene_id, gene_name, kde_primary_PDAC_to_liver_met_mahalanobis, kde_primary_PDAC_to_liver_met_mean_lfc, kde_primary_PDAC_to_liver_met_mahalanobis_local_fdr, kde_primary_PDAC_to_liver_met_is_de, kde_primary_PDAC_to_liver_met_mahalanobis_sample_var, kde_primary_PDAC_to_liver_met_refined, kde_primary_PDAC_to_liver_met_mahalanobis_effective
- obsm: X_cnv, X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: cnv, hvg, kompot_da, kompot_de, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, scrublet, umap

**GSE206552_spatial_mapped_harmonized.zarr**
- obs (32): in_tissue, array_row, array_col, section, gsm, n_genes_by_counts, log1p_n_genes_by_counts, total_counts, log1p_total_counts, total_counts_mt, log1p_total_counts_mt, pct_counts_mt, n_counts, n_genes, section_idx, _indices, _scvi_batch, _scvi_labels, abund_B_cell, abund_CD4_T, abund_CD8_T, abund_HSC_CAF, abund_Mast, abund_Monocyte_macrophage, abund_NK, abund_Naive_T, abund_Plasma, abund_Proliferating, abund_SPP1_TAM, abund_Treg, abund_Malignant_epithelium, abund_pDC
- var (0): 
- obsm: celltype_abundance_q05, means_cell_abundance_w_sf, q05_cell_abundance_w_sf, q95_cell_abundance_w_sf, spatial, stds_cell_abundance_w_sf
- varm: —
- obsp: —
- varp: —
- layers: counts
- uns: _scvi_manager_uuid, _scvi_uuid, mod, spatial

**GSE225857_harmonized.zarr**
- obs (20): patient, organ_code, author_cluster, percent_mt_author, nCount_author, nFeature_author, predicted_doublet, compartment, tissue, _src, sample, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, cell_type, cell_type_original, kompot_da_lfc
- var (13): mt, n_cells, highly_variable, means, dispersions, dispersions_norm, kde_normal_liver_to_liver_met_mahalanobis, kde_normal_liver_to_liver_met_mean_lfc, kde_normal_liver_to_liver_met_mahalanobis_local_fdr, kde_normal_liver_to_liver_met_is_de, kde_normal_liver_to_liver_met_mahalanobis_sample_var, kde_normal_liver_to_liver_met_refined, kde_normal_liver_to_liver_met_mahalanobis_effective
- obsm: X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: hvg, kompot_da, kompot_de, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, umap

**GSE225857_spatial_mapped_harmonized.zarr**
- obs (30): array_row, array_col, section, tissue, gsm, n_genes_by_counts, total_counts, total_counts_mt, pct_counts_mt, _b, _indices, _scvi_batch, _scvi_labels, abund_B_cell, abund_CD4_T, abund_CD8_T, abund_DC, abund_HSC_CAF, abund_LSEC, abund_Mast, abund_Monocyte_macrophage, abund_NK, abund_Plasma, abund_Proliferating, abund_SPP1_TAM, abund_Treg, abund_Malignant_epithelium, abund_Vascular_endothelial, abund_gamma_delta_T, abund_pDC
- var (0): 
- obsm: cell_abundance_q05, means_cell_abundance_w_sf, q05_cell_abundance_w_sf, q95_cell_abundance_w_sf, spatial, stds_cell_abundance_w_sf
- varm: —
- obsp: —
- varp: —
- layers: counts
- uns: _scvi_manager_uuid, _scvi_uuid, c2l_celltypes, mod, spatial

**GSE235863_harmonized.zarr**
- obs (51): sample, tissue, patient, n_genes_by_counts, total_counts, total_counts_rp, pct_counts_rp, total_counts_mt, pct_counts_mt, total_counts_hb, pct_counts_hb, total_counts_hsp, pct_counts_hsp, doublet_scores, predicted_doublets, doublet_info, n_genes, S_score, G2M_score, phase, sub_cluster, major_cluster, UMAP_1, UMAP_2, timepoint, response, recist, author_major, author_sub, pass_count_bounds, doublet_score, predicted_doublet, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, cell_type, exhaustion_score, spp1_score, _spp1, kompot_da_lfc, kde_pre_to_post__pre_smoothed__score_cytotoxic, kde_pre_to_post__pre_smoothed__score_exhaustion, kde_pre_to_post__post_smoothed__score_cytotoxic, kde_pre_to_post__post_smoothed__score_exhaustion, kde_pre_to_post_fold_change__score_cytotoxic, kde_pre_to_post_fold_change__score_exhaustion, kde_pre_to_post_fold_change_zscores__score_cytotoxic, kde_pre_to_post_fold_change_zscores__score_exhaustion
- var (34): gene_ids, feature_types, genome, mt, rp, hb, IG, TCR, CC, hsp, n_cells_by_counts, mean_counts, pct_dropout_by_counts, total_counts, n_cells, exclude, highly_variable, means, dispersions, dispersions_norm, kde_NR_to_R_mahalanobis, kde_NR_to_R_mean_lfc, kde_NR_to_R_mahalanobis_local_fdr, kde_NR_to_R_is_de, kde_NR_to_R_mahalanobis_sample_var, kde_NR_to_R_refined, kde_NR_to_R_mahalanobis_effective, kde_pre_to_post_mahalanobis, kde_pre_to_post_mean_lfc, kde_pre_to_post_mahalanobis_local_fdr, kde_pre_to_post_is_de, kde_pre_to_post_mahalanobis_sample_var, kde_pre_to_post_refined, kde_pre_to_post_mahalanobis_effective
- obsm: X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_de_pre_to_post__post_smoothed, kompot_de_pre_to_post__pre_smoothed, kompot_de_pre_to_post_fold_change, kompot_de_pre_to_post_fold_change_zscores, kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: hvg, kompot_da, kompot_de, kompot_de_layers_pre_to_post, kompot_de_pre_to_post, kompot_de_scores_pre_to_post, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, scrublet, umap

**GSE263733_harmonized.zarr**
- obs (25): patient, origin, author_celltype, sample, site, n_genes_by_counts, total_counts, total_counts_mt, pct_counts_mt, pass_count_bounds, n_genes, doublet_score, predicted_doublet, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, leiden, cell_type, cell_type_original, cnv_score, cnv_high, cell_type_fine, kompot_da_lfc
- var (23): gene_symbol, mt, n_cells_by_counts, mean_counts, pct_dropout_by_counts, total_counts, n_cells, highly_variable, means, dispersions, dispersions_norm, chromosome, start, end, gene_id, gene_name, kde_primary_to_liver_met_mahalanobis, kde_primary_to_liver_met_mean_lfc, kde_primary_to_liver_met_mahalanobis_local_fdr, kde_primary_to_liver_met_is_de, kde_primary_to_liver_met_mahalanobis_sample_var, kde_primary_to_liver_met_refined, kde_primary_to_liver_met_mahalanobis_effective
- obsm: X_cnv, X_pca, X_pca_harmony, X_umap
- varm: PCs
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_smooth_all_smoothed, logcounts, normalized_counts
- uns: cnv, hvg, kompot_da, kompot_de, leiden_r0.4, leiden_r0.6, leiden_r0.8, leiden_r1.0, leiden_r1.2, neighbors, pca, pca_n85, scrublet, umap

**MH1_22-049K4_spatial_annzarro.zarr**
- obs (22): origin, celltype, sample, x_centroid, y_centroid, cell_id, leiden_hires, cluster_celltype, cluster_label, celltype_transfer, kompot_da_Flex_to_Xenium_lfc, kompot_da_Flex_to_Xenium_lfc_zscore, kompot_da_Flex_to_Xenium_neg_log10_lfc_ptp, kompot_da_Flex_to_Xenium_lfc_direction, kompot_da_Flex_log_density, kompot_da_Xenium_log_density, sctx_log_density, sctx_nearest_landmark, sctx_is_start_cell, leiden_res1_0, leiden_res0_5, leiden_res0_25
- var (5): panel, kompot_de_Flex_to_Xenium_mahalanobis, kompot_de_Flex_to_Xenium_mean_lfc, kompot_de_Flex_to_Xenium_mahalanobis_local_fdr, kompot_de_Flex_to_Xenium_is_de
- obsm: DM_EigenVectors, X_context_slices, X_pca_harmony, X_umap, X_umap_3d, spatial
- varm: —
- obsp: context_diff_ls1, context_diff_ls10, context_diff_ls3, context_fn_ls1, context_fn_ls10, context_fn_ls3, dist_context_rows, dist_diffmap, dist_spatial
- varp: gene_corr_pearson_lognorm, gene_corr_spearman_lognorm, gene_cosine_lognorm
- layers: X_within, X_within_shared, counts, kompot_de_Flex_smoothed, kompot_de_Xenium_smoothed, kompot_de_fold_change, kompot_imputed_crossassay
- uns: DM_EigenValues, better_embedding, imputed_crossassay_genes, kompot_augmented, kompot_da, kompot_da_Flex_to_Xenium_lfc_direction_colors, kompot_de_genes, kompot_de_smoothed_note, kompot_smooth, leiden_hires, leiden_hires_colors, leiden_res0_25_colors, leiden_res0_5_colors, leiden_res1_0_colors, neighbors, norm_chosen_name, panel_sizes, pipeline, sample, smF, smX, spatial_context

**healthy_liver_atlas_snRNA_harmonized.zarr**
- obs (21): sample, batch, n_genes_by_counts, log1p_n_genes_by_counts, total_counts, log1p_total_counts, pct_counts_in_top_50_genes, pct_counts_in_top_100_genes, pct_counts_in_top_200_genes, pct_counts_in_top_500_genes, total_umis_manual, log_total_counts, total_counts_mt, pct_counts_mt, total_counts_ribo, pct_counts_ribo, leiden, cluster_annotations, zones, cell_type, zone
- var (16): gene_ids, feature_types, n_cells_by_counts, mean_counts, log1p_mean_counts, pct_dropout_by_counts, total_counts, log1p_total_counts, mt, ribo, highly_variable, means, dispersions, dispersions_norm, mean, std
- obsm: X_pca, X_pca_harmony, X_umap
- varm: —
- obsp: —
- varp: —
- layers: counts, logcounts
- uns: cluster_annotations_colors, dolimap_provenance, log1p, sample_colors

**healthy_liver_atlas_visiumHD_harmonized.zarr**
- obs (82): Image, Object type, Classification, Parent, ROI, cell_x_um, cell_y_um, nuc_area_um2, Nucleus: Length µm, Nucleus: Circularity, Nucleus: Solidity, Nucleus: Max diameter µm, Nucleus: Min diameter µm, cell_area_um2, Cell: Length µm, Cell: Circularity, Cell: Solidity, Cell: Max diameter µm, Cell: Min diameter µm, Nucleus/Cell area ratio, cell_number_spots, nuc_number_spots, ROI: 2.00 µm per pixel: Hematoxylin: Mean, ROI: 2.00 µm per pixel: Hematoxylin: Std.dev., ROI: 2.00 µm per pixel: Hematoxylin: Min, ROI: 2.00 µm per pixel: Hematoxylin: Max, ROI: 2.00 µm per pixel: Hematoxylin: Median, ROI: 2.00 µm per pixel: Eosin: Mean, ROI: 2.00 µm per pixel: Eosin: Std.dev., ROI: 2.00 µm per pixel: Eosin: Min, ROI: 2.00 µm per pixel: Eosin: Max, ROI: 2.00 µm per pixel: Eosin: Median, Smoothed: 25 µm: Nucleus: Area µm^2, Smoothed: 25 µm: Nucleus: Length µm, Smoothed: 25 µm: Nucleus: Circularity, Smoothed: 25 µm: Nucleus: Solidity, Smoothed: 25 µm: Nucleus: Max diameter µm, Smoothed: 25 µm: Nucleus: Min diameter µm, Smoothed: 25 µm: Cell: Area µm^2, Smoothed: 25 µm: Cell: Length µm, Smoothed: 25 µm: Cell: Circularity, Smoothed: 25 µm: Cell: Solidity, Smoothed: 25 µm: Cell: Max diameter µm, Smoothed: 25 µm: Cell: Min diameter µm, Smoothed: 25 µm: Nucleus/Cell area ratio, Smoothed: 25 µm: nSpots, Smoothed: 25 µm: nNucSpots, Smoothed: 25 µm: ROI: 2.00 µm per pixel: Hematoxylin: Mean, Smoothed: 25 µm: ROI: 2.00 µm per pixel: Hematoxylin: Std.dev., Smoothed: 25 µm: ROI: 2.00 µm per pixel: Hematoxylin: Min, Smoothed: 25 µm: ROI: 2.00 µm per pixel: Hematoxylin: Max, Smoothed: 25 µm: ROI: 2.00 µm per pixel: Hematoxylin: Median, Smoothed: 25 µm: ROI: 2.00 µm per pixel: Eosin: Mean, Smoothed: 25 µm: ROI: 2.00 µm per pixel: Eosin: Std.dev., Smoothed: 25 µm: ROI: 2.00 µm per pixel: Eosin: Min, Smoothed: 25 µm: ROI: 2.00 µm per pixel: Eosin: Max, Smoothed: 25 µm: ROI: 2.00 µm per pixel: Eosin: Median, Smoothed: 25 µm: Nearby detection counts, array_row, array_col, cx, cy, in_cell, in_nucleus, sample_id, total_umi, n_genes_by_counts, log1p_n_genes_by_counts, total_counts, log1p_total_counts, pct_counts_in_top_50_genes, pct_counts_in_top_100_genes, pct_counts_in_top_200_genes, pct_counts_in_top_500_genes, log10_total_counts, Classification_binary, AR_ratio, leiden, log_total_umi, cluster_annotations, cell_type, sample
- var (10): n_cells_by_counts, mean_counts, log1p_mean_counts, pct_dropout_by_counts, total_counts, log1p_total_counts, highly_variable, means, dispersions, dispersions_norm
- obsm: X_pca_harmony, X_pca_raw, X_umap, spatial
- varm: —
- obsp: —
- varp: —
- layers: counts, logcounts
- uns: Classification_colors, cluster_annotations_colors, dolimap_provenance, log1p, sample_id_colors

**atlas-1.17M-raw.zarr**
- obs (8): dataset, accession, patient, sample, site_role, cohort, cell_type, cell_type_original
- var (0): 
- obsm: —
- varm: —
- obsp: —
- varp: —
- layers: counts, lognorm
- uns: log1p

**atlas-1.17M-scvi.zarr**
- obs (10): dataset, accession, patient, sample, site_role, cohort, cell_type, cell_type_original, C_scANVI, kompot_da_lfc
- var (6): highly_variable, highly_variable_rank, means, variances, variances_norm, highly_variable_nbatches
- obsm: DM_EigenVectors, X_diffmap, X_scANVI, X_scVI, X_umap
- varm: —
- obsp: connectivities, distances
- varp: —
- layers: counts, kompot_smooth_all_smoothed, lognorm
- uns: diffmap_evals, hvg, kompot_da, log1p, neighbors, umap

**atlas-scPLM.zarr**
- obs (20): 10.Sample_accession, nCount_RNA, nFeature_RNA, percent.mt, nGene, nUMI, nCount_SCT, nFeature_SCT, 02.Minor_cell_types, 01.Major_cell_types, 03.Minor_cell_subtypes, 07.Patient_stages, 09.Study_accession, 08.Patient_tissues, 04.Minor_cell_subtypes_ID, 05.Cell_stages, 06.Patient_ID, 00.Cancer_types, cell_type, kompot_da_lfc
- var (0): 
- obsm: X_umap
- varm: —
- obsp: —
- varp: —
- layers: kompot_smooth_all_smoothed, logcounts
- uns: kompot_da

