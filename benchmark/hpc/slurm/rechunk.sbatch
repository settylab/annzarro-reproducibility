#!/bin/bash
# Chunk-shape sweep inputs: rechunk spatial-A layers/kompot_de_Xenium_smoothed (75000 x 18345,
# f4, blosc-lz4) into one minimal store per shape on $SCRATCH. Array index -> shape.
# (all,64) is the CURRENT shape, rewritten so every shape sits on the same filesystem.
#SBATCH --partition=<value>
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=4:00:00
#SBATCH --array=0-6
#SBATCH --job-name=azb-rechunk
#SBATCH --output=$SCRATCH/annzarro-bench/runs/slurm-%A_%a.out
set -euo pipefail
B=$SCRATCH/annzarro-bench
H=$B/src/annzarro-reproducibility/benchmark/hpc
SRC=$DATA_ROOT/lab-data/data/processed_zarr/spatial-A.zarr
SHAPES=(all,64 1024,1024 4096,256 256,4096 2048,2048 512,512 1024,512)  # index 6: the manuscript rule shape (follow-up 2026-10-02)
S=${SHAPES[$SLURM_ARRAY_TASK_ID]}
mkdir -p $B/data/chunksweep
echo "node=$(hostname) start=$(date -Is) shape=$S"
"$B/venv/bin/python" -u "$H/scripts/rechunk_layer.py" "$SRC" kompot_de_Xenium_smoothed \
    "$B/data/chunksweep/spatial-A-xenium_smoothed_${S/,/x}.zarr" "$S"
echo "end=$(date -Is)"
