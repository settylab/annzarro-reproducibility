# AnnZarro performance benchmark

Measures what one user interaction in AnnZarro costs (payload bytes, latency,
server memory) as datasets grow, how chunk shape and sparse layout change that
cost, and where the time goes. Results and their interpretation are in
[FINDINGS.md](FINDINGS.md).

## Contents

| File | Purpose |
| --- | --- |
| `generate_data.py` | Writes the synthetic zarr v2 stores to `../data/bench/` (gitignored) and records them in `../data/bench/manifest.json` |
| `run_benchmark.py` | Starts AnnZarro servers on localhost, issues HTTP requests, records latency, bytes and server RSS to `results/<experiment>.csv` |
| `sweep_1m.sh` | Chunk-shape sweep at 1,000,000 cells: generates, measures and deletes one ~18 GB store at a time |
| `make_plots.py` | Reads `results/*.csv`, writes `plots/*.pdf`, `plots/*.png`, `results/memory_summary.csv` and `results/chunk_read_volume.csv` |
| `results/environment.json` | Hardware, OS, package versions, AnnZarro commit |

## Rerunning

Use the paper repository's environment (AnnZarro installed editable,
anndata 0.12, zarr 3.1). Everything is seeded (`--seed`, default 20261001).

```bash
PY=../.venv/bin/python
$PY generate_data.py check                 # confirms anndata's default chunking
$PY generate_data.py sweep                 # 11 chunk shapes at 100k x 5k (~19 GB)
$PY run_benchmark.py sweep --fresh
./sweep_1m.sh default c1024x1024 c4096x256 c1024x64 c4096x16 c16384x16 c2048x32 c256x4096 cNx64
$PY generate_data.py scale --chunks c2048x32   # 10k-1M cells (~25 GB)
$PY generate_data.py sparse                # CSR + CSC at 100k and 1M x 20k (~5 GB; 1M takes ~2.5 h)
$PY run_benchmark.py scale --fresh
$PY run_benchmark.py sparse --fresh
$PY run_benchmark.py breakdown
$PY run_benchmark.py env
$PY make_plots.py
```

Do not run generation and measurement at the same time: both are CPU and disk
bound. Measurement takes about 1.5 h on a 16-core M3 Max; generating the 1M
sparse matrix adds ~2.5 h. Peak disk use is ~70 GB (the 1M sweep stores are
deleted after use). After the published run the 1M and 300k stores were
deleted; regenerate them to rerun.

Dense pairwise matrices (obsp, varp) are not measured here: the HPC benchmark
(`benchmark/hpc/`, branch `dominik/hpc-bench`) covers them on real data up to
200k cells and 30k genes. `generate_data.py obsp|varp` and
`run_benchmark.py obsp|varp` still work if a laptop number is wanted.

The server is started as `python -m annzarro.server --data-dir <dir> --port <free port>`
with `ANNZARRO_HEADLESS=1`, i.e. Flask's threaded werkzeug server with
AnnZarro's default configuration (debug off, result cache 1000 MB), bound to
127.0.0.1. This is the same Flask app and `app.run` call that
`annzarro start` uses. (`annzarro start` itself only finds its YAML defaults
when launched from the AnnZarro source directory; see FINDINGS.md.)

## Measurement conditions

| `condition` | Meaning |
| --- | --- |
| `cold` | First request to a freshly started server process, against a fresh APFS clone (`cp -c`) of the store. A clone is a new file system object, so none of its pages are in the macOS buffer cache and chunks come from the SSD. One sample per process; `--reps` (default 5) processes, each with a new random index |
| `cold_new` | The next `--cold-new` (default 3) requests on that cold process and clone, each for a new random index. Process warm, data mostly uncached |
| `warmup` | First request of the warm phase (discarded in summaries) |
| `warm_new` | Original store after every file was read once (page cache warm); `--warm` (default 10) requests, each for a new random index |
| `warm_repeat` | The warm-up index requested again `--warm` times. Served from AnnZarro's result cache for obs, obsm, obsp and varp; re-read for X and layers, which are never cached |

`cold` cannot drop the page cache of the original files (`purge` needs root);
the clone approach is the substitute. It removes OS caching but not SSD
controller caches, and an Apple NVMe SSD (several GB/s) is much faster than
network file systems typical of HPC, so cold numbers are a lower bound for a
cluster deployment.

## CSV columns

### `results/{scale,sweep,obsp,varp,sparse}.csv` (one row per HTTP request)

| Column | Meaning |
| --- | --- |
| `experiment` | `scale`, `sweep`, `obsp`, `varp` or `sparse` |
| `store` | Store path relative to `data/bench/` |
| `family` | Dataset family from `generate_data.py` |
| `n_cells`, `n_genes` | Matrix dimensions of the store (`obsp`: n_genes = 100; `varp`: n_cells = 100) |
| `matrix` | Array the request reads, e.g. `layers/fc`, `obsp/kernel_c1024x1024`, `X` |
| `layout` | `dense`, or `csr`/`csc` for sparse X |
| `chunk_tag` | Chunking recipe: `default` (zarr/anndata choice), `c<h>x<w>` (`N` = whole axis), or the sparse layout |
| `chunks` | Actual chunk shape `h x w` read from the array (sparse X: chunk length of the 1-D `data` array) |
| `interaction` | `layer_gene` (one gene column of a dense layer, `cols=j`), `layer_cell` (one cell row, `rows=i`), `obsm_col` (one column of `obsm/X_umap`), `obs_col` (`obs/score`, float32), `obsp_knn_row` (row of the sparse 15-NN graph), `obsp_row`/`varp_row` (row of a dense pairwise matrix), `X_gene`/`X_cell` (column/row of sparse X), `open_structure` (`/data/dataset_structure`), `open_cells` (`/data/cells`, all cell names) |
| `condition` | See table above |
| `rep` | Cold repetition (fresh process + clone); 0 for warm conditions |
| `seq` | Position of the request within its process/condition |
| `index` | Gene or cell index requested |
| `status` | HTTP status (all 200 in the published results) |
| `bytes` | Response body size in bytes (JSON, uncompressed: the server sends no gzip) |
| `n_values` | Number of scalar values in the payload |
| `latency_s` | Wall time from sending the request to having the full body, client side, seconds |
| `rss_base_bytes` | Server RSS right after startup, before any data request |
| `rss_peak_bytes` | Peak server RSS while this request was served (psutil, sampled every 2 ms) |
| `server_pid` | PID of the server process that served the request |
| `timestamp` | Unix time |

### `results/breakdown.csv` (warm, in-process vs HTTP)

| Column | Meaning |
| --- | --- |
| `store`, `n_cells`, `n_genes`, `chunks`, `interaction`, `rep`, `index` | As above |
| `t_open_s` | `zarr.open_group` on the store (AnnZarro re-opens the store on every request; included in `t_read_s`) |
| `t_read_s` | AnnZarro's own reader method (`ZarrReader.get_layer` / `get_X` / `get_obsm_varm` / `get_obsp_varp`, cache disabled): open, chunk reads, decompression, sparse densification |
| `t_tolist_s` | `ndarray.tolist()` as done in `annzarro/core/process_file.py` |
| `t_jsonify_s` | `flask.jsonify(...)` of that list, i.e. JSON encoding to bytes |
| `t_http_s` | Latency of the same request through the running server (client side) |
| `bytes` | JSON body size |

The remainder `t_http_s - t_read_s - t_tolist_s - t_jsonify_s` is werkzeug
request handling, socket transfer and the client's receipt of the body.

### `results/chunk_read_volume.csv` (derived, analytic)

Per sweep chunk shape: `chunk_bytes` (uncompressed bytes per chunk),
`chunks_per_gene` / `bytes_per_gene` (chunks and uncompressed bytes one gene
column must decompress), `chunks_per_cell` / `bytes_per_cell` (same for one
cell row).

### `results/memory_summary.csv` (derived by `make_plots.py`)

Per store and interaction: `full` = size of the matrix if held in memory
uncompressed (dense: n x m x 4 B; sparse: nnz x 8 B + indptr), `peak` = max
server RSS over the cold phases (one fresh server per interaction), `base` = idle RSS, `delta` = max(peak - base).
