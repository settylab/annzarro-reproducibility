# T2: extra $SCRATCH arm for the 5 node-local-only claims, AnnZarro v0.4.1

- **Job:** Slurm run-076, exclusive node compute-node (Intel Xeon Gold 6254 @ 3.10 GHz, 36 CPUs, 755 GiB RAM), 2026-10-08 11:00:18-13:18:51 PDT. It was run on the operator's decision (laptop request 20261008T173855Z).
- **Release pin:** AnnZarro v0.4.1, tag commit 78c9da657ecbff30163fd29055f0e6b10e915c5c (tree 661a454f), the same install as J4/T (byte-identical to PyPI `annzarro==0.4.1`). The pin guard passed.
- **Harness:** annzarro-reproducibility `dominik/hpc-bench-v030` @ 1804118b, `rerun_release.sbatch`, stages tahoe_x and pairwise_public.
  - Cases selected by T_CASES (full match):
    `(tahoe_kernel_(50000|100000|200000)|tahoe_dist_(50000|100000)|tahoe_corr_20000):.*|tahoe_x_1\.17M:(X_gene_col|obsp_csr_row:connectivities)`
  - That gives 8 cases (2 tahoe_x, 6 pairwise).
- **Storage:** stores read in place on `$SCRATCH` (NFS). Filer cache uncontrolled; each store was warm-read once (`warmup.tsv`), with filer checks in `warmcheck.tsv` and `canary.csv`. No other benchmark job ran on the filer during the run.
- **Protocol:** node-cold, as T. `posix_fadvise(DONTNEED)` on every file of the case's arrays, verified by `mincore()`; a fresh server per cold repeat; 5 cold repeats per case.
- **Results:** `run_v041_hpctemp_extra/<stage>/http.csv` (and `raw.csv` for the 6 dense cases, `http.env_*.json`, `spec_*.json`). 280 HTTP rows, all status 200; 210 raw rows.
- **`MANIFEST.tsv`:** the sha256 of every file of the run as copied off $SCRATCH, including the files left out here.

**Left out of this commit** (not read by any claim; all in `MANIFEST.tsv`):
- `run_v041_hpctemp_extra/<stage>/logs/**`: 81 per-case logs, 96092 B, at `W/t2_v041_hpctemp_extra/run_v041_hpctemp_extra/<stage>/logs/`.
- `run_v041_hpctemp_extra/done/*`: 2 stage-completion markers.

`W/` = `$DATA_ROOT/annzarro-scale-results/` (HPC host). The originals are purged after ~2026-10-31.
