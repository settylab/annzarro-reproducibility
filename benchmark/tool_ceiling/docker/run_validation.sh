#!/bin/bash
# The hard-limit points: the two ladder Ns around each library's 16 GB crossing (+ one clear fail).
cd "$(dirname "$0")"
while read tool var n; do
  echo "== $tool $var $n $(./validate.sh $tool 16g $var /data/tahoe_first$n.h5ad 2>&1 | tail -1)"
done <<'PTS'
scanpy default 7100000
scanpy default 8400000
scanpy default 10000000
seurat default 2000000
seurat default 5000000
PTS
