## Candidate tools for extending the matrix (desk research, 2026-10-04)

This is a scout of 25 further single-cell and spatial viewers, made to decide which deserve a matrix row. The criteria: an interactive GUI for AnnData/SCE-like data, usable without code, maintained since 2024-10 or widely cited, and obtainable for testing. Scale claims are recorded with their sources. Nothing was installed or run; every entry rests on web pages, repositories and papers checked on 2026-10-04.

### Shortlist

| Tool | Recommendation | Effort | Why |
|---|---|---|---|
| [TissUUmaps](#tissuumaps) | **ADD** | M | Open source (MIT) and maintained. It loads h5ad directly. It draws every point with WebGL: the paper benchmarks 16.7M points (transcript markers) without subsampling. It overlays graph edges, the closest thing to an obsp view in this list, and links spatial and UMAP selections. It is the nearest published scale competitor in spatial work. |
| [ManiVault / Cytosplore](#cytosplore-manivault-cytosplore-viewer-hsne) | **ADD** | L | Open source (LGPL-3.0) desktop app, maintained (v1.5.1, 2026-09), and it reads h5ad. Its HSNE design shows 15M cells (CyTOF) through hierarchical landmarks rather than drawing every cell. That is the strongest published counter-design to drawing every cell, so reviewers will expect it. |
| [VizIt](#vizit-formerly-braindataportal) | **ADD (optional)** | M | The newest multi-view portal framework (arXiv 2026-09, GPL-3.0). Its linked navigation between genes, cell types and regions is the closest conceptual neighbour to AnnZarro's focus-driven views. It works over precomputed tables, not obsp/varp, and it subsamples UMAP points. It needs Seurat .rds input and Docker. |
| [Cellenics / Trailmaker](#cellenics-trailmaker) | MENTION (ADD only if the user provides an account) | M | Widely used free hosted analysis platform. It needs a sign-up, which this audit may not create; its free quota is 0.3 to 0.5M cells; and data must enter through its own pipeline. |

Mention in the text only:
- scSVA: the prior art for "hundreds of millions to a billion cells". Its demo is 274,000 cells upsampled to 100 million and drawn binned; it is **not comparable** (binned density only: no mark is an identifiable cell; evidence in [scsva/evidence/](scsva/evidence/README.md)), and it has been unmaintained since 2019.
- BBrowserX (BioTuring): claims 10M+ cells; proprietary and sales-gated.
- Xenium Explorer and MERSCOPE Vizualizer: vendor viewers tied to their own instrument formats.
- cellxgene VIP and cellxgene-gateway: CELLxGENE engine, so they would duplicate that row.
- WebAtlas: Vitessce engine, a duplicate.
- ASAP: hosted analysis pipeline that claims "millions of cells".
- TooManyCellsInteractive: tree view, benchmarked to 483k cells against CELLxGENE and Cirrocumulus.
- Partek Flow: commercial, no published scale claim.
- Galaxy interactive tools: wrap existing rows.

Skip: Azimuth (no GUI successor), EBI Single Cell Expression Atlas (a database, not for the user's own data), SCelVis and Cellar (unmaintained, no scale story), Pagoda2 web app (needs R to build its input), Giotto Viewer (abandoned), SODB/SOView (a portal), the SpatialData web viewer (none exists), xCell (Cahan lab; unpublished and unlicensed), CZ CELLxGENE successors (already the CELLxGENE row, or not GUIs).

### Per-tool notes

#### TissUUmaps
- What: Uppsala University (Wählby lab, SciLifeLab BIIF); GPU (WebGL) browser viewer for spatial omics markers/cells over gigapixel images; desktop app, local server, or Jupyter.
- Engine/duplicate: own engine (OpenSeadragon images + custom WebGL marker renderer). Not a duplicate.
- Paper: Pielawski N, Andersson A, Avenel C, Behanova A, ... TissUUmaps 3: Improvements in interactive visualization, exploration, and quality assessment of large-scale spatial omics data. Heliyon 9(5):e15306 (2023). DOI 10.1016/j.heliyon.2023.e15306 (Crossref-verified, citations 50).
- Repo / site: https://github.com/TissUUmaps/TissUUmaps3 (last release 3.2.1.11 2024-10-24; last commit 2025-05-16; MIT). Successor https://github.com/TissUUmaps/TissUUmaps = TissUUmaps 4, rewrite in beta (tissuumaps@4.0.0-beta.1 2026-09-30; last commit 2026-10-01; MIT).
- Inputs: CSV markers, h5ad (drag-and-drop; coords from obsm/spatial, X_spatial, X_umap, tSNE, UMAP; X must be sparse CSC), .tmap projects, images (pyramidal TIFF via libvips).
- Scale claim: "10^7+ data points" (abstract) and benchmark up to "16.7 M points" rendered "without relying on data sub-sampling" (Heliyon paper, PMC10149187, sec. 3.2.3). Note these are transcript markers, not cells.
- Rendering: every point drawn in TU3 (TU1 quad-tree subsampling explicitly disabled for the benchmark); WebGL point sprites or instanced quads.
- Relationship views: partial. Draws "millions of anti-aliased edges between markers" (graph/connectivity overlay, closest thing to obsp in this list); feature-space plugin links spatial and UMAP selections. No gene x gene (varp) view, no focus-driven neighbour panels.
- Testable how: local `pip install "TissUUmaps[full]"` (+conda libvips) or .dmg/.exe installers; hosted TU4 beta https://tissuumaps.github.io/TissUUmaps/ (HTTP 200); no account.
- Recommendation: ADD as row: maintained, open, loads h5ad directly, and its draw-all-points WebGL scale claim (16.7M) is the closest published competitor to AnnZarro's in the spatial space, so a reviewer will ask.
- Effort for full treatment: M (half day): pip install + h5ad scale ladder is direct; extra hour to decide TU3 (stable) vs TU4 (beta) and to convert ladder X to CSC; h5ad path is whole-file in browser memory so expect an early ceiling.

#### Cytosplore / ManiVault (Cytosplore Viewer, HSNE)
- What: LUMC + TU Delft visual-analytics group (Höllt, Lelieveldt, Vilanova); ManiVault Studio is a plugin-based C++/Qt/OpenGL desktop framework; Cytosplore Viewer (Allen brain cell-type atlases, e.g. HMBA) is built on it; original Cytosplore targeted CyTOF.
- Engine/duplicate: own engine. Not a duplicate.
- Paper: Vieth A, Kroes T, Thijssen J, ... ManiVault: A Flexible and Extensible Visual Analytics Framework for High-Dimensional Data. IEEE TVCG (2023/2024). DOI 10.1109/TVCG.2023.3326582 (Crossref-verified, citations 5). Scale paper: van Unen V, Höllt T, Pezzotti N, ... Visual analysis of mass cytometry data by hierarchical stochastic neighbour embedding reveals rare cell types. Nat Commun 8:1740 (2017). DOI 10.1038/s41467-017-01689-9 (citations 222). Also Höllt T et al. Cytosplore, Comput Graph Forum 2016, DOI 10.1111/cgf.12893 (citations 128).
- Repo / site: https://github.com/ManiVaultStudio/core (last release v1.5.1 2026-09-14; last commit 2026-09-25; LGPL-3.0); binaries https://github.com/ManiVaultStudio/Releases (1.5.1 Windows 2026-09-14, 1.5.0 macOS 2026-04-17); https://www.manivault.studio/ (200); https://viewer.cytosplore.org/ (200).
- Inputs: plugin loaders: HDF5Loader ("10X, TOME and H5AD"), CSV, FCS, binary, images, volumes, Cell Annotation Schema taxonomies.
- Scale claim: "data sets, consisting of up to 15 million cells" with Cytosplore+HSNE (van Unen 2017, PMC5700955; CyTOF, ~30 markers). ManiVault scatterplot plugin: "Millions of points" (manivault.studio, no number).
- Rendering: HSNE shows landmark subsets per hierarchy level and drills down to single cells on selection ("without the need for downsampling" in the sense of no random subsample, but the overview is NOT every cell drawn); plain scatterplot plugin draws all points (OpenGL) with optional density mode.
- Relationship views: multiple linked views and on-the-fly re-embedding of selections; HSNE hierarchy is a cell-similarity structure, but no user-supplied obsp/varp graph view and no gene x gene panel found.
- Testable how: local installers (Win/macOS/Linux), no account; Cytosplore Viewer projects downloadable from viewer.cytosplore.org.
- Recommendation: ADD as row: maintained, open source, loads h5ad, and HSNE's 15M-cell hierarchical-landmark approach is the strongest published counter-design to AnnZarro's draw-every-cell claim; visualisation reviewers will expect it.
- Effort for full treatment: L (day+): native desktop install plus plugin selection, h5ad loader limits unknown (likely in-RAM; Tahoe-scale will need a subsampled ladder), HSNE precompute per ladder step, and screenshot evidence across many plugin views.

#### VizIt (formerly BrainDataPortal)
- What: Dong lab (Yale) open-source self-hostable framework for multi-view portals over single-cell, spatial, epigenomic and QTL/GWAS data; flagship deployment is the Parkinson's Cell Atlas (https://pd5d.yale.edu).
- Engine/duplicate: own engine (React + plotly.js/echarts/d3 frontend, Python backend with SQLite/JSON stores); not a duplicate.
- Paper: Zhang CC, Lou Y, Yuan J, ..., Dong X. "VizIt: A multi-view framework for exploring single-cell, spatial, and genetic data online." arXiv:2609.04658 (2026-09-04), doi:10.48550/arXiv.2609.04658 (DataCite registration pending, so not resolvable on Crossref; citations 0). Code archived at doi:10.5281/zenodo.21925072.
- Repo / site: https://github.com/thedonglab/VizIt, docs https://thedonglab.github.io/VizIt/; last release v1.0.0 2026-08-13; last push 2026-09-08; licence GPL-3.0; 2 stars.
- Inputs: Seurat .rds (scRNA, Visium/Xenium/MERFISH), preprocessed by its R/Python scripts into SQLite + per-gene JSON; QTL/GWAS summary tables. No direct h5ad loading.
- Scale claim: none for a single dataset. The atlas has "millions of cells and spatial locations across multiple human brain regions" (arXiv paper, Fig. 1c legend), but that is a portal total. The tutorial dataset is about 50,000 cells.
- Rendering: downsampled. The prep guide lists "UMAP embedding sampling (Subset UMAP points for faster loading)" (https://github.com/thedonglab/VizIt/blob/main/docs/prepare_dataset/scrnaseq.md). Plotting is plotly SVG/WebGL.
- Relationship views: partly. Reciprocal entity navigation (gene <-> cell type <-> peak <-> region <-> variant), driven by precomputed DE/QTL tables, with shareable view URLs. That is conceptually close to "focus-driven linked views", but over summary tables, not obsp/varp cell x cell or gene x gene matrices.
- Testable how: local docker compose (docker compose up; refresh_db); hosted demo https://pd5d.yale.edu (HTTP 200 today).
- Recommendation: MENTION in text only, possibly ADD later if a reviewer asks. It is the newest (Sept 2026) multi-view single-cell portal and the closest conceptual neighbour to AnnZarro's linked relationship views, but it is a precomputed-portal builder with point subsampling, not a scale competitor. Cite it in related work as "entity-centric linked navigation".
- Effort for full treatment: M. Docker up plus the R prep script on a Seurat object is a few hours; the scale ladder needs a Seurat .rds per rung and deliberately subsamples UMAP, so the "every cell drawn" column is a known No.

#### Cellenics / Trailmaker
- What: Cloud scRNA-seq analysis platform from Biomage and Harvard Medical School DBMI (Cellenics, open source). Biomage was acquired by Parse Biosciences and its hosted instance was rebranded Trailmaker.
- Engine/duplicate: own platform (React UI, deck.gl/vega embeddings, reuses @vitessce/heatmap components; R/Python workers). Not a duplicate row, but partly built from Vitessce components.
- Paper: none (no peer-reviewed or Crossref-indexed Cellenics/Trailmaker paper found).
- Repo / site: https://github.com/hms-dbmi-cellenics/ui (+ api, worker, pipeline); last release ui 0.90.1 2026-07-29; last commit 2026-07-29; licence MIT. Hosted: https://cellenics.hms.harvard.edu, https://scp.biomage.net; Trailmaker https://www.parsebiosciences.com/data-analysis/ (marketed "It's free!").
- Inputs: 10x mtx trio (barcodes/features/matrix), 10x h5, Parse Evercode output, Seurat objects (added 2023); other formats via conversion guides.
- Scale claim: free academic instance "up to 500,000 cells" (https://www.biomage.net). Older HMS/community material says "up to 300,000 cells" free. Both figures are quota caps, not tested ceilings.
- Rendering: not documented. Embedding is deck.gl/vega-webgl; no downsampling statement found.
- Relationship views: no obsp/varp. There are linked panels (embedding, heatmap, gene list, cell sets), but they are not focus-driven relationship views.
- Testable how: hosted, account needed (free sign-up). cellenics.hms.harvard.edu 200, scp.biomage.net 200 today; trailmaker.parsebiosciences.com timed out from here. Self-hosting needs the full AWS-style stack (api+worker+pipeline+inframock), so it is not practical.
- Recommendation: MENTION in text only. It is an analysis pipeline-as-a-service with a viewer, not an exploration viewer. Inputs go through its own QC pipeline, so a precomputed 95.6M-cell h5ad cannot be loaded, and the free tier stops at 0.3 to 0.5M cells.
- Effort for full treatment: M. Needs an account, an upload, and a pipeline run on a small dataset to screenshot 16 columns. The scale ladder stops at the quota (at most 500k), so it adds little.

#### scSVA
- What: Broad / Klarman Cell Observatory (Tabaka, Gould, Regev) R/Shiny app for big-data embedding visualization, Python vaex backend.
- Engine/duplicate: own engine (Shiny UI plus vaex grid aggregation); not a duplicate.
- Paper: Tabaka M, Gould J, Regev A. "scSVA: an interactive tool for big data visualization and exploration in single-cell omics." bioRxiv 2019, doi:10.1101/512582 (Crossref-verified, preprint only, no journal version linked; citations 19).
- Repo / site: https://github.com/klarman-cell-observatory/scSVA; no GitHub releases (README says v0.2); last commit 2019-03-26; licence NOASSERTION (no recognised licence file).
- Inputs: HDF5, loom, compressed text expression matrices plus an embedding table.
- Scale claim: "visualize and explore interactively hundreds of millions of cells on a laptop or a billion cells on a moderate desktop" (README). The only demo is "100 Million cells (FLE up-sampled for demonstration purposes from 274,000 human bone marrow cells)" (README, https://github.com/klarman-cell-observatory/scSVA). So no real dataset over 274k cells is shown.
- Rendering: vaex bins points onto a 2D grid, so the plot is a density/aggregate image, not one mark per cell. Every cell counts toward the image but none is an individually addressable mark.
- Relationship views: no. Single embedding with gene/metadata colouring, group statistics, ggplot2 export.
- Testable how: local only. devtools install pinned to R>=3.4.3 / Python 3.6 / BiocInstaller (deprecated), vaex plus pyopengl plus orca; no hosted demo, no docker. Likely broken on current R/Python.
- Recommendation: **not comparable: binned density only** (operator decision 2026-10-08: no Fig. 1c row, no Supp. Note 1 entry; the paper names it in Comparison as not comparable). Evidence (HPC worker pack, scSVA at c9e8fd6, skeptic CHECK): every plot draws grid bins at their centers, so no mark carries a cell's identity, a cell cannot be hovered or picked, and a selection's cells cannot be listed or exported ([verdicts with code permalinks](scsva/evidence/scsva_render.txt), [pack README](scsva/evidence/README.md), [screenshots](scsva/evidence/screenshots.txt), [backend probes 1M-95.6M](scsva/evidence/probe/)). Not claimed: that every mark aggregates several cells (at 8,090 cells 6,803 of 7,422 marks hold one cell, [replication](scsva/evidence/snap_bm_aging_grid512.json)). The install that ran (R 3.6.2, vaex 2.0.3) is in [recipe](scsva/evidence/recipe/README.md); its claim still rests on 274,000 cells upsampled to 100 million.
- Effort for full treatment: L. Needs archaeology to get R 3.x/Py 3.6/vaex-legacy working, which may simply fail. If a row is wanted anyway, fill it from the README/paper and mark it "not run".

#### BBrowserX / BioTuring Browser (+ SpatialX, Talk2Data)
- What: BioTuring Inc. commercial desktop/enterprise single-cell analysis and visualization suite (BBrowser, then BBrowserX / BBrowserX Pro). SpatialX is its Windows spatial viewer for CosMx/Xenium/Visium/MERSCOPE. Talk2Data is a curated cross-study data hub.
- Engine/duplicate: own proprietary engine; not a duplicate.
- Paper: Le T, et al. (28 authors). "BBrowser: Making single-cell data easily accessible." bioRxiv 2020, doi:10.1101/2020.12.11.414136 (Crossref-verified, preprint; citations 65).
- Repo / site: https://bioturing.com/bbrowserx-pro (other bioturing.com product/pricing pages are JS-rendered or returned 404 to fetchers today); closed source; licence proprietary; release cadence not public.
- Inputs: Seurat, Scanpy/h5ad, FASTQ, mtx/tsv/csv matrices (https://www.rna-seqblog.com/visualize-analyze-and-manage-seurat-and-scanpy-single-cell-objects-in-an-interactive-platform/, 2020). SpatialX: CosMx, Xenium, Visium, MERSCOPE (https://bioturing.com/spatialx).
- Scale claim: BBrowserX Pro "Handles 10M+ cells" / "giga-scale studies exceeding 10M cells while staying responsive" (https://bioturing.com/bbrowserx-pro). Older BBrowser: "up to 1 million cells on a standard laptop" (2020 marketing). The AWS listing says "450 million+ cells across 3,600+ studies", but that is a portal total, not one dataset. None of these is benchmarked.
- Rendering: not documented.
- Relationship views: none documented beyond standard linked analysis panels (DE, pathway, cell-cell communication results as plots).
- Testable how: paid. Free trial "on request" (AWS Marketplace listing, https://aws.amazon.com/marketplace/pp/prodview-ewamk5slzdir6: Multi Omics Platform SaaS at $300,000 per 12 months, with a vendor-terms free trial). Historically there was a free academic BBrowser tier, but no current free download was confirmed.
- Recommendation: MENTION in text only. It is the most aggressive commercial scale claim (10M+), so cite it as "claimed, not verifiable" alongside Loupe. Without a free, reproducible build it cannot get a fair row.
- Effort for full treatment: L. Needs a sales-gated trial, a Windows/desktop install, and licence terms that may forbid publishing benchmarks.

#### Xenium Explorer
- What: 10x Genomics' free desktop viewer for Xenium In Situ output (cells, transcripts, morphology images, clusters, UMAP).
- Engine/duplicate: own proprietary engine. Not a duplicate (sibling of the Loupe Browser row, same vendor).
- Paper: none.
- Repo / site: https://www.10xgenomics.com/support/software/xenium-explorer ; latest seen v4.1.1 (per search snippets of the 10x release-notes page; the site returned HTTP 429 to every direct fetch today, so date unverified); licence proprietary EULA.
- Inputs: Xenium output bundle (experiment.xenium + zarr.zip cell/transcript/analysis files + OME-TIFF). Third-party conversion exists (spatialdata_xenium_explorer, now folded into Sopa), but that README states the Explorer "is licensed for usage on Xenium data" per the 10x EULA.
- Scale claim: release notes (search snippet, unverified page) cite performance work for "datasets with > 200 million unique cell by transcript features"; no cell-count ceiling stated.
- Rendering: undocumented (tiled multi-resolution transcript layers are implied by the zarr pyramid; cannot confirm).
- Relationship views: no (spatial + UMAP + cluster linking only, per vendor descriptions).
- Testable how: free download (10x account/email gate); public Xenium datasets load. Scale ladder with Tahoe-100M is not legitimately possible: non-spatial, and EULA limits use to Xenium data.
- Recommendation: MENTION in text only: vendor viewer locked to its own instrument format and EULA, like Loupe, so it cannot run our ladder and adds no distinct matrix contrast.
- Effort for full treatment: L (day+): download gate, page 429s, Xenium-format conversion for a ladder that the licence forbids.

#### MERSCOPE Vizualizer
- What: Vizgen's desktop viewer for MERFISH data from the MERSCOPE platform (transcripts, protein images, cell boundaries, imported UMAP/t-SNE, Leiden heatmaps, ROI export).
- Engine/duplicate: own proprietary engine. Not a duplicate.
- Paper: none.
- Repo / site: https://vizgen.com/vizualizer-software/ (HTTP 200); no public versioned release notes found; licence proprietary.
- Inputs: .VZG (instrument-generated proprietary bundle); imports AnnData (.HDF5), cell metadata CSV/Parquet, ROI CSV.
- Scale claim: "174 million individual transcripts from 500 genes" in one tumour section shown in the Vizualizer (vizgen.com product page and blog https://vizgen.com/developing-spatial-transcriptomics-data-analysis-solutions-to-empower-researchers/). Transcripts, not cells.
- Rendering: undocumented; recommended hardware i9 / 32 GB RAM / RTX 3080 10 GB (product page "Technical Specifications").
- Relationship views: no (UMAP/t-SNE scatter, heatmap, gene groups).
- Testable how: download via the Vizgen Portal; "free for all MERSCOPE users and Vizgen Lab Services customers" (blog) i.e. customer account needed. A free web version is claimed in search snippets but I could not find or open it.
- Recommendation: SKIP (mention at most alongside Xenium Explorer as instrument-vendor viewers): gated to customers, needs .VZG, cannot run our ladder.
- Effort for full treatment: L (day+) and likely blocked: requires a Vizgen customer account.

#### cellxgene VIP
- What: Biogen (interactivereport) plugin that injects ~18 extra server-rendered plot modules (violin, dotplot, Sankey, DEG, GSEA, spatial, multiome) into the CELLxGENE Annotate UI.
- Engine/duplicate: built on CELLxGENE Annotate (pinned to cellxgene 1.1.1); scatter/selection engine is CELLxGENE's, VIP plots are server-side matplotlib/R images. Duplicate of the existing CELLxGENE row.
- Paper: Li K, Ouyang Z, Chen Y, Gagnon J, Lin D, Mingueneau M, et al. "Cellxgene VIP unleashes full power of interactive visualization and integrative analysis of scRNA-seq, spatial transcriptomics, and multiome data." bioRxiv 2020, doi:10.1101/2020.08.28.270652 (Crossref, citations 30); Research Square 2022 doi:10.21203/rs.3.rs-1544196/v1 (citations 1). No peer-reviewed version found in Crossref.
- Repo / site: https://github.com/interactivereport/cellxgene_VIP ; last release v3.1 2024-02-27; last commit 2026-06-23; licence MIT (165 stars)
- Inputs: h5ad (same CLI args as cellxgene launch); spatial/multiome via h5ad conventions
- Scale claim: none stated (README says "large scale" without a number)
- Rendering: CELLxGENE WebGL scatter of all cells; VIP panels are static server-rendered images
- Relationship views: no obsp/varp; dual-gene co-expression plot is the closest gene x gene view
- Testable how: local conda + R install (heavy, pinned old R packages); hosted demos https://cellxgenevip-ms.bxgenomics.com (HTTP 200 today), -spatial (200)
- Recommendation: MENTION in text only. Plugin on the CELLxGENE engine; its scale ceiling equals CELLxGENE's, so a row would duplicate CELLxGENE except for extra static plots.
- Effort for full treatment: M. Hosted demo makes screenshots easy, but a local scale ladder needs a fragile conda+R install pinned to 2020-era packages.

#### cellxgene-gateway
- What: Novartis multi-dataset launcher/reverse proxy that lists a folder or S3 bucket of h5ad files and spawns one CELLxGENE server per file.
- Engine/duplicate: built on CELLxGENE Annotate (no viewer of its own). Pure duplicate of the CELLxGENE row.
- Paper: none
- Repo / site: https://github.com/Novartis/cellxgene-gateway ; last release v0.4.2 2025-12-02; last commit 2025-12-02; licence Apache-2.0 (70 stars)
- Inputs: h5ad (local dir or S3)
- Scale claim: none stated
- Rendering: whatever CELLxGENE does (all cells, WebGL)
- Relationship views: no
- Testable how: local pip (pip install cellxgene-gateway); no hosted demo
- Recommendation: SKIP (at most a footnote under CELLxGENE as a deployment helper). It adds dataset management, not visualisation.
- Effort for full treatment: S, but pointless; results would equal CELLxGENE's.

#### WebAtlas
- What: Haniffa/Bayraktar labs (Sanger/Newcastle); Nextflow pipeline that converts h5ad/SpaceRanger/Xenium/MERSCOPE output to zarr + Vitessce config, plus a React portal app (webatlas-app) that "builds on the Vitessce framework" (app README).
- Engine/duplicate: built on Vitessce -> DUPLICATE of the existing Vitessce row (the viewer is Vitessce; WebAtlas only adds preprocessing + config generation).
- Paper: Li T, Horsfall D, Basurto-Lozada D, ... Haniffa M, Bayraktar OA. WebAtlas pipeline for integrated single-cell and spatial transcriptomic data. Nature Methods (2024). DOI 10.1038/s41592-024-02371-x (Crossref-verified, citations 20).
- Repo / site: https://github.com/haniffalab/webatlas-pipeline (last release v0.5.3 2024-12-02; last commit on default branch 2025-01-21; MIT); https://github.com/haniffalab/webatlas-app (last release v0.2.1 2023-05-10; last commit 2023-05-10; MIT).
- Inputs: h5ad, TIFF (raw/label images), SpaceRanger, Xenium, MERSCOPE output -> zarr / OME-zarr.
- Scale claim: none stated (README/docs; Nature Methods full text paywalled from here, bioRxiv 10.1101/2023.05.19.541329 not retrievable).
- Rendering: whatever Vitessce does (deck.gl, all points of the converted zarr).
- Relationship views: none beyond Vitessce's linked views.
- Testable how: hosted demos https://cellatlas.io/webatlas (HTTP 200); local = Nextflow + Docker pipeline then npm app.
- Recommendation: SKIP as a row; at most one clause in text ("Vitessce-based portals such as WebAtlas") because the viewer engine is Vitessce and the app has not been committed to since 2023.
- Effort for full treatment: M (half day): Nextflow+Docker conversion of each scale-ladder step, then it would just re-measure Vitessce.

#### ASAP (Automated Single-cell Analysis Portal, EPFL / SIB)
- What: Deplancke lab hosted collaborative web portal running a full scRNA-seq/scATAC pipeline (QC, normalisation, clustering, DE, enrichment) with interactive plots; release 8 adds h5ad input and scFAIR validation.
- Engine/duplicate: own engine (Rails web app plus Dockerised asap_run pipeline); not a duplicate. Closest existing rows: Single Cell Portal and Kana.
- Paper: David FPA, Litovchenko M, Deplancke B, Gardeux V. "ASAP 2020 update: an open, scalable and interactive web-based portal for (single-cell) omics analyses." Nucleic Acids Res 48:W403-W414 (2020), doi:10.1093/nar/gkaa412 (Crossref, citations 30). Original: Gardeux V et al., Bioinformatics 33:3123-3125 (2017), doi:10.1093/bioinformatics/btx337 (citations 131).
- Repo / site: https://asap.epfl.ch (HTTP 200); https://github.com/DeplanckeLab/ASAP last release v7 2024-10-16, last commit 2026-03-10, GPL-3.0; active dev in https://github.com/DeplanckeLab/asap_web, last commit 2026-09-29, GPL-3.0
- Inputs: loom (v3), 10x h5, MEX/MTX archive, plain-text matrices, h5ad (from release 8) (https://asap.epfl.ch/home/file_format)
- Scale claim: "ASAP can now handle datasets containing millions of cells" (NAR 2020 abstract, doi:10.1093/nar/gkaa412); no single-dataset number given; hosts the Fly Cell Atlas
- Rendering: not documented (whether every cell is drawn is unknown)
- Relationship views: no obsp/varp; standard linked analysis steps, not focus-driven panels
- Testable how: hosted, free account needed to upload; public projects browsable; pipeline container asap_run can run locally but the GUI is server-only
- Recommendation: MENTION in text only (ADD only if the matrix wants a second hosted analysis-pipeline row next to Single Cell Portal). It is maintained and claims "millions of cells", so cite it for the scale discussion, but it is an analysis pipeline and its scale can only be tested by uploading large data to a third-party server.
- Effort for full treatment: L. Account, uploads plus server-side pipeline runs for each scale-ladder rung, with unknown upload limits.

#### TooManyCellsInteractive (TMCI)
- What: Schwartz lab (Princess Margaret / U Toronto) browser tool for exploring TooManyCells hierarchical cluster trees (radial tree with overlays, pruning, batch SVG export).
- Engine/duplicate: own engine (D3/React frontend, Node/Express + PostgreSQL, Docker Compose); not a duplicate.
- Paper: Klamann C, Lau C, Rehman A, Schwartz GW (4 authors). "TooManyCellsInteractive: A visualization tool for dynamic exploration of single-cell data." GigaScience 13:giae056 (2024), doi:10.1093/gigascience/giae056 (Crossref-verified; citations 4).
- Repo / site: https://github.com/schwartzlab-methods/too-many-cells-interactive, docs https://schwartzlab-methods.github.io/too-many-cells-interactive; last release v0.2.1-beta 2023-12-06; last commit 2026-06-23; licence GPL-3.0.
- Inputs: TooManyCells tree (cluster_tree.json) + label CSV; matrix (mtx/10x) for feature overlays. Needs the upstream TooManyCells (Haskell) run first.
- Scale claim: benchmarked up to "483,152 cells from the Tabula Sapiens dataset", compared against CELLxGENE and Cirrocumulus (https://pmc.ncbi.nlm.nih.gov/articles/PMC11340645/).
- Rendering: no per-cell marks. Cells are aggregated into tree nodes (pies/branch widths), so it is aggregation by design.
- Relationship views: a hierarchy view only (cluster tree); no obsp/varp, no cell x cell graph or gene x gene panels.
- Testable how: local docker compose; no live hosted demo found.
- Recommendation: MENTION in text only. It is a different paradigm (tree, not embedding) with a modest scale, and it requires a non-GUI upstream Haskell step, but it is a recent peer-reviewed tool that benchmarked against two matrix rows, which is worth one sentence.
- Effort for full treatment: M to L. Needs Docker plus TooManyCells (Haskell) preprocessing per dataset; most of the 16 columns do not apply to a tree viewer.

#### Partek Flow
- What: Illumina (formerly Partek Inc.) commercial point-and-click NGS / single-cell / spatial analysis platform with interactive visualizations.
- Engine/duplicate: own proprietary engine; not a duplicate.
- Paper: none (no tool paper; vendor documentation only).
- Repo / site: https://www.illumina.com/products/by-type/informatics-products/partek-flow.html; docs https://help.partek.illumina.com/partek-flow/; latest release 12.11.2, 2026-08-05 (https://help.connected.illumina.com/partek/partek-flow/release-notes); licence proprietary.
- Inputs: 10x outputs, text matrices, h5ad (import/export), Seurat 4/5 objects including .qs, Xenium/CosMx/Visium spatial (release notes, product page).
- Scale claim: none stated (product page and scatter-plot docs give no cell count).
- Rendering: not documented. Docs offer a "Downsample Cells" task to cut large datasets "to small and manageable sizes" (https://help.partek.illumina.com/partek-flow/user-manual/task-menu/filtering/downsample-cells). The 2026 release note says only "points with a higher expression level are moved to the front".
- Relationship views: no. It is a pipeline-node DAG with per-node 2D/3D scatter, heatmaps and DE tables.
- Testable how: paid. Annual licence via sales; demo or trial "on request"; on-prem or cloud.
- Recommendation: MENTION in text only. It is an established commercial analysis suite but is sales-gated and makes no published scale claim, so a row would be mostly "unknown".
- Effort for full treatment: L. Needs a sales trial and an on-prem server install, and it is pipeline-centric, so h5ad import means a full ingest per scale-ladder rung.

#### Galaxy-hosted viewers (Galaxy Interactive Tools)
- What: Galaxy wraps existing viewers as Interactive Tools: "Interactive CellXgene Environment" (cellxgene 1.1.1 biocontainer) and iSEE ship in galaxyproject/galaxy tools/interactive; UCSC Cell Browser and others come via separate tool repos.
- Engine/duplicate: built on CELLxGENE / iSEE / UCSC Cell Browser. All duplicates of existing rows.
- Paper: none specific to these wrappers
- Repo / site: https://github.com/galaxyproject/galaxy/tree/dev/tools/interactive (interactivetool_cellxgene_1.1.1.xml last changed 2025-05-12); https://usegalaxy.eu/?tool_id=interactive_tool_cellxgene (HTTP 200); licence: GitHub reports NOASSERTION for Galaxy (MIT-style core, mixed)
- Inputs: h5ad (Galaxy dataset)
- Scale claim: none stated
- Rendering: same as the wrapped engine (cellxgene 1.1.1 is an older Annotate)
- Relationship views: no
- Testable how: free usegalaxy.eu account
- Recommendation: MENTION in text only (one clause: "also deployable via Galaxy Interactive Tools"); no row.
- Effort for full treatment: n/a (would replicate the CELLxGENE/iSEE rows on an older version)

#### Azimuth (Satija lab / HuBMAP)
- What: Shiny web app for query-to-reference mapping and annotation of scRNA-seq against curated Seurat references.
- Engine/duplicate: own Shiny app (Seurat backend); not a duplicate, but a mapping tool rather than an explorer.
- Paper: Hao Y, Hao S, Andersen-Nissen E, et al. "Integrated analysis of multimodal single-cell data." Cell 184:3573-3587.e29 (2021), doi:10.1016/j.cell.2021.04.048 (Crossref, citations 15869; this is the Seurat v4 paper, which introduced Azimuth)
- Repo / site: https://github.com/satijalab/azimuth ; no GitHub releases (latest tag v0.5.0); last commit 2026-05-22; licence GPL-3.0. Site https://azimuth.hubmapconsortium.org (200) now states: "we are no longer supporting the web applications for individual tissue-specific references"; the successor, Pan-Human Azimuth, is command-line/API only (R CloudAzimuth, Python panhumanpy).
- Inputs: Seurat rds/h5Seurat, h5ad, 10x h5, matrix (query upload)
- Scale claim: max_cells default 100,000 query cells in the example config (README, https://github.com/satijalab/azimuth)
- Rendering: Shiny/plotly output plots of the mapped query; not documented further
- Relationship views: no
- Testable how: local Docker plus a downloaded reference; the hosted web apps are being retired
- Recommendation: SKIP. The hosted GUI is discontinued, the successor has no GUI, and the tool's job is annotation transfer, not dataset exploration.
- Effort for full treatment: L (Docker build plus reference download, against a sunset app with a 100k-cell cap)

#### EBI Single Cell Expression Atlas
- What: EMBL-EBI curated knowledgebase of reprocessed public scRNA-seq experiments, with per-experiment tSNE/UMAP plots, marker heatmaps, cell-type wheel search and anatomograms.
- Engine/duplicate: own web components (ebi-gene-expression-group/atlas-web-single-cell); not a general viewer, since users cannot load their own data.
- Paper: George N, Fexova S, Fuentes AM, Madrigal P, et al. "Expression Atlas update: insights from sequencing data at both bulk and single cell level." Nucleic Acids Res 52:D107-D114 (2024), doi:10.1093/nar/gkad1021 (Crossref, citations 57). Earlier: Papatheodorou I et al., NAR 2020, doi:10.1093/nar/gkz947 (citations 223).
- Repo / site: https://www.ebi.ac.uk/gxa/sc/home (HTTP 200); https://github.com/ebi-gene-expression-group/atlas-web-single-cell last release 17.3.0 2026-01-20, last commit 2026-09-04, licence Apache-2.0
- Inputs: none from users (curated public experiments only); exports MTX/TSV
- Scale claim: none stated for a single experiment
- Rendering: not documented (per-experiment server-provided coordinates)
- Relationship views: no
- Testable how: hosted portal only, no account
- Recommendation: SKIP (or one-line MENTION among data atlases alongside Discover). It is a database portal, not a tool for a user's own dataset, so most matrix columns would be N/A.
- Effort for full treatment: M; screenshots are easy, but no scale ladder is possible and many columns are N/A.

#### SCelVis
- What: BIH (Berlin) Plotly Dash web app for exploring preprocessed scRNA-seq on the desktop or a server, with embedding, violin/dot plots and simple DE.
- Engine/duplicate: own engine (Dash/Plotly); not a duplicate.
- Paper: Obermayer B, Holtgrewe M, Nieminen M, Messerschmidt C, Beule D. "SCelVis: exploratory single cell data analysis on the desktop and in the cloud." PeerJ 8:e8607 (2020), doi:10.7717/peerj.8607 (Crossref, citations 8)
- Repo / site: https://github.com/bihealth/scelvis ; last GitHub release v0.8.6 2021-09-20 (README references a 0.8.8 container); last commit 2022-09-06; licence MIT; docs https://scelvis.readthedocs.io (200)
- Inputs: h5ad (plus conversion from 10x/loom/text via its CLI)
- Scale claim: none stated (tutorial dataset ~14,000 PBMCs)
- Rendering: not documented
- Relationship views: no
- Testable how: local pip/bioconda/docker
- Recommendation: SKIP. No commit since 2022-09, low citations, and no scale claim; it fails the maintained-or-widely-cited bar.
- Effort for full treatment: M (easy pip install, but 2021-era dependencies will likely need pinning)

#### Cellar
- What: CMU Systems Biology Group (HuBMAP) Dash/Plotly web app for interactive clustering, label transfer and annotation of single-cell and spatial (CODEX, Visium) data.
- Engine/duplicate: own engine (Python Dash/Plotly); not a duplicate.
- Paper: Hasanaj E, Wang J, Sarathi A, Ding J, Bar-Joseph Z. "Interactive single-cell data analysis using Cellar." Nature Communications 13:1998 (2022), doi:10.1038/s41467-022-29744-0 (Crossref-verified; citations 31).
- Repo / site: https://github.com/euxhenh/cellar; last release v1.12 2022-07-10; last commit 2023-04-14; licence MIT.
- Inputs: h5ad (plus HuBMAP datasets); spatial tiles for CODEX/Visium.
- Scale claim: none stated in README.
- Rendering: Plotly scatter; no scale engineering documented.
- Relationship views: no.
- Testable how: local pip/docker (Python 3.7 to 3.9 only); hosted https://cellar.cmu.hubmapconsortium.org/app/cellar did not respond today (curl timeout, status 000).
- Recommendation: SKIP. Unmaintained since 2023-04, hosted instance down, Python <=3.9, and no scale story. The citation count (31) is moderate at best.
- Effort for full treatment: M. Needs an old-Python environment, and Plotly/Dash will cap out early on the scale ladder.

#### Pagoda2 web application
- What: Kharchenko lab R package pagoda2, whose companion JS frontend lets users browse embeddings, clusters, gene sets/GO overdispersion and run DE in the browser.
- Engine/duplicate: own engine (bundled JS app serving a pagoda2-exported .bin); not a duplicate.
- Paper: none dedicated to the web app (the README's citation block points to the package; there is no separate viewer paper).
- Repo / site: https://github.com/kharchenkolab/pagoda2 (CRAN); last release v1.0.15 2026-04-01; last push 2026-06-28; licence not declared via the GitHub API (CRAN lists GPL-3).
- Inputs: a pagoda2 R object exported to its own binary (.bin) format; an R pipeline is needed first.
- Scale claim: package methods "optimized to rapidly process ... (approximately 1e6 cells or greater)" (README). No viewer-specific number.
- Rendering: not documented.
- Relationship views: geneset/aspect panels linked to embedding; no obsp/varp.
- Testable how: local R (CRAN/docker); demo is only a YouTube video; pagoda2.org did not respond today.
- Recommendation: SKIP. The viewer cannot be used without R programming to build the .bin, and the 1e6 claim is about the analysis methods, not the viewer.
- Effort for full treatment: M. R pipeline per scale rung plus the .bin export.

#### Giotto Viewer
- What: Dries/Yuan labs; web viewer half of the Giotto spatial toolbox (spatial + UMAP linked panels, transcripts, stains).
- Engine/duplicate: own engine (legacy JS viewer); current Giotto Suite (R) does static/interactive plots in R, not a standalone GUI.
- Paper: Dries R, Zhu Q, Dong R, ... Giotto: a toolbox for integrative analysis and visualization of spatial expression data. Genome Biol 22:78 (2021). DOI 10.1186/s13059-021-02286-2 (Crossref-verified, citations 953).
- Repo / site: original Bitbucket repo (qzhudfci/giotto_viewer) no longer accessible; only GitHub mirror TianxiaoNYU/Giotto_viewer, last push 2019-09-05; licence unclear.
- Inputs: Giotto exports (text/JSON tiles).
- Scale claim: none stated.
- Rendering: undocumented.
- Relationship views: linked spatial/expression-space panels only.
- Testable how: no maintained distribution; no hosted demo found.
- Recommendation: SKIP: unmaintained since ~2019 (only the paper's citations keep it visible).
- Effort for full treatment: L (day+): resurrecting an abandoned viewer.

#### SODB / SOView
- What: Tencent AI Lab + Fudan; Spatial Omics DataBase (>2,400 experiments) with web analysis modules incl. SOView, a colour-embedding visualisation of spatial omics.
- Engine/duplicate: own portal; SOView is a visualisation algorithm/module, not a general dataset explorer.
- Paper: Yuan Z, Pan W, ... SODB facilitates comprehensive exploration of spatial omics data. Nature Methods 20:387 (2023). DOI 10.1038/s41592-023-01773-7 (Crossref-verified, citations 113).
- Repo / site: https://gene.ai.tencent.com/SpatialOmics/ (HTTP 200); pysodb loader; licence n/a.
- Inputs: curated SODB datasets only (no upload of the user's own data in the GUI).
- Scale claim: none stated per dataset.
- Rendering: n/a.
- Relationship views: no.
- Testable how: hosted portal, but cannot load our data.
- Recommendation: SKIP: a data portal, not a viewer for user datasets.
- Effort for full treatment: n/a.

#### SpatialData web viewer
- What: checked whether scverse ships its own browser viewer for SpatialData zarr.
- Engine/duplicate: none exists; SpatialData's interactive routes are napari-spatialdata (existing row) and Vitessce's SpatialData loaders (existing row); spatialdata-plot is a static matplotlib library (no new code-library rows).
- Paper: n/a.
- Repo / site: https://github.com/scverse/spatialdata-plot (BSD-3-Clause, pushed 2026-09-28) is the only scverse plotting repo.
- Inputs / Scale / Rendering / Relationship views: n/a.
- Testable how: n/a.
- Recommendation: SKIP: no distinct tool; already covered by napari-spatialdata and Vitessce rows.
- Effort for full treatment: n/a.

#### XCell (CahanLab)
- What: Cahan lab (Johns Hopkins) local web app (FastAPI backend + JS frontend) for loading, analysing (Scanpy pipeline in GUI) and exploring scRNA-seq and spatial data.
- Engine/duplicate: own engine; not a duplicate.
- Paper: none.
- Repo / site: https://github.com/CahanLab/xcell; no releases; last commit 2026-10-03 (created 2026-02); licence none declared; 2 stars.
- Inputs: h5ad, 10x h5, Visium HD feature_slice.h5, Seurat .rds, CellRanger mtx folder, GEO 10x trio.
- Scale claim: none stated.
- Rendering: not documented (deck.gl according to third-party search snippets; not verified in repo).
- Relationship views: no obsp/varp panels; does run kNN/Leiden in-app and has gene-program (NMF) views.
- Testable how: local pixi install (two processes); no hosted demo.
- Recommendation: SKIP. Brand-new, two-star, unpublished, unlicensed lab tool. Re-check at revision time if it gets a paper.
- Effort for full treatment: S to M. A pixi install is easy, but it is a moving target with no release tag to pin.

#### CZ CELLxGENE successors and forks (Explorer, Census, Portable-CELLxGENE, Virtual Cells Platform)
- What: (a) CZ CELLxGENE Explorer, CZI's maintained fork of Annotate deployed inside Discover, now with a spatial deep-zoom mode; (b) CELLxGENE Census, a TileDB-SOMA data API, not a GUI; (c) Portable-CELLxGENE, standalone executables of Annotate; (d) CZI/Biohub Virtual Cells Platform, a model/benchmark/data hub with a no-code "AI workspace", not a cell viewer.
- Engine/duplicate: (a) and (c) are the CELLxGENE engine, already covered by the "CELLxGENE (Annotate + Discover Explorer)" row; (b) is a code library (excluded by the brief); (d) is not a single-cell viewer.
- Paper: CZI Cell Science Program et al. "CZ CELLxGENE Discover: a single-cell data platform for scalable exploration, analysis and modeling of aggregated data." Nucleic Acids Res 53:D886-D900 (2025), doi:10.1093/nar/gkae1142 (Crossref, citations 439), already cited for the existing row. Portable-CELLxGENE: Hall et al., Gigabyte 2025, gigabyte151, doi:10.46471/gigabyte.151 (citations 0).
- Repo / site: https://github.com/chanzuckerberg/single-cell-explorer last release v1.20.2 2026-02-05, last commit 2026-03-13, MIT; https://github.com/chanzuckerberg/cellxgene (Annotate) last release 1.3.0 2024-09-12, last commit 2026-03-09, MIT; https://github.com/chanzuckerberg/cellxgene-census last release v1.18.0 2026-06-24, MIT; https://virtualcellmodels.cziscience.com (HTTP 200, account for workspace)
- Inputs: Explorer: Discover-curated CXG/TileDB conversions of h5ad (not user data); Annotate/Portable: h5ad
- Scale claim: "fast visualizations of at least 1 million cells" (Explorer README, https://github.com/chanzuckerberg/single-cell-explorer)
- Rendering: WebGL scatter of all cells (as for the existing row)
- Relationship views: no obsp/varp views in Explorer; Discover's separate Gene Expression dot-plot tool is gene x tissue, not linked to the embedding
- Testable how: hosted https://cellxgene.cziscience.com (200); Annotate via pip
- Recommendation: SKIP as new rows. Explorer is already in the matrix; update that row only if the spatial deep-zoom mode changes a column. Census and VCP are not GUIs for exploring a dataset.
- Effort for full treatment: S (only re-check the existing CELLxGENE row for the spatial-mode column)

