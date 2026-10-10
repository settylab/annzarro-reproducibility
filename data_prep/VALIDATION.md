# Validation of the draft Procedure, Steps 5–10 (data preparation)

Validated on 2026-10-01 against these versions: anndata 0.12.19, zarr 3.1.6, kompot 0.8.0,
palantir 1.4.5, numpy 2.4.6, scipy 1.17.1, Python 3.11, and AnnZarro at commit `63b57e6`.
Every step below was executed on the real dataset. Timings come from a 16-core
Apple-silicon Mac with 128 GB RAM.

Legend: **FAILS** means the step crashes or produces a broken store. **WORKS*** means it
runs but the text needs a correction or caveat. **WORKS** means it runs as written.

## Before Step 5: producing the processed h5ad

| Issue | Severity | Correction for the protocol text |
|---|---|---|
| The tutorial ends with `kompot.cleanup(adata)` before `write_h5ad`, which **deletes** `kompot_de_*_smoothed` and `*_fold_change`. A user who follows the tutorial gets an h5ad without the layers Steps 7 and C/D need. | **blocking** | Say explicitly: "skip `kompot.cleanup()`" (or re-run DE). `run_kompot.py` does this. |
| Kompot 0.8 names the per-condition layers `kompot_de_<cond>_smoothed`. The notebook's rendered output (older Kompot) says `_imputed`. | text | Use the discovered `smoothed_key_1/2`; never quote `_imputed`. |
| There are **two** smoothed layers (Young, Old), so a single `SMOOTHED_KEY` is ambiguous. | text | See Step 7. |
| `examples/04_differential_abundance.ipynb` does not exist in the kompot repo. DA is covered in `01_getting_started.ipynb`. | text | Remove the reference. |
| The local `~/gits/kompot/data/murine_bone_marrow_aging.h5ad` is truncated (4.7 MB of 2,439,076,864 B) and h5py cannot open it. Zenodo md5 is `3e346c91e029e5fde551a9ebf9ecee78`. | data | Download from Zenodo and check the md5 (`download_data.sh`). |
| Re-running with kompot 0.8 gives 190 DE genes at FDR < 0.05 with a Mahalanobis threshold of 5.82. The notebook printout shows 192 and 27.35. Top genes match (H2-Q7, Cd74, H2-Aa, H2-Ab1, …). | note | Quote numbers from a fixed Kompot version. Don't copy them from the notebook. |
| The processed h5ad is **5.6 GB**: the Kompot layers are float64. Peak RSS was 29 GB. | note | State RAM needs (≈32 GB). |

## Step 5: load and discover keys. **FAILS as written**

`adata.uns['kompot_de']['last_run_info']['field_names']` raises
`TypeError: string indices must be integers`. In kompot 0.8, `last_run_info` is stored as a
**JSON string**, and it stays a string after the h5ad round trip.

Corrected:

```python
import json
def kompot_field_names(adata, kind):              # kind = "kompot_de" | "kompot_da"
    info = adata.uns[kind]["last_run_info"]
    if isinstance(info, (str, bytes)):
        info = json.loads(info)
    return info["field_names"]
# or, with kompot installed: kompot.RunInfo(adata, analysis_type="de").field_names

de = kompot_field_names(adata, "kompot_de"); da = kompot_field_names(adata, "kompot_da")
FC_KEY      = de["fold_change_key"]                  # kompot_de_Young_to_Old_fold_change
SMOOTH_KEYS = [de["smoothed_key_1"], de["smoothed_key_2"]]   # ..._Young_smoothed, ..._Old_smoothed
LFC_KEY     = de["mean_lfc_key"];  MAHAL_KEY = de["mahalanobis_key"]
DA_Z_KEY    = da["zscore_key"]                       # kompot_da_Young_to_Old_lfc_zscore
assert FC_KEY in adata.layers                       # fails if kompot.cleanup() was run
```

Caveat: `field_names` also lists keys that were **not** stored. Here
`all_patterns["obsp"]` names `kompot_de_Young_to_Old_posterior_covariance`, but it is absent
because `store_posterior_covariance=False`. Always test membership before using a key.

What the listing shows for this dataset:
- layers: 4 dense (`MAGIC_imputed_data` f32, the 3 Kompot layers **f64**) and 4 CSR f32.
- obsp: `DM_Kernel`, `DM_Similarity`, `connectivities`, `distances`, all CSR.
- varp: empty.

Time: 0.9 s.

## Step 6: cell × cell kernel in obsp. **WORKS*** (the "if missing" branch never fires)

- The raw file already contains `DM_Kernel`, `DM_Similarity` (row-stochastic T),
  `connectivities` and `distances`. The tutorial's `run_diffusion_maps` call rewrites them,
  and the eigenvectors are reproduced exactly (checked with `allclose`). The protocol
  should say Palantir writes **both** `DM_Kernel` and `DM_Similarity`.
- A sparse kernel row is a poor "kernel walk" picture: the median effective support of a T
  row (1/Σp²) is **33 cells**, so the UMAP shows a speck. Effective support of rows of Tᵗ:

  | t | 1 | 2 | 4 | 8 | 16 | 32 |
  |---|---|---|---|---|---|---|
  | cells | 33 | 134 | 282 | 474 | 735 | 1123 |

  We store a dense **`obsp/diffusion_walk_t5`** (T⁵, smallest t with support ≥ 300). It is
  cheap at 8k cells: 6.8 s, 262 MB in RAM, 192 MB on disk. The walk from the example HSC
  keeps 90.7 % of its mass inside HSCs.

  ```python
  K = sp.csr_matrix(adata.obsp["DM_Kernel"], dtype=np.float64)
  T = sp.diags(1 / np.asarray(K.sum(1)).ravel()) @ K       # row-stochastic
  W = T.toarray(); M = W.copy()
  for _ in range(t - 1): M = M @ W
  adata.obsp[f"diffusion_walk_t{t}"] = M.astype(np.float32)
  ```

  Dense obsp scales as n²: 4 GB at 32k cells and 400 GB at 320k. Above roughly 30k cells,
  keep the sparse kernel, or threshold Tᵗ into a sparse CSR. AnnZarro reads CSR rows lazily
  (11 ms, below).

## Step 7: genes × genes Spearman in varp. **WORKS***, with three decisions to document

The draft code is numerically correct. The checks requested:
- **Constant genes → NaN:** none in either the smoothed or the fold-change layer (Kompot
  smoothing is never exactly constant), but the guard is cheap and generalises. With
  `sd == 0`, divide by 1 so the column becomes all zeros and ρ = 0, not NaN. AnnZarro would
  survive NaN (`server/core.py` uses a NaN-safe encoder and the client maps `NaN` to
  `null`), but a NaN row renders as an empty volcano.
- **Memory and time** (16,285 genes): stacking both conditions gives S = 16,180 × 16,285
  f32 = 1.05 GB. `rankdata` returns float64 (2.1 GB transient). R is 1.05 GB and the output
  C is 1.06 GB. `rankdata` takes 18.4 s and `R.T @ R` takes 2.0 s. The varp is 968 MB on
  disk because correlations barely compress. Clip to [−1, 1]: float32 accumulation gives
  1 + 1e-7.
- **Which smoothed expression:** stack the Young and Old smoothed layers row-wise (all
  cells × 2 conditions), so one matrix captures co-variation along the manifold *and* with
  age. Per-condition matrices double the disk for little gain.

**Biological finding that changes the protocol's recommendation.** Spearman on smoothed
expression mostly recovers **lineage programs**, not ageing modules. For S100a8 there are
45 genes with ρ > 0.8 (the neutrophil program), of which 24 % are DE. For Cd52 there are
37 genes, 14 % DE. For Fcer1g there are 137 genes, 12 % DE. Spearman on the **fold-change
layer** asks which genes' *age effect* co-varies across cell states. It recovers
co-regulated responses:
- H2-Q7 → H2-Q6, Tapbpl, H2-D1, B2m (MHC-I antigen presentation).
- H2-Aa → H2-Eb1, H2-Ab1, Ciita, Cd74, H2-DMb1 (MHC-II).

It costs 10 s more and adds 985 MB. We store both:

```python
def spearman_columns(S):
    R = rankdata(S, axis=0).astype(np.float32)
    sd = R.std(0); const = sd == 0
    R -= R.mean(0); R /= np.where(const, 1.0, sd)
    C = (R.T @ R) / np.float32(R.shape[0]); np.clip(C, -1, 1, out=C)
    return C
adata.varp["spearman_smoothed"]    = spearman_columns(np.vstack([adata.layers[k] for k in SMOOTH_KEYS]).astype(np.float32))
adata.varp["spearman_fold_change"] = spearman_columns(np.asarray(adata.layers[FC_KEY], np.float32))
```

Recommendation: colour the view-B volcano with `spearman_fold_change` for an
ageing-module story. `spearman_smoothed` answers "which genes share this gene's
cell-type pattern". Both are in panel set B.

Time: 30.5 s for both.

## Step 8: `adata.X = adata.X.tocsc()`. **WORKS***

It runs in 0.7 s. Two things the text should add.

1. **`X` here is scaled expression** (range −10.3 to 7.8) stored as CSR with **100 % non-zeros**
   (nnz = 131,745,650 = 8,090 × 16,285). Colouring by X shows z-scored values, and storage
   is ≈2× a dense array because of the indices. Tell users what `X` holds, or colour by a
   layer.
2. CSC only helps **X**. AnnZarro's lazy single-column path (`zarr_reader._lazy_sparse_slice`)
   fires only for CSC + column-only or CSR + row-only requests. Everything else
   materialises the whole matrix:
   - `logged_counts` (CSR) gene column: **76 ms** vs 16 ms for CSC X.
   - X **cell row** after CSC: **212 ms** (full load). The gene plot asks for this when
     coloured by X.

   Add: "convert every sparse layer you will colour cells by to CSC as well", e.g.
   `adata.layers['logged_counts'] = adata.layers['logged_counts'].tocsc()`. Do this only
   when gene-column access matters more than cell-row access for that layer.

## Step 9: `ad.settings.zarr_write_format = 2; adata.write_zarr(...)`. **WORKS***

It runs: 6.08 GB in 6.2 s. anndata 0.12 emits *"Writing zarr v2 data will no longer be the
default in the next minor release"*. Format 2 is **required**, not merely preferred: the
AnnZarro reader rejects a local directory without `.zgroup`/`.zarray`
(`zarr_reader._get_root`). Two further points:
- `write_zarr` **consolidates metadata** (`.zmetadata`), which matters for Step 10.
- `write_zarr`'s `chunks=` argument applies only to `X`. Per-element chunking needs Step 10.

## Step 10: rewrite dense arrays as float32 with chunks (1024, 1024). **FAILS as written**

`ad.io.write_elem(g[slot], key, arr, dataset_kwargs={'chunks': (1024, 1024)})` on
`zarr.open_group(path, mode='r+')` raises:

```
ValueError: Cannot overwrite/edit a store with consolidated metadata
```

With `use_consolidated=False` the rewrite succeeds: `write_elem` replaces the existing key
and the old chunk files are removed. **But the store is then corrupt for every reader**,
because `.zmetadata` still describes the old array (`<f8`, chunks (375, 250) in the toy
test). `zarr.open_group(path, 'r')`, which AnnZarro uses, and `anndata.read_zarr` both fail
with `ValueError: cannot reshape array of size 524288 into shape (375,250)`. Re-consolidation
is mandatory. Corrected:

```python
import zarr, anndata as ad, numpy as np, scipy.sparse as sp
g = zarr.open_group("bm_aging.zarr", mode="r+", use_consolidated=False)   # 1. bypass .zmetadata
for slot in ("layers", "obsp", "varp"):
    for key, arr in getattr(adata, slot).items():
        if sp.issparse(arr) or np.ndim(arr) != 2:
            continue
        ad.io.write_elem(g[slot], key, np.asarray(arr, dtype=np.float32),
                         dataset_kwargs={"chunks": (1024, 1024)})
zarr.consolidate_metadata("bm_aging.zarr")                                 # 2. MANDATORY
```

The signature in anndata 0.12 is
`write_elem(store, k, elem, *, dataset_kwargs=...)`; `dataset_kwargs` is keyword-only.

Checked afterwards for every rewritten array:
- `.zarray` has `chunks [1024,1024]`, `dtype <f4` and compressor blosc/lz4/clevel 5/shuffle.
- `.zattrs` is `{"encoding-type": "array", "encoding-version": "0.2.0"}`.
- `.zmetadata` matches the `.zarray`.
- Values are bit-identical to `astype(float32)` of the h5ad.
- `anndata.read_zarr` round trip works.

Time: 3.2 s for 7 arrays. Store size went from 6.08 GB to 4.78 GB.

**Is the step worth it?** We measured direct zarr reads on the real fold-change layer and
varp:

| chunks | FC gene column | FC cell row | varp row | note |
|---|---|---|---|---|
| (1024, 1024) | 5.2 ms | 9.8 ms | 10.5 ms | draft choice: balanced |
| (256, 256) | 6.0 | 11.4 | 11.4 | |
| (4096, 4096) | 59 | 61 | 61 | chunk too big |
| (64, n_genes) | 62 | 4.2 | 4.2 | row-optimised |
| (n_cells, 64) | 2.1 | 70 | 74 | column-optimised |
| unchunked | 457 | 458 | 463 | |
| anndata default (auto, 253 × 1018, float64) | 10.7 | 5.7 | – | what Step 9 alone gives |

So (1024, 1024) is a sound default. At this size, though, anndata's auto-chunking is
already interactive, and most of Step 10's benefit is **float64 → float32**: half the disk,
half the bytes to decompress. A simpler and equally valid protocol is to cast the dense
layers, obsp and varp to float32 **in memory before Step 9**, and keep Step 10 (corrected)
as the optional step for explicit chunk control. Square chunks matter more as n grows,
because auto-chunks become thin.

## Serving the store: `annzarro start`. **FAILED as written; fixed in AnnZarro PR #43**

> Update 2026-10-02: the config loader now reads its defaults from the installed package and maps `--host`/`--port`/`--data-dir` to `server.*` (regression tests in `annzarro/tests/utils/test_config_precedence.py`, branch `dominik/protocol-integration`). The draft command works verbatim from any directory on that branch. The record below describes the version that was validated first.

`annzarro start --data-dir <dir> --port 8010 --no-browser --auth-disabled`, run from
anywhere but the AnnZarro source tree, exits with:

```
Configuration error: Missing required configuration: server.host / server.port / server.data_dir
```

There are two causes in `annzarro/utils/config_manager.py`:
1. Environment defaults load from `config/{env}.yaml` **relative to the CWD**.
2. `_apply_cli_args` maps `--data-dir` to `config['data']['dir']` and `--host` to
   `config['host']`, never to `server.*`, and validation runs before `start_server`'s
   overrides.

Working command, with `data_prep/annzarro_local.yaml` setting
`server.{host,port,data_dir,log_file}` and `auth.enabled: false`:

```bash
annzarro start --config data_prep/annzarro_local.yaml --no-browser --auth-disabled
```

We also ran the draft command verbatim from inside the AnnZarro checkout. It works there,
and `--port`/`--data-dir` are honoured, but it appends to the checkout's
`logs/annzarro_server.log`. So the bug only bites the normal user case of a pip install
launched from the user's project directory.

This is an AnnZarro bug worth fixing before publication. Until it is fixed, the protocol
must ship a config file or say "run from the AnnZarro checkout". The server is Flask's
built-in server ("production" mode label notwithstanding). The server log had no errors
during the benchmark and validation.

## API latency and payload on the real store

Localhost, client wall time from request to full body. Each latency column means:
- **cold:** first request after `POST /cache/reset`. The OS page cache was *not* dropped,
  because macOS `purge` needs sudo.
- **random:** 10 different indices, median and p90.
- **warm:** the same request repeated.

Payload is the JSON body; responses are not gzipped. Indices: gene S100a9 (2551), cell
HSC 2089.

| Request (front-end call) | cold ms | random median / p90 ms | warm ms | payload kB |
|---|---|---|---|---|
| X gene column (CSC, lazy) | 23.7 | 15.8 / 18.2 | 17.3 | 170 |
| X cell row (CSC, full load) | 339 | 212 / 221 | 210 | 332 |
| fold-change layer gene column (dense 1024²) | 15.8 | 16.0 / 17.8 | 17.6 | 182 |
| fold-change layer cell row (dense 1024²) | 21.5 | 22.2 / 22.7 | 22.1 | 340 |
| Old-smoothed layer gene column | 16.2 | 16.3 / 17.9 | 17.1 | 168 |
| logged_counts gene column (CSR, full load) | 81.4 | 76.3 / 86.2 | 83.5 | 122 |
| obsp row, dense `diffusion_walk_t5` | 15.3 | 15.3 / 17.2 | 2.6 | 77 |
| obsp row, sparse `DM_Kernel` (CSR, lazy) | 10.7 | 11.5 / 12.4 | 1.9 | 33 |
| varp row, dense `spearman_smoothed` | 25.7 | 26.4 / 32.4 | 7.0 | 327 |
| var `mean_lfc` + `mahalanobis` (volcano, all genes) | 24.4 | – | 11.7 | 658 |
| obs `highres_celltype` + DA z (table, all cells) | 18.1 | – | – | 248 |
| obsm `X_umap` (all cells) | 16.0 | – | – | 320 |
| `dataset_structure` (open dataset) | 56.2 | – | – | 9.5 |

Every request a view needs on focus change takes ≤ 26 ms. The two slow cases are
structural, and both are covered by the Step 8 caveat: CSC-X cell rows and CSR-layer gene
columns. JSON carries about 21 bytes per float32 value, so a binary or gzip transport
would cut payloads by 4–5×. That belongs in the tool's limitations, not the protocol.
Raw data: `data/api_benchmark.json`.

## Panel sets (views A–E). Validated through the server

`demo_panelsets/{A..E}_*.json` follow the schema `SessionManager.saveSession` writes:
`name`, `timestamp`, `dataset`, `datasetName`, `constants{focusedCell, focusedGene,
taxonomyId}`, and `panelConfigs{id: {id, type, title, config, isSelectionTile}}`.

`validate_panelsets.py` (server on localhost, sessions dir `data/sessions/`) checked:
- **Import and load:** `POST /sessions/import` returns 200 and `GET /sessions/load` returns
  200. The round trip is lossless and each set appears in `/sessions/list`. This holds for
  all 5 views.
- **Data references:** all 33 references (axes, colours, table columns) were resolved by
  issuing the request the front end would make. Each returned 200 with full length:
  8,090 values for cells and 16,285 for genes, all finite.
- **Deep links:** each `*.view.json` round-trips through AnnZarro's own
  `static/js/utils/deeplink.js` (`encodeView` → `decodeView` → `normalizeView`) in Node,
  is unchanged, and `layoutHasPanels` is true. Every tile id maps to a `panelConfig` of the
  right type.

| View | Panels | Focus (constants) |
|---|---|---|
| A kernel walk | cell-plot UMAP coloured by `obsp/diffusion_walk_t5` row; second panel by sparse `DM_Kernel` row | HSC 2089 |
| B volcano | gene-plot x = `mean_lfc`, y = `mahalanobis`, colour = `varp/spearman_smoothed` (B) and `spearman_fold_change` (B′), RdBu fixed at [−1, 1] | S100a9 |
| C fold change on UMAP | FC layer (RdBu, centred) + Young smoothed + Old smoothed of the focused gene | S100a9 |
| D locked vs focused cell | gene-plot x = FC layer of **locked** HSC, y = FC layer of **focused** cell, colour = Mahalanobis; plus a cell-type UMAP | focused = monocyte 4236 |
| E table filter | cell-table (`highres_celltype`, DA z, Age) with SearchBuilder `celltype = HSC AND DA z > 2`; a cell-plot with `tableFilter = cell-table-E1` | expected 290 of 319 HSCs |

AnnZarro behaviours the protocol text must reflect:

1. **Loading a panel set does not reproduce a view.** `loadSession` → `_applySessionPanels`
   only registers the panels as **closed** panels in the panel selector. It does not load
   the dataset, set the focused gene or cell (`constants` are ignored on this path), or
   arrange panels. To reproduce a figure panel, use the deep link (then `?dataset_path=…&view=…`,
   about 2–2.9 kB each; since 2026-10-04 `demo_panelsets/deeplinks.json` holds the portable
   `?dataset_path=bm_aging.zarr#view=z1.…` form, 0.7–0.9 kB). The deep link sets
   dataset, focus and layout through `PanelManager.restoreLayout`.
2. **Panel ids.** `registerClosedPanel` keeps an id only if it is inside `config`. The UI's
   own `saveSession` stores it outside (`getConfig()` has no `id`), so on load every panel
   gets `type-Date.now()`. That has two consequences, both AnnZarro bugs:
   - It breaks the cell-plot → cell-table filter link (`tableFilter` holds the old id).
   - Panels of one type registered in the same millisecond collide in `_panels`.

   Our files put `id` inside `config` to avoid both.
3. Not verified: actual browser rendering. In particular, whether DataTables'
   SearchBuilder accepts the pre-defined criteria with `type: "num"` on the DA z column (it
   may detect `html-num`). Before taking screenshots, open deep link E and confirm the
   table shows 290 rows.

## Recommended example genes and cells (from the data)

These are chosen by `pick_examples.py`; details are in `README.md`.
- **S100a9** is the focus gene: DE rank 8, its module is all-DE in both varp, and its
  fold change is HSC-specific (−1.20 in HSCs vs |FC| ≤ 0.26 elsewhere).
- **H2-Q7** (rank 1, broadly up, MHC-I module) and **H2-Aa** (MHC-II module) are the
  alternatives.
- **HSC `HSPC_Old_1#GAAGCCCGTGGCTCTG-1`** (DA z 10.99 = HSC median, walk 91 % in-type).
- **Monocyte `Mature_Young_2#TCAATTCAGTGAGGCT-1`** (DA z −3.34, walk 89 % in-type).
