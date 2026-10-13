#!/bin/bash
# Real-data cases against node tmpfs (RAM; the floor reference): copy ONE $SCRATCH real
# store into $TMPDIR, then run its real + real_rows cases (same case ids, so the same seeded
# indices as the $DATA_ROOT and $SCRATCH runs). Usage: sbatch --mem=<size> real_tmpfs.sbatch STORE
#SBATCH --partition=<value>
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=12:00:00
#SBATCH --job-name=azb-realtmpfs
#SBATCH --output=$SCRATCH/annzarro-bench/runs/slurm-%j.out
set -euo pipefail
B=$SCRATCH/annzarro-bench
H=$B/src/annzarro-reproducibility/benchmark/hpc
PY=$B/venv/bin/python
export H_SCRIPTS=$H/scripts
S=$1
OUT=$B/runs/real_post/real_tmpfs.csv; mkdir -p "$(dirname "$OUT")" $B/runs/canary
echo "node=$(hostname) job=$SLURM_JOB_ID start=$(date -Is) store=$S"; grep -m1 'model name' /proc/cpuinfo
t0=$(date +%s); cp -r "$B/data/real/$S" "${TMPDIR:?}/$S"; echo "tmpfs copy $(( $(date +%s)-t0 ))s"; df -hT "$TMPDIR"
SPEC=$B/runs/real_post/spec_tmpfs_${S%%.*}_${SLURM_JOB_ID}.json
"$PY" - "$TMPDIR" "$S" "$SPEC" <<'PYEOF'
import json, subprocess, sys, os
root, store, out = sys.argv[1:4]
H = os.environ.get("H_SCRIPTS")
cases = []
for name in ("real", "real_rows"):
    tmp = out + "." + name
    subprocess.run([sys.executable, os.path.join(H, "make_specs.py"), name, tmp, "--root", root, "--fs", "tmpfs"],
                   check=True)
    s = json.load(open(tmp)); os.remove(tmp)
    cases += [c for c in s["cases"] if os.path.basename(c["dataset"]) == store]
s["cases"] = cases; s["name"] = "real_tmpfs"
json.dump(s, open(out, "w"), indent=1)
print(f"{out}: {len(cases)} cases")
PYEOF
CAN=( "$PY" -u "$H/scripts/fs_canary.py" --array "$B/data/chunksweep/spatial-A-xenium_smoothed_allx64.zarr/layers/kompot_de_Xenium_smoothed" --label hpctemp --out "$B/runs/canary/canary.csv" )
"${CAN[@]}" --when "pre:real_tmpfs:$S"
"$PY" -u "$H/scripts/bench_http.py" --spec "$SPEC" --out "$OUT" --env "${OUT%.csv}.env_${SLURM_JOB_ID}.json"
"${CAN[@]}" --when "post:real_tmpfs:$S"
echo "end=$(date -Is)"
