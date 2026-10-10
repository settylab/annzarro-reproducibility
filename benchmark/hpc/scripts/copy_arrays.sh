#!/bin/bash
# copy_arrays.sh SRC DST ARRAY... : copy the named arrays (and every group's .zgroup/.zattrs on
# the way down) of a zarr v2 store into a new store. Chunk files are copied byte-identically,
# so the copy differs from the source only in filesystem and in the arrays left out.
set -euo pipefail
SRC=$1; DST=$2; shift 2
[[ -e "$DST" ]] && { echo "exists: $DST" >&2; exit 1; }
TMP="$DST.partial"; rm -rf "${TMP:?}"; mkdir -p "$TMP"
cp "$SRC"/.zgroup "$TMP"/; [[ -f "$SRC/.zattrs" ]] && cp "$SRC/.zattrs" "$TMP"/
for a in "$@"; do
  d=$(dirname "$a")
  if [[ "$d" != "." ]]; then
    mkdir -p "$TMP/$d"; cp "$SRC/$d/.zgroup" "$TMP/$d/"; [[ -f "$SRC/$d/.zattrs" ]] && cp "$SRC/$d/.zattrs" "$TMP/$d/"
  fi
  cp -r "$SRC/$a" "$TMP/$a"
done
mv "$TMP" "$DST"
du -sh "$DST"
