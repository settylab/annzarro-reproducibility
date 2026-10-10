#!/bin/bash
# $SCRATCH health canary: N readings of fs_canary.py against a fixed array (the (75000,64)
# spatial-A chunk-sweep copy: 287 chunk files of ~5 MB), SLEEP seconds apart.
#SBATCH --partition=<partition>
#SBATCH --constraint=compute
#SBATCH --exclude=hpc-demo-node,hpc-node-32
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=1:00:00
#SBATCH --job-name=azb-canary
#SBATCH --output=$SCRATCH/annzarro-bench/runs/slurm-%j.out
set -euo pipefail
B=$SCRATCH/annzarro-bench
H=$B/src/annzarro-reproducibility/benchmark/hpc
N=${1:-5}; SLEEP=${2:-30}
ARR=$B/data/chunksweep/spatial-A-xenium_smoothed_allx64.zarr/layers/kompot_de_Xenium_smoothed
mkdir -p $B/runs/canary
for i in $(seq 1 "$N"); do
  "$B/venv/bin/python" -u "$H/scripts/fs_canary.py" --array "$ARR" --label hpctemp --when "probe$i" \
      --out "$B/runs/canary/canary.csv"
  if (( i < N )); then sleep "$SLEEP"; fi
done
