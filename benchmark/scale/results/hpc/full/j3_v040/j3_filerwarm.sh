#!/bin/bash
#SBATCH --partition=<value>
#SBATCH --exclusive
#SBATCH --mem=350G
#SBATCH --time=16:00:00
#SBATCH --job-name=scale-worker-j3-filerwarm
#SBATCH --output=$SCRATCH/annzarro-scale/logs/j3_filerwarm.slurm.out
# J3: every J rung re-measured under the operator's override (orchestrator relay, 10-05): the filer is treated as
# HOT and made equally warm before each measured pass; "cold" = TOOL-cold (a fresh server per rep) with the client
# page cache evicted (fadvise, verified by mincore). ORDER per rung: warm the filer (mode B: read every
# file of the store), THEN bench_http.py's cold prep evicts the node page cache for every store file, THEN a fresh
# server is started for each cold rep. warmcheck.py times a seeded sample of chunk files read from the filer (node
# cache evicted for them) before the warm-up (pre), after it (post_warm) and after the measured pass (post_measure),
# so filer warmth is measured, not assumed: results_j3/warmcheck.tsv. Protocol otherwise as R: paper bfd7cd0
# bench_http.py, 3 reps, 2 warm, one call per rung 1M..95.6M ascending,
# --skip cell_row_cscscan_all at >= 20M (J's skip), a $SCRATCH canary before and after each rung.
#   sbatch j3_filerwarm.sh A|B
#   A = warm-up: an identical bench_http.py pass per rung, discarded (warmup_discarded.csv)
#   B = warm-up: every file of the rung's store read once by warmread.py (bytes vs apparent size, read errors,
#       seconds, MB/s per rung in warmup.tsv; rc 1 on any error or short read)
MODE=${1:?A|B}
# AnnZarro PIN (operator rule, request 20261006T010117Z): v0.3.1 = 1391357, non-editable in hpcbench/venv_v031 (from the
# clone hpcbench/src_v031); repinned to v0.4.0 at submission through V/ANNZ_SRC/ANNZ_COMMIT (NOTES.md). The job
# exits 2 unless the installed annzarro came from ANNZ_SRC at ANNZ_COMMIT; annzarro_pin.json records it (bench_http's own
# environment.json leaves annzarro_commit empty for a non-editable install).
V=${V:-$SCRATCH/annzarro-scale/hpcbench/venv_v031}
ANNZ_SRC=${ANNZ_SRC:-$SCRATCH/annzarro-scale/hpcbench/src_v031}
ANNZ_COMMIT=${ANNZ_COMMIT:-13913570654876210dc4a274dfcaa0bfbc367a7a}
exec >> $SCRATCH/annzarro-scale/logs/j3_filerwarm.log 2>&1
set -uo pipefail
export SCRATCH=$SCRATCH/annzarro-scale SITE=hpc
H=$SCRATCH/paper-bfd7cd0/benchmark/scale; O=$SCRATCH/results_j3; mkdir -p $O $SCRATCH/tmp_j3
echo "=== J3 start $(date -Is) mode=$MODE host=$(hostname) job=${SLURM_JOB_ID:-} cpus=${SLURM_CPUS_ON_NODE:-} loadavg=$(cut -d' ' -f1-3 /proc/loadavg)"
git -C $SCRATCH/paper-bfd7cd0 rev-parse HEAD
src_head=$(git -C "$ANNZ_SRC" rev-parse HEAD)
inst=$("$V/bin/python" -c 'import importlib.metadata as m, json; d=m.distribution("annzarro"); print(m.version("annzarro"), json.loads(d.read_text("direct_url.json"))["url"])')
src_tree=$(git -C "$ANNZ_SRC" rev-parse "HEAD^{tree}")
[[ $src_head == "$ANNZ_COMMIT" && ${inst#* } == "file://$ANNZ_SRC" && ( -z ${ANNZ_TREE:-} || $src_tree == "$ANNZ_TREE" ) ]] || { echo "pin mismatch: $ANNZ_SRC HEAD=$src_head tree=$src_tree want $ANNZ_COMMIT ${ANNZ_TREE:-}; installed $inst"; exit 2; }
if [[ -n ${ANNZ_RELEASE_TAG:-} ]]; then  # the release tag must name ANNZ_RELEASE_COMMIT and carry the SAME tree as the source
  rel_c=$(git -C "$ANNZ_SRC" rev-parse "${ANNZ_RELEASE_TAG}^{commit}"); rel_t=$(git -C "$ANNZ_SRC" rev-parse "${ANNZ_RELEASE_TAG}^{tree}")
  [[ $rel_c == "${ANNZ_RELEASE_COMMIT:-}" && $rel_t == "$src_tree" ]] || { echo "release mismatch: $ANNZ_RELEASE_TAG -> $rel_c tree $rel_t; want ${ANNZ_RELEASE_COMMIT:-} tree $src_tree"; exit 2; }
fi
printf '{"annzarro_version": "%s", "annzarro_commit": "%s", "annzarro_tree": "%s", "annzarro_release_tag": "%s", "annzarro_release_commit": "%s", "annzarro_src": "%s", "venv": "%s", "installed_from": "%s", "harness": "paper %s", "job": "%s", "node": "%s", "start": "%s"}\n' \
  "${inst%% *}" "$src_head" "$src_tree" "${ANNZ_RELEASE_TAG:-}" "${ANNZ_RELEASE_COMMIT:-}" "$ANNZ_SRC" "$V" "${inst#* }" "$(git -C $SCRATCH/paper-bfd7cd0 rev-parse HEAD)" "${SLURM_JOB_ID:-}" "$(hostname)" "$(date -Is)" > $O/annzarro_pin.json
cat $O/annzarro_pin.json
CAN=( $SCRATCH/hpcbench/venv/bin/python -u $SCRATCH/paper-hpcbench/benchmark/hpc/scripts/fs_canary.py --array $SCRATCH/public/grid/tahoe_dense_1M_allx64.zarr/layers/lognorm_panel --label hpctemp --out $O/canary.csv )
for L in 1M 2M 5M 10M 20M 50M 95.6M; do
  st=$SCRATCH/stores/n$L/tahoe_$L.zarr
  SKIP=(); case $L in 20M|50M|95.6M) SKIP=(--skip cell_row_cscscan_all) ;; esac
  # 1M slow-rule straddle (cell_row_cscscan_all cold near bench_http's --slow 120 s): made deterministic, decided by the laptop and read at RUN time from jobs/j3_slow1m.txt
  # (a = always run the warm reps: --slow 1e9; b = always cold only: --slow 60, every other 1M click is <= 5.4 s;
  # c = harness default 120, i.e. chance). Missing/unknown file -> a (orchestrator default). Other rungs unchanged.
  SLOW=()
  if [[ $L == 1M ]]; then
    D1=$(tr -d '[:space:]' < $SCRATCH/jobs/j3_slow1m.txt 2>/dev/null); case $D1 in a|b|c) ;; *) D1=a ;; esac
    case $D1 in a) SLOW=(--slow 1000000000) ;; b) SLOW=(--slow 60) ;; esac
    echo "1M slow-rule decision: $D1 -> ${SLOW[*]:-default --slow 120}"
  fi
  "${CAN[@]}" --when "pre:$L"
  WC=( $SCRATCH/hpcbench/venv/bin/python -u $SCRATCH/jobs/warmcheck.py "$st" )
  "${WC[@]}" pre $O/warmcheck.tsv
  t0=$(date +%s); ts=$(date -Is)
  if [[ $MODE == A ]]; then
    timeout 6h $V/bin/python $H/bench_http.py "$st" --site hpc --out $O/warmup_discarded.csv \
        --scratch $SCRATCH/tmp_j3 --port 8900 "${SKIP[@]}" "${SLOW[@]}"; echo "warm-up $L rc=$?"
    printf '%s\t%s\t%s\tA: discarded bench pass\n' "$L" "$ts" "$(( $(date +%s) - t0 ))" >> $O/warmup_A.tsv
  else
    $SCRATCH/hpcbench/venv/bin/python -u $SCRATCH/jobs/warmread.py "$st" "$L" $O/warmup.tsv; echo "warm-up $L rc=$? (1 = read errors or a short read: see warmup.tsv)"
  fi
  "${WC[@]}" post_warm $O/warmcheck.tsv
  "${CAN[@]}" --when "mid:$L"
  timeout 6h $V/bin/python $H/bench_http.py "$st" --site hpc --out $O/http_hpc_filerwarm.csv \
      --scratch $SCRATCH/tmp_j3 --port 8900 "${SKIP[@]}" "${SLOW[@]}"
  echo "rung $L rc=$?"
  "${WC[@]}" post_measure $O/warmcheck.tsv
  "${CAN[@]}" --when "post:$L"
done
echo "=== J3 end $(date -Is)"
