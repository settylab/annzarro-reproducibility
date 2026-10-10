## ManiVault Studio (Cytosplore)

> **Column order note (2026-10-04).** Fig. 1c has 18 columns: the Scale group holds lazy reads, every cell drawn and user subset. Column 3 uses the strict definition: "a focused cell or gene, through its stored pairwise row, re-drives every linked panel". The authoritative marks and evidence are in `evidence/matrix/tools/manivault.yaml`.

### What it is

ManiVault Studio is a plugin-based desktop framework for visual analytics of high-dimensional data, written in C++, Qt and OpenGL. It comes from LUMC and TU Delft. Cytosplore Viewer, the viewer for the Allen brain cell-type atlases, is built on it, and so was the earlier Cytosplore for mass cytometry. Its own scale design is HSNE, which shows hierarchical landmarks and lets the user drill down into them.

- **Primary paper** (Crossref-verified): Vieth A, Kroes T, Thijssen J, van Lew B, Eggermont J, Basu S, et al. ManiVault: A Flexible and Extensible Visual Analytics Framework for High-Dimensional Data. *IEEE Trans Vis Comput Graph* (2023), 1-11. [doi:10.1109/TVCG.2023.3326582](https://doi.org/10.1109/TVCG.2023.3326582). Cited 5 times.
- **Scale paper** (Crossref-verified): van Unen V, Höllt T, Pezzotti N, Li N, Reinders MJT, et al. Visual analysis of mass cytometry data by hierarchical stochastic neighbour embedding reveals rare cell types. *Nat Commun* 8, 1740 (2017). [doi:10.1038/s41467-017-01689-9](https://doi.org/10.1038/s41467-017-01689-9). HSNE was used there on up to 15 million cells (CyTOF, about 30 markers). Cited 222 times.
- **Scored version:** ManiVault Studio **1.5.0-dev** as the app reports it: the official "ManiVault 1.5.0 macOS installer" [`manivault_1.5.0_mac.dmg`](https://github.com/ManiVaultStudio/Releases/releases/tag/manivault_1.5.0_mac). It is 303,070,062 bytes, and its sha256 `06837bc1…aa77287` matches GitHub's digest. It is a universal binary (arm64 and x86_64), notarized under Developer ID. The app reports 1.5.0-dev because the dmg was built from a pre-release commit: core's VERSION file has SUFFIX "dev", while the v1.5.0 tag has SUFFIX "" (checked 2026-10-04). No release-tagged macOS build exists; 1.5.1 is Windows and Ubuntu only. Supp Note 1 should say "ManiVault Studio 1.5.0-dev".
- **Source:** [ManiVaultStudio/core](https://github.com/ManiVaultStudio/core) at `3451a06` (2026-09-25), and the H5AD loader [ManiVaultStudio/HDF5Loader](https://github.com/ManiVaultStudio/HDF5Loader) at `8907734` (2026-09-07). Site: [manivault.studio](https://www.manivault.studio/). Licence: LGPL-3.0.

### How it was checked

ManiVault is a native app with no scripting route, and this terminal may not capture or drive windows. It was therefore run in a Claude desktop session with computer use (user decision X7). That session followed the 20-step [checklist](manivault_checklist.md) on the shared bone marrow demo (`bm_demo.h5ad`, 8,090 cells) on 2026-10-04 and logged one line per step ([session notes](demos/manivault/session_notes.txt)). It asked one question, about step 6, which is answered in [ANSWERS.md](demos/manivault/ANSWERS.md).
- The 19 screenshots are in [`screens/manivault/`](screens/manivault/). Each has a manual sidecar pinned by sha256, with boxes read off the image.
- Plot shots come from the view's own Screenshot action (F2). Those PNGs have red and blue swapped relative to the screen; see export.

### Matrix row (proposed; ManiVault is not yet in Fig. 1c)

| Column | Proposed | Observed in the app (2026-10-04) | Evidence |
|---|---|---|---|
| cell × cell matrix | **Y** | The loader brings in obsp by default. Datasets > Color offers obsp/connectivities, obsp/diffusion_distance and obsp/distances. Colouring the UMAP by `diffusion_distance` dimension "4237" shows one cell's row. Rows are chosen by number: 1-based for dense input, 0-based for sparse input. They are not chosen by cell. | [m01 sources](screens/manivault/m01_cells_colour_sources.jpg), [m01 row](screens/manivault/m01_cells_obsp_row_as_colour.jpg); [HDF5_AD_Loader.cpp L317-L327](https://github.com/ManiVaultStudio/HDF5Loader/blob/89077343023b0d6767b4308c1f507a45964e4195/src/H5ADLoader/HDF5_AD_Loader.cpp#L317-L327), [H5ADUtils.cpp L1303-L1306](https://github.com/ManiVaultStudio/HDF5Loader/blob/89077343023b0d6767b4308c1f507a45964e4195/src/H5ADLoader/H5ADUtils.cpp#L1303-L1306) |
| gene × gene matrix | N | varp is never offered. | [m04 loader](screens/manivault/m04_slots_loader_dialog.jpg) |
| focus (strict) | N | A click on a cell does nothing, and the obsp row is picked by number, not by a focused cell. | [m03](screens/manivault/m03_focus_gene_colouring.jpg) |
| all slots | P | X, layers, obs, obsm and obsp load; varm, varp and uns do not. | [m04 hierarchy](screens/manivault/m04_slots_data_hierarchy.jpg) |
| remote stores | N | Data are opened through a local file dialog only. | source |
| spatial coordinates | P | Not observed. The Visium demo's X is stored as CSC, and the loader reads X as CSR ([H5ADUtils.cpp L456-L462](https://github.com/ManiVaultStudio/HDF5Loader/blob/89077343023b0d6767b4308c1f507a45964e4195/src/H5ADLoader/H5ADUtils.cpp#L456-L462)). It therefore loaded 2,000 × 2,000 with no obs or obsm. The file itself is correct: 2,693 spots, checked with h5py. A 2-D obsm such as X_umap plots fine, so obsm['spatial'] in a CSR file should plot too. | [m05](screens/manivault/m05_spatial_csc_input_misread_hierarchy.jpg) |
| table filters | N | No filter panel; the closest control is Subset. | [m07](screens/manivault/m07_filters_panel.jpg) |
| annotation editing | **Y** | Desktop follow-up: Clustering popup (2x2-grid icon) > name, colour, target cluster dataset > Add cluster turned a lasso selection into **my_cells (442 cells)** in leiden; Export > Clusters (JSON) wrote name, colour and indices. Quirks: fields stay disabled until a target dataset is chosen (why the first session missed it); choosing leiden switched the colouring to leiden; adding into an existing set leaves those cells in two leiden clusters. Same criterion as CELLxGENE Annotate and UCSC (named labels stored as data, exported from the GUI). | [f1](screens/manivault/f1_annot_clustering_popup.jpg), [f2](screens/manivault/f2_annot_cluster_added.jpg), [JSON](demos/manivault/f3_my_cells_clusters.json) |
| on-the-fly DE | N | Analyze offers HSNE, t-SNE, UMAP, PCA, mean-shift and examples. | [m09](screens/manivault/m09_de_analyze_menu.jpg) |
| tissue image underlay | N | Render Mode offers Scatter, Density and Contour; there is no image layer. | [m10](screens/manivault/m10_image_layers.jpg) |
| shareable view state | Y | A .mv project (1.88 GB, data included) reopens with its views, colouring and HSNE datasets, but not the selection. | [m11](screens/manivault/m11_share_project_reopened.jpg) |
| plot export | P | F2 saves PNG only, with no size options, and the saved colours differ from the screen (red and blue swapped). | [m12](screens/manivault/m12_export_screenshot_dialog.jpg) |
| desktop app | Y | Notarized installers for macOS, Windows and Ubuntu. | release page |
| hosted multi-user | N | Desktop only. | docs |
| static site | N | None found. | docs |
| lazy reads | N | X is held dense in memory: storage "Owner", 502.57 MiB = 8,090 × 16,285 × 4 bytes. | [m16](screens/manivault/m16_lazy_data_properties.jpg) |
| every cell drawn | Y | The scatterplot draws all 8,090 cells. HSNE is optional; its top level shows 300 landmarks. | [m00](screens/manivault/m00_render_umap.jpg), [m17](screens/manivault/m17_every_cell_hsne_top_level.jpg) |
| user subset | Y | HSNE "Refine selection" (2,749 cells give 2,858 points at the next level), and "Create subset". | [m18](screens/manivault/m18_subset_hsne_refine.jpg), [m07](screens/manivault/m07_filters_panel.jpg) |
| *selection cross-filters (proposed column)* | Y | A lasso in the UMAP highlights the same 1,376 cells in the force-directed view. | [m19 UMAP](screens/manivault/m19_selection_linked_umap.jpg), [m19 FA](screens/manivault/m19_selection_linked_fa.jpg) |

**Two findings for the paper.**
- ManiVault is the only other GUI tool in the audit that can colour a plot by a stored obsp row. That makes the cell × cell column Y by its definition.
- What it lacks is AnnZarro's distinctive step. The row is chosen by number in a dimension field, so no focused cell drives linked panels, and the focus column stays N. The text should name the difference precisely, not claim that no other tool can show obsp.

**Scale.** The documented largest dataset is 15 million cells (HSNE, CyTOF, van Unen 2017). On the bone marrow demo X is held dense (m16: 502.57 MiB = 8,090 x 16,285 x 4 bytes). The earlier extrapolation from that (dense float32, about 20 KB per cell for 5,000 genes, so about 18.6 GiB at 1M and over the 16 GiB budget) was wrong. Measured in the ceiling-benchmarker desktop session (benchmark/tool_ceiling/results.csv, rows manivault_default_*): every cell drawn at 0.25M (4.06 GiB), 0.5M (6.94 GiB) and 1M (12.73 GiB); 2M drew every cell too but took 24.35 GiB, over the 16 GiB client budget. Ceiling: 1M. The growth, about 11-12 GiB per million cells, fits dense 2-byte storage (the loader's default "Data Type: Optimized (lossless)", the bf16 path at H5ADUtils.cpp L460) plus overhead. That is an inference, not checked in Data properties.

**Scope of this row:** it scores ManiVault Studio 1.5.0 only. Cytosplore Viewer 5.0.0 is a separate distribution on the same framework, with its own plugin set; the ManiVault paper's Fig. 11 credits it with a differential-expression option. It was not examined.

**Not scored:**
- After saving a project, File > New Project crashed the app once.
- File > Publish was not tried.

### How to validate it yourself

1. Install from the release page above and open `bm_demo.h5ad` via File > Import data... > H5AD Loader. Leave obs, obsm and obsp ticked.
2. Open a scatterplot on obsm/X_umap. In the Datasets popup, set Color to obsp/diffusion_distance and type 4237 in Dimension. The UMAP now shows the distances from cell 4236.
3. Lasso in the UMAP, open a second scatterplot on X_draw_graph_fa, and check that the same cells light up there.
4. Right-click X > Analyze > HSNE > Start. The top level has 300 landmarks. Lasso some of them, then press Data properties > Refine selection.
5. Data properties of X: storage Owner, 502.57 MiB.
6. Press F2 in a view and compare the saved PNG's colours with the screen.
7. Re-save `spatial_demo.h5ad` with a CSR X (for example `adata.X = adata.X.tocsr()`) and load it again. Expect obsm/spatial to appear and to plot as axes.

### Compatibility note: h5ad from anndata 0.13 with pandas 3 does not open

Found in the ceiling-benchmarker desktop session (2026-10-05). This is a format-version limit, not a scale result.

- **What happens:** File > Import data... > H5AD Loader on a 250,000-cell h5ad written by anndata 0.13.4 with pandas 3.0.6. ManiVault answers at once, before the "Load:" dialog: "Could not open <file>. Make sure the file has the correct file extension and is not corrupted." The screenshot is `$DEMO_ROOT/manivault/session_v031/shots/250000_1_error.png`.
- **Why:** pandas 3 infers its string dtype for the obs and var index. anndata then writes `obs/_index` and `var/_index` as `nullable-string-array` groups (`values` plus `mask`), not as string datasets.
- **The loader's side:**
  - `HDF5_AD_Loader::open()` (HDF5Loader `8907734`, [HDF5_AD_Loader.cpp#L28-L80](https://github.com/ManiVaultStudio/HDF5Loader/blob/89077343023b0d6767b4308c1f507a45964e4195/src/H5ADLoader/HDF5_AD_Loader.cpp#L28-L80)) takes the var dimension names from `LoadIndexStrings`.
  - [H5ADUtils.cpp#L554-L584](https://github.com/ManiVaultStudio/HDF5Loader/blob/89077343023b0d6767b4308c1f507a45964e4195/src/H5ADLoader/H5ADUtils.cpp#L554-L584) reads `_index` only when it is a dataset.
  - With no dimension names, `open()` returns false, and [H5ADLoader.cpp#L150](https://github.com/ManiVaultStudio/HDF5Loader/blob/89077343023b0d6767b4308c1f507a45964e4195/src/H5ADLoader/H5ADLoader.cpp#L150) shows the message.
- **Same data, older writer:** written with anndata 0.11.4 and pandas 2.3.3, the index is a vlen-string dataset (the form the loader reads; the retry, run r1, tests it in the app). That is the encoding of every other ceiling-benchmarker input; the faulty copy is kept as `tahoe_first250000.anndata0134.h5ad`.
- **Who it affects:** anyone on current anndata with pandas 3. A workaround is to write with an object-dtype index (pandas `future.infer_string` off) or to use an older anndata.

### Tool-ceiling desktop session (v031), conditions

These conditions apply to every ManiVault row in benchmark/tool_ceiling/results.csv.

- **Load dialog:** the H5AD Loader's "Load:" dialog defaulted to obs, obsm and obsp ticked, and they were left ticked. The Tahoe inputs have an empty obsp, so nothing extra was loaded. "Select Dimensions" listed 5,000 genes, and all were accepted.
- **Status bar message:** after the Scatterplot opened, the status bar showed "Failed to load DensityCompute shader". The scatter points were drawn regardless; the density render mode was not used.
- **Stray launch:** one unintended Loupe Browser launch (about 20:06, before 250000 attempt 2) was quit before ManiVault opened for that size.
- **Retired attempts** (summarize.py HARNESS_FAILURES):
  - 250000 r0 is an input fault (see the compatibility note above).
  - 500000 r0: the session quit the app before writing drawn_, although all 500,000 points had been drawn.
