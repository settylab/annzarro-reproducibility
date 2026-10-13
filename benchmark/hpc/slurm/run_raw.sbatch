#!/bin/bash
# Raw zarr benchmark job (dense cases of a spec): one spec, one CSV. Submit from benchmark/hpc with
#   sbatch --export=ALL,SPEC=<spec.json>,OUT=<results.csv>[,ONLY=<case_ids>] slurm/run_raw.sbatch
# All nodes are HPC compute nodes (36-core Xeon, 700 GB), excluding demo-server where the live
# AnnZarro instance runs, so that cold-cache measurements neither perturb nor are
# perturbed by it.
#SBATCH --partition=<value>
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --job-name=azb-raw
#SBATCH --output=$SCRATCH/annzarro-bench/runs/slurm-%j.out
set -euo pipefail
B=$SCRATCH/annzarro-bench
H=$B/src/annzarro-reproducibility/benchmark/hpc
echo "node=$(hostname) job=$SLURM_JOB_ID start=$(date -Is) spec=$SPEC out=$OUT"
# lscpu needs /sys, which the job sandbox hides; /proc/cpuinfo is visible.
grep -m1 'model name' /proc/cpuinfo
echo "logical_cpus=$(grep -c ^processor /proc/cpuinfo) nproc=$(nproc)"
df -h "${TMPDIR:-/tmp}" $LOCAL_SCRATCH 2>&1 || true
args=(--spec "$SPEC" --out "$OUT")
[[ -n "${ONLY:-}" ]] && args+=(--only "$ONLY")
CAN=( "$B/venv/bin/python" -u "$H/scripts/fs_canary.py" --array "$B/data/chunksweep/spatial-A-xenium_smoothed_allx64.zarr/layers/kompot_de_Xenium_smoothed" --label hpctemp --out "$B/runs/canary/canary.csv" )
mkdir -p "$B/runs/canary"; "${CAN[@]}" --when "pre:$(basename "$OUT")"
"$B/venv/bin/python" -u "$H/scripts/bench_raw.py" "${args[@]}"
"${CAN[@]}" --when "post:$(basename "$OUT")"
echo "end=$(date -Is)"
