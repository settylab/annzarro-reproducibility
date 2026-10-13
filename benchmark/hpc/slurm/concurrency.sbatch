#!/bin/bash
# Concurrency test for the live-instance 23-26 s cold cell row: 3 sync workers (the live
# config), N = 1, 2, 4, 8 simultaneous cold cell-row requests; served (75000, 64) store on
# $DATA_ROOT, its same-shape copy on $SCRATCH, and the (1024, 1024) rechunk.
#SBATCH --partition=<value>
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=6:00:00
#SBATCH --job-name=azb-conc
#SBATCH --output=$SCRATCH/annzarro-bench/runs/slurm-%j.out
set -euo pipefail
B=$SCRATCH/annzarro-bench
H=$B/src/annzarro-reproducibility/benchmark/hpc
L=$DATA_ROOT/lab-data/data/processed_zarr
MODE=${1:-all}   # "post": the follow-up rerun, $SCRATCH stores only (a filer-load incident (2026-10-01) still open)
STORES=("$B/data/chunksweep/spatial-A-xenium_smoothed_allx64.zarr=allx64_hpctemp"
        "$B/data/chunksweep/spatial-A-xenium_smoothed_1024x1024.zarr=1024x1024_hpctemp"
        "$B/data/chunksweep/spatial-A-xenium_smoothed_1024x512.zarr=1024x512_hpctemp")
if [[ $MODE == post ]]; then OUT=$B/runs/post/concurrency/conc.csv
else OUT=$B/runs/concurrency/conc.csv; STORES=("$L/spatial-A.zarr=served_allx64_fhfast" "${STORES[@]:0:2}"); fi
mkdir -p "$(dirname "$OUT")"
echo "node=$(hostname) job=$SLURM_JOB_ID start=$(date -Is) mode=$MODE"; grep -m1 'model name' /proc/cpuinfo
"$B/venv/bin/python" -u "$H/scripts/bench_concurrency.py" --out "$OUT" "${STORES[@]}"
echo "end=$(date -Is)"
