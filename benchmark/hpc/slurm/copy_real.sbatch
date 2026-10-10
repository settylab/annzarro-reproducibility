#!/bin/bash
# Byte-identical copies of the arrays the real-data cases touch, from the served stores on
# $DATA_ROOT (read-only use) to $SCRATCH, so the real-data cases can be measured off $DATA_ROOT.
#SBATCH --partition=<partition>
#SBATCH --constraint=compute
#SBATCH --exclude=hpc-demo-node,hpc-node-32
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=8:00:00
#SBATCH --array=0-2
#SBATCH --job-name=azb-copyreal
#SBATCH --output=$SCRATCH/annzarro-bench/runs/slurm-%A_%a.out
set -euo pipefail
B=$SCRATCH/annzarro-bench
H=$B/src/annzarro-reproducibility/benchmark/hpc
L=$DATA_ROOT/lab-data/data/processed_zarr
mkdir -p $B/data/real
case $SLURM_ARRAY_TASK_ID in
  0) S=atlas-1.17M-scvi.zarr; A=(X layers/lognorm layers/kompot_smooth_all_smoothed obsm/X_umap obsm/X_scVI obs var obsp/connectivities) ;;
  1) S=atlas-1.17M-raw.zarr;         A=(X obs var) ;;
  2) S=atlas-scPLM.zarr; A=(X layers/kompot_smooth_all_smoothed obsm/X_umap obs var) ;;
esac
echo "node=$(hostname) start=$(date -Is) store=$S"
"$H/scripts/copy_arrays.sh" "$L/$S" "$B/data/real/$S" "${A[@]}"
echo "end=$(date -Is)"
