#!/bin/bash
# The regular-path heap after repeated subset swaps (4M <-> 100k on the 5M
# store), on this branch, v0.2.0 and v030-preview 639a2f9. Bench lock and
# the GUI window (:00-:15) as run_memguard.sh; ps recorded at every start.
set -u
cd benchmark/scale/memguard
R=benchmark/scale/results
W=$ANNZARRO_SRC/.claude/worktrees
STORE=$DATA_ROOT/tahoe_scale/stores/rerun_prefix/tahoe95_first5000000.zarr
L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
OUT=$R/memguard_swap.jsonl
snap() { (echo "== $1"; date -u '+%F %TZ'; uptime; ps -axo pid,etime,%cpu,rss,command | grep -E '[p]ython|[a]nnzarro|[C]hrom' | cut -c1-200) >> $R/ps_memguard.txt; }
fits_now() { local m=$((10#$(date +%M))); [ $m -ge 15 ] && [ $((m + $1)) -lt 60 ]; }
run() {  # run TAG WORKTREE
  local tag=$1 wt=$2
  while true; do
    while ! fits_now 15; do sleep 30; done
    $L bash -c "$(declare -f fits_now); fits_now 15 || exit 75; R=$R; $(declare -f snap); snap 'swap $tag'; ../ceiling/.venv/bin/python swap_repeat.py $wt $STORE --big 4000000 --k 6 --out $OUT --tag $tag" >> $R/memguard_swap.log 2>&1
    [ $? -ne 75 ] && break
  done
}
for v in "$@"; do
  case $v in
    branch) run swap_branch_5aa3a83 $W/memory-guard ;;
    v020)   run swap_v020 $W/v020 ;;
    pre)    run swap_639a2f9 $W/leak-639a2f9 ;;
  esac
done
