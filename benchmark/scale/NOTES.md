# How far AnnZarro scales: Tahoe-100M

How many cells AnnZarro serves interactively, measured on a laptop with nested subsets of
Tahoe-100M and synthetic stores beyond it. The paper cites AnnZarro v0.4.1
(below, "Results (v0.4.1)"); a series not yet rerun on v0.4.1 says so in its heading. Earlier
series (v0.4.0, v0.3.0, release-0.3, the pre-#62/#63 baseline) are in `HISTORY.md`; they are superseded and not cited by the paper.
Results are in `results/`, the summary tables come from `summarize.py`, and the figure
is drawn by `../../figures/fig_scale.py` (`manuscript/figures/fig_scale.{pdf,png}`).

## Large-plot threshold

Large-plot mode starts above 1,000,000 points (`ui.defaults.large_plot_points`, default 1000000): at that size
several plots with hover and click fit in memory side by side (400-900 B of browser heap per point).

## Data

- **Tahoe-100M** (Tahoe Therapeutics with the Arc Institute; Zhang et al.,
  bioRxiv 2025, doi:10.1101/2025.02.20.639398). Taken from the Hugging Face
  release `tahoebio/Tahoe-100M` (dataset card licence **CC0-1.0**, last
  modified 2025-07-23): 3,388 parquet shards, 95,624,334 cells, 62,710 genes,
  raw UMI counts. Checked 2026-10-02.
- The per-plate h5ad files on Google Cloud Storage (`gs://arc-ctc-tahoe100/`)
  were not used. Anonymous listing and object reads of that bucket returned
  401/403 on 2026-10-02, while the Hugging Face release is public.
- Everything is **real data**. There is no synthetic scale-up. The laptop used
  shards 0-1771 (the first 50,000,000 cells).

## Stores (`build_tahoe.py`)

The stores are nested: the store with N cells holds the first N cells in shard
order, so every store is a prefix of every larger one. The 1M-10M stores were
cut from a 10M master and the 20M and 50M stores from a 50M master. The two
masters were checked to agree on the shared prefix (indptr, indices, data,
names, embedding). The layout follows the paper's Procedure (Steps 8-10):

| element | content |
| --- | --- |
| `X` | CSC float32 counts (a gene column is one contiguous slice) |
| `layers/counts_csr` | the same counts as CSR (a cell row is one contiguous slice); its chunk files are hard links into the master CSR, so it costs no extra disk |
| `obs` | sample, plate, cell_line_id, drug, moa_fine (categorical), n_genes, total_counts; index BARCODE_SUB_LIB_ID |
| `var` | index gene_symbol, column ensembl_id |
| `obsm/X_pca_2d` | PCs 1-2 (see below) |

Storage settings:

- zarr format 2, Blosc-zstd level 3 (shuffle for values, bitshuffle for
  indices), 1-D chunks of 2^21 values, consolidated metadata.
- 1.44-1.50 billion stored values per million cells.
- On disk: the CSC takes 1.6 GB (1M) to 91 GB (50M); the master CSR for 50M
  cells takes 107 GB.
- Every store passed `build_tahoe.py check`: CSC gene columns are compared
  with the CSR, CSR rows with the master, and stores up to 2M are read with
  anndata.

**Embedding.** Tahoe-100M ships no UMAP, so the stores carry a PCA projection instead:

1. Fit cells: every 5th cell of shards 0-35 (203,220 cells).
2. Normalise counts to 10,000 per cell, then log1p.
3. Keep the 2,000 genes of highest variance and centre them.
4. Compute 50 components by randomized SVD (seed 0).
5. Project every cell exactly (the map is linear) and store PCs 1-2.

It only supplies coordinates to draw. PCs 1-2 explain 2.0% and 1.6% of the
variance of the fitted cells.

**Build cost on the laptop** (`results/builds_laptop.csv`):

- 50M master: 23 min at 24 GB peak RSS.
- Stores: 21 s (1M), 4 min (10M), 11 min (20M) and 2.2 h (50M).
- The CSC builder keeps at most 35% of RAM in values per pass (peak RSS
  31-62 GB). One pass of the 50M build ran for 1.7 h under memory pressure
  from other jobs; each of the other 12 passes took about 2.3 min.

## Server per click (`bench_http.py`, method)

Each repetition has two sessions, each on a fresh process and a freshly
cloned store, so neither warms the other's caches:

- `_sub` is the default 100,000-cell subset, as the client opens any
  dataset over 200,000 cells.
- `_all` has the subset off.

Each session runs these steps in order:

1. Replay the requests the client sends to open a dataset (`open_*`), in the client's order.
2. Make each click once (`cold`).
3. Repeat it twice (`warm`). AnnZarro's result cache can answer these.
4. Click other genes or cells (`warm_new`).
5. Make 8 concurrent gene-column requests (`burst8`).

Numeric clicks use `format=f32`. Latency is client-side time to the last byte
over 127.0.0.1. RSS is that of the server process tree, sampled every 5 ms. A
click slower than 120 s is recorded once and not repeated; this applies to the
CSC cell-row scan at 50M.

## Results (v0.4.1)

### Conditions

- **Code under test.** AnnZarro 0.4.1, the tag v0.4.1 itself (78c9da6, tree 661a454f), built by
  `ceiling/setup_build.sh 78c9da6 v041-bench`; `results/v041_build.json`. Every run's environment
  record is in `results/browser_v041_environment.json`, `browser_v041_ceiling_environment.json` and
  `http_v041_environment.json`.
- **Stores.** Real Tahoe-100M throughout below 95.6M: `tahoe_panel_95.6M_plot.zarr`, all
  95,624,334 cells, 200 panel genes in a CSC `X`, `obsm/X_umap`, obs incl.
  `cell_line_id` (50 categories) and `total_counts`, and its first-N-cell prefixes at 1M, 2M, 5M, 10M, 20M
  and 50M (`ceiling/cut_prefix.py`).
- **Laptop.** Apple M3 Max (16 cores), 128 GB RAM, internal APFS SSD, macOS 26.5. Two idle AnnZarro servers of
  earlier sessions (about 2.2 GiB resident together) stayed up through steps 1 and 2; they served
  nothing (`results/ps_v041.txt`).
- **Browser.** Chromium 153.0.8010.12 (Playwright bundled), new headless mode, WebGL on the
  GPU (ANGLE Metal), viewport 1400 x 1000 (`ceiling.py`); the only flag is
  `--enable-precise-memory-info`.
- **Runs.** `ceiling/queue_v041.sh step1`: one store, colour and rep per `run-timed` call (exclusive
  bench lock), `ps` inside it (`results/ps_v041.txt`), 30 s between holds until 2026-10-07 21:17Z and
  5 s after. Seven rungs whose `ps` showed another process's headless browser were set aside
  (`results/excluded/browser_v041_overlapped.jsonl`) and rerun.
- **View.** One Cell Plot on `X_umap` at the app's automatic point size and opacity (they
  follow the number of points drawn), except `conf95_v041` (point size 1, opacity 0.2).
  Colour is gene FN1 (`gene`) or `cell_line_id` (`cat`).
- **Tags.** `all_v041` every cell, `sub_v041` the default 100,000-cell subset, `ceil_v041` and `guard175_v041` beyond 95.6M (synthetic),
  `conf95_v041` / `conf95auto_v041` cold confirmations at 95.6M, `endpoint_v041` the recolour
  end-point check (passed).
- **Recolour time** ends at the later of the data change and the last Plotly draw
  (`seconds_drawn`); the data-based end is kept as `seconds_data`.
- **Bytes per click.** f32 vectors are 4 bytes per cell. Categorical codes are 1 byte per cell
  (`categorical=codes`).
- **Tables.** `summarize_rerun.py` writes `results/browser_v041_events.csv`,
  `browser_v041_summary.csv` and `http_v041_summary.csv` (server per click, `ceiling/queue_v041.sh http`).

### Browser, every cell (seconds, median (min-max) of 3 cold reps; tag `all_v041`)

| |1M|2M|5M|10M|20M|50M|95.6M|
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| first plot, gene |2.68 (2.65-2.76)|0.87 (0.85-0.88)|1.09 (1.04-1.12)|1.31 (1.31-1.41)|1.89 (1.87-1.89)|3.45 (3.35-3.49)|6.13 (6.13-7.13)|
| first plot, category |1.15 (1.14-1.21)|0.79 (0.78-0.83)|0.99 (0.95-1.01)|1.33 (1.32-1.43)|1.93 (1.72-1.99)|3.22 (3.18-3.24)|5.22 (5.21-5.32)|
| recolour, gene |0.79 (0.73-0.80)|0.24 (0.21-0.29)|0.40 (0.39-0.43)|0.66 (0.62-0.73)|1.21 (1.16-1.34)|2.95 (2.76-3.12)|5.68 (5.54-7.05)|
| zoom |0.03 (0.01-0.03)|0.03 (0.02-0.03)|0.04 (0.04-0.06)|0.08 (0.07-0.16)|0.15 (0.14-0.30)|0.43 (0.35-0.98)|0.78 (0.65-1.61)|
| drag pan |0.08 (0.05-0.13)|0.05 (0.04-0.08)|0.08 (0.04-0.13)|0.18 (0.10-0.36)|0.34 (0.16-0.61)|1.24 (0.77-2.20)|2.42 (1.56-3.16)|

### Browser, default 100,000-cell subset (seconds, median (min-max) of 3 cold reps; tag `sub_v041`)

| |1M|2M|5M|10M|20M|50M|95.6M|
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| open, first plot (gene) |0.86 (0.85-0.93)|0.92 (0.91-0.93)|1.11 (1.07-1.12)|1.25 (1.21-1.27)|1.51 (1.50-1.56)|2.54 (2.46-2.57)|4.03 (4.02-4.04)|
| open, first plot (category) |0.70 (0.69-0.73)|0.77 (0.76-0.77)|0.88 (0.88-0.89)|1.06 (1.05-1.07)|1.41 (1.32-1.42)|2.27 (2.25-2.28)|3.79 (3.79-3.81)|
| recolour, gene |0.20 (0.14-0.20)|0.23 (0.15-0.24)|0.15 (0.14-0.23)|0.17 (0.14-0.23)|0.24 (0.18-0.31)|0.31 (0.30-0.32)|0.46 (0.39-0.49)|
| next part |0.24 (0.20-0.30)|0.27 (0.23-0.29)|0.31 (0.29-0.35)|0.42 (0.37-0.53)|0.58 (0.56-0.92)|1.21 (1.05-1.81)|2.79 (1.94-3.28)|
| balanced subset |0.77 (0.74-0.80)|0.82 (0.78-0.85)|0.83 (0.82-0.85)|0.96 (0.96-0.99)|1.24 (1.20-1.25)|1.95 (1.92-1.98)|3.26 (3.18-3.31)|

### Ceiling for drawing every cell (synthetic stores beyond 95.6M)

**Stores.** Synthetic, from `ceiling/build_stores.py`: obs `cell_type` with 50 categories,
`X_umap` drawn as 50 Gaussian blobs and 4 float genes; larger stores are hard-linked prefixes
of a master. The memory guard's ceiling at default settings is ceiling-benchmarker's
(`benchmark/tool_ceiling/ceilings.csv`, annzarro/v041).

## Reproduce

```bash
SCRATCH=/path/to/scratch SITE=laptop SIZES="1000000 2000000 5000000 10000000 20000000 50000000" \
  MAX_CELLS=50000000 SHARDS=1772 benchmark/scale/run_site.sh all
python benchmark/scale/summarize.py      # tables, results/summary.csv
python figures/fig_scale.py              # manuscript/figures/fig_scale.{pdf,png}
```

The laptop runs used the same scripts step by step. The 50M master was built
with `--delete-consumed` to stay under the disk budget. Peak disk use was
about 220 GB. The stores were deleted after the runs; the 50M master CSR (107 GB) is kept in `~/tahoe_scale/work50` for reruns (any store rebuilds from it in minutes to hours).

## HPC on v0.4.1

The HPC worker ran the HPC series on AnnZarro v0.4.1 (tag 78c9da6) on whole exclusive Fred Hutch nodes
(Xeon Gold 6254, 36 CPUs, 755 GiB), stores on `$SCRATCH` (an NFSv4.1 scratch filer), node-cold: a
fresh server and the node's page cache evicted before each cold request. Results, each copy checked
against its MANIFEST sha256, are in `results/hpc/full/`:

- `j5_v041/`: J5 (HPC job), the Tahoe-100M per-click ladder of this page at 1M to 95.6M cells.
- `t_v041_hpctemp_reduced/`: T (HPC job), the public HPC set on `$SCRATCH`: dense Tahoe-100M
  layers in several chunk shapes (`grid`), dense pairwise matrices up to 200,000 x 200,000
  (`pairwise_public`), and the node environment.
- `t2_v041_hpctemp_extra/`: T2 (HPC job), the cases T did not cover: kernels and distances at
  50,000 to 200,000 cells, a 20,000-gene correlation row and a 1.17-million-cell Tahoe-100M prefix.
- `hpc_v041_case_map.tsv` maps every paper claim to its case, file and statistic (medians over a
  case's cold rows). Run J4 (node-local NVMe) is kept with them but is not a claim source.

The evidence site's HPC page shows J5, T and T2; Fig. 9 plots the T and T2 series.

## HPC gene-panel series (done 2026-10-03)

Hand-off `20261003T012048Z-...-tahoe-handoff` (plus addendum, slim-copy and
subset-check follow-ups). Nested panel stores of every cell of Tahoe-100M with
a UMAP, built on the Fred Hutch HPC by `build_tahoe.py obs | refit | master
--n-pcs 50 | panel | panel-master | store --genes | plot-copy` and
`umap_tahoe.py sample | fit | place | validate | write`. The details, the
numbers and the deviations from the request are in `results/hpc/README.md`.

- **PCA:** refit on 999,073 cells stratified over plate × cell line (≤1,430 per stratum, seed 0). The old plate-4 basis is not used.
- **Genes:** 5,000 = the top 5,000 by variance on that sample. MALAT1 and every prefix's 2,008 most-detected genes fall inside it. Stored values kept per cell: median 0.753.
- **Stores:** 1M, 2M, 5M, 10M, 20M, 50M and 95,624,334 cells (2.7 GB to 294 GB with the panel `counts_csr`). Each has `X` (CSC), `layers/counts_csr` (panel CSR, not all genes: a full-gene layer would not match `X`), `obsm/X_pca` (50), `obsm/X_pca_2d` (PCs 1-2 of the refit, NOT the plate-4 basis of the laptop stores) and `obsm/X_umap`. There is also a 16 GB slim 95.6M plot copy (200 genes with values, no layers).
- **UMAP:** one island per cell line, plates nearly mixed within islands. Cell-line purity 0.948; same-plate 15-NN fraction 0.093 vs 0.079 if mixed. Placement recall@15 0.997 (faiss IVF4096, nprobe 32).
