# Demonstration dataset for the AnnZarro protocol

Murine bone-marrow ageing (Kompot tutorial data, Zenodo doi:10.5281/zenodo.15587768):
8,090 cells × 16,285 genes, Young (2,917) vs Old (3,116) cells; the 2,057 Mid cells stay in
the store but are not used by Kompot. This directory turns the raw h5ad into an AnnZarro-ready
Zarr store and the five demo views. All data lands in `data/`, which git ignores.

See `VALIDATION.md` for what was wrong in the draft Procedure (Steps 5–10) and the
corrected code.

## Commands (run from the repository root)

```bash
PY=.venv/bin/python

# 0. Raw data. 16 parallel HTTP range requests, then the published md5 is checked.
#    Do NOT use ~/gits/kompot/data/murine_bone_marrow_aging.h5ad: that copy is truncated
#    (4.7 MB of 2.44 GB) and h5py refuses to open it.
N=16 data_prep/download_data.sh data

# 1. Kompot tutorial as a script: diffusion maps, DA and DE (Young -> Old).
#    Writes data/murine_bone_marrow_aging_processed.h5ad. Unlike the notebook, it does NOT
#    call kompot.cleanup(), so the smoothed and fold-change layers are kept.
$PY data_prep/run_kompot.py --timings data/run_kompot_timings.json

# 2. Procedure Steps 5-10, corrected. Writes data/bm_aging.zarr.
$PY data_prep/prepare_annzarro_store.py --report data/prepare_report.json

# 3. Pick the example gene and cells from the data. Writes demo_panelsets/examples.json.
$PY data_prep/pick_examples.py

# 4. Panel sets and deep links for views A-E.
# Links are for http://127.0.0.1:8000 with the store in the server's data directory.
$PY data_prep/make_panelsets.py --dataset-path bm_aging.zarr

# 5. Serve on localhost only. Pass --config: see VALIDATION.md for why
#    `annzarro start --data-dir ... --port ...` on its own fails.
.venv/bin/annzarro start --config data_prep/annzarro_local.yaml --no-browser --auth-disabled &

# 6. Validation and benchmarks against the running server.
$PY data_prep/api_benchmark.py --dataset $PWD/data/bm_aging.zarr --out data/api_benchmark.json
$PY data_prep/validate_panelsets.py --out data/panelset_validation.json
$PY data_prep/bench_chunks.py            # direct-zarr chunk-shape comparison, no server needed

# 7. Stop the server.
pkill -f "annzarro start --config data_prep/annzarro_local.yaml"
```

Panel sets are imported into `data/sessions/` (the server's `<data_dir>/sessions`).

## Runtime on this machine

Apple-silicon Mac, 16 cores, 128 GB RAM, local NVMe. All times are wall clock.

| Step | Time | Peak RSS |
|---|---|---|
| download (16 range requests, network-bound) | 5 min 28 s | – |
| `run_kompot.py` total | 62 s | 29 GB |
|  read h5ad / diffusion maps / `kompot.da` / `kompot.de` / write h5ad | 0.5 / 0.3 / 15.9 / 43.2 / 2.3 s | |
| `prepare_annzarro_store.py` total | 51 s | 24.6 GB |
|  Step 5 load + discover keys | 0.9 s | |
|  Step 6 dense 5-step diffusion walk (obsp) | 6.8 s | |
|  Step 7 two Spearman varp (smoothed: 18.4 s rank + 2.0 s matmul; fold change: 8.1 s + 1.1 s) | 30.5 s | |
|  Step 8 X → CSC | 0.7 s | |
|  Step 9 `write_zarr` (format 2, 6.08 GB before Step 10) | 6.2 s | |
|  Step 10 rewrite 7 dense arrays as float32 (1024, 1024), then re-consolidate | 3.2 s | |
|  verify (read back with `anndata.read_zarr`) | 1.6 s | |
| `pick_examples.py`, `make_panelsets.py`, `validate_panelsets.py` | < 10 s each | |

Memory is dominated by holding the 5.6 GB h5ad in RAM: the Kompot layers are float64.
Plan for about 32 GB at this dataset size.

## Resulting store `data/bm_aging.zarr`

Zarr format 2 with consolidated metadata. Total 4.78 GB (4.5 GiB). The h5ad it came from
is 5.6 GB.

| Path | Encoding | Shape | dtype | Chunks | On disk |
|---|---|---|---|---|---|
| `X` (scaled expression, 100 % non-zero) | csc_matrix | 8090 × 16285 | float32 | data (514632,) | 462.6 MB |
| `layers/kompot_de_Young_to_Old_fold_change` | array | 8090 × 16285 | float32 | (1024, 1024) | 516.6 MB |
| `layers/kompot_de_Young_smoothed` | array | 8090 × 16285 | float32 | (1024, 1024) | 472.6 MB |
| `layers/kompot_de_Old_smoothed` | array | 8090 × 16285 | float32 | (1024, 1024) | 471.7 MB |
| `layers/MAGIC_imputed_data` | array | 8090 × 16285 | float32 | (1024, 1024) | 351.4 MB |
| `layers/logged_counts` | csr_matrix | 8090 × 16285 | float32 | data (201719,) | 97.6 MB |
| `layers/normalized_counts` | csr_matrix | 8090 × 16285 | float32 | data (201719,) | 87.4 MB |
| `layers/cc_counts` | csr_matrix | 8090 × 16285 | float32 | data (201719,) | 96.7 MB |
| `layers/raw_counts` | csr_matrix | 8090 × 16285 | float32 | data (201719,) | 59.1 MB |
| `obsp/diffusion_walk_t5` (new, T⁵, row-stochastic) | array | 8090 × 8090 | float32 | (1024, 1024) | 191.6 MB |
| `obsp/DM_Kernel` | csr_matrix | 8090 × 8090 | float64 | data (41931,) | 2.8 MB |
| `obsp/DM_Similarity` | csr_matrix | 8090 × 8090 | float64 | data (41931,) | 2.9 MB |
| `obsp/connectivities` | csr_matrix | 8090 × 8090 | float32 | data (83180,) | 0.9 MB |
| `obsp/distances` | csr_matrix | 8090 × 8090 | float64 | data (28283,) | 0.6 MB |
| `varp/spearman_smoothed` (new) | array | 16285 × 16285 | float32 | (1024, 1024) | 967.7 MB |
| `varp/spearman_fold_change` (new) | array | 16285 × 16285 | float32 | (1024, 1024) | 984.6 MB |
| `obsm/X_umap`, `X_draw_graph_fa` | array | 8090 × 2 | f32 / f64 | (8090, 2) | 0.1 MB |
| `obsm/DM_EigenVectors` | array | 8090 × 40 | float64 | (2023, 20) | 2.4 MB |
| `obsm/X_pca*` (3 keys) | array | 8090 × 50 | float32 | (4045, 25) | 1.5 MB each |
| `obsm/AbCapture`, `obsm/HTO` | dataframe | – | – | – | 0.4 / 0.1 MB |

Each rewritten array has `.zattrs` `{"encoding-type": "array", "encoding-version": "0.2.0"}`
and compressor blosc/lz4, clevel 5, byte shuffle. `.zmetadata` agrees with the on-disk
`.zarray` (checked after re-consolidation).

Kompot columns: `obs` gets `kompot_da_Young_to_Old_{lfc, lfc_zscore, neg_log10_lfc_ptp,
lfc_direction}`, `kompot_da_{Young,Old}_log_density` and `kompot_de_{Young,Old}_std`. `var`
gets `kompot_de_Young_to_Old_{mahalanobis, mean_lfc, mahalanobis_local_fdr, is_de}`.

## Examples chosen for the figures

These are in `demo_panelsets/examples.json`; `pick_examples.py` gives the rationale.

- **Focus gene: S100a9.** DE rank 8, 190 DE genes at FDR < 0.05. It was chosen
  algorithmically: among the 10 top DE genes it has the most DE genes among its 5 nearest
  Spearman neighbours, counted in both varp matrices (score 7 of 10). Its smoothed-expression
  module is the neutrophil granule program: S100a8 0.99, Ngp 0.96, Camp 0.96, Retnlg 0.94,
  Lcn2 0.93, all DE. Its fold-change partner is S100a8 (ρ = 0.95). The age effect is
  HSC-specific: mean fold change −1.20 in HSCs and |FC| ≤ 0.26 in every other cell type.
  The notebook's interpretation ("antioxidant genes S100a8/9 higher in Young") puts it in
  the tutorial's own narrative.
- **Alternative gene: H2-Q7.** DE rank 1, up in Old broadly (FC +0.2 to +0.9). Its
  fold-change Spearman neighbours are the MHC-I/antigen-presentation genes H2-Q6, Tapbpl,
  H2-D1 and B2m. **H2-Aa** (MHC-II: H2-Eb1, H2-Ab1, Ciita, Cd74) gives the cleanest module
  in both correlation types.
- **HSC: `HSPC_Old_1#GAAGCCCGTGGCTCTG-1`** (index 2089). Old cell, DA z-score 10.99, which
  is exactly the HSC median (HSCs are the most Old-enriched type). 90.7 % of its 5-step
  walk stays within HSCs. S100a9 fold change here is −1.35.
- **Monocyte: `Mature_Young_2#TCAATTCAGTGAGGCT-1`** (index 4236). Young cell, DA z −3.34
  (monocyte median −2.98). 88.6 % of its walk stays within monocytes. S100a9 FC ≈ 0.
- Both cells are the one closest to their type's median in diffusion space, chosen among 15
  candidates by walk purity. Cell names contain `#`. That is harmless in the API (it uses
  indices) and in deep links (base64url), but the name must be URL-encoded if typed into a
  query string.
- **View E filter:** `highres_celltype == HSC AND DA z > 2` should leave **290 of 319 HSCs**
  (230 Old, 56 Mid, 4 Young).

## Files

| File | Purpose |
|---|---|
| `download_data.sh` | parallel Zenodo download + md5 |
| `run_kompot.py` | notebook → script (DA, DE), keeps the layers |
| `prepare_annzarro_store.py` | Procedure Steps 5–10, corrected |
| `pick_examples.py` | data-driven choice of the gene and cells |
| `make_panelsets.py` | panel sets + deep-link views for A–E |
| `validate_panelsets.py` | import/load through the server, resolve every data reference, deep-link round trip in Node |
| `api_benchmark.py` | real-data API latency/payload table |
| `bench_chunks.py` | chunk-shape comparison (direct zarr) |
| `annzarro_local.yaml` | minimal server config (localhost, port 8010, `data/`) |
| `demo_panelsets/*.json` | 5 panel sets, 5 `*.view.json` deep-link views, `deeplinks.json` (URLs), `examples.json` |
