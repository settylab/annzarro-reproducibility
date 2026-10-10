## Summary: AnnZarro's competitors, cell by cell

> **Column order note (2026-10-04).** The mark strings and "Current" marks in this file use the old 16-column order, with lazy reads in the Data group. Fig. 1c now has 18 columns: lazy reads, every cell drawn and user subset form a Scale group. `evidence/matrix/tools/*.yaml` uses the figure's 18 column ids. Column 3 is scored by the strict definition: "a focused cell or gene, through its stored pairwise row, re-drives every linked panel".

This audit covers twelve tools. Seven are matrix rows in Fig. 1c: CELLxGENE, Vitessce, Cirrocumulus, iSEE, UCSC Cell Browser, ShinyCell, and Scanpy/Seurat. The other five are named only in the manuscript's "Comparison with other methods": Single Cell Portal, SCope, Kana, napari-spatialdata and Loupe Browser. Each tool has its own file with the paper (DOI checked against Crossref), repository and commit, demos, every matrix cell with evidence, and a validation checklist. Everything was checked on 2026-10-03. It extends `figures/COMPARISON_DEMOS.md` (2 October).

### Headline

1. **The central claim holds.** No tool turns a stored cells × cells or genes × genes matrix into a colour or axis in its GUI (columns 1 and 2). Each of the twelve was searched in source for obsp, varp, colPairs, rowPairs and pairwise loaders. The local demos confirm it on the paper's own data: Cirrocumulus, CELLxGENE Annotate and the UCSC Cell Browser load an h5ad that carries three obsp matrices, and none of them offers one. Only code (Scanpy/Seurat) reaches them, and each new focus needs a re-run.
2. **The focus column, scored strictly, is AnnZarro's alone.** Under the loose definition ("one selected cell or gene re-drives other panels"), iSEE looked like a Y. The running iSEE shows otherwise. Its single selection carries only an identity: a gene becomes feature colouring and a cell becomes a red dot, and no panel uses the cell's colPairs row. The strict definition, "a focused cell or gene, through its stored pairwise row, re-drives every linked panel", gives Y for AnnZarro, P for Scanpy/Seurat (by code) and N for every other tool. Selection that cross-filters linked views is a different strength, and most viewers have it; see the proposed column below.
3. **The reported-scale column mixes kinds of number.** UCSC shows a portal total (160M), Vitessce a slogan ("millions of points") and ShinyCell build-time RAM advice ("~30k per 8 GB"). Each tool should get its largest documented single dataset; see the table below. Two numbers also outgrow the manuscript's wording: CELLxGENE Explorer serves an 11.4M-cell dataset, and the UCSC portal a 21.8M-cell one. AnnZarro's 95.6M remains the largest, but the text should not imply that others stop near 1M.

### Tools at a glance

| Tool | Maker | Primary paper | Live demo (2026-10-03) | Local demo | Licence | File |
|---|---|---|---|---|---|---|
| CELLxGENE (Explorer, Annotate) | CZI | [Megill et al. 2021, bioRxiv](https://doi.org/10.1101/2021.04.05.438318); CZ CELLxGENE Discover, NAR 2025 | [Tabula Sapiens 1.1M](https://cellxgene.cziscience.com/e/53d208b0-2cfd-4366-9866-c3c6114081bc.cxg/) | Annotate, :8903 | MIT | [cellxgene.md](cellxgene.md) |
| Vitessce | HIDIVE, Harvard | [Keller et al., Nat Methods](https://doi.org/10.1038/s41592-024-02436-x) | [Visium lymph node](https://vitessce.io/#?dataset=human-lymph-node-10x-visium), [LuCA 1.28M](https://vitessce.io/#?dataset=salcher-2022) | hosted app + local zarr, :8904 | MIT | [vitessce.md](vitessce.md) |
| Cirrocumulus | Broad, now lilab-bcb | inside Cumulus, [Li et al. 2020, Nat Methods](https://doi.org/10.1038/s41592-020-0905-x) | none reachable | :8901 | BSD-3 | [cirrocumulus.md](cirrocumulus.md) |
| iSEE | Bioconductor (Rue-Albrecht, Marini, Soneson, Lun) | [Rue-Albrecht et al. 2018, F1000Research](https://doi.org/10.12688/f1000research.14966.1) | none reachable (all 5 README instances fail) | :8902 | MIT | [isee.md](isee.md) |
| UCSC Cell Browser | UCSC | [Speir et al. 2021, Bioinformatics](https://doi.org/10.1093/bioinformatics/btab503) | [adultPancreas](https://cells.ucsc.edu/?ds=adultPancreas), [PanSci 21.8M](https://cells.ucsc.edu/?ds=mouse-pansci+all) | :8906 | GPL-3.0 | [ucsc-cell-browser.md](ucsc-cell-browser.md) |
| ShinyCell / ShinyCell2 | Ouyang lab | [Ouyang et al. 2021, Bioinformatics](https://doi.org/10.1093/bioinformatics/btab209) | [tutorial app](http://shinycell1.ddnetbio.com), [ShinyCell2 showcase](https://shinycell.ouyanglab.com/) | :8907 | GPL-3.0 | [shinycell.md](shinycell.md) |
| Scanpy / Seurat | scverse / Satija lab | [Wolf et al. 2018, Genome Biol](https://doi.org/10.1186/s13059-017-1382-0); Hao et al. 2024, Nat Biotechnol | libraries (tutorials) | paper `.venv` | BSD-3 / MIT | [scanpy-seurat.md](scanpy-seurat.md) |
| Single Cell Portal | Broad | [Tarhan et al. 2023, bioRxiv](https://doi.org/10.1101/2023.07.13.548886) | [SCP2805, 3.18M cells](https://singlecell.broadinstitute.org/single_cell/study/SCP2805) | none (live) | BSD-3 | [single-cell-portal.md](single-cell-portal.md) |
| SCope | Aerts lab | [Davie et al. 2018, Cell](https://doi.org/10.1016/j.cell.2018.05.057) | [scope.aertslab.org](https://scope.aertslab.org) (Fly Cell Atlas) | none (live) | GPL-3.0 | [scope.md](scope.md) |
| Kana | Genentech (Lun, Kancherla) | [Lun & Kancherla 2023, JOSS](https://doi.org/10.21105/joss.05603) | [kanaverse.org/kana](https://www.kanaverse.org/kana/) (runs in your browser) | load `bm_demo.h5ad` into the live app | MIT | [kana.md](kana.md) |
| napari-spatialdata | scverse | [Marconato et al., Nat Methods (SpatialData)](https://doi.org/10.1038/s41592-024-02212-x) | desktop only | desktop, `start.sh` | BSD-3 | [napari-spatialdata.md](napari-spatialdata.md) |
| Loupe Browser | 10x Genomics | none | desktop only; download needs a 10x account | not installed (account) | proprietary, free | [loupe.md](loupe.md) |

### Proposed matrix

Marks follow the figure's order, `cells genes focus | slots lazy remote spatial | filters annot DE image | share export | desktop hosted static`. Y documented, P partial or code only, N searched and not found, ? not verified. Each changed mark is in bold in that tool's file, with its evidence.

Column 3 is scored by the strict definition: **"a focused cell or gene, through its stored pairwise row, re-drives every linked panel"**. Gene feature colouring that propagates to several views does not count. Each tool was checked in its running app; see the "Focus, feature colouring and selection" section in each file, with screenshots under [`screens/`](screens/).

| Tool | Current (fig_comparison.py) | Proposed | Changes |
|---|---|---|---|
| AnnZarro | `YYY YYYY YNNN YY YYN` | not audited here | none |
| CELLxGENE | `NNN NYPY PYYY PY NPN` | `NNN NYPY PYYY NY NYN` | share P→N; hosted P→Y |
| Vitessce | `NNN PYYY PPNY YN NPY` | `NNN PYYY PPNY YP NPY` | export N→P (Vega plots only) |
| Cirrocumulus | `NNN PYYY YYYY YY NYY` | `NNN PYPY YYYY YY NYY` | **remote Y→P** (checked 2026-10-04: `cirro launch` cannot open public anonymous S3, GCS or HTTPS AnnData zarr stores; there is no anonymous option, it wants write access next to the dataset by default, and HTTPS crashes; reading the operator's own credentialed buckets is documented but not shown). Lazy is Y for prepared data (zarr, parquet, jsonl) but N for a plain h5ad, so the Scale group's S3 says P. If column 5 scores default behaviour, change it to P (decide) |
| iSEE | `NNP PPNN YNNN YY NYN` | `NNN PPNN YNPN PY NYN` | **focus P→N** (checked in the app: the single selection carries an identity, so a cell becomes a red dot; no panel uses its colPairs row); DE N→P (iSEEu, by code); **share Y→P** (checked in the app: the state downloads as an RDS file, but the shipped GUI cannot restore it; that works only via `iSEE(initial=)` in code) |
| UCSC Cell Browser | `NNN PYPY PYPY YY NYY` | `NNN PYPY PYNY YY NYY` | **DE P→N** (checked: off by default and absent on the portal; with the flag on but no backend, the client shows placeholder statistics) |
| ShinyCell | `NNN PPNP NNNP NY NYN` | `NNN PYNP NNNP NY NYN` | lazy P→Y (one HDF5 chunk per gene at view time; the Scale group's S3 already says Y) |
| Scanpy / Seurat | `PPN YP?? PPP? YP NNN` | `PPP PPPP PPPP PP NNN` | focus N→P (obsp row by code, re-run per focus: screens/scanpy-seurat/01); every ? resolved to P; slots and share Y→P by the rule "only by writing code" |
| Single Cell Portal | not in matrix | `NNN PYNY PYPN YY NYN` | |
| SCope | not in matrix | `NNN PYNN PYNN YN NYN` | desktop P→N (the only binaries are 2019 x64 builds that the maintainers flag as "likely to be non-functional") |
| Kana | not in matrix | `NNN NNPP PPYN PY NPY` | |
| napari-spatialdata | not in matrix | `NNN PPPY NPNY NY YNN` | |
| Loupe Browser | not in matrix | `NNN NYNY PYYY PY YNN` | **lazy ?→Y** (measured in the app 2026-10-08: memory after opening 1.273 vs 1.272 GiB for 200 vs 2,000 genes, same 1,000,000 cells; format closed, how it reads not established) |

Under the strict definition, column 3 is Y for AnnZarro only, P for Scanpy/Seurat and N for every other tool.

### Proposed column: selection or filter restricts linked views

The definition: a selection or filter made in one view highlights or restricts the same cells in other linked views, in the GUI. This should **replace** column 8, "table filters mask plots", rather than become a 17th column, because the two overlap. Marks were observed in each running app, except where noted.

| Tool | Mark | What was observed | Screenshot |
|---|---|---|---|
| AnnZarro | Y | table filters (AND/OR on any column) mask every linked plot; no lasso | not re-shot here |
| CELLxGENE | Y | Annotate: a lasso in the embedding highlights the cells in the gene-gene scatter; category and histogram filters mask the embedding | [cellxgene/03](screens/cellxgene/03_annotate_lasso_highlights_in_scatter.jpg) |
| Vitessce | Y | a lasso in the UMAP highlights the same cells in the FA plot and the heatmap (2,078 selected); unticking a cell set changes only the heatmap | [vitessce/03](screens/vitessce/03_lasso_UMAP_highlights_FA.jpg) |
| Cirrocumulus | Y | a legend selection or double-click highlights the cells in every gallery chart | [cirrocumulus/03](screens/cirrocumulus/03_legend_selection_highlights_gallery.jpg) |
| iSEE | Y | a brush in the UMAP highlights the cells in the PCA plot, and "Restrict" filters them | [isee/03](screens/isee/03_brush_umap_highlights_in_pca.jpg) |
| UCSC Cell Browser | Y | a lasso in one split pane highlights the cells in the other and splits the violin | [ucsc/03](screens/ucsc-cell-browser/03_lasso_selection_both_panes_and_violin.jpg) |
| Single Cell Portal | Y (P if the column means plot brushing) | "Filter plotted cells" facets act on every scatter; the lasso stays in its own plot | [scp/04](screens/single-cell-portal/04_filter_macrophage_off_both_scatters.jpg) |
| SCope | Y | observed 2026-10-09 in headed Chrome: a lasso of 25 cells recolors the same cells in all 3 Regulon viewers, and on Compare marks them in a first-half-filtered display; the AUC threshold only recolors | [scope/m08 lasso](screens/scope/m08_selection_APP_regulon_lasso_linked_3_viewers.jpg) |
| Kana | P | the lasso highlights only in its own plot and becomes a group for markers | [kana/03](screens/kana/03_lasso_main_view_only.jpg) |
| napari-spatialdata | P | the Scatter ROI acts inside the scatter widget only | [napari/02](screens/napari-spatialdata/02_scatter_umap_leiden_spatial_Mbp.jpg) |
| Loupe Browser | P (docs only) | a selection becomes a labelled group that other panels then use | none |
| Scanpy / Seurat | P | Seurat `CellSelector`, then code | none |
| ShinyCell | N | no selection; there is a per-tab subset form | [shinycell/04](screens/shinycell/04_subset_per_plot.jpg) |

### Scale group (sent to manuscript-writer)

| Tool | Largest single dataset documented | Every cell drawn? | Where data live | User subset |
|---|---|---|---|---|
| CELLxGENE | 4.3M (NAR 2025); 11.4M served on Discover | yes, WebGL, no downsampling | Explorer: TileDB slices on S3, read lazily by the server; the browser keeps whole columns. Annotate: whole h5ad in server RAM unless `--backed` | yes, subset to selection (view only) |
| Vitessce | 1.28M (LuCA demo) | yes (deck.gl); optional density contours | browser only: per-gene zarr chunks; obsm and obs whole | no (highlight only) |
| Cirrocumulus | 1.3M (docs, dataset unnamed) | yes (scatter-gl) | h5ad: server RAM. Prepared data: server per gene. Static: browser byte ranges | partial (dim the rest; export ids) |
| iSEE | 68.6k (bigdata vignette) | yes by default; optional grid downsampling | server R; assays may be lazy HDF5 | yes (restrict to selection, downsample) |
| UCSC Cell Browser | 21.8M (PanSci "All") | yes, WebGL above 200k | browser, one gene per byte-range request; coordinates whole | yes (hide or show only selected) |
| ShinyCell | 162k (ShinyCell2 CITE-seq tutorial) | yes (ggplot) | server R, one HDF5 row per gene; the browser gets a PNG | yes, by metadata group |
| Scanpy / Seurat | 1.3M (Scanpy paper; Seurat sketch vignette) | yes; Seurat rasterises above 100k | user process, whole by default; lazy only by code | yes, by code |
| Single Cell Portal | 3.18M (SCP2805) | **P: draws every cell up to 100k, subsampled to 100k above that by default; "All cells" is opt-in** (the same pattern as AnnZarro's default subset above 200k) | server per gene; the browser gets whole coordinate arrays | coarse (100k or all) |
| SCope | 568k (Fly Cell Atlas) | yes (PIXI) | server per gene (loom); browser full arrays | by annotation |
| Kana | 174k (paper) | yes | everything in the browser's Wasm heap (4 GiB cap) | subset and recompute at load |
| napari-spatialdata | no cell count | points subsampled to 100k | local process; images lazy (dask) | only by code |
| Loupe Browser | more than 1M (8.1.0 release notes) | not documented | local process, closed format | Reanalyze subset (cap 100k) |

### Manuscript text to revisit

- "CELLxGENE and Cirrocumulus document datasets of one million or more cells and Vitessce millions of points": the documented and served numbers are now known (above). Suggested: "CELLxGENE serves single datasets of up to 11.4 million cells, the UCSC Cell Browser 21.8 million; we did not benchmark them."
- "iSEE introduced a table row that drives other panels": correct, and stronger than the matrix shows (column 3). See Q1.
- "iSEE exports the exact code behind a view": verified (Extract the R code), see [isee.md](isee.md).
- "Loupe and CELLxGENE run differential expression on demand", "CELLxGENE, Cirrocumulus and Loupe edit annotations": verified from docs ([loupe.md](loupe.md), [cellxgene.md](cellxgene.md)). CELLxGENE annotation is Annotate only, not the hosted Explorer.
- "Vitessce and napari-spatialdata render tissue images": verified.
- Cirrocumulus has a citable source: the Cumulus paper (Li et al. 2020) describes it in its Methods.
