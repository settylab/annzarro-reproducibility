# Every cell of Tahoe-100M (95.6M cells, real UMAP)

Store: `n95.6M_plot`, all 95,624,334 cells of Tahoe-100M; a 200-gene panel in X (raw counts),
`obsm/X_umap` from `benchmark/scale/umap_tahoe.py`. The UMAP was fit on a 999,073-cell reference
stratified by plate x cell line, and every other cell was placed with faiss (recall 0.997).
Client: AnnZarro 0.4.1, the tag v0.4.1 (78c9da6; `tahoe95M_*.view_environment.json` record the
install and commit). Browser: headless Chromium 153.0.8010.12 (new headless, WebGL "ANGLE (Apple, ANGLE Metal
Renderer: Apple M3 Max)"), viewport 1600x1000 at device scale factor 2, modebar hidden. Every-cell views are drawn in large-plot mode; the app's status line at the bottom of
each `_panel` PNG says so ("Large plot: no hover/click"). `ready_s` in each `*.view.json` is the time
from navigation to a drawn plot in its screenshot session; for every-cell views at the full extent
this is 6.4 to 7.5 s, and for the MALAT1 view opened zoomed (c) 17.6 s. The older zoom shots were
zoomed after the full plot was drawn, so their `ready_s` is the full extent's.

| file prefix | what |
| --- | --- |
| `tahoe95M_umap_all_cat` | every cell, coloured by `cell_line_id`, size 1, opacity 0.2 (6.4 s) |
| `tahoe95M_umap_all_gene` | every cell, coloured by FN1 (variance rank 1) on the full 0 to 725 scale (7.7 s) |
| `tahoe95M_umap_cmax30_all_gene` | the same with the colour scale capped at 30 counts, the 99th percentile of FN1 over all cells (7.3 s) |
| `tahoe95M_umap_all_zoom` | a 0.33 x 0.35 box inside the CVCL_0023 island at size 1 / opacity 0.2 (6.5 s) |
| `tahoe95M_umap_ps5_all_zoom`, `tahoe95M_umap_ps5_all_cat` | the same box, and every cell, at point size 5 and opacity 1 (6.3 s, 6.4 s): single cells (Fig. scale c) |
| `tahoe95M_umap_default_all_cat`, `tahoe95M_umap_default_all_zoom` | every cell, and the box, at the app's automatic size and opacity (about 0.78 px and 0.16 at 95.6M); zoomed, the dots are too faint to see |
| `tahoe95M_umap_sub_cat`, `*_sub_gene`, `tahoe95M_umap_cmax30_sub_gene` | the server's default subset: part 1 of 957 (100,000 cells) in the regular plot (2.9 to 6.4 s) |
| `tahoe95M_umap_default_sub_cat` | the same part 1 of 957 at the app's automatic size and opacity (Fig. scale d; 4.1 s) |
| `tahoe95M_malat1_all_gene` | every cell by MALAT1, colour scale 0 to 400 counts, size 1, opacity 0.2 (Fig. scale b) |
| `tahoe95M_malat1_zoom_all_gene` | the operator's view: every cell by MALAT1 on the same scale, opened zoomed (viewport2D x 8.2813-9.6364, y 1.6535-2.4479; equal aspect widens x to fill the plot), automatic size and opacity, a focused cell in the link (Fig. scale c) |
| `tahoe95M_malat1_stats.json` | MALAT1 over all cells and the cells in c's drawn region (`benchmark/scale/ceiling/gene_view_stats.py`) |

Notes:

- Every cell line forms its own island. What the central haze and the radial streaks between islands
  are has not been checked; do not caption them without looking.
- With the full scale, the few cells with very high FN1 compress the colour of every other cell.
  The capped version shows FN1 high in roughly a dozen lines and absent from the rest.
- MALAT1 (b, c) is non-zero in all but 3,019 cells; 400 counts, the scale's top, is at or above
  97.9% of cells. In large-plot mode colours are drawn in order of value, so at size 1 the islands
  look uniformly high where cells overlap; zoomed (c), each cell shows its own count. The view link
  of c focuses cell 37_073_022-lib_1982 (row 65,507,916, at UMAP 14.64, 7.72, outside c's region);
  large-plot mode draws no focused-cell marker on v0.4.1 (`drawn.focus_traces` is empty).
- Axis titles come from the panel's `xaxisTitle`/`yaxisTitle` in the view link.
