#!/bin/bash
# Regenerates scsva_render.txt. Every code excerpt is copied verbatim from the clone by awk (line-numbered),
# never typed by hand.  Usage: bash build_render_txt.sh > scsva_render.txt
set -euo pipefail
C=$SCRATCH/annzarro-scale/scsva/src/scSVA
SHA=c9e8fd6b280910eadf9daba35badcf6933c7f353
[ "$(git -C $C rev-parse HEAD)" = "$SHA" ] || { echo "clone not at $SHA" >&2; exit 3; }
[ "$(git -C $C rev-parse --show-toplevel)" = "$C" ] || { echo "clone is not its own repo root" >&2; exit 3; }
[ -z "$(git -C $C status --porcelain -- inst R)" ] || { echo "clone modified" >&2; exit 3; }
P=https://github.com/klarman-cell-observatory/scSVA/blob/$SHA
ex() { # ex FILE A B  -> permalink + verbatim lines A..B
  echo "    $P/$1#L$2-L$3"; awk -v a=$2 -v b=$3 'NR>=a && NR<=b {printf "      %5d| %s\n", NR, $0}' $C/$1; echo; }
cat <<'H'
scSVA RENDERING CLASS: EVIDENCE (code at c9e8fd6b280910eadf9daba35badcf6933c7f353, the last commit)
=====================================================================================================
EVERY MARK IS A GRID BIN DRAWN AT THE BIN CENTRE, NOT A CELL. NO MARK CARRIES CELL IDENTITY. A SINGLE CELL
CANNOT BE HOVERED OR PICKED, AND A SELECTION'S CELLS CANNOT BE LISTED OR EXPORTED (a lasso returns only a
count and summary statistics).
A bin that happens to hold ONE cell is drawn as one mark that depicts that cell, snapped to the bin centre and
with no identity. At small N or deep zoom most marks are such single-cell bins (measured below: 6,803 of
7,422 marks at 8,090 cells; 145 of 145 in the zoomed screenshot). So "a mark per cell" can occur by
coincidence of density; "a cell as an addressable, identifiable mark" never occurs.
(One residual item is NOT VERIFIED in a browser: the 3-D plotly default tooltip, Q2b. By code it can only
show a voxel centre's x/y/z (and at most the voxel aggregate), because the plotted table holds voxel indices and
aggregates, never a cell row.)

VERDICTS
  Q1 Rendering modes: every view of the embedding is a vaex grid aggregate drawn as one mark per non-empty
     bin, at the bin centre (a one-cell bin yields a snapped, anonymous mark for that cell). 2-D grid 128..5,120 (default 512); 3-D grid 100..512 (default 200). There is no small-N
     path, no "points"/"raw" option and no zoom-dependent switch.
  Q2 Single-cell hover/click/select: none. No hover input exists; click places a label or a polygon vertex;
     brush and lasso select bins (overlay) or return a COUNT and summary statistics (cell level, but never
     listed). No export of a selection's cell IDs exists; the app never loads a cell ID column.
  Q3 Zoom: brush + double-click re-bins the brushed window at the SAME grid. There is no lower bound on the
     window. A bin can reach one cell, but the mark is still the bin centre with a count/statistic and no
     identity.
  Q4 Bin colour: gene = per-bin Mean (default) | Median (approximate) | Max; density = cell count (log10 by
     default); category = the colour of whichever group's layer is drawn LAST at that bin (not mode, not
     count).
  Q5 Per-cell drawing: no code path draws from a cell row; only bin rows. Highlights, group overlays, polygons, annotations and group labels are bins or
     user-placed or group-level marks.

Abbreviations: S = inst/scSVA/server.R, U = inst/scSVA/ui.R. Line numbers below are the clone's, at the sha.
The app's R code is global.R, server.R, ui.R (inst/scSVA) and R/scSVA.R (a launcher). There is no Python in
the app; the examples/ scripts only prepare input files.
H
echo; echo "Q1. EVERY RENDERING PATH (all 13 renderPlot/renderPlotly/renderImage calls in server.R, L928 L1433 L1450 L1467 L1487 L1529 L1564 L1753 L1814 L2380 L2559 L2584 L2891; global.R and R/scSVA.R contain none)"
echo; echo "  Data loaded into the vaex frame: only x, y (z for 3-D), 'Gene', 'clusters'. The frame is created from one array:"
ex inst/scSVA/server.R 292 292
echo "  1a. Main 2-D plot. plot1..plot4 are ONE renderPlot, so the server renders an image and sends it (measured: 755x700 PNG)."
ex inst/scSVA/server.R 928 930
echo "  1b. Density branch: count per (grid x grid) bin."
ex inst/scSVA/server.R 652 656
echo "  1c. Gene branch: per-bin statistic (see Q4)."
ex inst/scSVA/server.R 663 668
echo "  1d. Group branch: per-group count per bin, one layer per group."
ex inst/scSVA/server.R 697 708
echo "  1e. Bin index -> bin CENTRE coordinate; these centres are what geom_point draws."
ex inst/scSVA/server.R 720 723
ex inst/scSVA/server.R 760 763
echo "  1f. Grid slider (2-D)."
ex inst/scSVA/ui.R 117 123
echo "  1g. 3-D view: plotly scatter3d of VOXEL centres (count/mean/median/max on an N x N x N grid)."
ex inst/scSVA/server.R 1819 1826
ex inst/scSVA/server.R 1890 1892
ex inst/scSVA/server.R 1954 1958
ex inst/scSVA/server.R 1973 1973
ex inst/scSVA/ui.R 248 254
echo "  1h. 3-D -> 2-D projection: projects the same voxel table."
ex inst/scSVA/server.R 2380 2385
echo "  1i. Analysis tab: Group A/B histograms (plotly bar over 40 expression bins), not embeddings."
ex inst/scSVA/server.R 1433 1441
echo "  1j. Analysis tab: per-group Density / ECDF / Violin are 40-bin expression histograms of the group (same count call in each)."
ex inst/scSVA/server.R 1495 1498
ex inst/scSVA/server.R 1537 1540
ex inst/scSVA/server.R 1572 1575
echo "  1k. Analysis tab: Census = pie of cells per group."
ex inst/scSVA/server.R 1472 1476
echo "  1l. Cloud (FLE) panels: convergence line + progress bar; FLE coordinates downloaded from the VM are loaded into the same frame and shown by the same binned 2-D/3-D paths."
ex inst/scSVA/server.R 2559 2565
ex inst/scSVA/server.R 2614 2621
echo "  1m. Remaining outputs: colour-palette preview and a stitched image of saved main-plot PNGs."
ex inst/scSVA/server.R 1753 1755
ex inst/scSVA/server.R 2878 2880
ex inst/scSVA/server.R 2891 2893
echo "  Small-N path: none. plotInput() has exactly three branches (plot.ID 1/2/3), with no condition on N:"
ex inst/scSVA/server.R 651 652
ex inst/scSVA/server.R 657 658
ex inst/scSVA/server.R 689 690
echo; echo "Q2. SINGLE-CELL HOVER / CLICK / SELECT / IDENTITY"
echo "  2a. Hover: plotOutput declares click, dblclick and brush, and NO hover (the same for plot2/3/4 at U#L446, L1018, L1183)."
ex inst/scSVA/ui.R 109 114
echo "      Measured: the run registered no hover input (timings.json hover_input_exists: [] in HPC job and run-075; screenshot 05)."
echo "  2b. 3-D plotly: no text= or hoverinfo= is set (full plot_ly call S#L1954-L1973), so plotly's default tooltip shows the"
echo "      x/y/z of a voxel centre (h,i,j). NOT VERIFIED in a browser."
echo "  2c. Click: a free text annotation or a polygon vertex at the click coordinate; no lookup of a cell."
ex inst/scSVA/server.R 1031 1036
ex inst/scSVA/server.R 1046 1048
echo "  2d. Brush 'Select': brushedPoints over the BIN table (vals\$data), toggling bins."
ex inst/scSVA/server.R 1014 1017
echo "  2e. Group A/B by polygon: a cell-level vaex lasso, used only for a COUNT, then for histograms and summary stats."
ex inst/scSVA/server.R 1189 1191
ex inst/scSVA/server.R 1342 1344
echo "  2f. Group A/B by box: bins for the overlay, a count over the box for the number."
ex inst/scSVA/server.R 1198 1203
echo "  2g. Exports: only two download handlers exist, both for plot IMAGES (2-D plot, 3-D plot)."
ex inst/scSVA/server.R 1143 1144
ex inst/scSVA/server.R 2017 2018
echo "      There is no export of a selection's cell IDs, and no cell ID/barcode column is ever read (see 'Data loaded' above)."
echo; echo "Q3. ZOOM"
echo "  Double-click on a brush sets the window to the brush and flags a re-bin (trans), with no minimum width:"
ex inst/scSVA/server.R 1019 1028
echo "  The re-bin uses the same input\$grid over the new limits (1b). Bin width = window width / grid."
echo "  Initial view: 0.5% padding around the data range:"
ex inst/scSVA/server.R 644 648
echo; echo "Q4. BIN COLOUR"
echo "  Gene statistic choices, default Mean:"
ex inst/scSVA/ui.R 491 495
ex inst/scSVA/server.R 669 680
echo "  Bins with cells but no finite value are set to 0:"
ex inst/scSVA/server.R 681 687
echo "  Density colour = count (log10 if dens_scale). Category colour = the group colour of each layer; the layers are rbind-ed in"
echo "  group order (1d) and drawn in row order, so where groups share a bin the last drawn wins. 'Shuffle cells' shuffles BIN rows:"
ex inst/scSVA/server.R 741 741
ex inst/scSVA/server.R 750 758
ex inst/scSVA/server.R 1237 1239
echo; echo "Q5. ANYTHING DRAWN PER CELL: NO CODE PATH DRAWS FROM A CELL ROW (one-cell bins: see MEASURED NUMBERS)"
echo "  Highlighted group = that group's bins at 5x size; Group A/B and Select overlays = bin subsets; polygon = user clicks."
ex inst/scSVA/server.R 765 785
echo "  Group labels sit at each group's mean x/y (one label per group):"
ex inst/scSVA/server.R 1281 1285
cat <<'T'

MEASURED NUMBERS (each with its source)
  - 95,624,334 cells, grid 512, density view: 153,749 non-empty bins (= marks drawn); max 18,243 cells in one bin.
    Source: runs/probe_95624334_run-070/probe.json (scSVA's own ds$count call, run/backend_probe.R; Slurm HPC job),
    reproduced by runs/probe_95624334_run-068/probe.json (HPC job). Also ladder/hpc_probe_backend.csv row 6.
    Of those marks, a fraction 0.0847 hold exactly one cell (probe.json frac_bins_with_one_cell = mean over non-empty
    bins, backend_probe.R L41), i.e. about 13,020 single-cell marks (13,015..13,030 given the 4-digit rounding).
    Caveat: the probe (run/backend_probe.R L26-27) bins over the UNPADDED data min/max, whereas the app pads the
    initial view by 0.5% (S#L644-648), so the app's own grid-512 view differs slightly from these counts.
  - The image sent to the browser: one PNG, 755 x 700 px (naturalWidth x naturalHeight of #plot1 img).
    Source: runs/<label>_<job>/timings.json "plot1_img_natural": [755, 700], all four GUI runs (run-073, run-071,
    run-074, run-075).
  - 8,090 cells (bm_aging), grid 512, initial view: 7,422 marks, of which 6,803 are single-cell bins (marks by
    cells per bin: 1:6803 2:576 3:37 4:6); 1,287 cells share a bin with another cell; every cell is moved to its bin
    centre (median 0.0199, max 0.0349 UMAP units; bin 0.0521 x 0.0474).
  - The zoomed screenshot's window (x 3.925829..9.239898, y 2.467689..6.862822, grid 512): 145 cells -> 145 marks,
    ALL single-cell bins. Source: evidence/snap_bm_aging_grid512_zoomwindow.json (same script, window arguments).
    Source: evidence/snap_bm_aging_grid512.json, produced by evidence/snap_bm_aging.py, an offline REPLICATION of
    S#L644-656 + L720-723 on inputs/bm_aging/coords.h5. This is NOT scSVA output; it reproduces scSVA's binning
    arithmetic (vaex: idx = floor((v-lo)/(hi-lo)*grid)). The skeptic (req-001) re-derived 7,422 / 1,287 / max 4 /
    6,803 / 145 with real vaex 2.0.3.
  - ESTIMATE, not measured: at grid 5,120 over the same full 95.6M extent the densest region would hold ~182 cells per
    bin (18,243 / 10^2, assuming uniform density within the grid-512 bin). Reaching ~1 cell per bin would need a further
    ~13.5x zoom per axis. The plot panel is ~630 px wide inside the 755 px PNG, so any grid above ~630 puts several
    bins in one pixel.

NOT VERIFIED
  - The 3-D plotly default tooltip (Q2b). Code only.
  - The Analysis tab's plotly panels were not exercised in a browser: they froze headless Chromium 105 in run 10168843.
    The verdicts in 1i-1k are code-only.
  - The Diffusion Maps / NNG / FLE cloud tabs need Google Compute Engine and were not run. 1l is code-only.
T
