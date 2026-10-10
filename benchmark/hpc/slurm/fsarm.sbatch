#!/bin/bash
# Filesystem arm: the same spatial-A endpoints (HTTP + raw zarr) on three locations, in ONE job
# on ONE node: $DATA_ROOT (served original), $SCRATCH (subset copy), node tmpfs ($TMPDIR, which
# inside the job sandbox is RAM-backed tmpfs, NOT the node's NVMe).
#SBATCH --partition=<partition>
#SBATCH --constraint=compute
#SBATCH --exclude=hpc-demo-node,hpc-node-32
#SBATCH --cpus-per-task=4
#SBATCH --mem=96G
#SBATCH --time=12:00:00
#SBATCH --job-name=azb-fsarm
#SBATCH --output=$SCRATCH/annzarro-bench/runs/slurm-%j.out
set -euo pipefail
B=$SCRATCH/annzarro-bench
H=$B/src/annzarro-reproducibility/benchmark/hpc
PY=$B/venv/bin/python
ORIG=$DATA_ROOT/lab-data/data/processed_zarr/spatial-A.zarr
HT=$B/data/fsarm/spatial-A-subset.zarr
TF="${TMPDIR:?}/spatial-A-subset.zarr"
MODE=${1:-all}   # "post": the follow-up rerun, which leaves $DATA_ROOT out (a filer-load incident (2026-10-01) still open)
if [[ $MODE == post ]]; then OUT=$B/runs/post/fsarm; ARMS=("hpctemp $HT" "tmpfs $TF"); else OUT=$B/runs/fsarm; ARMS=("fhfast $ORIG" "hpctemp $HT" "tmpfs $TF"); fi
mkdir -p $OUT $B/data/fsarm $B/runs/canary
CAN=( "$PY" -u "$H/scripts/fs_canary.py" --array "$B/data/chunksweep/spatial-A-xenium_smoothed_allx64.zarr/layers/kompot_de_Xenium_smoothed" --label hpctemp --out "$B/runs/canary/canary.csv" )
echo "node=$(hostname) job=$SLURM_JOB_ID start=$(date -Is)"; grep -m1 'model name' /proc/cpuinfo
[[ -e $HT ]] || "$H/scripts/copy_subset.sh" "$ORIG" "$HT"
t0=$(date +%s); "$H/scripts/copy_subset.sh" "$HT" "$TF"; echo "tmpfs copy $(( $(date +%s)-t0 ))s"; df -hT "$TMPDIR"
"${CAN[@]}" --when "pre:fsarm:$MODE"
for arm in "${ARMS[@]}"; do
  read -r fs root <<< "$arm"
  "$PY" "$H/scripts/make_specs.py" fsarm "$OUT/spec_${fs}_${SLURM_JOB_ID}.json" --root "$root" --fs "$fs"
  "$PY" -u "$H/scripts/bench_http.py" --spec "$OUT/spec_${fs}_${SLURM_JOB_ID}.json" --out "$OUT/http.csv" --env "$OUT/env_${fs}_${SLURM_JOB_ID}.json"
  "$PY" -u "$H/scripts/bench_raw.py" --spec "$OUT/spec_${fs}_${SLURM_JOB_ID}.json" --out "$OUT/raw.csv"
done
"${CAN[@]}" --when "post:fsarm:$MODE"
echo "end=$(date -Is)"
