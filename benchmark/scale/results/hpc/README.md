# Tahoe-100M gene-panel stores on the HPC (2026-10-02/03)

Nested AnnZarro stores of every cell of Tahoe-100M (95,624,334 cells), with a 5,000-gene panel, 50 PCs and a UMAP, built on the Fred Hutch HPC (Slurm, `$SCRATCH` NFS scratch). Subset-stability checks run against annzarro 0.2.0.

- **Requests:** hand-off `20261003T012048Z`, addendum `20261003T012154Z`, slim copy `20261003T065051Z`, subset checks `20261003T035446Z` (the HPC worker request channel).
- **Code:**
  - the build and UMAP code as run is commit `09496f7` (base `be36092`);
  - `bench_subset.py` from `fc5eaab`;
  - the slim-copy rule follows `store --panel` at `f5c01b7`.
- **Package under test:** annzarro 0.2.0 from PyPI.
- **Environment:** `environment_hpc_build.json`, `venv_panel.freeze.txt`, `subset_hpc_environment.json`.

## Pipeline and cost (`builds_hpc.csv`, from sacct)

| step | job | node (cores) | wall | peak RSS |
|---|---|---|---|---|
| download: 3,388 shards, 315 GB, plus metadata | 10000196 | hpc-node-42 (8) | 22 min | 0.2 GB |
| A1: `build_tahoe.py obs`; `umap_tahoe.py sample`; `build_tahoe.py refit` | 10000646 | hpc-node-02 (16) | 19 min | 38.6 GB |
| A2: `master --n-pcs 50 --detect-at …` (8,378 s); `panel`; `panel-master` (3,736 s) | 10000650 | hpc-node-02 (16) | 3 h 27 min | 45.1 GB |
| B: `store --genes` + `check`, 1M..95.6M | 10000651 | hpc-node-02 (16) | 3 h 46 min | 265 GB |
| C: `umap_tahoe.py fit` (1,339 s); `place` (1,859 s); `validate` | 10000652 | hpc-node-45 (24) | 1 h 09 min | 30.9 GB |
| D: `umap_tahoe.py write` × 7 | 10000653 | hpc-node-03 (4) | 3 min | 0.1 GB |
| F: `build_tahoe.py plot-copy` (slim 95.6M) | 10008693 | hpc-node-33 (4) | 9 min | 2.9 GB |
| E: `bench_subset.py --verify`, 7 stores | 10008694 | hpc-node-21 (8) | 1 h 48 min | 20.1 GB |

No node was exclusive; the lab QOS was near its 800-CPU cap. B ran with `--mem-entries 3e10`: the 50M store took 2 CSC passes and 95.6M took 4.

## Data and sample

- **Download check** (`download_check.json`): all 3,388 parquet footers read, 95,624,334 rows in total, 28,224-28,225 rows per shard.
- **Obs:** read from the shards in store order (`obs`). `metadata/obs_metadata.parquet` has 100,648,790 rows (cells failing the filter included), no `cell_line_id` and no `moa-fine`, so it was not used.
- **Reference sample** (`umap/sample.json`, `umap/ref_strata.csv`): up to 1,430 cells per plate × cell_line_id stratum, seed 0. 999,073 cells from 700 strata (14 plates × 50 lines). 10 strata are below 1,430, all CVCL_1571 (972-1,404 cells). Every plate contributes 71,042-71,500 cells.

## PCA and gene panel

- **Refit** (`refit.json`, `pca_fit.npz`): 1e4 normalisation, log1p, top 2,000 HVGs by variance on the reference sample, centred, 50 PCs (randomized SVD, seed 0). PC1-5 explain 2.35 / 1.64 / 1.19 / 1.07 / 0.86%; the 50 PCs 17.0%. Every cell is projected exactly (`master_done.json`: 139,624,620,220 stored values).
- **Panel** (`../../genes_panel.txt`, `panel.json`): 5,000 genes = the top 5,000 by the same variance. MALAT1 and the 2,008 most-detected genes of every prefix (1M..all) already fall inside it: 2,871 genes are hvg only, 2,128 hvg + detected, MALAT1 hvg + extra + detected. So the gene picks of `bench_http.py` / `bench_browser.py` (detection rank ≤ 2,007) are the same as in full-gene stores.
- **Stored values kept per cell:**

  | set | median | mean | p05 | p95 |
  |---|---|---|---|---|
  | all cells (`panel_master_done.json`) | 0.7535 | 0.7523 | 0.683 | 0.816 |
  | reference sample | 0.7529 | 0.7516 | | |

  Pooled over all cells: 0.7404. UMI kept per cell on the reference sample: median 0.817.

## Stores (`stores/`)

Paths are under `$SCRATCH/annzarro-scale/stores_panel/`; `stores/store_sizes.tsv` has the exact bytes and file counts, and the `*.build.json` files sit beside the stores.

| store | cells | bytes (`du -sb`) | of which counts_csr | build s |
|---|---|---|---|---|
| n1M/tahoe_panel_1M.zarr | 1,000,000 | 2,713,609,433 | 1,278,897,977 | 135 |
| n2M/tahoe_panel_2M.zarr | 2,000,000 | 5,576,368,147 | 2,632,714,474 | 169 |
| n5M/tahoe_panel_5M.zarr | 5,000,000 | 15,106,865,000 | 7,168,332,108 | 331 |
| n10M/tahoe_panel_10M.zarr | 10,000,000 | 30,277,401,694 | 14,366,551,920 | 613 |
| n20M/tahoe_panel_20M.zarr | 20,000,000 | 62,749,176,298 | 29,815,876,749 | 1,259 |
| n50M/tahoe_panel_50M.zarr | 50,000,000 | 152,809,815,359 | 72,557,971,602 | 3,026 |
| n95.6M/tahoe_panel_95.6M.zarr | 95,624,334 | 294,428,670,848 | 139,901,650,884 | 7,312 |
| n95.6M_plot/tahoe_panel_95.6M_plot.zarr (slim) | 95,624,334 | 15,968,692,462 | none | 476 |

**Layout of every full store:**
- X: CSC float32 over the 5,000 panel genes, 2^21-value 1-D chunks;
- layers/counts_csr: panel CSR, hard links into the panel master;
- obs: sample, plate, cell_line_id, drug, moa_fine, n_genes, total_counts;
- var: gene_symbol index, ensembl_id;
- obsm/X_pca: 50 PCs, chunks 2^20 × 50;
- obsm/X_pca_2d: PCs 1-2 of the REFIT basis (the stratified sample), identical to the first two columns of X_pca. This is NOT the plate-4 basis of the laptop's older stores, so X_pca_2d is not comparable across the two series;
- obsm/X_umap: chunks 2^20 × 2;
- zarr v2, Blosc-zstd 3, consolidated.

**The slim copy:** obs, var, obsm/X_umap and X_pca_2d, and an X with values for 200 genes only (`stores/tahoe_panel_95.6M_plot.zarr.panel.tsv`): 14 benchmark genes, then panel genes by variance on the reference sample. No layers. sha256 of X_umap's raw float32 bytes: `575e8bb1efac3a69d556d129f3d44b53946501554b0122061a60766e3fda458a`.

**Checks, stated as narrowly as they are:**
- `build_tahoe.py check` on every store compares 5 random cells' `layers/counts_csr` indices with the panel master, sliced by the MASTER's indptr. Those files are hard links to the same inodes, so this verifies the links and not the store's own `counts_csr/indptr`.
- It compares 20 random X gene columns with a CSC of the first 200,000 cells (cells ≥ 200k are not compared), and 5 random X_pca rows with master_pcs.npy. AnnData reads the stores up to 2M in full.
- X_umap of the 1M, 50M and 95.6M stores is checked against `tahoe_umap_95M.f32.npy` (random rows plus the last rows).
- The skeptic's independent pass checks counts_csr/indptr against the master for all 7 stores, and X rows against columns at random cells over the full range.

## UMAP (`umap/`, `umap/README_tahoe_umap_95M.md`)

- **Fit:** umap-learn 0.5.12 on the 999,073 reference cells (50 PCs), n_neighbors 15, min_dist 0.3, euclidean, seed 0.
- **Placement:** IDW over the 15 nearest reference cells, faiss IVF-Flat nlist 4096. **nprobe 32 gives recall@15 = 0.997** vs exact on 100k cells, so the 0.9 target is met at the first rung.
- **Validation** (100k random cells, 20k queries, 15-NN):

| metric | UMAP | PCA (50) | reference value |
|---|---|---|---|
| cell-line purity | 0.948 | 0.950 | random 0.027 |
| cell-line silhouette | 0.597 | 0.162 | |
| same-plate fraction | 0.093 | 0.129 | 0.079 if plates fully mixed within lines |
| plate entropy (bits) | 2.91 | 2.78 | 3.02 if mixed; max 3.81 |

- **kNN preservation PC → UMAP depends on the pool size** (`umap/knn_preservation_by_pool_v2.json`, script `umap/knn_preservation_by_pool_v2.py`):

  | pool | reference | placed |
  |---|---|---|
  | 1M (validate.json) | 0.027 | 0.023 |
  | 100k | 0.115 | 0.111 |
  | 10k | 0.373 | 0.356 |
  | 5k | 0.481 | 0.453 |

  - The pools are uniform random draws, and the search is exact within each pool (the validate function).
  - Placed cells sit 0.004-0.027 below reference cells; the gap is largest in the smallest pool.
  - **Correction (skeptic Q1):** the first version of this control (`umap/knn_preservation_by_pool.py` and `.json`) drew its placed pools from the low-row-index half of the rows, not uniformly. It reported 0.003-0.015.
  - For comparison only: the 20-shard HPC smoke run (plate-4 fixture with its own refit, 3,555-cell pool) gave 0.505 / 0.391. That is not a laptop number.
  - **The pool trend alone does not show the layout is good:** preservation falls with pool size for a null layout too. What separates them, measured by the skeptic (out/sk_umap.json under $SCRATCH/scale-worker-sk):
    - the within-line shuffle null scores 0.00063 at 1M and 0.113 at 5k, so the layout is 42× and 4× the null;
    - a UMAP fitted fresh on a 5k pool scores 0.471, against 0.481 for a 5k subsample of the 1M fit;
    - re-placing 20k cells by exact 15-NN reproduces the layout: median error 1e-6, with 1.2% of cells off by more than 1% of the span, from IVF misses.
- **Previews:** `preview_1M_{cell_line_id,moa_fine,plate}.png` show one island per cell line.

## Subset checks (`subset_hpc.csv`, `subset_hpc_environment.json`)

- **Run:** `bench_subset.py` (paper `fc5eaab`; its environment JSON does not record the paper commit, so `subset_hpc_provenance.json` does) against annzarro 0.2.0, `--verify`, cold = `posix_fadvise(DONTNEED)`, 3 fresh server processes. Same flags as `run_site.sh subset`, but called directly with the panel venv and stores, because `run_site.sh` hard-wires the full-gene venv and stores.
- **Result: every check passes on all 7 stores:**
  - determinism: 6 answers per store, 1 distinct hash, equal to the independent recomputation;
  - nesting 50k ⊂ 100k ⊂ 200k for seeds 0 and 1;
  - balance by cell_line_id (50 groups; water-filled quotas 255-2,087 at 1M, 481-2,057 at 2M, 1,017-2,022 at 5M, 2,000 each from 10M up) and by drug (95-380 groups), with server-reported and returned group counts equal to an independent water-filling;
  - one `where` (moa_fine), with names equal to the recomputation;
  - across consecutive sizes: the larger store's cells in the smaller store's rows are all in its subset. Overlaps: 50,247; 40,185; 50,022; 49,884; 39,975; 52,128 of 100,000, against an expected 50,000 / 40,000 / 50,000 / 50,000 / 40,000 / 52,288.

**Cost, cold `/data/subset` (n = 100,000), server peak RSS of the process tree:**

| cells | unfiltered (s, GB) | balance cell_line_id (s) | balance drug (s) | where (s) | max RSS of balance/where (GB) |
|---|---|---|---|---|---|
| 1M | 0.07, 0.12 | 3.5 | 7.2 | 1.9 | 0.56 |
| 10M | 0.49, 0.42 | 51.1 | 31.0 | 16.7 | 3.8 |
| 20M | 0.96, 0.75 | 109.0 | 64.1 | 33.3 | 6.2 |
| 50M | 2.19, 1.74 | 296.9 | 168.5 | 82.2 | 12.4 |
| 95.6M | 4.41, 3.24 | **578.3** | **321.6** | **157.6** | **21.0** |

- At 95.6M a balanced subset takes 5.4-9.6 min. That is about 3.4-6.0 s per million cells, against the requester's laptop expectation of ~1.2 s per million. The balanced cell-name fetch (`/data/cells`) then takes another 75 s there, against 0.1-0.2 s up to 20M.
- Warm repeats are 4-45 ms.
- The 1M-5M timings overlap a `du` scan of the stores (03:00-03:15) and carry that noise.

## Deviations from the request, and what did not run

- **layers/counts_csr holds the panel genes only.** A full-gene layer beside a 5,000-gene X is not valid AnnData. The requester accepted this.
- **Variance ranking:** the slim copy's variance ranking uses the reference sample, not the first 200,000 cells (which are all plate 4).
- **No browser step:** Playwright 1.63's Node needs GLIBC 2.28 and the nodes have 2.27. The official Playwright image cannot run under Apptainer inside the Slurm sandbox: no setuid starter, no squashfuse, and `--userns` fails to set mount propagation.
- **No failures** in the build, UMAP or subset jobs.
- `$SCRATCH` purges files 30 days after creation, so the stores expire around 2026-11-01.

## Server benchmark on the panel series (`http_hpc_panel.csv`, `http_hpc_panel_environment.json`)

- **Run:** `bench_http.py` at `77d2a7b` (the main e2907e6 version) against annzarro 0.2.0, over the 7 panel stores. Defaults: 3 reps; each rep runs a fresh server process with a cold store (`posix_fadvise(DONTNEED)`) for the default 100k subset (`_sub`) and for all cells (`_all`), then 2 warm repeats; request timeout 600 s; a click slower than 120 s is not run at larger N.
- **Job:** 10011105 on one **exclusive** hpc-node-46 node (36 cores, 810 GB), 3 h 23 min. No build ran during it. The full-gene builds were chained after it, and only the skeptic's read-only checks were queued behind it.
- **Statuses:** 1,507 requests returned HTTP 200. 11 were skipped by the slow rule (`cell_row_cscscan_all`, which took 126.6 s at 10M, skipped from 10M rep 1 upward). No errors and no timeouts.

**Cold medians, seconds:**

| interaction | 1M | 10M | 20M | 50M | 95.6M |
|---|---|---|---|---|---|
| startup_sub / _all | 3.2 / 3.1 | 3.4 / 3.4 | 3.4 / 3.2 | 3.5 / 3.4 | 3.7 / 4.4 |
| open_total_sub | 1.2 | 9.3 | 18.1 | 43.9 | 84.2 |
| open_total_all | 1.6 | 13.9 | 27.4 | 67.8 | 210.4 |
| open_cells_sub / _all | 1.0 / 1.2 | 8.7 / 10.7 | 17.1 / 21.2 | 41.7 / 51.6 | 79.8 / 100.7 |
| open_names_cells_all | 0.30 | 3.1 | 6.1 | 15.9 | 109.5 |
| gene_high_sub / _all | 0.19 / 0.21 | 0.66 / 0.89 | 1.16 / 1.78 | 2.42 / 4.19 | 2.40 / 6.18 |
| gene_mid_sub / _all | 0.14 / 0.16 | 0.27 / 0.41 | 0.41 / 0.68 | 0.74 / 2.30 | 1.26 / 2.89 |
| emb_sub / _all | 0.13 / 0.17 | 0.82 / 1.28 | 1.50 / 2.22 | 3.10 / 6.02 | 5.82 / 8.16 |
| obs_cat_sub / _all | 0.48 / 1.03 | 0.48 / 8.63 | 0.53 / 17.4 | 0.59 / 43.9 | 0.66 / 87.5 |
| cell_row_csr_sub / _all | 0.14 / 0.14 | 0.20 / 0.19 | 0.26 / 0.26 | 0.45 / 0.46 | 0.72 / 0.73 |
| burst8_sub / _all | 0.38 / 0.47 | 0.72 / 1.91 | 0.72 / 3.43 | 1.07 / 6.71 | 3.73 / 14.9 |

- **Server peak RSS** (process tree, max over the run): 0.71 GB at 1M, 3.8 at 10M, 7.5 at 20M, 14.5 at 50M and **25.2 GB at 95.6M**.
- **Warm repeats:** the 100k-subset clicks stay at 6-50 ms at every N. All-cell gene and embedding clicks are 1.2-1.6 s warm at 95.6M.
- **Warm `obs_cat_all` at 95.6M (83.7 s, against 6.7 s at 50M) is a cache-budget eviction, measured** (`diag/`, jobs 10013007 and 10013040, annzarro 0.2.0, shared nodes):
  - `annzarro start` uses the production config; `/api/v1/cache/info` reports `max_memory_mb: 4000`.
  - A categorical obs column is returned and cached as a Python list of strings. annzarro costs it at 57 B + len per value: **3,147 MB at 50M, 6,019 MB at 95.6M**.
  - At 50M it fits: after the first request the cache holds 3,147 MB (79%), and warm requests take 8.4 s, which is JSON encoding of the 600 MB response (5.5-6.1 s in process).
  - At 95.6M it exceeds the budget and is evicted on insertion: `memory_usage_mb` reads 0 after each request, so every repeat recomputes (92.5 / 92.8 / 92.0 s over HTTP; in process 68.4 s to build the list plus 11.0 s of JSON).
  - Control: with the cache budget raised to 200 GB in process, the warm `get_obs_var` takes 0.0 s, but the JSON encoding of the 1.2 GB response still costs 11 s every time.
  - So the codes→strings list representation, plus a fixed 4 GB budget, sets a hard warm ceiling between 50M and 95.6M cells for this request. Above it, a categorical colouring of all cells costs a full recompute on every repeat.

## Full-gene series: server benchmark of the original request (http_hpc)

`full/` holds the original scale request's deliverable: `run_site.sh http` from annzarro-reproducibility **bfd7cd0** against AnnZarro **2858fc58** (package 0.1.1, venv SCRATCH/venv), over full-gene stores (62,710 genes).

**Jobs** (`full/jobs_sacct.txt`):
- H 10011110 (hpc-node-25, 14 min): old plate-4-basis PCA fit (`full/pca_fit_plate4_basis.npz`; 203,220 cells, PC1-2 2.01/1.57%, as on the laptop) and the projection of all cells onto its 2 PCs, for `obsm/X_pca_2d`.
- I 10011111 (hpc-node-25, 16 CPUs, 4h41m, MaxRSS 244 GiB): 7 stores from `work/master.zarr`. Build seconds, check seconds and sizes are in `full/builds_full_hpc.tsv`; the build JSONs are in `full/stores/`. The 1M store is 3,721,994,538 B and the 95.6M store is 410,892,598,870 B. All passed `build_tahoe.py check`, with the same narrow scope as above.
- J 10013772 (hpc-node-23, `--exclusive`, 36 CPUs, Xeon Gold 6254, 755 GiB RAM, 7h36m): `full/http_hpc.csv` (1,518 rows: 1,507 with status 200, 11 skipped) and `full/http_hpc_environment.json`. Settings: cold_mode fadvise, 3 reps, 2 warm repeats; stores on $SCRATCH NFS4.
  - The 11 skipped rows are `cell_row_cscscan_all` cold at 10M and above; run_site.sh skips it once it is slow at a smaller N.

**Contaminated cold reps at 95.6M.** `cold prep` (posix_fadvise over every store file, `full/j_cold_prep.txt`) is stable across reps for 1M-50M (e.g. 50M: 449-572 s). At 95.6M it was 1,104 / 923 / 941 s for rep0 sub, rep0 all and rep1 sub, then **6,779 s (rep1 all), 6,184 s (rep2 sub) and 1,607 s (rep2 all)**.
- The cold latencies of those three segments are inflated: emb_all 23.4 / 19.1 s against 7.8 s in rep0, and server startup 19 s against 5 s. Warm latencies are unchanged.
- The filer was slow in those windows (16:26-20:42 PDT, Oct 3). The rep1-all window overlapped my own small $SCRATCH activity (three uv venv builds in copy mode, 0.24-0.56 GB each, created 17:17-17:54, and a 37-min parser smoke job reading only its venv). The rep2-sub window had almost none, so the slowdown is not explained by my load alone. Either way those rows are not window-free.
- So for 95.6M the clean cold values are rep0 (all) and rep0-1 (sub). Cold numbers for 1M-50M and all warm numbers are unaffected. A 95.6M-only rerun (~1.5-2 h on an exclusive node) would restore 3 clean reps.

| cells | open_total all / sub, cold s | gene_high all, cold s | emb all, cold s | obs_cat all, cold / warm s | server peak RSS |
|---|---|---|---|---|---|
| 1M | 1.74 / 1.34 | 0.21 | 0.16 | 1.04 / 0.14 | 0.76 GB |
| 10M | 13.6 / 9.3 | 0.81 | 1.09 | 8.65 / 1.37 | 3.9 GB |
| 50M | 65.9 / 43.2 | 4.99 | 4.88 | 43.4 / 6.38 | 14.8 GB |
| 95.6M, rep0 only (clean) | 212.8 / 82.7 | 5.28 | 7.78 | 87.4 / 84.4 | 25.3 GB |

(Medians over the 3 reps; at 95.6M rep0 alone. Peak RSS is the max of rss_peak, in bytes/1e9.) The warm obs_cat_all of 84 s at 95.6M is the cache eviction explained in the obs_cat section above.

**Browser step:** not run on HPC. The nodes have glibc 2.27, Playwright 1.63 needs 2.28, and Apptainer cannot run the image inside the Slurm sandbox. The laptop drives a browser against a dedicated HPC bench server instead (requests 20261004T005035Z / 011502Z).
