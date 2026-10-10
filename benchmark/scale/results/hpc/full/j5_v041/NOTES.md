# J5: the Tahoe-100M per-click ladder (1M-95.6M) on an HPC node, AnnZarro v0.4.1

- **Job:** Slurm 10163489, exclusive node hpc-node-15 (compute class, board x11dpu, 36 CPUs, 755 GiB RAM), 2026-10-08 06:34:19-09:42:19 PDT.
  - The CPU model is not recorded by this harness. HPC compute nodes in the other v0.4.1 jobs report Xeon Gold 6254.
- **Release pin:** AnnZarro v0.4.1, tag commit 78c9da657ecbff30163fd29055f0e6b10e915c5c (tree 661a454f), byte-identical to PyPI `annzarro==0.4.1`. Recorded in `results_j5/annzarro_pin.json`; the job refuses to run on a mismatch.
- **Harness:** annzarro-reproducibility b9cd439b (`dominik/j5-v041-harness`), `benchmark/scale/bench_http.py`, which is bfd7cd0 with `categorical=codes` on the two obs_cat requests.
  - 3 cold reps plus warm repetitions per click, rungs 1M, 2M, 5M, 10M, 20M, 50M, 95,624,334.
  - 1M slow rule "a" (`j5_slow1m.txt`): warm reps always run.
- **Storage:** Tahoe-100M-derived panel stores (public, CC0-1.0), read in place on `$SCRATCH` (NFS4). Each store was read once before its rung (`warmup.tsv`); filer cache uncontrolled.
- **Protocol:** node-cold. Full text in `results_j5/cold_protocol.json`, written 2026-10-08 from this run's records in the same form as J3's.
  - `posix_fadvise(DONTNEED)` on every store file and a fresh server per cold rep.
  - No per-rep mincore check in this harness; `warmcheck.tsv` checked 60 sampled files 21 times, and resident_after_evict was 0.0 every time.
- **Results:** `results_j5/http_hpc_filerwarm.csv` and `results_j5/http_hpc_filerwarm_environment.json`.
- **#404:** https://github.com/settylab/user-HPC worker/issues/404#issuecomment-6064683947
- **`MANIFEST.tsv`:** the sha256 of every file as copied off $SCRATCH. `results_j5/cold_protocol.json` was appended later, and its row says so.

**Left out of this commit:**
- `j5_v041.sh`: the job script as run, 6,941 B, at `W/j5_v041/j5_v041.sh`, sha256 in `MANIFEST.tsv`. Its comments cite pre-v0.4.0 smoke timings, so it is left out under the no-pre-v0.4.0-build rule. Not read by any claim.
- `j5_v041.log`: the job log, 15,895 B, at `W/j5_v041/j5_v041.log`. The repo `.gitignore` excludes `*.log`.

`W/` = `$DATA_ROOT/annzarro-scale-results/` (HPC host). The originals at `$SCRATCH/annzarro-scale/results_j5/` are purged after ~2026-10-31.
