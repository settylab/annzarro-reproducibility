# Comparison matrix (Fig. 1c, `fig_comparison`): cell values and sources

Regenerate: `.venv/bin/python figures/fig1_overview.py` (the manuscript figure, `manuscript/figures/fig1_overview.{pdf,png}`); `.venv/bin/python figures/fig_comparison.py` writes the matrix alone to `manuscript/figures/fig_comparison.{pdf,png}` for review.
The mark strings live in `TOOLS` in the script; keep this file in sync with them.

`L<n>` = line n of the landscape research notes
`scratchpad/notes/05_landscape_and_format.md` (session d0efd83a; A.1 per-tool notes L16 to L113, A.2 matrix L115 to L138).
"Lead correction" = the authoritative corrections to that research given with the figure brief (2026-10-02).

Marks: Y filled (documented), P half (partial, or only by writing code), N open (searched docs and/or source, not found), ? dash (not verified).
N means "not found", not proof of absence (L3).

Tools dropped: Loupe, BBrowser, SCope, Single Cell Portal, Kana, napari-spatialdata, scViewer, CellView, Cellenics (mostly `?` or out of scope; not in the brief's list). The body text still names the ones that were checked.

## Columns

| Group | Column | Definition used |
|---|---|---|
| Relationships | cell × cell matrix as colour or axis | a stored obsp (or SCE colPairs) row becomes a colour or axis in the GUI |
| Relationships | gene × gene matrix as colour or axis | same for varp (rowPairs) |
| Relationships | focused cell/gene drives linked panels | one selected cell or gene re-drives other panels (A.2 "Focused-entity" column; iSEE row click is the precedent) |
| Data | all AnnData slots incl. obsp/varp/varm | X, layers, obs, var, obsm, varm, obsp, varp all reachable |
| Data | lazy chunked reads | data read in slices on demand rather than loaded whole |
| Data | remote stores (S3, GCS, HTTP) | reads data from object storage / HTTP |
| Data | spatial coordinates | spatial positions shown as plot axes |
| Work | table filters mask plots | filter conditions restrict what linked plots show |
| Work | annotation editing | user labels written back |
| Work | on-the-fly DE | differential expression computed in the session |
| Work | tissue image underlay | histology / image layer under spatial points |
| Sharing | shareable view state | link or file restores the view |
| Sharing | plot export | the user downloads a plot from the GUI as an image (PNG, SVG or other image/PDF), without writing code |
| Deploy | desktop app | a downloadable application; no server setup by the user (every tool can run locally, so "local" alone is not scored) |
| Deploy | hosted multi-user | one deployment serves many users |
| Deploy | static site, no server | works as static files with no backend process |

## Scale group (added 2026-10-03)

The "lazy chunked reads" column moved from Data into a new Scale group with two new columns, and the
free-text "Reported scale" became "Largest documented dataset (cells)". Capability marks are unchanged.
Values come from comparison-auditor's per-tool files `notes/comparison/<tool>.md`, sections S1-S4
(checked 2026-10-03); AnnZarro from `figures/scale/README.md`. Mark changes proposed in those files
are not applied until the user validates them.

| Tool | every cell drawn | user picks a subset of cells | largest documented dataset |
|---|---|---|---|
| AnnZarro | Y | Y (reproducible subset, parts) | 95.6M (Tahoe-100M) |
| CELLxGENE | Y | Y ("Subset to currently selected cells") | 11.4M, label "served and drawn; Discover docs state 4.3M" (Discover mouse embryo timelapse; drawn in full by the hosted Explorer in 3 headless runs, 2026-10-04, notes/comparison/cellxgene.md; the docs' 4.3M is a submission/hosting policy) |
| Vitessce | Y | N (highlight only) | 1.28M (LuCA demo) |
| Cirrocumulus | Y | P (dim or shrink unselected) | 1.3M |
| iSEE | Y (downsampling optional, off by default) | Y | 68.6k |
| UCSC Cell Browser | Y | Y ("Only show selected") | 21.8M (PanSci "All", 21,786,931 cells; cells.ucsc.edu dataset.json sampleCount, verified by comparison-auditor and coordinator 2026-10-03); docs state only a 160M portal total |
| ShinyCell | Y | Y (per-plot toggle) | 162k (ShinyCell2 tutorial) |
| Scanpy / Seurat code | Y (Seurat rasterizes >100k, drops none) | P (by code) | 1.3M |

## Cell values

### AnnZarro
| Column | Mark | Source |
|---|---|---|
| cell × cell | Y | L12 (`cell-plot.js`: obsp feeds x, y, z or colour); L121 |
| gene × gene | Y | L12 (`gene-plot.js` varp mirrors obsp); L121 |
| focus drives panels | Y | L13 (deep link `focusedGene`, `focusedCell`); L121 |
| all slots | Y | L12; L121 (varm Y); L144 |
| lazy chunked | Y | L11 ("reads zarr AnnData lazily"); L121 |
| remote stores | Y | Lead correction: local zarr/h5ad and remote s3://, gs://, https:// zarr (settylab/annzarro#43). Note: body.tex Limitations ("Remote HTTP or S3 stores are not served by the data API") is now stale and must be updated. |
| spatial coordinates | Y | Lead correction (spatial coords as axes); body.tex Limitations "Plot vocabulary" |
| table filters | Y | Lead correction (arbitrary AND/OR, masks linked plots); L121 |
| annotation editing | N | Lead correction (read-only by design); L162 |
| on-the-fly DE | N | L164; body.tex Limitations ("computes no statistics") |
| image underlay | N | Lead correction (no image underlay); L157, L163 |
| shareable view state | Y | Lead correction (server-side shared panel sets + deep links with layout, panel configs, focus); L13 |
| plot export | Y | AnnZarro docs `docs/user-guide/export.md`: Plotly camera button (PNG), Plot Options > Export (PNG, JPEG, WEBP, SVG at a chosen size). SVG points are an embedded bitmap. |
| desktop app | Y | Electron app for Windows, macOS and Linux (GitHub releases); runs its own local server process, no server setup by the user. Author decision 2026-10-02. |
| hosted multi-user | Y | Lead correction (multi-user hosted server) |
| static site, no server | N | L11 (Flask backend required) |
| Reported scale | 95.6M cells (Tahoe-100M, every cell in one plot: `figures/scale/README.md`, `*.view.json`); 200k × 200k pairwise matrix by row | Updated 2026-10-03 from 1.17M. Earlier source: Lead brief; `figures/PERFORMANCE_NOTES.md` L60 (atlas 1.17M cells, gene column 1.75 s) and L43/L59 (dense 200k obsp row 305 ms). Supersedes L14/L121 "not benchmarked". |

### CELLxGENE (Annotate / Explorer)
| Column | Mark | Source |
|---|---|---|
| cell × cell | N | L28; L122 |
| gene × gene | N | L28 (bivariate gene scatter is co-expression, not a stored matrix) |
| focus drives panels | N | L122 ("N (bivariate gene scatter only)") |
| all slots | N | L25 (X + obsm `X_*` only; obsp/varp/varm not mentioned) |
| lazy chunked | Y | Hosted Explorer (`chanzuckerberg/single-cell-explorer` @ dbbcef3 `server/dataset/cxg_dataset.py` L13, L53-54) opens TileDB `.cxg` arrays and reads slices on demand. Annotate (`chanzuckerberg/cellxgene` @ 76a39fc `server/data_anndata/anndata_adaptor.py` L154-165) loads h5ad into memory unless `--backed` is set (`server/default_config.py` L33, default false). |
| remote stores | P | L24 (`cellxgene launch` takes a file or a URL; not a lazily read object store) |
| spatial coordinates | Y | Hosted Explorer: README "Spatial Mode with Deep Zoom" (Visium, Slide-seq V2), `client/src/components/Graph/Graph.tsx` L269 (`isSpatialMode`). Not in Annotate (`server/` has no spatial code, searched). |
| table filters | P | L26 (cross-filtering by cut-offs and categories); L122 |
| annotation editing | Y | L26 (Annotate adds user categorical annotation) |
| on-the-fly DE | Y | L26 (Welch t-test) |
| image underlay | Y | Hosted Explorer: `Graph.tsx` L62, L320-324, L379-404 (`imageUnderlay`, `imageOpacity`, OpenSeadragon tiles). Not in Annotate (searched). |
| shareable view state | P | L122 (annotations CSV; Explorer URL unverified) |
| plot export | Y | Hosted Explorer: `client/src/components/MenuBar/components/Download/Download.tsx` L30-32 ("Download current view" dispatches `graph: screencap start`), `Graph.tsx` L590-692 and `Graph/util.ts` L200 (writes `CELLxGENE_<layout>_emb.png` and a legend PNG). Not in Annotate (`chanzuckerberg/cellxgene` `client/src` searched for toDataURL, toBlob, png, svg: none). Corrects the earlier N, which searched Annotate only. |
| desktop app | N | Annotate is a PyPI package (`pip install cellxgene`; 1.3.0, 2024-09-12) that starts a local web server; https://github.com/chanzuckerberg/cellxgene README "Quick start" and https://cellxgene.cziscience.com/docs/01__CellxGene ("A PyPI package"). Old docs call it "Cellxgene Desktop" (cellxgene-documentation `desktop/quick-start.md`) but it is installed with pip, not a downloadable application; no packaged installer found. Not a discontinued app: no evidence of one. |
| hosted multi-user | P | L26 (hosted Explorer serves only curated Discover data); L27 (Gateway, one server per dataset) |
| static site, no server | N | L24 (Python server) |
| Reported scale | ≥1M cells | L24 ("at least 1 million cells", README) |

### Vitessce
| Column | Mark | Source |
|---|---|---|
| cell × cell | N | L33 (obsp not documented, not in any loader); L123 |
| gene × gene | N | L33; L123 |
| focus drives panels | N | L123; L146 (no focused-entity concept). Caveat: its coordination model links views on >50 parameters (L34), which is linking but not a focused row. |
| all slots | P | L33 (X, obs, var, obsm, layers; no obsp/varp/varm) |
| lazy chunked | Y | L32, L123 (HTTP range reads of zarr) |
| remote stores | Y | L32 (static web servers and cloud object storage) |
| spatial coordinates | Y | L31, L33 (SpatialData, obsSpots/obsLocations) |
| table filters | P | L123 (obsSets) |
| annotation editing | P | User-made cell sets: `packages/view-types/obs-sets-manager/src/ObsSetsManagerSubscriber.js` L496-572 (create, import) and L579-595 (download as JSON or CSV). Held in view state, not written back to the dataset. (`annotation-controller` is a story-telling feature, not cell labels.) |
| on-the-fly DE | N | https://vitessce.io/docs/data-comparative/ (source `sites/docs/docs/data-comparison.md` L7-10): comparative results are displayed from precomputed data; searched `packages/` for t-test and differential: none. |
| image underlay | Y | L33 (OME-Zarr/TIFF); L150; body.tex ("Vitessce and napari-spatialdata render tissue images") |
| shareable view state | Y | L34 (JSON view config via URL) |
| plot export | N | Searched `vitessce/vitessce` @ fed6719 (2026-09-30) `packages/` for toDataURL, toBlob, screenshot, saveAs: none. The per-view "Download" menu (`vit-s/src/TitleInfo.js` L118-136) links source data files, not the plot. |
| desktop app | N | https://vitessce.io/docs/platforms/ (source `sites/docs/docs/platforms.md`): web app, React component, Jupyter widget, R htmlwidget; no desktop application. |
| hosted multi-user | P | L32 (static sites and portals; no server with users) |
| static site, no server | Y | L32 |
| Reported scale | millions of points | L32 |

### Cirrocumulus
| Column | Mark | Source |
|---|---|---|
| cell × cell | N | L57 (no obsp by code search) |
| gene × gene | N | L57 (no varp) |
| focus drives panels | N | L127; L146 |
| all slots | P | L57 (varm only for DE results); L127 |
| lazy chunked | Y | `docs/commands.rst` L31-32 (`prepare_data` format "allows efficient partial dataset retrieval over a network ... using limited memory"); `cirrocumulus/zarr_dataset.py` L22-23 (`get_orthogonal_selection` per gene); `parquet_dataset.py` L63-68 (one parquet per key). @ cae75c9 |
| remote stores | Y | L55 (server mode on S3/GCS/Azure) |
| spatial coordinates | Y | L55 (Xenium input); L56 (spatial image overlay) |
| table filters | Y | L56 (saved AND/OR filters with provenance) |
| annotation editing | Y | L56 (real-time collaborative annotation) |
| on-the-fly DE | Y | L56 |
| image underlay | Y | L56 |
| shareable view state | Y | L56 ("Copy Link" JSON state) |
| plot export | Y | `klarman-cell-observatory/cirrocumulus` @ cae75c9 `src/ChartToolbar.js` L250-271 ("Save Image" menu: PNG, SVG); `src/DotPlotCanvas.js` L351-415 (PNG/SVG for dot plots). |
| desktop app | N | https://cirrocumulus.readthedocs.io/en/latest/ : installed with pip (`cirro launch`), or deployed as a server; no desktop application. |
| hosted multi-user | Y | L55 (`cirro serve`, MongoDB, Okta/Google auth) |
| static site, no server | Y | L55 (static website mode) |
| Reported scale | 1.3M cells | L56 |

### iSEE
| Column | Mark | Source |
|---|---|---|
| cell × cell | N | L66 (no colPairs hits) |
| gene × gene | N | L66 (no rowPairs hits) |
| focus drives panels | P | L64 (table row click changes plotted gene; selection transmission); L128 ("P", no pairwise matrix) |
| all slots | P | L128 (reducedDims, assays; no colPairs/rowPairs) |
| lazy chunked | P | `vignettes/bigdata.Rmd` L86-88: assays can be file-backed `HDF5Matrix` and are "retrieved on demand". reducedDims and colData stay in memory. Earlier N was "in-memory SummarizedExperiment" only. @ f6c1903 |
| remote stores | N | Searched `R/` and vignettes for remote or object-store access: only local `HDF5Matrix` files (`vignettes/bigdata.Rmd` L88). |
| spatial coordinates | N | Searched `R/` for spatial: no hits. No spatial-aware panel in core (coordinates could only be stored as a reducedDim and drawn in a `ReducedDimensionPlot`). |
| table filters | Y | L128 (DT tables); L64 (selections transmitted to panels) |
| annotation editing | N | Searched `R/`: panels never write to colData (`R/cleanDataset.R` is the only colData assignment, at start-up). Results leave the app only as the RDS memory dump and code export (`R/observers_general.R` L74). |
| on-the-fly DE | N | `vignettes/basic.Rmd` L126 ("relies primarily on precomputed values", except custom panels). DE tables exist only as the separate iSEEde package. |
| image underlay | N | Searched `R/` for image or background layers: none. |
| shareable view state | Y | L65 ("Display panel settings"); L128 |
| plot export | Y | `iSEE/iSEE` @ main `R/outputs_general.R` L39-75 and `R/observers_general.R` L245-262 ("Download panel contents": zip of panel plots as PDF; `.exportOutput` in `R/family_DotPlot.R` L1101 writes `pdf()`). Vector PDF, not PNG/SVG; counted as Y (a plot image downloaded from the GUI without code). |
| desktop app | N | https://isee.github.io/iSEE/ : R/Bioconductor package launching a Shiny app (`iSEE(sce)`); no downloadable application. |
| hosted multi-user | Y | L128 (Shiny server) |
| static site, no server | N | L62 (R/Shiny server) |
| Reported scale | not reported | L128 ("?") |

### UCSC Cell Browser
| Column | Mark | Source |
|---|---|---|
| cell × cell | N | L40 (no obsp in `cellbrowser.py`) |
| gene × gene | N | L40 |
| focus drives panels | N | L124 |
| all slots | P | L40 (X or one layer, obs, obsm, uns) |
| lazy chunked | Y | `src/cbPyLib/cellbrowser/cbWeb/js/cbData.js` L192-224 (HTTP `Range` requests per gene); `docs/advanced.rst` L10-13 (web server must support byte-range requests). @ a11af81 |
| remote stores | P | `docs/internet.rst` L9-13 and `docs/basic_usage.rst` L28: the `cbBuild` output directory can be hosted on any static server, including S3, GCS or Azure. Viewer and converted files are served together; h5ad or zarr are not read from a store directly. |
| spatial coordinates | Y | L40 (reads `uns['spatial']` and obsm coordinates) |
| table filters | P | `docs/ui/analysis.rst` L24-32: Edit > Find Cells and legend checkboxes select cells by metadata or expression; matches stay highlighted, the rest dim. No table, no masking of other plots. |
| annotation editing | Y | `docs/ui/accounts.rst` L1-40: Edit > Name selection writes a custom annotation field, kept in browser storage, synced and shareable by link with a free account. Not written into the dataset files. |
| on-the-fly DE | P | `docs/ui/diffexp.rst` L1-8 and L84-90: Wilcoxon rank-sum run on a server compute backend; without one the tool shows placeholder statistics. Not available in a plain static deployment. (Docs page not yet on readthedocs; cited from the repo.) |
| image underlay | Y | `cbData.js` L573 and L645-652 (`loadBackgroundImage` for spatial images drawn behind the coordinates). |
| shareable view state | Y | `cellBrowser.js` L5659-5661 (`gene`), L5935 (`layout`), L2921 (`select`), `changeUrl` calls for `meta`, `gene`, `zoom`, `split`, `pal`: the URL restores colouring, layout, zoom and selection. Earlier P ("ds= only") was wrong. |
| code export | ? | not covered |
| desktop or local | ? | not covered |
| hosted multi-user | Y | L39 (public site, >1,600 datasets) |
| static site, no server | Y | L39 ("no backend server needed") |
| Reported scale | 160M cells (portal total) | L39 (portal total, not per dataset) |

### ShinyCell (ShinyCell2 where noted)
| Column | Mark | Source |
|---|---|---|
| cell × cell | N | L46 (no obsp/varp in code search) |
| gene × gene | N | L46 |
| focus drives panels | N | L46 (fixed tabs, no cross-plot linking) |
| all slots | P | L125 (obsm Y, layers P) |
| lazy chunked | P | L45 (HDF5, only plotted genes loaded) |
| remote stores | N | Searched `R/` (ShinyCell, ShinyCell2): files are read from the app directory; URLs appear only in `getExampleData.R` (example download). |
| spatial coordinates | P | L45 (spatial added in ShinyCell2, preprint) |
| table filters | N | L125 |
| annotation editing | N | Searched `R/`: no code writes user labels; metadata is edited only at build time (`modMetaName.R`, `addMeta.R`). |
| on-the-fly DE | N | Searched `R/` for FindMarkers, wilcox, limma: only a p-value overlay choice (wilcox.test, t.test) on a violin plot in ShinyCell2 `R/writer2.R` L563, which is not differential expression. |
| image underlay | P | ShinyCell2 only (`the-ouyang-lab/ShinyCell2` @ 33bfc8b `R/writer0.R` L863-869 draws `bg_image` under the spatial points; `R/makeShinyCodes.R` L89-136). Not in ShinyCell. |
| shareable view state | N | L125 |
| plot export | Y | `SGDDNB/ShinyCell` `R/writer.R` L705-760 (generated app: PDF and PNG `downloadHandler` per plot via `ggsave`). |
| desktop app | N | https://github.com/SGDDNB/ShinyCell README: generates a Shiny app run in R or on a Shiny server; no downloadable application. |
| hosted multi-user | Y | L45 (shinyapps.io, Shiny Server, AWS) |
| static site, no server | N | L45 (R Shiny server) |
| Reported scale | ~30k cells per 8 GB RAM | L45 |

### Scanpy / Seurat (code)
| Column | Mark | Source |
|---|---|---|
| cell × cell | P | L111 (any slot incl. obsp via code; re-run per focus); L137 |
| gene × gene | P | L137 ("Y via code") |
| focus drives panels | N | L111 (changing the focused cell means re-running code) |
| all slots | Y | L137 |
| lazy chunked | P | L137 ("in-memory / backed") |
| remote stores | ? | not covered |
| spatial coordinates | ? | not covered |
| table filters | P | L137 (filtering via code) |
| annotation editing | P | via code (writing obs); inferred from L111 example (`adata.obs[...] = ...`) |
| on-the-fly DE | P | via code; L40 references Scanpy `rank_genes_groups` results |
| image underlay | ? | not covered |
| shareable view state | Y | L137 (scripts) |
| plot export | P | Plots are saved by code (`sc.pl.*(save=...)`, `plt.savefig`; Seurat `ggsave`); no GUI. |
| desktop app | N | Python and R libraries; no application. |
| hosted multi-user | N | L137 (deployment: local) |
| static site, no server | N | L137 |
| Reported scale | memory-bound library | L137 ("library-limited") |

## Judgement calls worth a second look
- Vitessce "focus drives panels" = N. Its coordination links views on >50 parameters; it has no focused-entity row. A reviewer may argue P. The caption says what the column means.
- iSEE "table filters" = Y from DT tables plus selection transmission (L64, L128).
- UCSC "spatial coordinates" = Y from `uns['spatial']` handling in source (L40), not from a screenshot.
- The research notes (L11) say AnnZarro is GPL-3.0+; the lead says MIT. Licence is not in the figure.

## Caption draft

**Fig. 1c | AnnZarro compared with other single-cell viewers.** Rows are tools; columns are capabilities grouped by job. Filled circle, documented; half-filled, partial or reachable only by writing code; open circle, searched in documentation and/or source code and not found; grey dash, not verified. The shaded columns (Relationships) are AnnZarro's distinct contribution: a stored cells × cells (obsp) or genes × genes (varp) matrix becomes a colour or axis, and the focused cell or gene selects which row is shown in every linked panel. No other graphical viewer examined does this; in Scanpy or Seurat it needs code and a re-run per focus. AnnZarro lacks annotation editing, on-the-fly differential expression, tissue image underlays and a static-site mode, all of which other tools offer. Reported scale is as stated by each project and is not a like-for-like benchmark: AnnZarro served 1.17M cells in a lab deployment and browsed a dense 200k × 200k pairwise matrix row by row (Fig. 7); the UCSC figure is a portal total across datasets. Sources for every cell are in Supplementary Note X (checked October 2026).
