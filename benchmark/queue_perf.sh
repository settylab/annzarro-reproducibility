#!/bin/bash
# fig:performance laptop series (panels b-d: scale cold/warm and memory, chunk-shape sweep, sparse X) on a
# release build, in the binary wire format the web client uses (run_benchmark.py default).
# Usage: queue_perf.sh REV SUFFIX   e.g. queue_perf.sh <v0.4.0 sha> v040  ->  results/{scale,sparse,sweep}_v040.csv
# One run-timed call per measured command (one store size, or one sweep shape's measure; exclusive bench lock
# and timing marker, <= 30 min), ps inside it, 5 s apart; store generation is untimed (nice, no lock); holds while $HOME/.scale-rerun.PAUSE exists. Sweep stores are generated, measured and
# deleted one at a time (1M: ~18 GB each; 100k: 11 shapes, ~19 GB, deleted at the end).
set -eE
REV=${1:?REV}; S=${2:?SUFFIX}
cd "$(dirname "$0")"   # this checkout (never the shared tree); ../data/bench is this checkout's
EXE=$(scale/ceiling/setup_build.sh $REV $S-bench)
SPY=$(dirname $EXE)/python
PY=.venv/bin/python   # the paper venv (read only)
RB="$PY run_benchmark.py --suffix _$S --server-python $SPY"
export ANNZARRO_REPO=$(dirname $(dirname $(dirname $EXE)))
RT=$TMPDIR/teamlead-bench/run-timed
note() { echo "- $(date -u '+%F %TZ') $1" >> scale/ceiling/results/PROGRESS_rerun.md; }
snap() { (date -u '+%F %TZ'; uptime; sysctl -n kern.memorystatus_level; ps -axo pid,etime,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | grep -v 'Google Chrome.app' | cut -c1-180) >> results/ps_perf_$S.txt; }
run() {
  while [ -e $HOME/.scale-rerun.PAUSE ]; do sleep 30; done
  $RT bash -c "$(declare -f snap); S=$S; snap; $*" >> results/perf_$S.log 2>&1 || return 1
  sleep 5
}
gen() {  # untimed store generation: no lock, nice
  nice -n 10 "$@" >> results/perf_$S.log 2>&1 || return 1
}
has() { [ -f "results/$1_$S.csv" ] && grep -q ",$2," "results/$1_$S.csv"; }   # experiment, n_cells already measured
drop_manifest() { $PY - "$1" <<'PY'
import json, sys
from pathlib import Path
p = Path("../data/bench/manifest.json"); m = json.loads(p.read_text())
m = {k: v for k, v in m.items() if k != sys.argv[1]}
p.write_text(json.dumps(m, indent=1, sort_keys=True))
PY
}
# fail loudly: any failing command stops the queue, notes where, and leaves a flag file the operator's agent watches
trap 'note "perf $S FAILED (line $LINENO, exit $?): see results/perf_$S.log"; touch $HOME/.scale-rerun.FAILED' ERR
note "perf $S started (queue_perf.sh $REV)"
# the original stores (generate_data.py defaults: SEED, chunks c2048x32 for scale), rebuilt when missing
for n in 10000 30000 100000 300000 1000000; do
  [ -d ../data/bench/scale/cells_$n.zarr ] || gen $PY generate_data.py scale --sizes $n
done
for n in 100000 1000000; do
  [ -d ../data/bench/sparse/X_${n}_csr.zarr ] && [ -d ../data/bench/sparse/X_${n}_csc.zarr ] || gen $PY generate_data.py sparse --sizes $n
done
run $PY run_benchmark.py env --suffix _$S --server-python $SPY
for n in 10000 30000 100000 300000 1000000; do has scale $n || run $RB scale --sizes $n; done
note "perf $S: scale done"
for n in 100000 1000000; do has sparse $n || run $RB sparse --sizes $n; done
note "perf $S: sparse done"
if ! has sweep 100000; then
  gen $PY generate_data.py sweep --sizes 100000
  run $RB sweep --sizes 100000
  for d in ../data/bench/sweep/n100000/*.zarr; do rm -rf "$d"; drop_manifest "sweep/n100000/$(basename $d)"; done
fi
note "perf $S: sweep 100k done"
for TAG in default c1024x1024 c4096x256 c1024x64 c4096x16 c16384x16 c2048x32 c256x4096 cNx64; do
  [ -f results/sweep_$S.csv ] && grep -q "sweep/n1000000/$TAG.zarr" results/sweep_$S.csv && continue
  gen $PY generate_data.py sweep --sizes 1000000 --tags $TAG
  run $RB sweep --sizes 1000000
  rm -rf "../data/bench/sweep/n1000000/$TAG.zarr"; drop_manifest "sweep/n1000000/$TAG.zarr"
done
rm -rf ../data/bench/_cold
note "perf $S finished"
