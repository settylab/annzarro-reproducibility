#!/bin/bash
# Runs the beyond-budget rungs one after another, each its own run.py (the lock is taken per rung, so
# scale-benchmarker's runs interleave). Stops a ladder at its first failure. One line per rung to logs/beyond.log.
cd "$(dirname "$0")/.."
row() { grep "^annzarro_$1_run_$2_r0," results.csv | cut -d, -f1,8,9,10,11,15,16; }
for n in 160000000 175000000 200000000 250000000 300000000; do
  ./queue_v031_beyond.sh noguard $n > /dev/null 2>&1
  r=$(row v031_noguard $n); echo "$(date +%T) $r" >> logs/beyond.log
  case "$r" in *",ok,"*) ;; *) break ;; esac
done
echo "$(date +%T) noguard ladder done" >> logs/beyond.log
./queue_v031_beyond.sh build2b >> logs/beyond_build2b.log 2>&1; echo "$(date +%T) build2b rc=$?" >> logs/beyond.log
for n in 1250000000 1400000000 1500000000; do
  ./queue_v031_beyond.sh sub $n > /dev/null 2>&1
  echo "$(date +%T) $(row v031_sub $n)" >> logs/beyond.log; echo "$(date +%T) $(row v031_sub1m $n)" >> logs/beyond.log
done
echo "$(date +%T) beyond done" >> logs/beyond.log
