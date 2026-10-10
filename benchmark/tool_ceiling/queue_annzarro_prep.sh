#!/bin/bash
# AnnZarro's documented preparation path on the ladder's h5ads, until a step fails or passes
# the 48 GiB machine cap; each output store is deleted after its run (only the peak matters).
cd "$(dirname "$0")"
PY=.venv/bin/python D=$DATA_ROOT/tool_ceiling_data
mkdir -p $D/annzarro_prep
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
for n in 1000000 2000000 5000000 10000000 20000000 50000000 95624334; do
  f=$D/h5ad/tahoe_first$n.h5ad; [ -f $f ] || { echo "no h5ad $n"; break; }
  out=$D/annzarro_prep/first$n.zarr; rm -rf $out
  $PY run.py --tool annzarro --variant annzarro_prep --phase convert --n $n --timeout 7200 -- $PY annzarro_prep.py $f $out
  ok=$(tail -1 results.csv | cut -d, -f8); rm -rf $out
  [ "$ok" = ok ] || break
done
