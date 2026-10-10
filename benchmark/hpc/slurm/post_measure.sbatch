#!/bin/bash
# Follow-up (2026-10-02) post-#386 measurement: build the experiment's spec at RUN time (so it
# lists every store the prep jobs finished), drop any $DATA_ROOT case, bracket the run with
# $SCRATCH canary readings, run bench_http or bench_raw. Submitted with --dependency=singleton
# under one job name, so these jobs run strictly one at a time and never load $SCRATCH
# against each other.  Usage: sbatch post_measure.sbatch EXP http|raw
#   EXP: chunksweep | pairwise | atlas | real | real_rows   (real*: the $SCRATCH copies)
#SBATCH --partition=<partition>
#SBATCH --constraint=compute
#SBATCH --exclude=hpc-demo-node,hpc-node-32
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --job-name=azb-measure
#SBATCH --output=$SCRATCH/annzarro-bench/runs/slurm-%j.out
set -euo pipefail
B=$SCRATCH/annzarro-bench
H=$B/src/annzarro-reproducibility/benchmark/hpc
PY=$B/venv/bin/python
EXP=$1; KIND=$2
case $EXP in
  real|real_rows) ROOT=(--root "$B/data/real"); DIR=$B/runs/real_post; OUT=$DIR/real_hpctemp.csv ;;
  *)              ROOT=();                       DIR=$B/runs/post/$EXP;  OUT=$DIR/$KIND.csv ;;
esac
[[ $KIND == raw ]] && OUT=${OUT%.csv}_raw.csv && [[ $EXP != real* ]] && OUT=$DIR/raw.csv
mkdir -p "$DIR" $B/runs/canary
echo "node=$(hostname) job=$SLURM_JOB_ID start=$(date -Is) exp=$EXP kind=$KIND out=$OUT"; grep -m1 'model name' /proc/cpuinfo
SPEC=$DIR/spec_${EXP}_${SLURM_JOB_ID}.json
"$PY" "$H/scripts/make_specs.py" "$EXP" "$SPEC.all" "${ROOT[@]}" --fs hpctemp
"$PY" - "$SPEC.all" "$SPEC" <<'PYEOF'
import json, sys
s = json.load(open(sys.argv[1]))
s["cases"] = [c for c in s["cases"] if c["fs"] != "fhfast"]   # a filer-load incident (2026-10-01) still open
json.dump(s, open(sys.argv[2], "w"), indent=1)
print(f"{sys.argv[2]}: {len(s['cases'])} cases")
PYEOF
rm -f "$SPEC.all"
CAN=( "$PY" -u "$H/scripts/fs_canary.py" --array "$B/data/chunksweep/spatial-A-xenium_smoothed_allx64.zarr/layers/kompot_de_Xenium_smoothed" --label hpctemp --out "$B/runs/canary/canary.csv" )
"${CAN[@]}" --when "pre:$EXP:$KIND"
if [[ $KIND == http ]]; then
  "$PY" -u "$H/scripts/bench_http.py" --spec "$SPEC" --out "$OUT" --env "${OUT%.csv}.env_${SLURM_JOB_ID}.json"
else
  "$PY" -u "$H/scripts/bench_raw.py" --spec "$SPEC" --out "$OUT"
fi
"${CAN[@]}" --when "post:$EXP:$KIND"
echo "end=$(date -Is)"
