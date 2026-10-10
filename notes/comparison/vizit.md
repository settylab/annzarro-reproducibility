## VizIt

> The authoritative marks and evidence are in `evidence/matrix/tools/vizit.yaml`. This page explains them; it is not yet a Fig. 1c row (user decision: full row, Phase 2 GO).

### What it is

VizIt, from the Dong lab at Yale, is a web portal for single-cell, Visium and xQTL atlases: a React and Plotly front end over a FastAPI back end. Datasets are prepared offline from Seurat objects into per-gene JSON, a metadata table and a sampled UMAP. It is deployed as the hosted [PD5D atlas](https://pd5d.yale.edu).

- **Paper:** none found in Crossref (2026-10-05). The citable record is the software deposit: TheDongLab/VizIt: VizIt v1.0.0, Zenodo, 2026-08-13, [doi:10.5281/zenodo.21925071](https://doi.org/10.5281/zenodo.21925071).
- **Scored version:** VizIt v1.0.0 as deployed on pd5d.yale.edu (checked 2026-10-04/05). Source [thedonglab/VizIt `a0aabb2`](https://github.com/thedonglab/VizIt/tree/a0aabb2197b8eea4acf1b32e393bd7fc4619fa96) (2026-09-08; frontend package 1.0.0). Docs: [thedonglab.github.io/VizIt](https://thedonglab.github.io/VizIt/).
- **Largest observed:** 309,960 cells (pd5d, `PD5D_MTG_snRNAseq`). The Gene View UMAP draws 50,000 of them.

### How it was checked

- **Hosted app:** pd5d.yale.edu in headless Chromium, driven by [matrix_check.py](demos/vizit/matrix_check.py) and [followup_check.py](demos/vizit/followup_check.py). No local install: the source clone at `$DEMO_ROOT/vizit/src` was read, not run.
- **Point counts** come from the Plotly traces in the page.
- **Request log:** [l01](screens/vizit/l01_lazy_request_log.jpg) lists the API calls of one Gene View load, with response sizes.
- **Shots:** sidecars sit next to each shot in [`screens/vizit/`](screens/vizit/). Captions were written after looking at each image.

### Matrix row (proposed)

| Column | Proposed | Observed or found | Evidence |
|---|---|---|---|
| cell × cell matrix as colour or axis | N | No cell x cell data type: datasets are prepared from Seurat objects into expression, metadata and UMAP tables. | [m00_every_cell_geneview_umap](screens/vizit/m00_every_cell_geneview_umap.jpg), [docs](https://thedonglab.github.io/VizIt/prepare_dataset/scrnaseq/) |
| gene × gene matrix as colour or axis | N | No gene x gene data type. | [docs](https://thedonglab.github.io/VizIt/prepare_dataset/scrnaseq/) |
| focused cell/gene drives linked panels | N | A gene choice colours the UMAP and violins by its expression (feature colouring); no relation row. | [m00_every_cell_geneview_umap](screens/vizit/m00_every_cell_geneview_umap.jpg) |
| all AnnData slots incl. obsp/varp/varm | N | Only expression, cell metadata and a UMAP are prepared from a Seurat object; no AnnData slots beyond those. | [docs](https://thedonglab.github.io/VizIt/prepare_dataset/scrnaseq/) |
| remote stores (S3, GCS, HTTP) | N | The backend serves its own prepared files; no URL or object-store input for single-cell data. | [requirements.txt#L1](https://github.com/thedonglab/VizIt/blob/a0aabb2197b8eea4acf1b32e393bd7fc4619fa96/backend/requirements.txt#L1) |
| spatial coordinates | **Y** | Visium spots at tissue coordinates in the Spatial Tx View. | [m07_m11_spatial_he](screens/vizit/m07_m11_spatial_he.jpg) |
| selection or filter restricts linked views | N | Plotly's box/lasso tools exist, but no plot handles a selection, so nothing reaches another view. | [f03_selection_umap_toolbar](screens/vizit/f03_selection_umap_toolbar.jpg) |
| annotation editing | N | No control to label cells. | [m00_every_cell_geneview_umap](screens/vizit/m00_every_cell_geneview_umap.jpg) |
| on-the-fly DE | N | Markers and condition DE are read from tables computed at preparation (31_clustermarkers.R); nothing is computed for a selection. | [f02_de_cluster_markers](screens/vizit/f02_de_cluster_markers.jpg), [docs](https://thedonglab.github.io/VizIt/prepare_dataset/scrnaseq/) |
| tissue image underlay | **Y** | 'Show H&E image' draws the H&E section under the spots. | [f01_image_he_on](screens/vizit/f01_image_he_on.jpg) |
| shareable view state | **Y** | The URL carries dataset, gene, sample, colouring and grouping. | [m12_share_url_state](screens/vizit/m12_share_url_state.jpg) |
| plot export | **Y** | 'Download plot' saved a 9.7 MB SVG; Export SVG/PNG and Download CSV buttons. | [m13_export_plotly_download](screens/vizit/m13_export_plotly_download.jpg) |
| desktop app | N | A web portal (Docker or uvicorn plus npm); no desktop application. | [docs](https://thedonglab.github.io/VizIt/install/) |
| hosted multi-user | **Y** | One deployment (pd5d.yale.edu) serves all visitors. | [m12_share_url_state](screens/vizit/m12_share_url_state.jpg) |
| static site, no server | N | Needs the FastAPI backend. | [requirements.txt#L1](https://github.com/thedonglab/VizIt/blob/a0aabb2197b8eea4acf1b32e393bd7fc4619fa96/backend/requirements.txt#L1) |
| lazy chunked reads | **Y** | Expression is fetched per gene (getexprdata, 1.6 MB for SNCA on 309,960 cells); the backend reads per-gene files written at preparation. Cell metadata for the dataset arrive in one call. | [l01_lazy_request_log](screens/vizit/l01_lazy_request_log.jpg), [docs](https://thedonglab.github.io/VizIt/prepare_dataset/scrnaseq/), [api.js#L103](https://github.com/thedonglab/VizIt/blob/a0aabb2197b8eea4acf1b32e393bd7fc4619fa96/frontend/src/api/api.js#L103) |
| S2 | N | The Gene View UMAP draws 50,000 of 309,960 cells; no control draws them all. | [m00_every_cell_geneview_umap](screens/vizit/m00_every_cell_geneview_umap.jpg) |
| S4 | P | Choosing samples limits what is drawn; expression and cell metadata still arrive for all cells. | [f01_image_he_on](screens/vizit/f01_image_he_on.jpg) |
| auto subset | P | The UMAP is a sample fixed when the dataset was prepared ('UMAP embedding sampling'), not chosen at viewing time. | [m00_every_cell_geneview_umap](screens/vizit/m00_every_cell_geneview_umap.jpg), [docs](https://thedonglab.github.io/VizIt/prepare_dataset/scrnaseq/) |

Notes on contested cells:
- **every cell N, auto-subset P.** Under reading B a preparation step counts, so I checked whether the 50,000 cap can be set at preparation. It cannot: [31_rename_meta_SC.py L170-172](https://github.com/thedonglab/VizIt/blob/a0aabb2197b8eea4acf1b32e393bd7fc4619fa96/backend/funcs/scst_scripts/31_rename_meta_SC.py#L170-L172) hard-codes `sample_rows = 50000 if n_rows > 50000 else n_rows`, the runner passes no sampling argument ([x0_run_from_toml.py L158](https://github.com/thedonglab/VizIt/blob/a0aabb2197b8eea4acf1b32e393bd7fc4619fa96/backend/funcs/scst_scripts/x0_run_from_toml.py#L158)), and the backend serves only `umap_embeddings_50k.csv` ([get_data.py L818](https://github.com/thedonglab/VizIt/blob/a0aabb2197b8eea4acf1b32e393bd7fc4619fa96/backend/funcs/get_data.py#L818)). The full `umap_embeddings.csv` is written but never served. Drawing every cell needs a code change, so N (coordinator decision 2026-10-05).
- **DE N.** Markers and condition DE are tables computed at preparation (`31_clustermarkers.R`). Nothing is computed for a user's choice of cells.
- **selection N.** Plotly's box and lasso tools are in the toolbar, but the front end has no `onSelected` handler, so a selection goes nowhere.

### How to validate it yourself

1. Open `https://pd5d.yale.edu/views/geneview?dataset=PD5D_MTG_snRNAseq&gene=SNCA`, then sum the UMAP trace lengths in the console: `document.querySelector('.js-plotly-plot').data.reduce((a,t)=>a+(t.x?t.x.length:0),0)` gives 50,000. The dataset has 309,960 cells (m00).
2. In the Network tab, choosing another gene makes one `getexprdata?…&gene=<gene>` call (l01).
3. The URL query carries dataset and gene: copy it into a new tab (m12). Use "Download plot" for the SVG (m13).
4. Visium view: tick "Show H&E image" (f01, m07_m11). Cluster view: markers come from precomputed tables (f02, m10).
