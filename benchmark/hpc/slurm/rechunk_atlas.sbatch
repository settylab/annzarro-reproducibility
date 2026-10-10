#!/bin/bash
# Fix-at-scale: rechunk the (n_cells, 4)-chunked kompot_smooth_all_smoothed layers of the
# 1.17M-cell integrated atlas and scPLM 460k to the shape given as $1 (default 1024,1024) on $SCRATCH; "all,4" makes a same-filesystem copy of the original layout.
#SBATCH --partition=<partition>
#SBATCH --constraint=compute
#SBATCH --exclude=hpc-demo-node,hpc-node-32
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=12:00:00
#SBATCH --array=0-1
#SBATCH --job-name=azb-rechunk-atlas
#SBATCH --output=$SCRATCH/annzarro-bench/runs/slurm-%A_%a.out
set -euo pipefail
B=$SCRATCH/annzarro-bench
H=$B/src/annzarro-reproducibility/benchmark/hpc
L=$DATA_ROOT/lab-data/data/processed_zarr
SRCS=(atlas-1.17M-scvi.zarr atlas-scPLM.zarr)
TAGS=(atlas-1.17M-scvi scPLM)
i=$SLURM_ARRAY_TASK_ID
S=${1:-1024,1024}  # shape as a script ARGUMENT (the job sandbox does not forward exported env vars)
mkdir -p $B/data/atlas_rechunked
echo "node=$(hostname) start=$(date -Is) src=${SRCS[$i]}"
"$B/venv/bin/python" -u "$H/scripts/rechunk_layer.py" "$L/${SRCS[$i]}" kompot_smooth_all_smoothed \
    "$B/data/atlas_rechunked/${TAGS[$i]}_kompot_smooth_${S/,/x}.zarr" "$S"
echo "end=$(date -Is)"
