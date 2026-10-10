#!/usr/bin/env bash
# Download the Kompot murine bone-marrow ageing dataset (Zenodo 10.5281/zenodo.15587768)
# with N parallel HTTP range requests, then verify the published md5.
set -euo pipefail
OUT_DIR="${1:-$(dirname "$0")/../data}"
N="${N:-16}"
URL="https://zenodo.org/records/15587768/files/murine_bone_marrow_aging.h5ad?download=1"
SIZE=2439076864
MD5=3e346c91e029e5fde551a9ebf9ecee78
mkdir -p "$OUT_DIR/_parts"
cd "$OUT_DIR/_parts"
CH=$(( (SIZE + N - 1) / N ))
for i in $(seq 0 $((N-1))); do
  s=$(( i*CH )); e=$(( s+CH-1 )); [ $e -ge $SIZE ] && e=$((SIZE-1))
  curl -sfL --retry 5 -r "$s-$e" -o "part_$(printf %02d $i)" "$URL" &
done
wait
cat part_* > ../murine_bone_marrow_aging.h5ad
cd .. && rm -rf _parts
got=$( (md5 -q murine_bone_marrow_aging.h5ad 2>/dev/null) || md5sum murine_bone_marrow_aging.h5ad | cut -d' ' -f1)
[ "$got" = "$MD5" ] && echo "md5 OK $got" || { echo "md5 MISMATCH $got"; exit 1; }
