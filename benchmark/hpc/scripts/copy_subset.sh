#!/bin/bash
# copy_subset.sh SRC DST : copy the spatial-A arrays the fsarm endpoints touch (plus group
# metadata) into a new store. Byte-identical chunk files; only untouched arrays are omitted.
set -euo pipefail
SRC=$1; DST=$2
[[ -e "$DST" ]] && { echo "exists: $DST" >&2; exit 1; }
TMP="$DST.partial"; rm -rf "${TMP:?}"; mkdir -p "$TMP"
cp "$SRC"/.zgroup "$SRC"/.zattrs "$TMP"/
for g in obsm obsp varp layers; do mkdir -p "$TMP/$g"; cp "$SRC/$g"/.zgroup "$SRC/$g"/.zattrs "$TMP/$g"/ 2>/dev/null || cp "$SRC/$g"/.zgroup "$TMP/$g"/; done
for a in X obs var layers/kompot_de_Xenium_smoothed obsm/X_umap obsp/dist_spatial varp/gene_corr_pearson_lognorm; do
  cp -r "$SRC/$a" "$TMP/$a"
done
mv "$TMP" "$DST"
du -sh "$DST"
