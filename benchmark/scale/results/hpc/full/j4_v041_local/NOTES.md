# J4: public HPC set on node-local NVMe, AnnZarro v0.4.1

- **Job:** Slurm run-062, exclusive node compute-node (Intel Xeon Gold 6254 @ 3.10 GHz, 36 CPUs, 755 GiB RAM), 2026-10-07 13:10:23-16:26:53 PDT.
- **Release pin:** AnnZarro v0.4.1, tag commit 78c9da657ecbff30163fd29055f0e6b10e915c5c (tree 661a454f), installed non-editable from the tag clone.
  - Byte-identical to PyPI `annzarro==0.4.1`: `VERIFY.txt` (wheel sha256 = PyPI digest; 182/182 package files identical); `pin_v041.json`.
  - The job's pin guard passed (`annzarro pin OK` in its log).
- **Harness:** annzarro-reproducibility `dominik/hpc-bench-v030` @ 1804118b, `benchmark/hpc/slurm/rerun_release.sbatch` with STORE_TIER=locscratch and stages tahoe_x, grid, pairwise_public, hlca, limits, concurrency, deploy. `bench_http.py` uses the binary wire (f32) and `categorical=codes`; `bench_raw.py` is the raw-zarr baseline, dense cases only.
- **Storage:** 39 public stores (771 GB) staged to `$LOCAL_SCRATCH/$SLURM_JOB_ID` (ext4 on NVMe) before measuring (`run_v041_local/locscratch_staging.json`).
- **Protocol:** node-cold.
  - Before every cold repeat: `posix_fadvise(DONTNEED)` on every file of the case's arrays, verified by `mincore()` (CSV columns `resident_before` / `resident_after_evict`).
  - A fresh `annzarro start` per cold repeat; warm rows reuse it.
  - 5 cold repeats per case, 5 warm rows per repeat, 1 new-index row per repeat.
  - Full text: `cold_protocol` in each `http.env_*.json`.
- **Data:** public only. Tahoe-100M-derived (CC0-1.0), HLCA core (CELLxGENE 9f222629, CC BY 4.0), synthetic.
- **Results:** `run_v041_local/<stage>/http.csv` (and `raw.csv`, `http.env_*.json`, `spec_*.json`); `concurrency/conc.csv`; `deploy/deploy.csv`. 2,685 HTTP rows over 78 cases, all status 200.
- **#404:** https://github.com/settylab/user-HPC worker/issues/404#issuecomment-6050813695
- **`MANIFEST.tsv`:** the sha256 of every file of the run as copied off $SCRATCH, including the files left out here.

**Left out of this commit** (not read by any claim; all in `MANIFEST.tsv`):
- `run_v041_local/<stage>/logs/**`: 903 per-case server/app logs, 916,875 B, at `W/j4_v041_local/run_v041_local/<stage>/logs/`.
- `run_v041_local/done/*`: 7 stage-completion markers.
- `submit_v041.log`: the submission record (job ids, pin), 827 B, at `W/j4_v041_local/submit_v041.log`. The repo `.gitignore` excludes `*.log`.

`W/` = `$DATA_ROOT/annzarro-scale-results/` (HPC host). The originals at `$SCRATCH/annzarro-scale/hpcbench/run_v041_local/` are purged after ~2026-10-31.
