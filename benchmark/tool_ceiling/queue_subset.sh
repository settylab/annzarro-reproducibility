#!/bin/bash
# AnnZarro 120f322 with SUBSETTING, up 150M-1B on build_stores.py's synthetic stores:
# v030_sub = the app's default subset (100k above 200k cells), v030_sub1m = a 1M subset.
# Both colourings (gene, then category). The 1B master (and its 500M prefix) is built
# only if 300M passes. Stops at the first N where the default subset fails.
cd "$(dirname "$0")"
PY=.venv/bin/python EXE=$ENVS_ROOT/annzarro_v030p_120f322/.venv/bin/annzarro
OLD=$DATA_ROOT/tahoe_scale_ceiling CEIL=benchmark/scale/ceiling
while pgrep -f "queue_guard_r1.sh|queue_fixed.sh" >/dev/null; do sleep 30; done
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
sub() {  # sub VARIANT N STORE SUBSET
  $PY run.py --web --tool annzarro --variant $1 --n $2 --note "AnnZarro v030-preview 120f322, local server, subset $4" -- \
    $PY annzarro_task.py default $3 {out} --exe $EXE --inprocess --version-label 120f322 --cat cell_type --gene GENE0 --subset "$4"
}
for n in 150000000 200000000 300000000 500000000 1000000000; do
  case $n in
    300000000) st=$OLD/syn_master_300000000.zarr ;;
    1000000000) st=$OLD/syn_master_1000000000.zarr ;;
    *) st=$OLD/syn_$n.zarr ;;
  esac
  if [ ! -d $st ]; then
    df -h $HOME | tail -1
    $PY run.py --tool input_syn --variant build_stores --phase convert --n 1000000000 --timeout 7200 -- \
      $CEIL/.venv/bin/python $CEIL/build_stores.py $OLD --master-n 1000000000 --sizes 500000000
    last_ok || break
  fi
  sub v030_sub $n $st absent
  ok=$(tail -1 results.csv | cut -d, -f8)
  sub v030_sub1m $n $st '{"n": 1000000, "seed": 0}'
  [ "$ok" = ok ] || break
done
