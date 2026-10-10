# Fig. 9 (performance, `fig:performance`): numbers, sources, captions

Script: `figures/fig6_performance.py`. Regenerate with

```bash
.venv/bin/python figures/fig6_performance.py
```

Outputs: `manuscript/figures/fig6_performance.{pdf,png}`, and the supplementary
`figS_interactions.{pdf,png}` and `figS_chunk_sweep.{pdf,png}` (not in the paper).

Every plotted value is AnnZarro v0.4.1 (the tag, 78c9da6), with vectors sent in the binary format the web client uses: `format=f32`
on numeric slices, `categorical=codes` on obs (columns `wire`, `encoding`). Older notes, as of
AnnZarro 0.1.1, are in `PERFORMANCE_HISTORY.md` and are not cited.

## Machines and filesystems

| tag | machine | storage | server | source |
|---|---|---|---|---|
| laptop | Apple M3 Max, 128 GB, macOS 26.5.1 | internal NVMe, APFS; cold = fresh APFS clone + fresh process | Flask/werkzeug threaded, 1 process | `benchmark/results/{scale,sparse,sweep}_v041.csv`, `*_v041_environment.json` |
| HPC | Fred Hutch HPC compute nodes, Xeon Gold 6254, whole exclusive 36-CPU nodes (755 GiB) | `$SCRATCH`, an NFSv4.1 scratch filer; cold = a fresh server and the node's page cache evicted | one server process | HPC worker T (job 10163488), T2 (job 10195427) and J5 (job 10163489) on v0.4.1, `benchmark/scale/results/hpc/full/{t_v041_hpctemp_reduced,t2_v041_hpctemp_extra,j5_v041}/`; claim cases in `hpc_v041_case_map.tsv` |

Condition mapping (laptop). *cold* = `condition == "cold"`, *warm* = `warm_new` (page cache
warm, a new index). Points are medians, whiskers IQR (q25-q75), from the per-request CSVs.

## Panels

- **a, Clicks move vectors, not matrices.** Bytes per click, computed from the binary format
  (4 B per float32 value) for the slices read in b; a pairwise row of n cells carries n values,
  as a gene column does. Reference lines: the whole n x 5,000 layer and the whole n x n matrix.
- **b, Latency follows payload size.** Laptop gene column and cell row, cold and warm, 10k to
  1M cells (`scale_v041.csv`). HPC (squares, $SCRATCH, runs T and T2): pairwise distance rows at
  50,000-200,000 cells and the 1M gene column (whole-gene chunks); HPC warm = `newidx` (a new index).
- **c, Peak RSS stays far below matrix size.** Laptop server peak RSS against the uncompressed
  layer size (0.2 to 20 GB); per-size medians 82-102 MiB, idle 79 MiB. HPC pairwise matrices
  to 160 GB (T, T2): 85-89 MiB; idle 78-79 MiB across laptop and HPC.
- **d, Chunk shape trades rows against columns.** Laptop 1M x 5k, cold gene column against cold
  cell row per chunk shape (`sweep_v041.csv`); whole-gene (n, 64) has a 2.9 s cell row,
  anndata's default (15625, 79) about 70 ms both ways. HPC (hollow squares): T's 1M x 5,000 Tahoe-100M
  layer in four shapes; whole-gene (n, 4) 7.8 s cell row, the Step 10 shape (8192, 64) 0.38 s.

The caption's numbers are claims in `evidence/claims.yaml` (`fig8.*`); the HPC values in the caption
read the v0.4.1 run T (`hpc_v041_case_map.tsv`).
