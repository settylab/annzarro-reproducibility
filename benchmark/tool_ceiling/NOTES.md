# Synthetic stores past 95.6M cells (SYNTHETIC DATA)

Every AnnZarro size above Tahoe-100M's 95,624,334 cells (every cell from 150M, the
subset sizes from 150M to 1.5B) uses `../scale/ceiling/build_stores.py`'s synthetic
stores `syn_<N>.zarr`: a master store written chunk by chunk, smaller sizes as
hard-linked prefixes; obs `cell_type` with 50 categories, var GENE0-GENE3, X dense
float32 N x 4, obsm X_umap from 50 Gaussian blobs. A chunk's values depend only on
its index, so masters of different sizes agree on their shared cells. They exist only
to find AnnZarro's ceiling past the largest real dataset; no biological result comes
from them. The every-cell and subset tasks colour by `cell_type` and GENE0.

## Build under test (AnnZarro v0.4.1)

Every AnnZarro row is AnnZarro v0.4.1, the tag itself (78c9da6, tree 661a454f). One install,
shared with ../scale (`../scale/ceiling/setup_build.sh 78c9da6 v041-bench`): a detached worktree
at the tag, static/vendor fetched and checked by the tag's own scripts/vendor_assets.py (26 assets),
and its own venv. Runs: `queue_v041.sh main|noguard|profile`, one rung per `run-timed` call
(`RUN_TIMED`, the exclusive bench lock). Two idle AnnZarro servers of earlier sessions (about
2.2 GiB resident together) stayed up during the v0.4.1 ladder; they served nothing. Older builds:
HISTORY.md (not cited).

## The every-cell edges on v0.4.1

With the guard at default settings every rung from 150M to 200M drew every cell (150, 160, 167,
175, 182, 190, 200M). The client stayed within 16 GiB up to 175M (15.70 GiB) and passed it at
182M (16.14 GiB); 200M drew at 17.36 GiB. At 250M the guard declined the first plot: "250,000,000
points is above 200,000,000, the largest plot tested to draw" (r1; r0 was a harness misread of the
new wording, summarize.HARNESS_FAILURES). Large-plot mode keeps the positions off the V8 heap
(about 25 MiB of used heap at every size); they live in the renderer process.

With the guard off (v041_noguard, ui.memory.enforce off) at 250M, 300M and 500M the tab could not
allocate the positions buffer: the panel shows "Some data could not be read / plot data: failed to
read -- Array buffer allocation failed" (a RangeError in the tab), with the renderer at 14.4-15.9 GiB
RSS and the client footprint at 15.9-17.9 GiB. Nothing crashed or hung (r1; the r0 rows were logged
"stalled" by a driver that did not read the message).

The guard-off edge (v041_noguard_edge, not in Fig. 1c; rungs 210M, 215M, 220M, 225M, 230M, 235M and
240M on synthetic stores, v0.4.1 tag 78c9da6, ui.memory.enforce off, the same exe and driver for
every rung; 215M to 235M are hard-link prefixes of syn_master_300000000, built with
benchmark/scale/ceiling/build_stores.py): 210M (1 attempt), 215M and 220M (2 each) drew every cell by
category and by gene (renderer 13.1-14.6 GiB RSS, client footprint 17.5-18.4 GiB, above the 16 GiB
budget). At 225M (r1, r2, r3; r0 was a driver misread, summarize.HARNESS_FAILURES), 230M and 235M
(2 attempts each) the gene plot drew all cells and the category recolour failed with "Array buffer
allocation failed" in `groupByKey` (large-plot.js) in every attempt (renderer 13.8-15.1 GiB RSS).
At 240M the first plot failed on the same allocation in 3 of 3 runs (renderer 14.3-14.5 GiB RSS).
So the guard-off maximum is 220M by category (every attempt, max_n_ok) and 235M by gene
(every attempt, max_n_gene_drawn, derived from raw/*.task.json checks.gene), 5M resolution; the row
is final under the same rule as v041_noguard.

## AnnZarro v0.4.1 server at 1B cells with the default subset

Synthetic 1B store, server on the laptop, phys_footprint. The default-subset
requests one at a time against a fresh server (`profile_1b_subset_requests.py`;
`server_profile_1b.csv`, build "v0.4.1 78c9da6"):

| request (subset of 100,000) | time | server peak (GiB) | after |
| --- | --- | --- | --- |
| subset=auto | 4.7 s | 0.12 | 0.12 |
| cell names of the subset | 19.2 s | 0.51 | 0.36 |
| obsm/X_umap column 0 | 1.1 s | 0.78 | 0.64 |
| obsm/X_umap column 1 | 1.1 s | 0.74 | 0.74 |
| layer/X column 0 | 0.6 s | 0.75 | 0.75 |
| obs cell_type | 54.4 s | 2.74 | 1.58 |

In the full task (the browser's default view, requests in parallel) the server
process tree peaked at 3.99 GiB (lifetime maximum; run
annzarro_v041_sub1m_run_1000000000_r0); in parallel the subset took 7.8-8.3 s and the cell
names 27.1 s to reach the browser, the X_umap columns 3.0-3.1 s (`subset_request_times.csv`).
Subset reach: 1.5B, the server at most 4.3 GiB at any subset size, within the 32 GiB budget
(a lower bound: the largest size tested).

## Budgets and the input rule (operator decisions, 2026-10-05; final form)

**Input rule (quotable).** Each tool was given its input already prepared in
the format it reads; the time and memory of preparing it were not measured.

Preparation that generates or converts the data (h5ad writing,
CSC conversion, cbImportScanpy/cbBuild, makeShinyApp, cirro prepare_data, SCE
builds, BPCells writes, AnnZarro's documented h5ad-to-zarr
recipe) is **not measured**, for any tool. Every tool's input is assumed to exist
in the format it needs. The conversion runs made before this decision are kept
only in conversions_superseded.csv. A "triangle" (kind_16gb "input path limit")
means only that the tool cannot READ a valid input at that size (for example
ShinyCell's makeShinyApp on an HDF5-backed SCE at 20M). iSEE's input is the HDF5-backed SCE (variant
hdf5, to_sce_hdf5.R); its default in-memory dgCMatrix SCE is a conversion
artifact (ceilings_superseded.csv). Where the laptop could not build an input,
the HPC worker builds it (not measured) and serves it on a Slurm node; the laptop
browser is measured through the proxy.

**Server budget: 32 GiB, flat** (phys_footprint, the server process tree's
concurrent peak sampled every 50 ms, as every server value here). A server
above it at size N stops the tool at the previous size: kind_16gb "ceiling:
server exceeded the 32 GiB server budget at N", first_fail "server_budget ...".
**Client budget: 16 GiB** (unchanged). The machine cap (85 GiB since 2026-10-05 evening; 48 GiB before) is only a guard: a run that reaches it ends with status "cap", and its peak is then a lower bound.
Server peaks the HPC worker reports for HPC-hosted rungs are process-tree RSS (GB),
labelled as such. Borderline server cases: CELLxGENE default 29.65 GiB at 14.1M
passes, 35.86 at 16.8M stops (--backed 28.40 / 34.43); Cirrocumulus default
30.30 GiB at 10M passes, 43.59 at 14.1M stops (not bisected).

## Hang rule (operator decision, 2026-10-05)

A **hang** is a web run in which the client and server processes together use
less than 2 CPU-seconds over 300 s of wall time (no drawing, no loading, no
computing), measured by memmon.py (--hang-s 300, set by run.py for every web
run; status "hang", the run is ended at once instead of holding the bench lock
until the 30-min timeout). Before a hang counts, the run is checked for a
harness wait (a selector or ready signal the driver waits for that the tool
never produces although it has drawn): such runs go to
summarize.HARNESS_FAILURES and are not attempts. A size with at least 3 hang
attempts is not renderable for that tool: a client stop, first_fail mode
"hang (k attempts, no progress for 300 s)". Fewer attempts read "hang (k of 3
attempts so far)".

