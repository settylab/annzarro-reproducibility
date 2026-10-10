# Comparison tools: demos, and why each mark is what it is

Companion to `figures/fig_comparison.py` (the matrix) and `figures/COMPARISON_NOTES.md` (one source per cell). This file adds working links and the architectural reason behind each mark. Scanpy and Seurat are code libraries and are not covered here.

Links were checked on 2 October 2026 with `curl` (HTTP status, redirects followed). A 200 only shows that a page or file answers. For single-page apps (Vitessce, Cell Browser, Explorer) the dataset identifier was also checked against the project's source or index. "Slow" means more than 3 s to first byte. Where no live demo could be reached, that is stated.

Marks: Y documented; P partial, or only with extra work; N searched and not found. After this audit no mark for the seven tools below is "not verified". Source references use the repository and commit given in each section; `L<n>` in `COMPARISON_NOTES.md` refers to the older landscape notes.

## Summary

| Tool | Open it now | What it is for |
|---|---|---|
| CELLxGENE | [Tabula Sapiens, all cells (1.1M)](https://cellxgene.cziscience.com/e/53d208b0-2cfd-4366-9866-c3c6114081bc.cxg/) (slow, 8 s) | Hosted viewer for published datasets (Explorer), and a pip package for private data (Annotate) |
| Vitessce | [Visium lymph node with tissue image](https://vitessce.io/#?dataset=human-lymph-node-10x-visium) | Linked, configurable views of spatial and single-cell data, loaded straight from zarr |
| Cirrocumulus | no hosted demo found; run locally (below) | Large embeddings with collaborative annotation, as a server or a static site |
| iSEE | none reachable today (all five official instances failed) | Shiny panels over an R SingleCellExperiment, with linked selections |
| UCSC Cell Browser | [adultPancreas](https://cells.ucsc.edu/?ds=adultPancreas) | Public portal and static-site generator for annotated embeddings |
| ShinyCell | [ShinyCell tutorial app](http://shinycell1.ddnetbio.com) · [ShinyCell2 spatial showcase](https://shinycell.ouyanglab.com/) (slow, 6 s) | Generates a small Shiny app from a Seurat, SCE, h5ad or loom object |
| AnnZarro | [docs](https://annzarro.readthedocs.io) (currently 404, see below) · [repo](https://github.com/settylab/annzarro) | Linked cell and gene views with stored pairwise matrices over zarr AnnData |

## CELLxGENE

Two programs share the name and the matrix row mixes them. **Explorer** is the hosted viewer behind CELLxGENE Discover; its source is [`chanzuckerberg/single-cell-explorer`](https://github.com/chanzuckerberg/single-cell-explorer) (checked at dbbcef3, March 2026) and it is a fork of **Annotate** ([`chanzuckerberg/cellxgene`](https://github.com/chanzuckerberg/cellxgene), 76a39fc), which you install with `pip install cellxgene` and point at your own h5ad. Both are a Python server plus a browser client.

Links: [Discover](https://cellxgene.cziscience.com/) (200), [collections](https://cellxgene.cziscience.com/collections) (200), [Tabula Sapiens collection](https://cellxgene.cziscience.com/collections/e5f58829-1a66-40b5-a624-9046778e74f5) (200), [docs](https://cellxgene.cziscience.com/docs/01__CellxGene) (200), [Annotate repo](https://github.com/chanzuckerberg/cellxgene) (200), [Explorer repo](https://github.com/chanzuckerberg/single-cell-explorer) (200). No login. The old documentation repository now only redirects to the docs site.

| Column | Mark | How it works, or why not |
|---|---|---|
| cell × cell matrix | N | The server exposes X, `obs`, `var` and `obsm["X_*"]` embeddings only (`server/data_anndata/anndata_adaptor.py` L304-338 in Annotate). `obsp` never reaches the client. |
| gene × gene matrix | N | No `varp` access in either server (searched). Gene pairs are plotted as a bivariate scatter of expression, which is co-expression, not a stored matrix (L28). |
| focus drives panels | N | There is one embedding and a gene list; selecting a gene recolours it. No second panel is re-driven by a focused entity (L122). |
| all AnnData slots | N | Embeddings must be `obsm` keys starting `X_`, at most 30 of them (`server/common/constants.py` L35). Layers, `obsp`, `varp`, `varm` are not served. |
| lazy chunked reads | Y | Explorer converts datasets to TileDB `.cxg` arrays and opens slices on demand (`server/dataset/cxg_dataset.py` L13, L53-54). Annotate reads the whole h5ad into memory unless started with `--backed` (`anndata_adaptor.py` L154-165; default off, `server/default_config.py` L33). |
| remote stores | P | Explorer's arrays live on S3 (`cxg_dataset.py` L37, L118), but only for the datasets CELLxGENE hosts; you cannot point it at your own bucket. `cellxgene launch` accepts a URL to an h5ad and downloads it (L24). |
| spatial coordinates | Y | Explorer has a spatial mode (README, "Spatial Mode with Deep Zoom"; `client/src/components/Graph/Graph.tsx` L269). Annotate has none. |
| table filters mask plots | P | Categorical and continuous cut-offs cross-filter the one embedding (L26); there is no table of rows to filter. |
| annotation editing | Y | Annotate adds user categories to cells and exports them (L26). Explorer is read-only. |
| on-the-fly DE | Y | Welch t-test between two selections (`server/common/compute/diffexp_generic.py` L6-19; README "differential expression analysis"). |
| tissue image underlay | Y | Explorer draws the histology image under Visium spots with an opacity control, tiles served through OpenSeadragon (`Graph.tsx` L62, L320-324, L379-404). Annotate has none. |
| shareable view state | P | Annotations export as CSV and Explorer URLs identify a dataset, but layout and colouring are not restored from a link (L122). |
| plot export | Y | Explorer, Download menu, "current view": `Download.tsx` L30-32 dispatches a screen capture that saves `CELLxGENE_<layout>_emb.png` plus a legend PNG (`Graph.tsx` L590-692, `Graph/util.ts` L200). Annotate has no image export (`client/src` searched). **This corrects my earlier N, which searched Annotate only.** |
| desktop app | N | Annotate is a PyPI package (1.3.0, September 2024) that starts a local server. Old documentation says "Cellxgene Desktop", but there is no installer. |
| hosted multi-user | P | The hosted Explorer serves only curated Discover datasets; self-hosting is one server per dataset (L26-27). |
| static site, no server | N | A Python server answers every data request. |

## Vitessce

A JavaScript component library with a configuration file (JSON, or Python and R builders) that says which views to show, which data files feed them and how views are coordinated. Source: [`vitessce/vitessce`](https://github.com/vitessce/vitessce) (fed6719, September 2026).

Links: [web app](https://vitessce.io/) (200), [Visium lymph node](https://vitessce.io/#?dataset=human-lymph-node-10x-visium) (the `human-lymph-node-10x-visium` id is in `examples/configs/src/index.js`; its data, an AnnData zarr and an OME-zarr tissue image, both answer 200), [Habib 2017 snRNA-seq, zarr AnnData](https://vitessce.io/#?dataset=habib-2017) (id and zarr URL verified), [Codeluppi 2018 spatial](https://vitessce.io/#?dataset=codeluppi-2018), [docs](https://vitessce.io/docs/) (200), [platforms](https://vitessce.io/docs/platforms/) (200), [comparative analysis page](https://vitessce.io/docs/data-comparative/) (200). No login. Dataset fragments are rendered by JavaScript, so a 200 does not prove the view draws; the identifiers were checked against the source instead.

| Column | Mark | How it works, or why not |
|---|---|---|
| cell × cell matrix | N | The AnnData loader reads `X`, `obs`, `var`, `obsm`, layers (L33). No loader exists for `obsp`; a view type has to exist for a data type before it can be shown. |
| gene × gene matrix | N | Same, for `varp`. |
| focus drives panels | N | Coordination links views through more than 50 shared parameters (L34), for example the zoom or the selected gene set, but there is no focused-entity row that every view re-queries. A reviewer could argue P. |
| all AnnData slots | P | X, `obs`, `var`, `obsm`, layers; not `obsp`, `varp`, `varm` (L33). |
| lazy chunked reads | Y | Zarr stores are read by HTTP range over chunks, per gene or per cell group (L32, L123). |
| remote stores | Y | The browser reads zarr straight from any static host or bucket; the demo data above sit on Google Cloud Storage and `data-1.vitessce.io`. |
| spatial coordinates | Y | SpatialData and spot or segmentation coordinates are first-class (L31, L33). |
| table filters mask plots | P | Cell-set selections restrict other views (`obsSets`, L123), but there is no row table to filter. |
| annotation editing | P | Users can build cell sets from selections, import them and download them as JSON or CSV (`packages/view-types/obs-sets-manager/src/ObsSetsManagerSubscriber.js` L496-595). They live in view state and are not written back to the dataset. |
| on-the-fly DE | N | Comparative results are displayed from precomputed tables (docs "Comparative Analysis", L7-10). A browser-only app has no compute back end. |
| tissue image underlay | Y | OME-zarr and OME-TIFF layers are drawn under spots (L33, L150); see the lymph node demo. |
| shareable view state | Y | The whole view configuration is JSON, and can be put in a URL (L34). |
| plot export | N | No screenshot or image-save code in `packages/` (searched for `toDataURL`, `toBlob`, `saveAs`). The per-view download menu (`packages/vit-s/src/TitleInfo.js` L118-136) links the source data files. |
| desktop app | N | The platforms page lists web app, React component, Jupyter widget and R widget only. |
| hosted multi-user | P | Used inside portals such as HuBMAP, but Vitessce itself has no accounts or server (L32). |
| static site, no server | Y | Because every loader is a browser-side zarr or file reader, a static host is enough; the GitHub Pages tutorial in the docs does exactly this. |

## Cirrocumulus

A Python and JavaScript tool from the Klarman Cell Observatory. It runs as a local command (`cirro launch`), as a server with a database and logins (`cirro serve`), or as static files. Source: [`klarman-cell-observatory/cirrocumulus`](https://github.com/klarman-cell-observatory/cirrocumulus) (cae75c9, August 2026).

Links: [docs](https://cirrocumulus.readthedocs.io/en/latest/) (200), [repo](https://github.com/klarman-cell-observatory/cirrocumulus) (200), [commands reference](https://github.com/klarman-cell-observatory/cirrocumulus/blob/master/docs/commands.rst) (200). The Broad-hosted instance named in older material (`cirrocumulus.apps.broadinstitute.org`) does not resolve, and a web search found no public demo. To see it, follow the docs front page: `pip install cirrocumulus`, then `cirro launch pbmc3k.h5ad` (the docs link the PBMC 3k and Visium lymph node example data).

| Column | Mark | How it works, or why not |
|---|---|---|
| cell × cell matrix | N | The server's aggregators take X, `obs`, `obsm` (`embedding_aggregator.py`, `feature_aggregator.py`); no `obsp` path (L57). |
| gene × gene matrix | N | No `varp` path (L57). |
| focus drives panels | N | Panels share a search and a filter; no focused row (L127). |
| all AnnData slots | P | `varm` appears only for DE results (L57, L127). |
| lazy chunked reads | Y | `prepare_data` writes a layout "for efficient partial dataset retrieval over a network using limited memory" (`docs/commands.rst` L31-32); the zarr reader pulls one gene at a time with `get_orthogonal_selection` (`zarr_dataset.py` L22-23) and the parquet reader one file per key (`parquet_dataset.py` L63-68). |
| remote stores | Y | Server mode reads from S3, GCS or Azure paths (L55). |
| spatial coordinates | Y | Xenium and `--spatial` Visium input (L55; `docs/header.rst` L47). |
| table filters mask plots | Y | Saved AND/OR filters restrict every chart (L56). |
| annotation editing | Y | Real-time collaborative cell-type annotation, stored in the database (L56). |
| on-the-fly DE | Y | Server computes differential expression for selections (L56; `cirrocumulus/diff_exp.py`). |
| tissue image underlay | Y | The image chart draws the tissue image under points (`src/ImageChart.js`; L56). |
| shareable view state | Y | "Copy Link" puts the visualisation state in a URL (L56). |
| plot export | Y | Toolbar "Save Image" menu offers PNG and SVG (`src/ChartToolbar.js` L250-271); dot plots and composition plots have their own (`DotPlotCanvas.js` L351-415). |
| desktop app | N | pip install or server; no application bundle. |
| hosted multi-user | Y | `cirro serve` with MongoDB and Google or Okta login (L55). |
| static site, no server | Y | The docs describe a static-website mode on S3 or GCS buckets using a prepared jsonl dataset (`docs/installation.rst` L113-128; L55). Annotation and DE need the server. |

## iSEE

An R/Bioconductor package. A Shiny server process holds a `SummarizedExperiment` in memory and re-renders panels as the user interacts; selections flow between panels through a declared link graph. Source: [`iSEE/iSEE`](https://github.com/iSEE/iSEE) (f6c1903, July 2026).

Links: [docs](https://isee.github.io/iSEE/) (200), [basic vignette](https://isee.github.io/iSEE/articles/basic.html) (200), [big data vignette](https://isee.github.io/iSEE/articles/bigdata.html) (200), [Bioconductor page](https://bioconductor.org/packages/release/bioc/html/iSEE.html) (200), [repo](https://github.com/iSEE/iSEE) (200). **Live demos: none reachable.** The README's five instances (`marionilab.cruk.cam.ac.uk/iSEE_allen`, `_tcga`, `_pbmc4k`, `_cytof`, and `shiny.imbei.uni-mainz.de:3838/iSEE`) returned HTTP 503 or timed out on 2 October 2026, so they are not listed as demos. Local fallback: `BiocManager::install("iSEE")`, then `iSEE(sce)` on any SingleCellExperiment (vignette "basic").

| Column | Mark | How it works, or why not |
|---|---|---|
| cell × cell matrix | N | Panels read assays, `colData`, `rowData` and `reducedDims`; no `colPairs` use (L66). |
| gene × gene matrix | N | No `rowPairs` use (L66). |
| focus drives panels | P | A clicked table row or a brushed region is transmitted to child panels (L64); this is the nearest precedent to AnnZarro's focus, but only for gene or sample choice, not a matrix row (L128). |
| all AnnData slots | P | Assays and reduced dimensions; no pairwise slots (L128). |
| lazy chunked reads | P | Assays may be file-backed `HDF5Matrix` objects "retrieved on demand" (`vignettes/bigdata.Rmd` L86-88); everything else stays in memory. Earlier N was too strict. |
| remote stores | N | Only local files are used (`vignettes/bigdata.Rmd` L88); no object-store access in `R/`. |
| spatial coordinates | N | No spatial-aware panel in `R/` (searched). Coordinates could be stored as a reducedDim and drawn in a `ReducedDimensionPlot`, which is a workaround, not support. |
| table filters mask plots | Y | DT tables with column filters, and the selection is transmitted to linked plots (L64, L128). |
| annotation editing | N | No panel writes to `colData`; results leave only as an RDS dump or generated code (`R/observers_general.R` L74). |
| on-the-fly DE | N | "iSEE relies primarily on precomputed values" (`vignettes/basic.Rmd` L126). DE tables come from the separate iSEEde package. |
| tissue image underlay | N | No image layer in `R/` (searched). |
| shareable view state | Y | The panel configuration can be downloaded or restored, and shows as code (L65, L128). |
| plot export | Y | "Download panel contents" produces a zip of panel plots as PDF (`R/outputs_general.R` L39-75; `R/family_DotPlot.R` L1101). Vector PDF, not PNG or SVG; counted as Y. |
| desktop app | N | Runs from R. |
| hosted multi-user | Y | Standard Shiny Server deployment (L128). One R process per session. |
| static site, no server | N | A live R process computes each panel; there is nothing to serve statically. |

## UCSC Cell Browser

A Python tool (`cbBuild`) that converts a matrix and metadata into a directory of static files (JSON, per-gene binary expression, coordinates) plus a JavaScript viewer. The UCSC-run portal at cells.ucsc.edu is one deployment of the same code. Source: [`ucscGenomeBrowser/cellBrowser`](https://github.com/ucscGenomeBrowser/cellBrowser) (a11af81, 29 September 2026). Documentation cited below is the repository's `docs/` at that commit; some newer pages (for example differential expression) are not yet published on readthedocs.

Links: [portal](https://cells.ucsc.edu/) (200), [adultPancreas](https://cells.ucsc.edu/?ds=adultPancreas) (dataset index entry and `dataset.json` verified), [Brain Cut&Tag RNA, ATAC and Spatial](https://cells.ucsc.edu/?ds=brain-spatial-omics) (a collection; verified in the index; whether the background image shows was not checked), [docs](https://cellbrowser.readthedocs.io/en/master/) (200), [repo](https://github.com/ucscGenomeBrowser/cellBrowser) (200). No login to browse; accounts are optional for annotations.

| Column | Mark | How it works, or why not |
|---|---|---|
| cell × cell matrix | N | `cbBuild` ingests expression, metadata and coordinates; no `obsp` (L40). |
| gene × gene matrix | N | Same (L40). |
| focus drives panels | N | One plot, optionally split in two panes sharing a selection (L124). |
| all AnnData slots | P | X or one layer, `obs`, `obsm`, some `uns` (L40). |
| lazy chunked reads | Y | The browser requests one gene's bytes with an HTTP `Range` header from a pre-indexed binary file (`src/cbPyLib/cellbrowser/cbWeb/js/cbData.js` L192-224); the docs require servers to support byte ranges (`docs/advanced.rst` L10-13). |
| remote stores | P | The built directory can be hosted on S3, GCS or Azure static hosting (`docs/internet.rst` L9-13), but viewer and files are served together; h5ad and zarr are not read in place. |
| spatial coordinates | Y | Reads spatial coordinates from `uns['spatial']` and `obsm` (L40). |
| table filters mask plots | P | Edit > Find Cells and legend checkboxes select by metadata or expression; matches stay lit and the rest dim (`docs/ui/analysis.rst` L24-32). There is no table and no masking of other plots. |
| annotation editing | Y | Edit > Name selection stores a custom annotation field in the browser, synced and shareable by link with a free account; the dataset files are not changed (`docs/ui/accounts.rst`). Earlier P relied on an older note. |
| on-the-fly DE | P | A Wilcoxon test runs on a server compute backend; without one the tool shows placeholder statistics (`docs/ui/diffexp.rst` L1-8, L84-90). It is not part of a plain static deployment. |
| tissue image underlay | Y | `loadBackgroundImage` draws a JPEG behind the coordinates for spatial datasets (`cbData.js` L573, L645-652). |
| shareable view state | Y | The URL carries colouring (`meta`, `gene`), layout, zoom, selection, palette and split view (`cellBrowser.js` L5659-5661, L5935, L2921). Earlier P ("`ds=` only") was wrong. |
| plot export | Y | File menu: "Download bitmap image (PNG)" and "Download vector image (SVG)" (`cellBrowser.js` L4516-4517). |
| desktop app | N | A website; no application found. |
| hosted multi-user | Y | The public portal serves more than 1,600 datasets (L39). |
| static site, no server | Y | The output is plain files; "no backend server needed" (L39; `docs/basic_usage.rst` L28). Account features and DE need extra services. |

## ShinyCell

An R package that writes a small Shiny app for one dataset: the expression matrix goes into an HDF5 file, the metadata and configuration into RDS files, and a generated `server.R` and `ui.R` define fixed tabs (cell info against gene expression, coexpression, violin or box plots, proportions, bubble or heatmap). ShinyCell2 adds spatial, scATAC-seq and multi-omic tabs. Sources: [`SGDDNB/ShinyCell`](https://github.com/SGDDNB/ShinyCell) (5c61db7, April 2025) and [`the-ouyang-lab/ShinyCell2`](https://github.com/the-ouyang-lab/ShinyCell2) (33bfc8b, June 2025).

Links: [tutorial app](http://shinycell1.ddnetbio.com) (200, 1 s), [multi-dataset tutorial app](http://shinycell2.ddnetbio.com) (200, 5 s; despite the host name this is the ShinyCell multi-dataset tutorial, not ShinyCell2), [ShinyCell2 showcase with spatial data](https://shinycell.ouyanglab.com/) (200, 6 s), [ShinyCell repo](https://github.com/SGDDNB/ShinyCell) (200), [ShinyCell2 repo](https://github.com/the-ouyang-lab/ShinyCell2) (200), [cloud deployment tutorial](https://htmlpreview.github.io/?https://github.com/SGDDNB/ShinyCell/blob/master/docs/4cloud.html) (200), [ShinyCell2 spatial tutorial](https://htmlpreview.github.io/?https://github.com/the-ouyang-lab/ShinyCell2-tutorial/master/docs/tutSpatial.html) (200). All are plain HTTP or HTTPS pages without login; the apps may sleep and start slowly.

| Column | Mark | How it works, or why not |
|---|---|---|
| cell × cell matrix | N | The builder writes expression and metadata only (no `obsp`, L46). |
| gene × gene matrix | N | Same (L46). |
| focus drives panels | N | Tabs are independent; no cross-plot linking (L46). |
| all AnnData slots | P | `obsm` embeddings and expression, plus layers with extra work (L125). |
| lazy chunked reads | P | Expression sits in HDF5 on disk and only plotted genes are read (L45; ShinyCell2 README FAQ "stored on disk and not on memory"). The reported scale still assumes the build step fits in RAM, hence P. |
| remote stores | N | Files are read from the app directory; URLs appear only in the example-data downloader (`R/getExampleData.R`). |
| spatial coordinates | P | ShinyCell proper has none; ShinyCell2 adds spatial tabs (L45; ShinyCell2 README FAQ). |
| table filters mask plots | N | No data table and no filter conditions over plots (L125); at most a per-plot cell subset on one metadata field. |
| annotation editing | N | Metadata is edited only at build time (`modMetaName.R`, `addMeta.R`). |
| on-the-fly DE | N | No DE code in either package; ShinyCell2 offers a Wilcoxon or t-test p-value overlay on violin plots (`R/writer2.R` L563), which is not differential expression. |
| tissue image underlay | P | ShinyCell2 only: `R/writer0.R` L863-869 draws a `bg_image` under spatial points. |
| shareable view state | N | No link or file restores a view (L125). |
| plot export | Y | Each plot has PDF and PNG download buttons (`R/writer.R` L705-760 via `ggsave`; README: "export visualisations as PDF or PNG"). |
| desktop app | N | The package makes a Shiny app to run in R or on a server. |
| hosted multi-user | Y | shinyapps.io, Shiny Server or cloud (L45; cloud tutorial above). |
| static site, no server | N | Every plot is drawn by an R process. |

## AnnZarro, for reference

Docs: https://annzarro.readthedocs.io **returned 404 on 2 October 2026** (the Read the Docs project page exists, so the build or the project slug needs checking before anyone cites this URL). Repository: [settylab/annzarro](https://github.com/settylab/annzarro) (200, GPL-3.0 on GitHub; the research note L11 and the lead's note disagree about the licence, which is not in the figure). Releases: [GitHub releases](https://github.com/settylab/annzarro/releases) (200). Plot export is documented in the repository's `docs/user-guide/export.md`.

What it does differently. It reads zarr AnnData lazily, from local paths or `s3://`, `gs://` and `https://`, and exposes `obsp`, `varp`, `varm` as well as X, layers, `obs`, `var` and `obsm`. A stored cell × cell or gene × gene matrix becomes a colour or axis in any panel, and one click sets a focused cell or gene that every linked panel re-queries, which fetches one matrix row at a time. Panel sets and deep links keep layout, panel settings and focus, and a server process serves many users. It also ships as an Electron desktop app that starts its own local server, so users need no server setup. Plot export is PNG, JPEG, WEBP or SVG at a chosen size.

What it lacks, against tools in this matrix:
- Annotation editing. It is read-only by design. CELLxGENE Annotate, Cirrocumulus and the UCSC Cell Browser let users label cells.
- On-the-fly differential expression. It computes no statistics. CELLxGENE, Cirrocumulus and (with a back end) the UCSC Cell Browser do.
- Tissue image underlays. Spatial coordinates work as axes, but no histology image is drawn beneath them. CELLxGENE Explorer, Vitessce, Cirrocumulus and the UCSC Cell Browser do this.
- A static-site mode. A Python server is required, whereas Vitessce, Cirrocumulus (partly) and the UCSC Cell Browser can be plain files on a web host.

SVG exports from AnnZarro embed the scatter points as a bitmap (WebGL), so only axes and labels are vector (docs `export.md`).

## Marks changed in this audit

Relative to the matrix as of commit 81006f8:

- CELLxGENE: lazy chunked `?`→Y; spatial `?`→Y; image underlay `?`→Y; plot export N→Y (the earlier N had searched Annotate and missed the hosted Explorer's PNG download).
- Vitessce: annotation editing `?`→P; on-the-fly DE `?`→N.
- Cirrocumulus: lazy chunked `?`→Y.
- iSEE: lazy chunked N→P (file-backed assays); remote, spatial, annotation, DE, image `?`→N.
- UCSC Cell Browser: lazy `?`→Y; remote `?`→P; table filters `?`→P; annotation P→Y; DE `?`→P; image `?`→Y; shareable view state P→Y.
- ShinyCell: remote, annotation, DE `?`→N; image underlay `?`→P.

Scanpy / Seurat keep their remaining `?` marks (not audited here).
