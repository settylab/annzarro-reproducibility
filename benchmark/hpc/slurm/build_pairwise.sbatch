#!/bin/bash
# Dense pairwise inputs: Gaussian obsp kernels (50k, 100k, 200k cells) and Pearson
# varp correlations (20k, 30k genes), written to $SCRATCH. Array index -> build.
#SBATCH --partition=<partition>
#SBATCH --constraint=compute
#SBATCH --exclude=hpc-demo-node,hpc-node-32
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=12:00:00
#SBATCH --array=0-7
#SBATCH --job-name=azb-pairwise
#SBATCH --output=$SCRATCH/annzarro-bench/runs/slurm-%A_%a.out
set -euo pipefail
B=$SCRATCH/annzarro-bench
H=$B/src/annzarro-reproducibility/benchmark/hpc
BUILDS=("kernel 50000" "kernel 100000" "kernel 200000" "corr 20000" "corr 30000" "dist 50000" "dist 100000" "dist 200000")
read -r KIND SIZE <<< "${BUILDS[$SLURM_ARRAY_TASK_ID]}"
mkdir -p $B/data/pairwise
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK OPENBLAS_NUM_THREADS=$SLURM_CPUS_PER_TASK
echo "node=$(hostname) start=$(date -Is) build=$KIND $SIZE"
"$B/venv/bin/python" -u "$H/scripts/build_pairwise.py" "$KIND" "$SIZE" "$B/data/pairwise/${KIND}_${SIZE}.zarr"
du -sh "$B/data/pairwise/${KIND}_${SIZE}.zarr"
echo "end=$(date -Is)"
