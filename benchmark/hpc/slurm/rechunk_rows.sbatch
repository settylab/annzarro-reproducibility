#!/bin/bash
# obsp/varp whole-row chunking rule (~1e6 values per chunk, rows rounded to a power of two):
# rechunk the dense pairwise stores to the rule's row counts and to bracketing ones.
#SBATCH --partition=<value>
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=8:00:00
#SBATCH --array=0-3
#SBATCH --job-name=azb-rows
#SBATCH --output=$SCRATCH/annzarro-bench/runs/slurm-%A_%a.out
set -euo pipefail
B=$SCRATCH/annzarro-bench
H=$B/src/annzarro-reproducibility/benchmark/hpc
P=$B/data/pairwise
JOBS=("dist_200000 obsp/diffmap_distance 4" "dist_200000 obsp/diffmap_distance 64"
      "dist_100000 obsp/diffmap_distance 8" "corr_30000 varp/gene_corr_pearson 32")
read -r NAME ARR R <<< "${JOBS[$SLURM_ARRAY_TASK_ID]}"
echo "node=$(hostname) start=$(date -Is) $NAME $ARR rows=$R"
"$B/venv/bin/python" -u "$H/scripts/rechunk_rows.py" "$P/$NAME.zarr" "$ARR" "$P/${NAME}_r${R}.zarr" "$R"
du -sh "$P/${NAME}_r${R}.zarr"
echo "end=$(date -Is)"
