#!/bin/sh
# Cirrocumulus remote-store check: `cirro launch` on public anonymous AnnData zarr stores
# (S3 via s3fs, HTTPS, GCS), then the schema through its API. v2: results dir kept local (--results),
# because by default cirro creates "results/" next to the dataset, which needs write access to the bucket.
DEMO_ROOT="${DEMO_ROOT:-$HOME/annzarro_compare}"  # local demos, apps and data
export AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_CONFIG_FILE=/dev/null  # no user credentials: anonymous access only
C=$DEMO_ROOT/cirrocumulus/.venv/bin
for url in s3://lamindata/.lamindb/CFcQxNjzSRzWZrVh.anndata.zarr https://lamindata.s3.amazonaws.com/.lamindb/CFcQxNjzSRzWZrVh.anndata.zarr gs://vitessce-demo-data/habib-2017/habib17.processed.h5ad.zarr; do
  echo "== $url"
  $C/cirro launch --host 127.0.0.1 --port 8901 --no-open --results $TMPDIR/cirro_results "$url" > $TMPDIR/cirro_remote.log 2>&1 &
  pid=$!; ok=""
  for i in $(seq 1 45); do curl -s -m 5 -o /dev/null http://127.0.0.1:8901/api/datasets && { ok=1; break; }; sleep 2; done
  if [ -n "$ok" ]; then
    id=$(curl -s http://127.0.0.1:8901/api/datasets | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
    curl -s -m 120 "http://127.0.0.1:8901/api/schema?id=$id" | python3 -c "import sys,json;d=json.load(sys.stdin);print('schema: shape',d.get('shape'),'embeddings',[e.get('name') for e in d.get('embeddings',[])][:4],'n_var',len(d.get('var',[])))" 2>&1 | tail -1
  else echo "server did not answer"; fi
  grep -iE "error|exception|credential" $TMPDIR/cirro_remote.log | head -3 | cut -c1-200
  kill $pid 2>/dev/null; wait $pid 2>/dev/null
done
