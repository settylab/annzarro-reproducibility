#!/bin/bash
# The v0.4.0 series in order (each rung its own run.py, lock per rung); one line per rung in logs/v040.log
cd "$(dirname "$0")/.."
export SHA=3bdeb0913d7e5761c496070dbb30acd2cd32ceb5
./queue_v040.sh $SHA > logs/v040_queue.log 2>&1; echo "$(date +%T) main ladder done rc=$?" >> logs/v040.log
for n in 160000000 175000000 200000000 250000000 300000000; do
  ./queue_v040_beyond.sh noguard $n > /dev/null 2>&1
  r=$(grep "^annzarro_v040_noguard_run_${n}_r0," results.csv | cut -d, -f8); echo "$(date +%T) noguard $n $r" >> logs/v040.log
  [ "$r" = ok ] || break
done
./queue_v040_beyond.sh build2b >> logs/v040_build2b.log 2>&1; echo "$(date +%T) build2b rc=$?" >> logs/v040.log
for n in 1250000000 1400000000 1500000000; do ./queue_v040_beyond.sh sub $n > /dev/null 2>&1; echo "$(date +%T) sub $n" >> logs/v040.log; done
echo "$(date +%T) v040 series done" >> logs/v040.log
