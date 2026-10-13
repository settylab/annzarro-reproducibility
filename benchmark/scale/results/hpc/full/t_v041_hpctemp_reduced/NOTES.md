# T: reduced public set on $SCRATCH (NFS), AnnZarro v0.4.1

- **Job:** Slurm run-063, exclusive node compute-node (Intel Xeon Gold 6254 @ 3.10 GHz, 36 CPUs, 755 GiB RAM), 2026-10-07 16:27:26 to 2026-10-08 06:34:18 PDT.
- **Release pin:** AnnZarro v0.4.1, tag commit 78c9da657ecbff30163fd29055f0e6b10e915c5c (tree 661a454f), the same install as J4 (byte-identical to PyPI `annzarro==0.4.1`). The pin guard passed.
- **Harness:** annzarro-reproducibility `dominik/hpc-bench-v030` @ 1804118b, `rerun_release.sbatch` with stages tahoe_x, grid, pairwise_public, hlca, ladder_obs.
  - The case list is reduced by T_CASES (full match):
    `(tahoe_x_1M|tahoe_dense_1M_(allx4|allx64|8192x64|1024x512)|tahoe_dist_200000|tahoe_corr_30000|hlca_dense|hlca_dense_allx4|tahoe_[0-9.]+M):.*`
  - That gives 29 cases.
- **Storage:** stores read in place on `$SCRATCH` (NFSv4.1 scratch filer).
  - Filer cache uncontrolled: each store was read once in full before its first measured pass (`warmup.tsv`), and filer speed was sampled before and after (`warmcheck.tsv`, `canary.csv`).
- **Protocol:** node-cold, as J4.
  - `posix_fadvise(DONTNEED)` on every file of the case's arrays, verified by `mincore()`, then a fresh server per cold repeat.
  - 5 cold repeats per case.
  - The wall time (14 h) is dominated by that eviction over NFS (~7.7 ms per file per repeat; hlca_dense has 241,619 files). This is not request latency.
- **Results:** `run_v041_hpctemp_reduced/<stage>/http.csv` (and `raw.csv` for dense cases, `http.env_*.json`, `spec_*.json`).
  - 965 HTTP rows over 29 cases, all status 200.
  - 490 raw rows over 14 dense cases.
  - `ladder_obs` = categorical obs click with `categorical=codes` on the Tahoe ladder 1M-95.6M (HTTP only).
- **#404:** https://github.com/settylab/user-HPC worker/issues/404#issuecomment-6061081022
- **`MANIFEST.tsv`:** the sha256 of every file of the run, including the files left out here.

**Left out of this commit** (not read by any claim; all in `MANIFEST.tsv`):
- `run_v041_hpctemp_reduced/<stage>/logs/**`: 291 per-case logs, 313,556 B, at `W/t_v041_hpctemp_reduced/run_v041_hpctemp_reduced/<stage>/logs/`.
- `run_v041_hpctemp_reduced/done/*`: 5 stage-completion markers.

`W/` = `$DATA_ROOT/annzarro-scale-results/` (HPC host). The originals at `$SCRATCH/annzarro-scale/hpcbench/run_v041_hpctemp_reduced/` are purged after ~2026-10-31.
