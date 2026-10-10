## Scanpy / Seurat (code libraries)

> **Column order note (2026-10-04).** The mark strings and "Current" marks in this file use the old 16-column order, with lazy reads in the Data group. Fig. 1c now has 18 columns: lazy reads, every cell drawn and user subset form a Scale group. `evidence/matrix/tools/*.yaml` uses the figure's 18 column ids. Column 3 is scored by the strict definition: "a focused cell or gene, through its stored pairwise row, re-drives every linked panel".

### What it is

Scanpy (Python, scverse) and Seurat (R, Satija lab) are the two standard analysis libraries for single-cell data. Scanpy works on the AnnData object (also scverse); Seurat on its own Seurat object (v5 with "layers" and on-disk BPCells matrices). Neither is a viewer: every plot is the output of a function call in a script or notebook, so this row is scored with one rule throughout: **P = reachable only by writing code**. All facts checked 2026-10-03.

**Primary papers** (all Crossref-verified 2026-10-03):
- Wolf FA, Angerer P, Theis FJ (2018). SCANPY: large-scale single-cell gene expression data analysis. *Genome Biology* 19, 15. https://doi.org/10.1186/s13059-017-1382-0
- Virshup I, Rybakov S, Theis FJ, Angerer P, Wolf FA (2021). anndata: Annotated data. *bioRxiv* preprint. https://doi.org/10.1101/2021.12.16.473007 ; published as Virshup I, Rybakov S, Theis FJ, Angerer P, Wolf FA (2024). anndata: Access and store annotated data matrices. *Journal of Open Source Software* 9, 4371. https://doi.org/10.21105/joss.04371
- Hao Y, Stuart T, Kowalski MH, Choudhary S, Hoffman P, Hartman A, et al. (2024). Dictionary learning for integrative, multimodal and scalable single-cell analysis. *Nature Biotechnology* 42, 293–304. https://doi.org/10.1038/s41587-023-01767-y (Crossref "issued" = online 2023-05-25; volume 42 is the 2024 print issue). This is the Seurat v5 paper (`satijalab/seurat/inst/CITATION`, first entry).

**Repositories** (shallow clones in `$DEMO_ROOT/scanpy-seurat/src/`):

| Repo | Commit | Commit date | Released version | Licence |
|---|---|---|---|---|
| [scverse/scanpy](https://github.com/scverse/scanpy) | `7ad567d` | 2026-10-02 | 1.12.4 (PyPI) | BSD-3-Clause (GitHub API) |
| [scverse/anndata](https://github.com/scverse/anndata) | `bb86151` | 2026-10-02 | 0.13.4 (PyPI) | BSD-3-Clause (GitHub API) |
| [satijalab/seurat](https://github.com/satijalab/seurat) | `b1fe780` | 2026-10-02 | DESCRIPTION `5.5.1.9999` | MIT (`DESCRIPTION` L33, `LICENSE.md`; GitHub API says NOASSERTION) |
| [scverse/squidpy](https://github.com/scverse/squidpy) | `1936a92` | 2026-10-01 | (checked for image underlay only) | BSD-3-Clause |

Docs: https://scanpy.readthedocs.io , https://anndata.readthedocs.io , https://satijalab.org/seurat/ .

### Demos

None: these are libraries with no hosted GUI. Tutorials that demonstrate the claims below (HTTP status checked 2026-10-03, all 200):

| Tutorial | Shows |
|---|---|
| https://scanpy.readthedocs.io/en/stable/tutorials/experimental/dask.html | Scanpy + dask on a 1.4M-cell CELLxGENE dataset, lazy chunked X |
| https://anndata.readthedocs.io/en/stable/tutorials/notebooks/read_lazy.html | `anndata.experimental.read_lazy` on a remote GCS Zarr store over HTTP (FsspecStore) |
| https://anndata.readthedocs.io/en/stable/tutorials/zarr-v3.html | "Remote data" section: FsspecStore / ObjectStore with `read_lazy` |
| https://squidpy.readthedocs.io/en/stable/notebooks/tutorials/tutorial_visium_hne.html | Visium spots over H&E image (squidpy) |
| https://satijalab.org/seurat/articles/seurat5_sketch_analysis | Seurat v5 sketch workflow, 1.3M mouse brain cells, BPCells on disk |
| https://satijalab.org/seurat/articles/seurat5_bpcells_interaction_vignette | BPCells on-disk matrices in Seurat |
| https://satijalab.org/seurat/articles/parsebio_sketch_integration | Sketch integration, 1M cells (Parse) |
| https://satijalab.org/seurat/articles/spatial_vignette | `SpatialDimPlot` over the tissue image |

URLs tried that 404: `scanpy.readthedocs.io/en/stable/tutorials/spatial/basic-analysis.html`, `scanpy.readthedocs.io/en/stable/generated/scanpy.pl.spatial.html` (the page now lives at `/api/generated/scanpy.pl.spatial.html`, 200), `scanpy-tutorials.readthedocs.io/en/latest/spatial/basic-analysis.html`.

### Matrix row

Permalinks: scanpy = `https://github.com/scverse/scanpy/blob/7ad567d9f7ca52b23b0ffb964e486034ef14283e/...`, anndata = `https://github.com/scverse/anndata/blob/bb86151f85f0608b9aaa83753ef6ec9eafe9d0b6/...`, seurat = `https://github.com/satijalab/seurat/blob/b1fe7806172bbcdfa31c8e723cb74b5c73691e63/...`, squidpy = `https://github.com/scverse/squidpy/blob/1936a92b365790f27574d3902e30761645847686/...`.

| Column | Current mark | Proposed | Evidence |
|---|---|---|---|
| cell × cell matrix as colour or axis | P | P | Code: `adata.obs["d"] = adata.obsp["distances"][i].toarray().ravel(); sc.pl.umap(adata, color="d")`. Seurat: `obj@graphs` holds cell × cell graphs, same pattern with `FeaturePlot`. No GUI; one re-run per focused cell. |
| gene × gene matrix as colour or axis | P | P | Scanpy: `adata.varp` row into a `var` column, then plotted with matplotlib or `sc.pl.scatter`. Seurat has no gene × gene slot (graphs are cell × cell; `misc` is free-form), so this is Scanpy-only and by code. |
| focused cell/gene drives linked panels | N | **P** | No linked panels exist; "re-drive" means re-running the cells for each focus (or writing an ipywidgets callback). That is exactly the "reachable only by writing code" definition already used for the two columns to its left. See Disagreements. |
| all AnnData slots incl. obsp/varp/varm | Y | **P** | AnnData exposes all slots, but only through code (`adata.obsp[...]`). Under the row's rule this is P. `read_h5ad_backed` loads obsm/varm/obsp/varp/uns/layers: `anndata/src/anndata/_io/h5ad.py#L189` (L195 lists the attributes). Seurat reads h5ad only via conversion packages. |
| lazy chunked reads | P | P | `read_h5ad(backed="r")`: `anndata/src/anndata/_io/h5ad.py#L234`; `anndata.experimental.read_lazy` (added 0.12.0, replacing 0.11's `read_elem_as_dask`, `docs/release-notes/0.12.0.md#L35`, `0.11.0.md#L43`): `anndata/src/anndata/experimental/backed/_io.py#L44`; Seurat BPCells `open_matrix_dir` "does not load the dataset into memory": `seurat/vignettes/seurat5_sketch_analysis.Rmd#L64`. All by code. Note: the brief's "read_lazy in 0.11+" is off by one minor; it is 0.12+. |
| remote stores (S3, GCS, HTTP) | ? | **P** | `read_lazy` with `zarr.storage.FsspecStore` / `ObjectStore`: `anndata/docs/tutorials/zarr-v3.md#L29-L38`; tutorial reads `https://vitessce-demo-data.storage.googleapis.com/anndata-demos/BALF_VIB-UGent_processed_cleaned.zarr/` lazily (read_lazy tutorial above). `read_zarr(store)` also accepts any store/MutableMapping: `anndata/src/anndata/_io/zarr.py#L151`. Seurat/BPCells: no remote reader found (BPCells docs searched for S3/cloud/remote/HTTP, only `remotes::install_github` hits). P on the strength of anndata. |
| spatial coordinates | ? | **P** | `sc.pl.spatial` / `sc.pl.embedding(basis="spatial")`: `scanpy/src/scanpy/plotting/legacy/_tools/scatterplots.py#L967`; Seurat `SpatialDimPlot`: `seurat/R/convenience.R#L313`; `ImageDimPlot` for imaging data: `seurat/R/visualization.R#L2461`. By code. |
| table filters mask plots | P | P | Subsetting by code: `adata[adata.obs.x > t]`, Seurat `subset()` (`seurat/vignettes/essential_commands.Rmd#L224`). No filter table. |
| annotation editing | P | P | Writing `adata.obs[...]` / `Idents<-` by code. Seurat `CellSelector` (Shiny gadget lasso that labels cells) is still launched from code: `seurat/R/visualization.R#L5618`, https://satijalab.org/seurat/reference/cellselector |
| on-the-fly DE | P | P | `sc.tl.rank_genes_groups`: `scanpy/src/scanpy/tools/_rank_genes_groups.py#L753`; Seurat `FindMarkers`: `seurat/R/differential_expression.R#L638`. By code. |
| tissue image underlay | ? | **P** | `sc.pl.spatial(img_key="hires", alpha_img=...)`: `scanpy/.../legacy/_tools/scatterplots.py#L972`, docstring "Use the parameter `img_key` to see the image in the background" (L989); squidpy `sq.pl.spatial_scatter`: `squidpy/src/squidpy/pl/_spatial.py#L397`; Seurat `SpatialPlot(image.alpha=...)`: `seurat/R/visualization.R#L4350` (param doc L4270), spatial vignette "overlaid on the image with `SpatialDimPlot()`": `seurat/vignettes/spatial_vignette.Rmd#L156`. By code. |
| shareable view state | Y | **P** | The "view state" is a script or notebook; reproducing it means re-executing code against the same data. Under the row's rule that is P, not Y. |
| plot export | P | P | `plt.savefig` / ggplot2 `ggsave`. Scanpy's own `save=` argument is now deprecated (`docs/release-notes/1.12.0.md#L36`; warning at `scanpy/src/scanpy/plotting/legacy/_utils.py#L373`). |
| desktop app | N | N | Python/R packages, no application. |
| hosted multi-user | N | N | Not a service. Users can run them inside JupyterHub/RStudio Server, but that is a third-party deployment, not the tool. |
| static site, no server | N | N | Not applicable; no web output beyond static images. |

Proposed string: `"PPP PPPP PPPP PP NNN"` (current `"PPN YP?? PPP? YP NNN"`).

**Scale group**

| Item | Finding | Evidence |
|---|---|---|
| S1 largest single dataset | **1.3M cells** (10x E18 mouse brain) in both the Scanpy paper ("analyzing 1.3 million cells without subsampling") and the Seurat v5 sketch vignette; Scanpy dask tutorial uses **1.4M cells** (COVID-19 atlas, one CELLxGENE dataset). Seurat docs claim scaling "beyond 10 million cells" without a named single dataset; Hao et al. 2024 harmonize **8.6M** profiles, but across many datasets (integration total, not a single dataset). | Wolf 2018, Fig. 1c and text; `seurat/vignettes/seurat5_sketch_analysis.Rmd#L37`; `scanpy/docs/tutorials/experimental/dask.ipynb` (markdown cell "1.4 million cells", ~L441); Hao 2024 abstract (nature.com, fetched 2026-10-03). |
| S2 every cell drawn? | Yes by default: `sc.pl.*` scatters every point (no downsampling mode found); Seurat `DimPlot` draws every cell and **rasterizes** (not downsamples) above 100,000 cells. In the sketch workflow the embedding is first computed and plotted on the sketch subset, then projected to all cells (`ProjectData`) and plotted in full. | `seurat/R/visualization.R#L850-L851`; `seurat5_sketch_analysis.Rmd#L108` (sketch DimPlot) and `#L142` (full.umap, all cells). |
| S3 lazy vs in memory, where | Default is the whole matrix in memory of the user's Python/R process. Opt-in, by code: anndata backed mode (h5ad, X on disk), `read_lazy` (dask/xarray, local or remote Zarr), Scanpy dask support ("highly experimental"), Seurat BPCells on-disk matrices. All in the local analysis process; no browser. | `h5ad.py#L234`, `_io.py#L44`, `dask.ipynb` intro cell, `seurat5_sketch_analysis.Rmd#L42-L47`. |
| S4 user-controlled subset/sample | Yes, by code: `sc.pp.sample` / `adata[mask]`; Seurat `subset()` and `SketchData` (leverage-score sketch, the user chooses `ncells`). | `scanpy/src/scanpy/preprocessing/_simple.py#L726`; `seurat/R/sketching.R#L45`; https://satijalab.org/seurat/reference/sketchdata |

Suggested scale label for the figure: "1.3M cells (paper); sketching for more" in place of "memory-bound library" (which is no longer accurate given backed/lazy/BPCells).

**Why every focus needs a re-run.** A script binds the focused entity as a value (`i = 1234`), extracts that row of `obsp`/`varp` into a column, then draws the plots. Changing the focus means editing `i` and re-executing the extraction and every plotting call; nothing links the panels, so each one is redrawn independently. A notebook widget can automate the loop, but someone has to write it.

**Disagreements with current marks**
- focused cell/gene drives linked panels: N -> P. The row already scores cell × cell and gene × gene as P "via code, re-run per focus"; refocusing a set of panels is the same code path. Keeping N here while the two neighbouring columns are P is internally inconsistent. If the author prefers N, the column definition should say "without code" and then the cell × cell and gene × gene columns should be N too.
- all AnnData slots: Y -> P. Reachable only by writing code (consistent rule).
- remote stores: ? -> P. anndata `read_lazy` + FsspecStore on a public GCS Zarr (zarr-v3.md L29-L38, read_lazy tutorial).
- spatial coordinates: ? -> P. `sc.pl.spatial`, Seurat `SpatialDimPlot`.
- tissue image underlay: ? -> P. `sc.pl.spatial(img_key=...)`, squidpy `spatial_scatter`, Seurat `SpatialPlot(image.alpha=...)`.
- shareable view state: Y -> P. A script is code; consistent rule.
- Scale label: "memory-bound library" -> "1.3M cells (paper); sketching for more" (the "memory-bound" wording is contradicted by backed mode, `read_lazy` and BPCells).
- Caption detail: COMPARISON_NOTES.md row says "L137 (in-memory / backed)" for lazy; correct, but the anndata function for lazy reads is `read_lazy` from 0.12.0, not 0.11.

### Matrix marks, checked in the running app

There is no app, so each P mark is shown by code. Run 2026-10-04 (05:10 to 05:11 UTC, logged in `$DEMO_ROOT/_browser/windows.log`) with scanpy 1.11.5 and anndata 0.12.19 in the paper `.venv`, on the shared bone marrow file (8,090 cells) unless stated. One script makes every figure: [`demos/scanpy-seurat/matrix_check.py`](demos/scanpy-seurat/matrix_check.py) (`.venv/bin/python notes/comparison/demos/scanpy-seurat/matrix_check.py`, about 50 s, most of it the remote read). **Seurat is not installed on this laptop** (`requireNamespace("Seurat")` is FALSE in both `/opt/homebrew/bin/Rscript` and the `rtools` env), so every Seurat statement in this file still rests on the docs only. The remote read needs fsspec, aiohttp, xarray and dask, which the paper venv lacks; the script appends a scratch `--target` install of them to `sys.path` (venv packages keep precedence).

| Column | Mark | Observed | Steps to repeat | Evidence |
|---|---|---|---|---|
| plots render | - | UMAP coloured by `highres_celltype`, all 8,090 cells. | `sc.pl.umap(a, color="highres_celltype")` | [screens/scanpy-seurat/m00_plots_render_umap.jpg](screens/scanpy-seurat/m00_plots_render_umap.jpg) |
| 1 cell × cell matrix | P | Row 4236 of `obsp["connectivities"]` copied to an obs column and drawn on UMAP (and, in the Focus section, `obsp["diffusion_distance"]` on two embeddings). Code only; one re-run per cell. | script block m04; `focus_row.py` | [m04 (right panel)](screens/scanpy-seurat/m04_slots_obsm_layers_obsp_by_code.jpg), [01_obsp_row_by_code.jpg](screens/scanpy-seurat/01_obsp_row_by_code.jpg) |
| 2 gene × gene matrix | P | bm_demo has no varp, so the paper's spatial demo (`data/spatial_demo.zarr`, varp `spearman_hvg`, 2000 × 2000) was used: the row for `Mbp` drawn as a bar axis; top partners `Mobp`, `Plp1`, `Mal` (oligodendrocyte genes, as expected). Code only. | script block m02 | [screens/scanpy-seurat/m02_varp_row_as_axis.jpg](screens/scanpy-seurat/m02_varp_row_as_axis.jpg) |
| 3 focus drives linked panels | P | see Focus section | | |
| 4 all slots | P | One figure reads three slots: `obsm["X_draw_graph_fa"]`, `layers["counts"]` (`layer=`), `obsp["connectivities"]` row. Printed slots: obsm 4, layers 1, obsp 3, uns 3; varm/varp empty in this file. All by code. | script block m04 | [screens/scanpy-seurat/m04_slots_obsm_layers_obsp_by_code.jpg](screens/scanpy-seurat/m04_slots_obsm_layers_obsp_by_code.jpg) |
| 5 lazy chunked reads | P | Observation: `read_h5ad(backed="r")` gives X as `_CSRDataset` (on disk); one gene comes back as an 8090 × 1 `csr_matrix`. But opening alone raised max RSS from 250 to 762 MB: backed mode keeps only X on disk and loads obs, obsm and obsp whole (this file holds a dense 8090 × 8090 `diffusion_distance`, 524 MB). So lazy for X only, and by code. | script block m05 | observation (printed RSS) |
| 6 remote stores | P | Observation: `anndata.experimental.read_lazy(FsspecStore.from_url("https://vitessce-demo-data.storage.googleapis.com/anndata-demos/BALF_VIB-UGent_processed_cleaned.zarr/"))` opened 275,056 × 24,740 in 0.7 s (X is a dask `Array`); one gene column came over HTTP in 41.7 s. Code only, and needs optional packages (fsspec, aiohttp, xarray, dask) that a plain scanpy install lacks. | script block m06 | observation  Also checked 2026-10-04 against public, **anonymous** stores with no credentials ([`demos/remote/anndata_remote.py`](demos/remote/anndata_remote.py); anndata 0.13.4, zarr 3.4.0, s3fs/gcsfs): `s3://lamindata/.lamindb/CFcQxNjzSRzWZrVh.anndata.zarr` (46,086 x 21,972), lazy open 24.5 s, one gene 5.2 s; `gs://vitessce-demo-data/habib-2017/habib17.processed.h5ad.zarr` (13,067 x 25,587), lazy open 5.5 s, one gene 0.2 s. Code only, so P holds. |
| 7 spatial coordinates | P | 10x V1_Human_Lymph_Node (3,962 spots), `obsm["spatial"]` from its `tissue_positions_list.csv`; `sc.pl.spatial(img_key=None)` draws the spots at tissue coordinates. | script block m07/m11 (data in `$DEMO_ROOT/cirrocumulus/lymph/`) | [screens/scanpy-seurat/m07_m11_spatial_and_image_underlay.jpg](screens/scanpy-seurat/m07_m11_spatial_and_image_underlay.jpg) (left) |
| 8 table filters mask plots | P | `a[a.obs.highres_celltype == "Neutrophil"]` (2,221 cells) replotted on the same axes. No filter table; the subset is a code expression. | script block m08 | [screens/scanpy-seurat/m08_filter_by_code.jpg](screens/scanpy-seurat/m08_filter_by_code.jpg) |
| 9 annotation editing | P | A UMAP rectangle became `obs["my_label"]` (1,324 `my_region`, 6,766 `other`), written to an h5ad (557 kB) and read back with the same counts. Code only. | script block m09 | [screens/scanpy-seurat/m09_annotation_by_code.jpg](screens/scanpy-seurat/m09_annotation_by_code.jpg) |
| 10 on-the-fly DE | P | `sc.tl.rank_genes_groups(..., groups=["my_region"], reference="other", method="wilcoxon")` on that label in 3.9 s; top genes Ighm, H3f3a, Ebf1, Cd79a, Vpreb3 (the rectangle sits on the B lineage). | script block m10 | [screens/scanpy-seurat/m10_rank_genes_groups_by_code.jpg](screens/scanpy-seurat/m10_rank_genes_groups_by_code.jpg) |
| 11 tissue image underlay | P | Same spots with `img_key="hires"`: clusters over the H&E (the `uns["spatial"]` entry was built from the 10x `spatial/` folder, as `sc.read_visium` does). | script block m07/m11 | [screens/scanpy-seurat/m07_m11_spatial_and_image_underlay.jpg](screens/scanpy-seurat/m07_m11_spatial_and_image_underlay.jpg) (right) |
| 12 shareable view state | P | Observation: the "state" is the script. Running the same plotting function twice gave byte-identical PNGs (md5 equal), so sending the script plus data reproduces the view; nothing else stores a view. | script block m12 | observation |
| 13 plot export | P | `fig.savefig` wrote `umap_compartment.pdf` (135,776 bytes) and `.png` (95,579 bytes). scanpy 1.11.5 raised no warning for `save=`; the deprecation cited above is in 1.12. | script block m13 | observation (file sizes) |
| 14 desktop app | N | N: nothing to show; there is no application, only `import scanpy`. | | |
| 15 hosted multi-user | N | N: nothing to show; not a service. | | |
| 16 static site, no server | N | N: nothing to show; outputs are image files, no web viewer. | | |

Contradictions found: none. Two qualifications for the notes: lazy reads (column 5) cover X only, since backed mode loads obsp whole (762 MB RSS on this 8k-cell file); remote reads (column 6) need optional packages beyond a scanpy install. Seurat was not run.

### Focus, feature colouring and selection (checked in the running app)

There is no app. Scanpy was run on 2026-10-03 in the paper `.venv` (scanpy, matplotlib Agg) on the shared bone marrow file; Seurat is not installed here, so its column below comes from the Seurat docs and **was not run**.

| Behaviour | What happens | Steps to repeat | Screenshot |
|---|---|---|---|
| (a1) one cell's relation row as colour in other views | Possible only by writing code: copy row `i` of `obsp` into an `obs` column, then call each plot again. Every new focus means editing `i` and re-running the extraction and every plot call; nothing re-draws by itself. | `/usr/bin/lockf -k ~/.annzarro-bench.lock .venv/bin/python notes/comparison/demos/scanpy-seurat/focus_row.py`; it writes the figure. Change `i` and re-run for another cell. | [screens/scanpy-seurat/01_obsp_row_by_code.jpg](screens/scanpy-seurat/01_obsp_row_by_code.jpg) |
| (a2) one gene colours several views | Only if the code passes the same `color=` to each plot call; there are no linked views. | Same script, second figure: `sc.pl.umap(adata, color="Mpo")`. | [screens/scanpy-seurat/02_feature_colouring_Mpo.jpg](screens/scanpy-seurat/02_feature_colouring_Mpo.jpg) |
| (b) selection cross-filters other views | Scanpy: no interactive selection at all (static matplotlib). Seurat (docs, not run): `CellSelector(plot)` lets you lasso cells in one `DimPlot` and **returns their names to R**; any other plot must then be redrawn by code, e.g. `DimPlot(obj, cells.highlight = sel)`. | Seurat: `p <- DimPlot(obj); sel <- CellSelector(p); FeaturePlot(obj, "Cd74", cells = sel)` ([CellSelector reference](https://satijalab.org/seurat/reference/cellselector)). | none |
| single-cell click | Scanpy: nothing (static image). Seurat (docs): `HoverLocator(plot)` shows cell info on hover; clicking does not drive anything. | n/a | none |

The scanpy code that produced screenshot 01 (exact):

```python
adata = sc.read_h5ad("$DEMO_ROOT/_data/bm_demo.h5ad")
i = 4236                                     # the focused cell: change this and re-run
row = adata.obsp["diffusion_distance"][i]    # dense ndarray in this file
row = np.asarray(row.todense()).ravel() if hasattr(row, "todense") else np.asarray(row).ravel()
adata.obs["d"] = row                         # copy ONE relation row into obs
fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
sc.pl.umap(adata, color="d", ax=axes[0], show=False, title=f"diffusion distance to cell {i}")
sc.pl.embedding(adata, basis="X_draw_graph_fa", color="d", ax=axes[1], show=False)
```

Output: `adata.obs_names[4236]` is `Mature_Young_2#TCAATTCAGTGAGGCT-1`; obsp keys `connectivities`, `diffusion_distance`, `distances`. Both panels show the same row (dark = near the circled monocyte), but only because the code drew both from the same column.

Seurat equivalent (from the docs, **not run**): Seurat keeps cell × cell graphs in `obj@graphs` (`Graph` objects, sparse), and `FeaturePlot` accepts any `meta.data` column ([FeaturePlot reference](https://satijalab.org/seurat/reference/featureplot), "features ... A column name from meta.data"):

```r
i <- "Mature_Young_2#TCAATTCAGTGAGGCT-1"
obj$d <- as.numeric(obj[["RNA_snn"]][i, ])      # one row of the SNN graph
FeaturePlot(obj, features = "d") | FeaturePlot(obj, features = "d", reduction = "pca")
```

`FeaturePlot(..., interactive = TRUE)` opens a Shiny gadget for changing the feature in one plot; it does not link plots or take a focused cell.

**Marks**

- `Column 3 (strict): P` (unchanged from the proposed P; was N in `fig_comparison.py`). The relation row reaches the plots only through code that is re-run for each focus, which is exactly the "reachable only by code" case.
- `Proposed column "selection cross-filters linked views": P`. Seurat's `CellSelector` makes a lasso selection that comes back as cell names and reaches other plots only through code; Scanpy alone would be N (no selection), so P holds for the row only because of Seurat.

**Could not do:** Seurat is not installed on this laptop, so neither the `obj@graphs` row nor `CellSelector` was run; both rest on the linked reference pages.

### How to validate it yourself

1. Open https://anndata.readthedocs.io/en/stable/tutorials/notebooks/read_lazy.html and confirm `read_lazy` reads `https://vitessce-demo-data.storage.googleapis.com/anndata-demos/BALF_VIB-UGent_processed_cleaned.zarr/` through an `FsspecStore` (remote = P).
2. Open https://anndata.readthedocs.io/en/stable/tutorials/zarr-v3.html, section "Remote data" (FsspecStore and ObjectStore both work with `read_lazy`).
3. Open https://anndata.readthedocs.io/en/stable/generated/anndata.io.read_h5ad.html and read the `backed` parameter (lazy = P; only X updates persist).
4. Open https://scanpy.readthedocs.io/en/stable/api/generated/scanpy.pl.spatial.html and find `img_key`, `alpha_img` (spatial axes and image underlay = P).
5. Open https://satijalab.org/seurat/articles/spatial_vignette and find the `SpatialDimPlot` figure over the H&E image.
6. Open https://satijalab.org/seurat/articles/seurat5_sketch_analysis : intro says 1.3M cells, "beyond 10 million"; `open_matrix_dir` "does not load the dataset into memory"; `SketchData` subset; final `DimPlot` on `full.umap` (S1 to S4).
7. Open https://satijalab.org/seurat/reference/dimplot and read `raster`: "automatically rasterizes if plotting more than 100,000 cells" (S2: rasterize, not downsample).
8. Open https://scanpy.readthedocs.io/en/stable/tutorials/experimental/dask.html : 1.4M cells, and the "highly experimental" warning.
9. Open https://doi.org/10.1186/s13059-017-1382-0 and find "analyzing 1.3 million cells without subsampling"; open https://doi.org/10.1038/s41587-023-01767-y and read the abstract's "8.6 million human immune cell profiles" (multi-dataset).
10. Decide the one judgement call: is "focused cell/gene drives linked panels" P (consistent with the cell × cell and gene × gene P marks) or N (if the column means "without code", then those two drop to N too).
11. Focus vs selection: run `notes/comparison/demos/scanpy-seurat/focus_row.py` under the bench lock, change `i`, re-run, and compare with the section "Focus, feature colouring and selection" above (one re-run per focus).
