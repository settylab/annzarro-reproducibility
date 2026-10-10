## TissUUmaps 3

> The authoritative marks and evidence are in `evidence/matrix/tools/tissuumaps.yaml`. This page explains them; it is not yet a Fig. 1c row (user decision: full row, Phase 2 GO).

### What it is

TissUUmaps 3 is a browser-based viewer for spatial omics from Uppsala University: WebGL markers over pyramidal (Deep Zoom) images, with a Python/Flask server, a PySide6 desktop build and a plugin system. It reads h5ad in the browser through h5wasm, by HTTP range request.

- **Paper** (Crossref-verified): Pielawski N, Andersson A, Avenel C, Behanova A, Chelebian E, Klemm A, et al. TissUUmaps 3: Improvements in interactive visualization, exploration, and quality assessment of large-scale spatial omics data. *Heliyon* 9(5), e15306 (2023). [doi:10.1016/j.heliyon.2023.e15306](https://doi.org/10.1016/j.heliyon.2023.e15306) (PMC10149187). Cited 50 times. Its rendering benchmark (sec. 3.2.3) draws datasets of 65k, 1.0 M and 16.7 M points, "without relying on data sub-sampling" (sec. 1.2). The points are mRNA markers, not cells.
- **Scored version:** TissUUmaps **3.2.1.11** (conda-forge, isolated env under `$DEMO_ROOT/_mamba/envs/tissuumaps`). PyPI's latest is 3.2.1.14. The five source files cited below (views.py, read_h5ad.py, gui.py, h5Utils.js, flask.js) are byte-identical between the installed 3.2.1.11 and tag 3.2.1.14, so the links point at [TissUUmaps/TissUUmaps3 `618b97c`](https://github.com/TissUUmaps/TissUUmaps3/tree/618b97caf0767bae5b2fc8580c9a29e203607fd8) (tag 3.2.1.14, 2025-05-16). TissUUmaps 4 is in beta and was not scored.
- **Largest documented:** 163k cells. The TissUUmaps gallery entry "Human Developmental Lung Cell Atlas", button "Single-cell RNA-sequencing", opens [hdca-lung.serve.scilifelab.se/UMAP.tmap?path=private/HDCA/UMAP/](https://hdca-lung.serve.scilifelab.se/UMAP.tmap?path=private/HDCA/UMAP/). Its `all_cells_data_for_viewer.csv` is 17,465,408 B with 163,237 lines, i.e. 163,236 cells (checked 2026-10-04). The 16.7 M benchmark counts markers, not cells.

### How it was checked

- **Server build** (`$DEMO_ROOT/tissuumaps/start.sh`, 127.0.0.1:8908, request log on) in headless Chromium, driven by [matrix_check.py](demos/tissuumaps/matrix_check.py) and [followup_check.py](demos/tissuumaps/followup_check.py).
- **Desktop build:** the pip PySide6 GUI on this Mac, driven over raw CDP ([desktop_check.py](demos/tissuumaps/desktop_check.py)). The .dmg was not used.
- **Data:** `bm_demo_csc.h5ad` (the shared 8,090-cell bone marrow demo, X re-encoded as CSC, 476 MB) and `spatial_demo.h5ad` (2,693 Visium spots, obsp `spatial_connectivities`, synthetic grey tissue image).
- **Shots:** every shot has a sidecar next to it in [`screens/tissuumaps/`](screens/tissuumaps/). Captions were written after looking at each image.
- **Request log:** [l01](screens/tissuumaps/l01_lazy_request_log.jpg) is the server's own werkzeug log rendered as a page. The first plain 200 for the h5ad is the viewer page: `views.py` sends file bytes only when the referrer is `h5Utils_worker.js` (L885-887). After that the worker reads the file as HTTP 206 byte ranges.

### Matrix row (proposed)

| Column | Proposed | Observed or found | Evidence |
|---|---|---|---|
| cell × cell matrix as colour or axis | N | The one obsp key read, spatial_connectivities, can only be drawn as edges between markers; no obsp row becomes a colour or an axis. Footnote: draws the stored spatial neighbour graph as edges. | [m01_cells_obsp_edges_zoom](screens/tissuumaps/m01_cells_obsp_edges_zoom.jpg), [read_h5ad.py#L277-278](https://github.com/TissUUmaps/TissUUmaps3/blob/618b97caf0767bae5b2fc8580c9a29e203607fd8/tissuumaps/read_h5ad.py#L277-L278) |
| gene × gene matrix as colour or axis | N | varp is never read. | [m04_slots_obs_categorical_list](screens/tissuumaps/m04_slots_obs_categorical_list.jpg), [read_h5ad.py#L62-82](https://github.com/TissUUmaps/TissUUmaps3/blob/618b97caf0767bae5b2fc8580c9a29e203607fd8/tissuumaps/read_h5ad.py#L62-L82) |
| focused cell/gene drives linked panels | N | Picking a gene colours the markers by its expression (feature colouring); nothing can be focused. | [m03_focus_gene_mpo](screens/tissuumaps/m03_focus_gene_mpo.jpg) |
| all AnnData slots incl. obsp/varp/varm | P | obs (numerical and categorical) and X genes are offered, obsm gives coordinates, one obsp key can be edges; layers, varm, varp and uns are not offered. | [m04_slots_obs_categorical_list](screens/tissuumaps/m04_slots_obs_categorical_list.jpg), [read_h5ad.py#L162-170](https://github.com/TissUUmaps/TissUUmaps3/blob/618b97caf0767bae5b2fc8580c9a29e203607fd8/tissuumaps/read_h5ad.py#L162-L170) |
| remote stores (S3, GCS, HTTP) | P | The browser worker can read an h5ad over https by Range when a project file references it, but the GUI opens local files only; not tested. | [h5Utils.js#L33-39](https://github.com/TissUUmaps/TissUUmaps3/blob/618b97caf0767bae5b2fc8580c9a29e203607fd8/tissuumaps/static/js/utils/h5Utils.js#L33-L39) |
| spatial coordinates | **Y** | Visium spots placed by obsm/spatial. | [m07_m11_spatial_spots_over_image](screens/tissuumaps/m07_m11_spatial_spots_over_image.jpg) |
| selection or filter restricts linked views | N | Regions act on the single main view; linked spatial/UMAP views need the Feature Space plugin (not part of the core app). | [f01_regions_rectangle](screens/tissuumaps/f01_regions_rectangle.jpg) |
| annotation editing | P | A drawn region gets an editable class and name and can be exported; it labels an area, not individual cells. | [f01_regions_rectangle](screens/tissuumaps/f01_regions_rectangle.jpg), [docs](https://tissuumaps.github.io/TissUUmaps-docs/docs/starting/regions.html) |
| on-the-fly DE | N | No DE in the core app; the official DGE plugin only displays a precomputed scanpy rank_genes_groups result. | [DGE.yml#L7-14](https://github.com/TissUUmaps/TissUUmaps3/blob/618b97caf0767bae5b2fc8580c9a29e203607fd8/plugins_repo/latest/DGE.yml#L7-L14) |
| tissue image underlay | **Y** | The uns/spatial image is drawn under the spots, with layer controls. | [m07_m11_spatial_spots_over_image](screens/tissuumaps/m07_m11_spatial_spots_over_image.jpg), [m11_image_layers_tab](screens/tissuumaps/m11_image_layers_tab.jpg) |
| shareable view state | P | Save project writes a .tmap; reopening restored the dataset and marker menus but not the chosen colouring (server build). | [m12_share_save_project_dialog](screens/tissuumaps/m12_share_save_project_dialog.jpg), [f02_share_project_reopened](screens/tissuumaps/f02_share_project_reopened.jpg), [docs](https://tissuumaps.github.io/TissUUmaps-docs/docs/starting/projects.html) |
| plot export | **Y** | Capture viewport with a resolution factor downloaded a 2.2 MB PNG. | [m13_export_capture_dialog](screens/tissuumaps/m13_export_capture_dialog.jpg), [docs](https://tissuumaps.github.io/TissUUmaps-docs/docs/starting/capture.html) |
| desktop app | **Y** | Desktop build: installers for Windows, macOS and Ubuntu; the pip GUI (PySide6) ran on this Mac and served the same page (observed over CDP; the Qt menu bar is not in the shots; not the .dmg). | [docs](https://tissuumaps.github.io/TissUUmaps-docs/docs/intro/installation.html) |
| hosted multi-user | **Y** | A Docker instance serving the web app is documented, with optional sftp multi-user access. | [docs](https://tissuumaps.github.io/TissUUmaps-docs/docs/sharing/docker.html) |
| static site, no server | **Y** | The desktop build's Export to static webpage writes index.html, static/ and data/ (the h5ad and DZI image tiles); served by a plain static server it opens and draws the image and marker panel with no backend. | [views.py#L905-1027](https://github.com/TissUUmaps/TissUUmaps3/blob/618b97caf0767bae5b2fc8580c9a29e203607fd8/tissuumaps/views.py#L905-L1027), [gui.py#L288-288](https://github.com/TissUUmaps/TissUUmaps3/blob/618b97caf0767bae5b2fc8580c9a29e203607fd8/tissuumaps/gui.py#L288), [docs](https://tissuumaps.github.io/TissUUmaps-docs/docs/sharing/apache.html) |
| lazy chunked reads | **Y** | The browser reads the h5ad by HTTP Range (1 MB chunks): the server logged 17 HTTP 206 responses for the 476 MB file in one session. | [l01_lazy_request_log](screens/tissuumaps/l01_lazy_request_log.jpg), [h5Utils.js#L18-39](https://github.com/TissUUmaps/TissUUmaps3/blob/618b97caf0767bae5b2fc8580c9a29e203607fd8/tissuumaps/static/js/utils/h5Utils.js#L18-L39), [views.py#L820-853](https://github.com/TissUUmaps/TissUUmaps3/blob/618b97caf0767bae5b2fc8580c9a29e203607fd8/tissuumaps/views.py#L820-L853) |
| S2 | **Y** | All 8,090 cells drawn in one WebGL call; the paper's rendering benchmark draws up to 16.7 M markers without sub-sampling. | [m00_every_cell_bm_umap_celltype](screens/tissuumaps/m00_every_cell_bm_umap_celltype.jpg), [paper](https://doi.org/10.1016/j.heliyon.2023.e15306) |
| S4 | P | Per-category visibility checkboxes hide cells from the view; data are not loaded less. | [m07_m11_spatial_spots_over_image](screens/tissuumaps/m07_m11_spatial_spots_over_image.jpg) |
| auto subset | N | No default subset: TU3 draws every marker (the TU1 quad-tree subsampling is gone). | [m00_every_cell_bm_umap_celltype](screens/tissuumaps/m00_every_cell_bm_umap_celltype.jpg), [paper](https://doi.org/10.1016/j.heliyon.2023.e15306) |

Notes on contested cells:
- **cell × cell N.** The one obsp key that is read, `spatial_connectivities`, is offered only as edges between markers (read_h5ad.py L277-278). Footnote: "draws the stored spatial neighbour graph as edges".
- **static Y.** This rests on the desktop build's *Export to static webpage* (gui.py L288, views.py L905). The exported folder was served by a plain static server and drew the image and markers with no backend.
- **share P.** A saved `.tmap` reopened the dataset and the marker menus, but not the chosen colouring (server build, f02).

### How to validate it yourself

1. `$DEMO_ROOT/tissuumaps/start.sh`, then open `http://127.0.0.1:8908/bm_demo_csc.h5ad`. Pick obs `highres_celltype`: all 8,090 points draw (m00). Pick gene Mpo: colouring only, no linked panel (m03).
2. In the server log, the h5ad appears once as 200 (the page), then as 206 range reads (l01).
3. Open `spatial_demo.h5ad`: spots sit over the image, layer controls are in the Layers tab, and edges are offered from obsp (m07_m11, m11, m01).
4. Regions tab: draw a rectangle, give it a class and name, export (f01). File > Save project, reopen it with `?path=` (m12, f02). File > Capture viewport (m13).
5. Desktop build: `tissuumaps` (PySide6), File > Export to static webpage, serve the folder with `python -m http.server`, open index.html.
6. Stop the server: `$DEMO_ROOT/tissuumaps/stop.sh`.
