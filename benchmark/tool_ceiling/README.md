# How many cells each tool draws within a memory budget

Fig. 1c's scale column, measured. For every tool: the largest number of cells
it can open and draw as a UMAP coloured by a category (cell line) and by one
gene (MALAT1), on one laptop, with the peak memory that took. The figure value
is the largest N whose **client** peak stays within **16 GiB**; the curves give
8 and 32 GiB as well.

- **Client** = what runs on the user's machine: every Chromium process
  (browser, renderer, GPU) for a web tool, whose server is treated as remote;
  the whole R or Python process for a library (Scanpy, Seurat), which has no
  server. The server's peak is measured in the same run and reported beside
  it, never hidden.
- **Server-rendered tools** (iSEE, ShinyCell) draw an image on the server and
  ship it to the page, so their client stays under 1 GiB at any N; for them the
  server number is the one that limits, and it is reported as such.

Status: final for every row of `ceilings.csv` (column `row_status`). AnnZarro is measured on v0.4.1 (NOTES.md,
"Build under test"); results from older AnnZarro builds are kept in HISTORY.md and are
not cited.

## Machine and rules

- Apple M3 Max (16 cores), 128 GB RAM, internal SSD, macOS 26.5. Shared with
  other agents' sessions; every measured step (input builds and runs) holds
  the bench lock (`/usr/bin/lockf -k ~/.annzarro-bench.lock`), so no two
  benchmarks overlap. `ps` (top 10 by CPU), `kern.memorystatus_level` and swap
  are recorded before each run (`raw/<id>.mem.json`, `ps_before`).
- Safety cap: a run is killed when its process tree passes **85 GiB** total
  (status `cap`; 48 GiB for runs before 2026-10-05 evening, see NOTES.md); timeout **30 min** per run (`timeout`), 2 h per conversion.
- Headless Chromium 153 (Playwright 1.63, `channel="chromium"`, new headless
  mode, WebGL on the GPU through ANGLE Metal: recorded per run), viewport
  1600 x 900, as in `../scale/ceiling`.

## Memory metric (`memmon.py`)

`phys_footprint` from `proc_pid_rusage` (what Activity Monitor calls Memory):
anonymous and dirty memory including the compressed and swapped parts, without
clean file-backed pages (mmap, page cache) that the kernel can drop for free.
RSS is logged too. Two peaks per group of processes:

- `fp_peak`: the largest sum over the group, sampled every 50 ms (the
  concurrent peak; the figure uses this);
- `fp_lifetime_sum`: the sum of each process's kernel-tracked lifetime
  maximum, an upper bound on the concurrent peak and exact for one process.

Groups for a web tool: client (any process named Chrom*), server (everything
else under the driver), harness (the Python driver, Playwright's node driver,
ceiling.py; not counted). Checked on a 2 GiB allocation.

Budget measured, not enforced: macOS has no cgroups, and Docker on macOS runs
a Linux VM without the GPU (Chromium would fall back to software WebGL). Each
tool climbs the N ladder past 16 GiB, so one curve answers 8, 16 and 32 GiB.
Hard-limit check for the libraries: `docker/validate.sh` runs the same task
under `docker run --memory=16g --memory-swap=16g` (linux/arm64, same package
versions) at the ladder points around the crossing (`validation.csv`):
Scanpy default 7.1M pass, 8.4M pass, 10M OOM-killed; Seurat default 2M pass,
5M OOM-killed. The one point where the two disagree is Scanpy at 8.4M
(16.5 GiB measured on macOS, yet it fits 16 GiB in Linux): macOS libmalloc
keeps large freed blocks in the footprint where glibc returns them, so the
measured macOS ceiling is conservative by at most one bisection step.

Units: memory is in GiB (2^30 bytes) throughout; the budget is 16 GiB.

Input rule: preparing a tool's input (conversions, builds) is not measured;
every tool's input is assumed to exist in the format it needs. Server budget:
32 GiB (phys_footprint, the server's concurrent peak), flat; a server above it at
size N stops the tool at the previous size. Hang rule: 3 attempts with no
progress for 300 s at a size make it not renderable. Details: NOTES.md.

## Data

Tahoe-100M (CC0-1.0) as prepared in `../scale/NOTES.md`: the store
`tahoe_panel_95.6M_plot.zarr` (95,624,334 cells, obsm/X_umap, obs cell_line_id
with 50 cell lines) and its prefixes `tahoe95_first{N}.zarr` (the first N
cells; `../scale/ceiling/cut_prefix.py`). Every tool gets the same cells.

**X is a 200-gene panel**: 5,000 genes in var, values stored for 200 of them
(about 110 stored values per cell; real Tahoe-100M has about 1,470). Tools
that hold all of X in memory (Scanpy default, Seurat default, CELLxGENE
without --backed, iSEE, ShinyCell builds) therefore need far less memory here
than on a full transcriptome: this favours them, never AnnZarro.

Inputs per tool, each built from the same store:

Under the input rule (NOTES.md) no build below is charged to a tool; the
conversion runs are kept in conversions_superseded.csv as a record.

| input | built by | charged to |
| --- | --- | --- |
| h5ad (X CSR float32, uncompressed, anndata 0.11 encoding, readable by every tool's anndata) | `to_h5ad.py` | nobody (input preparation) |
| AnnData zarr (X CSC) | the prefix stores themselves | nobody |
| SingleCellExperiment .rds | `to_sce.R` (hdf5r; zellkonverter not installed) | iSEE / ShinyCell (conversion row) |
| ShinyCell app | `shinycell_build.R` (makeShinyApp) | ShinyCell (conversion row) |
| UCSC site | cbImportScanpy, then cbBuild | UCSC (conversion rows) |
| cirro zarr | `cirro prepare_data --format zarr` | Cirrocumulus prepared (conversion row) |
| BPCells matrix dir | `seurat_task.R bpcells_write` | Seurat bpcells (conversion row) |

## The task, per tool

Success at N = both colourings drawn for every cell, verified, within 30 min.

| tool | variants | how every cell is checked |
| --- | --- | --- |
| Scanpy 1.12.4 | default `sc.read_h5ad`; backed `backed="r"`; lazy_h5ad / lazy_zarr `anndata.experimental.read_lazy`, one gene, `.to_memory()` | scatter offsets = N |
| Seurat 5.5.1 | default: `as(open_matrix_anndata_hdf5(), "dgCMatrix")`; bpcells: on-disk BPCells matrix | plot data rows = N |
| AnnZarro v0.4.1 | v041: every cell (real Tahoe to 95.6M; synthetic stores above, variant v041_syn); v041_sub / v041_sub1m: the app's default 100,000-cell subset and a 1,000,000-cell subset, to 1.5B; v041_noguard: every cell with the memory guard off | panel point count (ceiling.py); "all cells" chosen (above 200k cells the default view draws a 100k subset) |
| CELLxGENE Annotate 1.3.0 | default; backed `--backed` | the tool's "umap: N out of N cells", WebGL counter |
| Cirrocumulus 1.1.61 | default (h5ad); prepared (`prepare_data` zarr, read lazily) | WebGL: one draw call of N points |
| Vitessce (vitessce.io, hosted) | default: AnnData zarr read directly (CSC X) | WebGL: N instances |
| UCSC Cell Browser 1.2.20 | default: cbImportScanpy + cbBuild site | the tool's "N visible cells loaded" |
| iSEE 2.18.0 | default: ReducedDimensionPlot, Downsample off | the setting (server-side ggplot) |
| ShinyCell 2.1.0 | default: CellInfo vs GeneExpr tab | the code (plots every row) |
| Kana v3.2.0 (live build at kanaverse.org/kana, as served 2026-10-05; scran.js Wasm, 4 GiB heap) | default: explore mode on the h5ad (read in the browser, nothing uploaded) | Kana's header "N cells" |

TissUUmaps 3 and napari-spatialdata were measured too but are out of scope for the paper
(spatial-specific tools, operator decision 2026-10-06): their summary rows are in
`ceilings_out_of_scope.csv` (not in `ceilings.csv`), their notes in OUT_OF_SCOPE.md.

The WebGL counter (`web_task.py`, `GL_HOOK`) wraps drawArrays / drawElements
(mode POINTS) and their instanced forms on both WebGL contexts and records the
largest single call and the largest per-frame sum.

## Limits of the default input paths

- **dgCMatrix (iSEE, ShinyCell, Seurat default).** R's `dgCMatrix` stores at
  most 2^31 - 1 = 2,147,483,647 values. The default in-memory
  SingleCellExperiment (`to_sce.R`) failed at 20M cells (2,231,856,797
  values; `isee_to_sce_convert_20000000_r0`), so on this panel (~110 values
  per cell) the limit falls between 10M and 20M cells (about 19.2M by the
  same arithmetic). At Tahoe-100M's ~1,470 stored values per cell the same
  limit is reached at about **1.46M cells**: arithmetic, not measured. An
  HDF5Array/DelayedArray-backed SCE avoids the limit; it was not tested here.
  ShinyCell and Seurat's default hit the (then 48 GiB) machine cap before reaching it.
- **Server budget.** CELLxGENE and Cirrocumulus keep the whole dataset in the
  server process; their servers pass the 32 GiB server budget while their
  client stays well under 16 GiB (`ceilings.csv`, `kind_16gb`).

## Files

| file | what |
| --- | --- |
| `memmon.py` | the memory sampler and wrapper |
| `run.py` | one run under the lock: memmon + task, one row in `results.csv` |
| `scanpy_task.py`, `seurat_task.R` | library tasks |
| `web_task.py` | web drivers (CELLxGENE, Cirrocumulus, Vitessce, UCSC, iSEE, ShinyCell); `--server-url`/`--proxy` for a remote server |
| `annzarro_task.py` | AnnZarro through `../scale/ceiling/ceiling.py`; `--server-url`/`--proxy` for a server on another machine; `--guard-off`, `--heap-series` |
| `to_h5ad.py`, `to_sce.R`, `shinycell_build.R`, `vitessce_config.py`, `isee_app.R` | inputs |
| `queue_*.sh`, `queue_bisect.py` | run orders (ladders; bisection to 1.25x around 16 GiB; two repeats at the bracketing Ns) |
| `summarize.py` | `ceilings.csv` and `ceiling_curve.png` (a size fits a budget only if the median of its repeats does) |
| `HISTORY.md` | superseded AnnZarro builds (before v0.4.1); not cited by the paper |
| `results.csv` | one row per tool x variant x phase x N x run |
| `raw/` | per run: memmon JSON (peaks, trace, ps before), the task's JSON (phases, checks, versions), log |
| `docker/` | hard-limit check |

Runs that failed because of the harness are kept in `results.csv` and left
out of every number (`summarize.HARNESS_FAILURES`, with the reason).
