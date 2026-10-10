## Loupe Browser: checklist for scoring it in the running app

This is for the desktop session (computer use) to run by hand in Loupe Browser 9.1.0. It produces one or more screenshots per Fig. 1c column. Loupe is a native desktop app that this terminal cannot drive or capture, so the session does the clicking and saves the images. The comparison auditor then boxes, captions and scores them, from what the screenshots and the session notes show. Until then, Loupe's marks rest on its documentation only (`screens/loupe/*_DOCS_*`).

**Time.** About 40 minutes. Nothing here computes for long on 8,090 cells.

**Data.** `$DEMO_ROOT/loupe/validation/bm_demo.cloupe`, built from the shared bone marrow demo `bm_demo.h5ad`: the same 8,090 cells × 16,285 genes every Fig. 1c tool was scored on. It was built with LoupeR `create_loupe()` ([build script](demos/loupe/bm_build.R)) and contains:
- raw UMI counts (from `layers/counts`);
- barcodes such as `HSPC_Young_1_AAAGAACGTGGAAGTC-1` (the h5ad's `#` became `_`, the form LoupeR accepts);
- eight categorical clusterings: Age, Compartment, Replicate, Sample, highres_celltype, leiden, midres_celltype, phase;
- four projections: umap, draw_graph_fa, pca (PC1-2), diffusion (DC1-2).

LoupeR cannot carry numeric metadata, neighbour graphs, spatial positions or images, so a few columns cannot be shown with this file (marked "not testable here" below).

**Names.** Loupe's control names below come from its documentation. If a name differs in 9.1.0, use the closest control and write down the name you actually saw. That is evidence too.

**Before you start**
- Open Loupe Browser from /Applications. The operator is already signed in; skip any tour you can skip.
- Open the file with **File > Open**, not by double-click: `$DEMO_ROOT/loupe/validation/bm_demo.cloupe`.
- Save every image into `notes/comparison/screens/loupe/`, with the **exact file name** given in bold. Use a window shot: **⌘⇧4, then Space, then click the Loupe window**. It saves to the Desktop, so move the file and rename it. Check that each shot shows the Loupe window, not the remote-control overlay. If Loupe's own export (camera icon) offers a PNG, it is fine for plot-only shots, saved under the same name.
- After each step, write one line in `$DEMO_ROOT/loupe/validation/session_notes.txt`: the step number, the file name, and what you saw (for example "8,090 barcodes in header" or "no gene-gene option"). If a step does not work as described, write what you got.

### Load and render

1. **File > Open** `bm_demo.cloupe`. Note how long it takes until the plot appears. Pick the **umap** projection (projection menu, usually top left) and colour by the **highres_celltype** clustering. Window shot: **m01_plots_APP_umap_highres_celltype.png**.
   - Note the total number of cells (barcodes) Loupe shows and where you read it (header, or the sum of the cluster counts). It should be 8,090.
2. Zoom into a dense cluster (scroll or zoom tool) until single points separate. Window shot: **m16_every_cell_APP_zoomed_points.png**.
   - Is every cell drawn, or is there any sign of sampling, binning or density shading (a notice, a "showing N of M" label, a setting)? Write what you see. Then reset the zoom.

### Pairwise matrices and focus

3. Look through every view and menu for a neighbour graph, cell-cell distance or similarity view, or any way to colour cells by their relation to one chosen cell. Window shot of the view/plot-type menu: **m02_cells_APP_view_menu.png**.
   - Note "none found", or the name of anything that comes close.
4. Same for genes: any gene-gene correlation, co-expression or similarity view? Window shot of the feature/gene panel: **m15_genes_APP_feature_panel.png**.
5. Switch to **Feature (Gene) Expression**, search **Mpo** and select it. The umap colours by Mpo. Window shot: **m03_focus_APP_gene_mpo.png**.
6. Click a single cell in the umap (no lasso). Does anything change in any other panel, or does a detail box appear? Window shot: **m03_focus_APP_cell_click.png**.

### Slots and inputs

7. Open the clustering list (Categories / Clusters panel) so all eight clusterings show. Window shot: **m04_slots_APP_clusterings.png**.
8. Open the projection menu so all projections show (expect umap, draw_graph_fa, pca, diffusion). Window shot: **m04_slots_APP_projections.png**.
9. Open the **File** menu and any "Open" submenu. Is there any way to open data from a URL, a server or cloud storage, rather than a local file? Window shot with the menu open: **m06_remote_APP_file_menu.png**.
   - Do not sign in to anything or open any cloud item. Just look and note.

### Selection, annotation, DE, filters

10. Choose the **lasso** (or rectangle) selection tool and select a clear island of cells on the umap, for example one cell type. Window shot: **m18_selection_APP_lasso_umap.png**. Note the selected cell count.
11. Keep the selection, switch the projection to **draw_graph_fa**. Are the same cells still highlighted there? Then open any other plot type Loupe offers (violin, heatmap or dot plot). Does it follow the selection? Window shot of what you see: **m18_selection_APP_other_view.png**.
    - Write down exactly what follows the selection and what does not.
12. From the selection, make a new group: **Create new category** (or "Add to cluster"/"New cluster"). Name the category `audit` and the group `lasso1`. Window shot showing the new category in the list: **m09_annotation_APP_new_category.png**.
13. Run differential expression for `lasso1` against the rest: **Significant Features** / **Differential Expression**, choose `lasso1` vs all other cells, run. Window shot of the result table: **m10_de_APP_lasso1_vs_rest.png**. Note how long it took.
14. Open the **filter** tools (feature expression threshold or category filter). Set one filter, e.g. Mpo above a threshold, or only one Age. Window shot: **m08_filters_APP_filter_set.png**. Note whether the plot then hides the other cells or only greys them. Remove the filter.
15. Look for **Reanalyze** (or another way to work on a barcode subset). Open its dialog to see the options, then **Cancel**: do not run it. Window shot of the dialog: **m17_subset_APP_reanalyze_dialog.png**.
    - Note what it offers (choose barcodes, filters, a cell cap) and whether it would write a new file.

### Share, export, desktop

16. **File > Save As...** into `$DEMO_ROOT/loupe/validation/`, file name `bm_demo_saved.cloupe`. This is the one save allowed; it is a copy of our own demo file. Close it, then **File > Open** the saved copy. Is the `audit` category still there? Window shot after reopening: **m12_share_APP_reopened_with_category.png**.
17. Use Loupe's plot export (camera/export icon, or File > Export). Window shot with the export options visible: **m13_export_APP_export_options.png**. If it offers PNG or SVG, save one into `$DEMO_ROOT/loupe/validation/` as `export_umap` (with the format's extension) and note the format.
18. Open **Loupe Browser > About Loupe Browser**. Window shot: **m14_desktop_APP_about.png**. Note the exact version string.

### Not testable with this file

- Spatial positions and tissue images (columns spatial, image): LoupeR builds no spatial data, and the bone marrow demo has none. They stay scored from the documentation (`m07_spatial_DOCS_*`, `m11_image_DOCS_*`) unless the operator has a Visium `.cloupe` at hand. If so, open it and shoot **m07_spatial_APP_spots.png** and **m11_image_APP_he_under_spots.png**.
- Hosted, static: Loupe is a desktop application. The About box (step 18) is the visual.
- Lazy reads: while you work, the comparison auditor records Loupe's memory from a terminal. You do nothing for this beyond step 1's load-time note.

### Finish

19. Quit through **Loupe Browser > Quit**. If asked to save changes, choose **Don't Save** (the saved copy from step 16 is enough).
20. Write the last line of `session_notes.txt`: "done", plus anything odd.
