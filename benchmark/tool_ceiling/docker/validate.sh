#!/bin/bash
# Run one task under a hard memory limit in Docker (linux/arm64 VM), e.g.
#   validate.sh scanpy 16g default /data/tahoe_first5000000.h5ad
#   validate.sh seurat 16g default /data/tahoe_first5000000.h5ad
# /data is ~/tool_ceiling_data/h5ad (read-only). Docker Desktop's VM must have
# more memory than the limit. Appends one line to ../validation.csv.
set -u
cd "$(dirname "$0")"
tool=$1 lim=$2 var=$3 in=$4
D=/usr/local/bin/docker
img=tool-ceiling-$tool
cp ../${tool}_task.* . 2>/dev/null
/usr/bin/lockf -k $HOME/.annzarro-bench.lock $D build -q -t $img -f Dockerfile.$tool . >/dev/null
name=tc_${tool}_$$
t0=$(date +%s)
/usr/bin/lockf -k $HOME/.annzarro-bench.lock $D run --name $name --memory=$lim --memory-swap=$lim \
  -v $DATA_ROOT/tool_ceiling_data/h5ad:/data:ro -v /tmp:/out $img $var $in /out/$name > ../raw/validate_$name.log 2>&1
rc=$?
oom=$($D inspect -f '{{.State.OOMKilled}}' $name)
$D rm $name >/dev/null
echo "$(date +%FT%T),$tool,$var,$in,$lim,$rc,$oom,$(( $(date +%s) - t0 ))" >> ../validation.csv
echo "rc=$rc oom=$oom"
