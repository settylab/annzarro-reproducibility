# scSVA: evidence that it is not comparable (binned density images; marks are bins, not identifiable cells)

scSVA at its last commit, c9e8fd6b280910eadf9daba35badcf6933c7f353 (klarman-cell-observatory/scSVA, 2019).
Operator decision 2026-10-08 (request 20261008T003347Z): scSVA is not a comparison row, and this pack is the evidence
for "not comparable". After skeptic req-001 (F1) the supportable wording is: "each mark is a grid bin drawn at
its centre, not a cell; no mark carries cell identity; a cell cannot be hovered or picked, and a selection's cells
cannot be listed or exported." Do not claim that every mark aggregates several cells: a bin holding one
cell is a (snapped, anonymous) mark for that cell, and at small N or deep zoom most marks are such bins
(6,803 of 7,422 at 8,090 cells; 145 of 145 in the zoomed screenshot; ~13,020 of 153,749 at 95.6M).

**Result: binned only.** Every rendering path draws grid bins at bin centres; none draws from a cell row or lets a user identify a cell. Not verified:
the 3-D plotly default tooltip (code says voxel-centre x/y/z only) and the Analysis/cloud panels in a browser.

| file | what |
|---|---|
| `scsva_render.txt` | Verdict per question (rendering modes, single-cell hover/click/select, zoom, bin colour, per-cell drawing). Every plot path at c9e8fd6 has a permalink and a verbatim, line-numbered excerpt. Includes the measured numbers with sources and what is NOT VERIFIED. |
| `build_render_txt.sh` | Regenerates `scsva_render.txt` from the clone. It checks the clone is at the sha, unmodified and its own repo root; the excerpts are copied by awk, never typed. |
| `snap_bm_aging.py`, `snap_bm_aging_grid512.json`, `snap_bm_aging_grid512_zoomwindow.json` | Offline replication of scSVA's binning on the 8,090-cell input, full view and the zoomed screenshot's window: marks, single-cell marks, snap distance. Not scSVA output; re-derived with real vaex 2.0.3 by the skeptic. |
| `screenshots.txt` | Manifest: job id, driver step, dataset, grid and zoom window for each image. |
| `screenshots/` | The bin-centre density view (8,090 cells), the zoomed re-binned views, the 95.6M group (category) view, the hover probe. `provenance/` holds the driver scripts and each run's logs and timings. |
| `recipe/` | The install that worked: `README.md` (modules, versions, how to start), `build_hpc.sh`, the conda env + explicit lock, the R package inventory, the `launch.R` host shims, and `container/` (Dockerfile/Apptainer def; NOT built end to end, see the recipe README). |
| `probe/` | The backend probe (scSVA's own vaex `ds$count` binning, grid 512) at 1M, 10M, 20M, 50M and 95.6M cells, Slurm HPC job-run-070, plus `backend_probe.R` that produced them. `probe_95624334_run-070.json` is the source of 153,749 non-empty bins, up to 18,243 cells per bin and `frac_bins_with_one_cell` 0.0847. The probe bins over the raw min/max without the app's 0.5% padding (scsva_render.txt states this). |

Reproduce:
- The code evidence: `bash build_render_txt.sh > scsva_render.txt`.
- The replication: `<py with h5py,numpy> -I snap_bm_aging.py ../inputs/bm_aging/coords.h5 512`.
- The app runs: `recipe/README.md`, then `sbatch --mem=16G run/run_job.sh <label> inputs/<dataset> <GENE> shots` from the scsva dir.

The timings (`timings.json`: 755x700 PNG, `hover_input_exists: []`, the zoom window, `groups_draw_s`) are under `screenshots/provenance/<label>_<job>/`.
The verbatim code excerpts, each with a file:line permalink at c9e8fd6, are inside `scsva_render.txt`.

Not in this directory (kept on $SCRATCH, Fred Hutch HPC):
- The converted inputs, about 11.4 GB: `$SCRATCH/annzarro-scale/scsva/inputs/`. The relative paths in "Reproduce" resolve against the original pack, `$SCRATCH/annzarro-scale/scsva/evidence/` (the app-run line against its parent, `.../scsva/`).
- The scSVA clone at c9e8fd6 that `build_render_txt.sh` reads: `$SCRATCH/annzarro-scale/scsva/src/scSVA/` (or clone klarman-cell-observatory/scSVA at that sha).
- The full 11-shot sequences for all four GUI jobs, including tahoe 1M (run-071) and 10M (run-074): `$SCRATCH/annzarro-scale/scsva/runs/` and `.../scsva/screenshots/`.
- No file in this pack is over 2 MB; nothing was left out for size.
