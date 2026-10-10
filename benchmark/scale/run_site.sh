#!/bin/bash
# Build the nested Tahoe-100M stores and run the scale benchmark on one machine.
#
#   SCRATCH=$SCRATCH/.../annzarro-scale SITE=hpc benchmark/scale/run_site.sh all
#
# Steps (run one by name, or `all` in order; each is resumable):
#   env       uv venv (Python 3.11) with AnnZarro at $ANNZARRO_COMMIT, anndata, zarr 3, playwright
#   download  Tahoe-100M parquet shards 0..$((SHARDS-1)) from Hugging Face (tahoebio/Tahoe-100M, CC0-1.0)
#   build     PCA fit, master CSR of the first $MAX_CELLS cells, one store per size in $SIZES
#   http      bench_http.py over all stores        -> $SCRATCH/results/http_$SITE.csv
#   browser   bench_browser.py over all stores     -> $SCRATCH/results/browser_$SITE.csv
#   subset    bench_subset.py over all stores      -> $SCRATCH/results/subset_$SITE.csv
#
# Disk: parquet ~3.5 GB per million cells (337 GB for all 3,388 shards); master
# CSR ~1.85 GB and each store's CSC ~1.56 GB per million cells. KEEP_PARQUET=0
# deletes the shards once the master is built.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
: "${SCRATCH:?set SCRATCH to a scratch directory}"
SITE=${SITE:-hpc}
SHARDS=${SHARDS:-3388}
MAX_CELLS=${MAX_CELLS:-200000000}            # more than the release has: take every cell
SIZES=${SIZES:-1000000 2000000 5000000 10000000 20000000 50000000 all}
ANNZARRO_COMMIT=${ANNZARRO_COMMIT:-2858fc58ca80239b273dba691fd0567453f5fdda}
ANNZARRO_REPO=${ANNZARRO_REPO:-https://github.com/settylab/annzarro.git}
PAR=${PAR:-8}
KEEP_PARQUET=${KEEP_PARQUET:-1}
V=$SCRATCH/venv
PY=$V/bin/python
mkdir -p "$SCRATCH"/{parquet,work,stores,results,tmp}

label() { python3 -c "n=int('$1'); print(f'{n//1_000_000}M' if n % 1_000_000 == 0 else f'{n/1e6:.1f}M')"; }
store_path() { local l; l=$(label "$1"); echo "$SCRATCH/stores/n$l/tahoe_$l.zarr"; }

sizes() {    # cell counts for $SIZES that the master holds ("all" = every cell), smallest first
  local total; total=$(python3 -c "import json; print(json.load(open('$SCRATCH/work/master_done.json'))['n_cells'])")
  for s in $SIZES; do
    [ "$s" = all ] && s=$total
    if [ "$s" -le "$total" ]; then echo "$s"; fi
  done | sort -n | uniq
}
stores() { for n in $(sizes); do store_path "$n"; done; }

step_env() {
  [ -x "$PY" ] || uv venv -p 3.11 "$V"
  [ -d "$SCRATCH/src/annzarro" ] || git clone "$ANNZARRO_REPO" "$SCRATCH/src/annzarro"
  git -C "$SCRATCH/src/annzarro" fetch -q origin
  git -C "$SCRATCH/src/annzarro" checkout -q "$ANNZARRO_COMMIT"
  VIRTUAL_ENV=$V uv pip install -q -e "$SCRATCH/src/annzarro[remote]" anndata 'zarr>=3' numcodecs \
      pyarrow scikit-learn psutil requests playwright
  # setup.py fetches the browser libraries into static/vendor (scripts/vendor-assets.json)
  [ -d "$SCRATCH/src/annzarro/static/vendor/js" ] || { echo "static/vendor missing"; exit 1; }
  "$PY" -m playwright install chromium
  "$PY" -c "import annzarro, zarr, anndata; print('annzarro', annzarro.__file__, 'zarr', zarr.__version__)"
}

step_download() {
  cd "$SCRATCH/parquet"
  for f in metadata/gene_metadata.parquet; do
    [ -s "$SCRATCH/work/gene_metadata.parquet" ] || curl -sSfL --retry 8 --retry-all-errors --http1.1 -o "$SCRATCH/work/gene_metadata.parquet" \
      "https://huggingface.co/datasets/tahoebio/Tahoe-100M/resolve/main/$f"
  done
  # (re)fetch every shard that is not complete; a failed transfer leaves only a .part
  for i in $(seq 0 $((SHARDS-1))); do printf "train-%05d-of-03388.parquet\n" "$i"; done |
    xargs -P "$PAR" -n 1 bash -c 'f=$0; [ -s "$f" ] && exit 0
      curl -sSfL --retry 8 --retry-all-errors --http1.1 -o "$f.part" \
        "https://huggingface.co/datasets/tahoebio/Tahoe-100M/resolve/main/data/$f" && mv "$f.part" "$f"' || true
  ls "$SCRATCH"/parquet/*.parquet | wc -l
}

step_build() {
  B="$HERE/build_tahoe.py"
  "$PY" "$B" fit --parquet "$SCRATCH/parquet" --work "$SCRATCH/work"
  if [ ! -e "$SCRATCH/work/master_done.json" ]; then
    have=$(ls "$SCRATCH"/parquet/train-*-of-03388.parquet 2>/dev/null | wc -l)
    [ "$have" -ge "$SHARDS" ] || { echo "only $have of $SHARDS shards; rerun the download step"; exit 1; }
  fi
  "$PY" "$B" master --parquet "$SCRATCH/parquet" --work "$SCRATCH/work" --max-cells "$MAX_CELLS"
  [ "$KEEP_PARQUET" = 1 ] || rm -rf "$SCRATCH/parquet"
  for n in $(sizes); do
    st=$(store_path "$n")
    [ -d "$st" ] && continue
    mkdir -p "$(dirname "$st")"
    "$PY" "$B" store --work "$SCRATCH/work" --n "$n" --out "$st"
    "$PY" "$B" check --work "$SCRATCH/work" --store "$st"
  done
  du -sh "$SCRATCH"/stores/* "$SCRATCH/work/master.zarr" || true
}

step_http() {
  "$PY" "$HERE/bench_http.py" $(stores) --site "$SITE" --out "$SCRATCH/results/http_$SITE.csv" \
      --scratch "$SCRATCH/tmp" --port "${PORT:-8900}"
}

step_browser() {
  "$PY" "$HERE/bench_browser.py" $(stores) --site "$SITE" --out "$SCRATCH/results/browser_$SITE.csv" \
      --scratch "$SCRATCH/tmp" --port "${PORT_BROWSER:-8901}"
}

step_subset() {
  "$PY" "$HERE/bench_subset.py" $(stores) --site "$SITE" --out "$SCRATCH/results/subset_$SITE.csv" \
      --scratch "$SCRATCH/tmp" --port "${PORT_SUBSET:-8902}" --verify
}

case "${1:-all}" in
  all) step_env; step_download; step_build; step_http; step_browser; step_subset ;;
  *) "step_$1" ;;
esac
