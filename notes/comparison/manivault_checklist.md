## ManiVault Studio: checklist for scoring it in the running app (route c)

This is for you to run by hand. It produces one screenshot per matrix column. ManiVault Studio is a native desktop app, and this session cannot drive or capture its windows, so you do the clicking and save the images. I then box, caption and score them.

**Time.** About 45 minutes, plus a few minutes for HSNE (step 9) to compute on 8,090 cells.


**Exact names in ManiVault 1.5.0, from its source (core 3451a06):**
- Loading: **File > Import data...** opens a submenu of loaders; pick the one with "H5AD" in its name. The same loaders are in the right-click menu of the Data hierarchy panel, under **Import**.
- Panels: **Data hierarchy** is the dock with a tree of datasets, usually on the left. **Data Properties** sits below it and shows the selected dataset's details.
- Right-clicking a dataset in Data hierarchy shows the submenus **Analyze** (HSNE, t-SNE, UMAP, PCA, Mean Shift), **View** (Scatterplot, Heatmap, Image Viewer, Parallel Coordinates, ...), **Transform**, **Export** and **Data**. To open a view on a dataset, use right-click > View > Scatterplot, or drag the dataset onto the empty central area.
- **F2 screenshot:** first click inside the plot so the view has keyboard focus; F2 only works then. It opens a **"Save Screenshot"** file dialog: type the full path, e.g. `$DEMO_ROOT/manivault/shots/m00_render_umap.png`. It saves a PNG of that one view, without the panels around it. The view's settings (⚙) menu has the same action as "Screenshot...".
- **Projects:** File > **Save Project As...**, and File > **Open project from disk**, whose tooltip reads "Open project from disk".

**Before you start**
- App: `$DEMO_ROOT/manivault/ManiVault Studio/ManiVault Studio.app`, version 1.5.0. It is the official macOS build and notarized, so double-click opens it. No /Applications install is needed.
- Data: `$DEMO_ROOT/_data/bm_demo.h5ad`. This is the paper's bone marrow demo: 8,090 cells × 16,285 genes, with obsm UMAP, PCA, diffusion and force-directed layouts, and obsp `connectivities`, `distances` and a dense `diffusion_distance`.
- Save every image into `$DEMO_ROOT/manivault/shots/` (create the folder), with the **exact file name** given in bold.
- There are two ways to take a shot:
  - **F2**, or the view's ⚙ menu > "Screenshot...", saves one view. Use it for plots.
  - **⌘⇧4, then Space, then click the window** saves a whole window, menu or dialog. Use it when a step says "window shot". It saves to the Desktop, so move the file into `shots/` and rename it.
- After each step, write one line in `shots/notes.txt`: the file name and what you saw (for example "obsp listed: yes" or "no colour option for obsp"). If a step does not work as described, write down what you got. That is evidence too.

### Load the data

1. Open ManiVault Studio. If a start page shows, choose a blank project.
2. Choose **File > Import data...** and pick the loader with "H5AD" in its name. Select `$DEMO_ROOT/_data/bm_demo.h5ad`.
3. A "Load:" dialog lists the file's top-level groups, with the obs-prefixed ones ticked by default (obs, obsm, obsp). Take a window shot: **m04_slots_loader_dialog.png**.
   - It shows which AnnData slots it offers. The source says it hides X, uns, var, varm and varp from this list and loads X as the main matrix.
4. Leave obs, obsm and obsp ticked (also tick `layers` if it is listed) and press OK. Wait until loading finishes. Take a window shot of the **Data hierarchy** panel with every node expanded: **m04_slots_data_hierarchy.png**.
   - Look for what came in: one entry per obsm layout, and whether `obsp/connectivities`, `obsp/distances` and `obsp/diffusion_distance` appear as datasets and with how many dimensions.

### Plots

5. In Data hierarchy, right-click the UMAP dataset (from obsm, probably `X_umap`) > **View > Scatterplot**, or drag it onto the empty central area. A Scatterplot view opens. Click inside it, then Press F2: **m00_render_umap.png**.
   - Is every cell drawn? The point count is in the Data properties panel. Note it.
6. In the scatterplot's settings, open the colour menu ("Color" / "Point color" / "Mapping"). Take a window shot with the list of colour sources open: **m01_cells_colour_sources.png**.
   - This is the key cell × cell check. Can you colour by `obsp/diffusion_distance`, and if so by which column? If its dimensions are offered, pick the dimension for cell `Mature_Young_2#TCAATTCAGTGAGGCT-1` (index 4236). If that works, the UMAP colours by one cell's diffusion-distance row. F2: **m01_cells_obsp_row_as_colour.png** (only if it worked; otherwise note "not offered").
7. Same idea for genes. Is there any way to colour by a gene × gene matrix? The source suggests no, because varp is skipped. Note it. No shot is needed if the colour list in m01 already shows only obs and gene sources.
8. Colour the UMAP by one gene, `Mpo` (pick the X dataset as the colour source, then the dimension `Mpo`). F2: **m03_focus_gene_colouring.png**.
   - Then click a single point. Does anything happen in other views? Note it. This is focus, scored strictly: only a stored-relation row counts.

### Analysis

9. In Data hierarchy, right-click the X dataset (or the PCA dataset from obsm) > **Analyze > HSNE** (the item name may be "HSNE Analysis"). Keep the defaults and start. When it finishes, open the HSNE embedding in a scatterplot. F2: **m17_every_cell_hsne_top_level.png**.
   - Note how many landmark points the top level shows compared with 8,090 cells. HSNE is ManiVault's scale design, and this shot proves "every cell drawn = no, landmarks" at the top level.
10. In the HSNE view, lasso a region and use "Zoom into selection" / "Refine" to get the next level. F2: **m18_subset_hsne_refine.png**. This proves a user-controlled subset.
11. With a lasso selection still active in one scatterplot, open a second scatterplot with the force-directed layout (`X_draw_graph_fa`). Are the same cells highlighted there? F2 both views: **m19_selection_linked_umap.png** and **m19_selection_linked_fa.png**.
12. Filters: is there any filter panel (by obs category or by value) that masks the plots? Look in the scatterplot settings and the Data properties panel. Window shot of whatever comes closest: **m07_filters_panel.png**, or note "none".
13. Annotation: with a selection active, try to create a cluster or label from it (right-click in the scatterplot, or the Clusters data, "Create cluster from selection"). Then check whether it can be exported (Clusters > Export > JSON or Bin). Window shot: **m08_annot_cluster_from_selection.png**.
14. Differential expression: look in the Analyze menu for anything that compares groups (DE, markers, "Cluster differential expression"). The plugin list in this build has none. Window shot of the open Analyze menu: **m09_de_analyze_menu.png**.
15. Spatial: in the loader dialog of step 3, there is no spatial slot in this data. Load the paper's Visium demo instead: File > Import > H5AD, `$DEMO_ROOT/tissuumaps/data/spatial_demo.h5ad` (2,693 spots; obsm `spatial`). Then repeat step 5 with obsm `spatial`. F2: **m05_spatial_coordinates.png**.
16. Image underlay: is there any way to put an image layer under the spatial scatterplot? The ImageViewer plugin is separate. Note yes or no, and take a window shot of the view's layer settings: **m10_image_layers.png**.

### Sharing and export

17. File > **Save Project As...** to `$DEMO_ROOT/manivault/shots/bm_demo.mv`. Close the project (File > close or new project), then use File > **Open project from disk** on that file. Are the views, colouring and selection restored? Window shot after reopening: **m11_share_project_reopened.png**.
18. Export: the F2 dialog itself. Take a window shot of the Screenshot dialog showing the format and size options: **m12_export_screenshot_dialog.png**.

### Scale (one shot)

19. Data properties panel for the X dataset: shows rows × dimensions and the storage type. Window shot: **m16_lazy_data_properties.png**.
   - This settles whether X is held whole in memory. The source suggests it is loaded fully.
20. Quit ManiVault, then send me the folder path. Don't worry about wording in `notes.txt`; one line per step is enough.

### What I do with it

- I write one sidecar per image (`source: manual`, boxes read off the image, pinned by sha256) and a caption per proven mark.
- I score `evidence/matrix/tools/manivault.yaml` and add `notes/comparison/manivault.md`.
- Columns that need no app shot are scored from docs and source, with doc screenshots per the Columns-page rules: desktop (Y, the installer), hosted (N), static (N), remote (from the source).
