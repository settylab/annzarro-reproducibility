"""Loupe Part C shots: the desktop session saved full-screen captures that also show the operator's desktop (file
names, Finder sidebar, Dock). Keep only the Loupe window and the menu/dialog a shot is about, paint the rest of the
crop flat grey, save as JPEG next to a manual sidecar pinned by sha256. Raw PNGs go to
$DEMO_ROOT/loupe/validation/raw_shots/ (not published). Captions were written after viewing each shot."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
import hashlib, json, os, shutil, sys
from PIL import Image, ImageDraw
import yaml
S = f"{_REPO}/notes/comparison/screens/loupe/"
RAW = os.path.expanduser(f"{_DEMO_ROOT}/loupe/validation/raw_shots/")
W = (220, 148, 1153, 745); MB = (30, 0, 330, 28)
SW = "Loupe Browser 9.1.0 (macOS; About box: Version 9.1.0 (9.1.0))"
DATA = "bm_demo.cloupe: bm_demo.h5ad as .cloupe via LoupeR create_loupe() (8,090 cells x 16,285 genes; 8 clusterings, 4 projections)"
PLOT = (490, 205, 1145, 532)
SHOTS = {  # stem: (extra keep rects, proves [(column, mark, caption)], callouts [(box, label)])
 "m01_plots_APP_umap_highres_celltype": ([], [("every_cell", "Y", "bm_demo opened in Loupe Browser 9.1.0: UMAP coloured by highres_celltype; Age counts Mid 2,057 + Old 3,116 + Young 2,917 = 8,090 cells, the whole demo")],
   [(PLOT, "UMAP, highres_celltype"), ((285, 380, 480, 660), "cluster list with per-cluster counts")]),
 "m16_every_cell_APP_zoomed_points": ([], [("every_cell", "Y", "zoomed into the Neutrophil cluster: single round points, no sampling notice, no 'N of M' label, no density shading"), ("auto_subset", "N", "no default subsetting at 8,090 cells: no sampling notice or setting; the only display setting is marker size")],
   [(PLOT, "zoomed: individual points")]),
 "m02_cells_APP_view_menu": ([MB, (190, 28, 350, 58)], [("cells", "N", "no neighbour-graph, distance or similarity view: the View menu holds only 'Toggle Full Screen', and the left rail offers Clusters, Features, Reanalyze, Advanced Selection, V(D)J Clonotypes")],
   [((190, 28, 350, 58), "View menu: Toggle Full Screen only"), ((222, 215, 280, 560), "left rail")]),
 "m15_genes_APP_feature_panel": ([], [("genes", "N", "Features panel: 'Co-expression' plots two feature lists against each other per cell; no gene x gene matrix or similarity view")],
   [((285, 578, 485, 705), "Co-expression of two feature lists")]),
 "m03_focus_APP_gene_mpo": ([], [("focus", "N", "picking Mpo colours the UMAP by its expression (Log2 Exp, 2,879 barcodes > 0): feature colouring")],
   [(PLOT, "UMAP coloured by Mpo"), ((980, 215, 1140, 455), "legend: 2879 barcodes found")]),
 "m03_focus_APP_cell_click": ([], [("focus", "N", "after a click on one cell: no detail box, no change in any panel (still '2879 barcodes found')")],
   [(PLOT, "UMAP after a single-cell click")]),
 "m04_slots_APP_clusterings": ([], [("slots", "N", "what the .cloupe carries: eight categorical groups under 'LoupeR Analysis groups'; numeric metadata, graphs and other AnnData slots do not reach Loupe")],
   [((285, 240, 480, 560), "8 LoupeR groups")]),
 "m04_slots_APP_projections": ([], [("slots", "N", "projection menu: diffusion, draw_graph_fa, pca, UMAP (2-D each) plus 'Feature Plot'")],
   [((500, 205, 645, 370), "projection menu")]),
 "m06_remote_APP_file_menu": ([MB, (128, 28, 260, 112)], [("remote", "N", "File menu: New Window, Open File..., Save, Save As...; no URL, server or cloud entry")],
   [((128, 28, 260, 112), "File menu")]),
 "m18_selection_APP_lasso_umap": ([], [("selection", "P", "rectangle selection on the UMAP (63 barcodes) opens 'Save Barcodes' at once; the live selection exists only inside that dialog")],
   [((425, 232, 672, 570), "Save Barcodes dialog"), ((730, 470, 762, 495), "selected cells")]),
 "m18_selection_APP_other_view": ([], [("selection", "P", "the saved group (audit: lasso1) carries into another projection (draw_graph_fa) and the violin plot; a live, unsaved selection could not be shown in another view")],
   [((640, 375, 745, 415), "lasso1 in draw_graph_fa"), ((500, 600, 1140, 742), "violin plot for group audit")]),
 "m09_annotation_APP_new_category": ([], [("annot", "Y", "the selection saved as cluster 'lasso1' in a new group 'audit' (Custom groups, 63 cells)")],
   [((285, 475, 480, 570), "Custom groups: audit > lasso1 (63)")]),
 "m10_de_APP_lasso1_vs_rest": ([], [("de", "Y", "differential expression computed in the app: lasso1 vs entire dataset, table in about 8 s (Izumo1r, Foxp3, Tnfrsf4 at the top)")],
   [((500, 605, 1140, 742), "DE result table")]),
 "m08_filters_APP_filter_set": ([], [("subset", "P", "feature filter (Mpo >= 5): 833 barcodes highlighted, the other cells stay drawn in grey; it marks cells, it does not drop them")],
   [((980, 325, 1140, 450), "Filter barcodes: 5-9, 833 found"), (PLOT, "filtered cells purple, rest grey")]),
 "m17_subset_APP_reanalyze_dialog": ([(258, 186, 1191, 781)], [("subset", "P", "Reanalyze wizard on the selected barcodes (63 of 8,090): recomputes t-SNE/UMAP for a subset of up to 100,000 barcodes; opened and closed, not run")],
   [((460, 275, 980, 330), "Reanalyze: up to 100,000 barcodes"), ((1010, 240, 1185, 545), "barcode counts")]),
 "m12_share_APP_reopened_with_category": ([], [("share", "P", "Save As .cloupe and reopen: the custom group 'audit' is still listed; sharing means passing the whole file (title: bm_demo_saved)")],
   [((520, 150, 860, 167), "reopened bm_demo_saved"), ((285, 578, 480, 622), "Custom groups: audit")]),
 "m13_export_APP_export_options": ([], [("export", "Y", "Export menu: plot to PNG or SVG, projection to CSV; a PNG was saved (87,893 bytes)")],
   [((972, 212, 1140, 398), "Export menu")]),
 "m14_desktop_APP_about": ([(598, 195, 815, 333)], [("desktop", "Y", "About box: Loupe Browser 9, Version 9.1.0 (9.1.0), a native desktop application"), ("hosted", "N", "a desktop application; no server or hosted mode in the app"), ("static", "N", "a desktop application, not a web page")],
   [((598, 195, 815, 333), "About Loupe Browser 9.1.0")]),
}
# Loupe ceiling ladder (ceiling-benchmarker's channel, read only: the originals stay in session_v031/shots/).
LADDER = os.path.expanduser(f"{_DEMO_ROOT}/loupe/session_v031/shots/")
SRC = {}
for n, lab in ((1000000, "1M"), (2000000, "2M"), (5000000, "5M")):
    stem = f"m16_every_cell_APP_ladder_{lab}"; SRC[stem] = LADDER + f"{n}_1_points.png"
    SHOTS[stem] = ([], [("every_cell", "Y", f"Loupe ceiling ladder, tahoe_first{n} ({n:,} cells): UMAP drawn with no sampling notice; the 50 per-cluster counts in the cell_line_id list sum to exactly {n:,} (session record drawn_{n}_1)")],
                   [(PLOT, "whole UMAP, no sampling notice"), ((285, 240, 480, 555), "cell_line_id counts")])
for stem, (extra, proves, callouts) in SHOTS.items():
    src = SRC.get(stem, S + stem + ".png")
    if not os.path.exists(src): src = RAW + stem + ".png"
    im = Image.open(src).convert("RGB"); keep = [W] + extra
    x0 = min(r[0] for r in keep); y0 = min(r[1] for r in keep); x1 = max(r[2] for r in keep); y1 = max(r[3] for r in keep)
    mask = Image.new("L", im.size, 0); d = ImageDraw.Draw(mask)
    for r in keep: d.rectangle(r, fill=255)
    out = Image.composite(im, Image.new("RGB", im.size, (217, 217, 217)), mask).crop((x0, y0, x1, y1))
    jpg = S + stem + ".jpg"; out.save(jpg, "JPEG", quality=88)
    sha = hashlib.sha256(open(jpg, "rb").read()).hexdigest()
    data = DATA if stem not in SRC else "tahoe_first<N>.cloupe from the shared Tahoe-100M ladder (LoupeR, benchmark/tool_ceiling/loupe_build.R)"
    side = {"version": 1, "image": stem + ".jpg", "tool": "loupe", "software": SW, "data": data, "url": "desktop app",
            "captured": "2026-10-05", "by": "comparison-auditor (scored) / desktop session operator (shots)",
            "driver": ("Loupe ceiling ladder (desktop session Part B; record $DEMO_ROOT/loupe/session_v031/drawn_<N>_1; redacted by notes/comparison/demos/loupe/redact_shots.py)" if stem in SRC else "notes/comparison/loupe_checklist.md (Part C, computer-use desktop session; log: notes/comparison/demos/loupe/session_notes.txt; redacted by notes/comparison/demos/loupe/redact_shots.py)"),
            "source": "manual", "image_sha256": sha,
            "proves": [{"column": c, "mark": m, "caption": t} for c, m, t in proves],
            "callouts": [{"n": i + 1, "box": [b[0] - x0, b[1] - y0, b[2] - b[0], b[3] - b[1]], "label": l} for i, (b, l) in enumerate(callouts)]}
    open(S + stem + ".annot.yaml", "w").write(yaml.safe_dump(side, sort_keys=False, allow_unicode=True, width=110))
    if src.startswith(S): shutil.move(src, RAW + stem + ".png")  # ladder originals are never moved
    print(stem, out.size)
