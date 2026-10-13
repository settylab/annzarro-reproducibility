#!/bin/bash
# One scSVA run (HPC probe): start the app under memmon_linux.py, drive it in headless Chromium.
#   sbatch [--mem=16G] run_job.sh LABEL INPUTDIR GENE [shots]
set -uo pipefail
A=$SCRATCH/annzarro-scale; S=$A/scsva
LABEL=${1:?}; IN=${2:?}; GENE=${3:?}; SHOTS=${4:-}
J=${SLURM_JOB_ID:-local}; R=$S/runs/${LABEL}_${J}; mkdir -p $R
exec > $R/job.log 2>&1
echo "=== $LABEL start $(date -Is) host=$(hostname) job=$J mem=${SLURM_MEM_PER_NODE:-?}M input=$IN gene=$GENE"
lscpu | grep -E 'Model name|^CPU\(s\)'; free -g | head -2
source /app/lmod/lmod/init/bash; module load R/3.6.2-foss-2019b-fh1; 
export R_LIBS_USER=$S/rlib PATH=$S/pyenv/bin:$PATH RETICULATE_PYTHON=$S/pyenv/bin/python
PORT=$($A/hpcbench/venv/bin/python -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')
CAP=$(( ${SLURM_MEM_PER_NODE:-16384} / 1024 - 1 ))
# the app writes its tempdir under TMPDIR; keep it node-local
export TMPDIR=$LOCAL_SCRATCH/$J; mkdir -p $TMPDIR 2>/dev/null || export TMPDIR=$R/tmp; mkdir -p $TMPDIR
$A/hpcbench/venv/bin/python $A/competitors/memmon_linux.py --out $R/run.json --cap-gb $CAP --interval 0.5 \
   --live $R/live.tsv --stop-file $R/STOP --timeout 5400 -- \
   Rscript $S/run/launch.R $PORT &
MPID=$!
for i in $(seq 1 600); do curl -s -o /dev/null -m 5 http://127.0.0.1:$PORT/ && break; kill -0 $MPID 2>/dev/null || break; sleep 2; done
echo "app up after ~$((i*2))s on port $PORT"
# Playwright 1.25 / Chromium 105: the last line that runs on these glibc-2.27 nodes (container exec is refused here)
PLAYWRIGHT_BROWSERS_PATH=$S/ms-playwright timeout 80m $S/pwvenv/bin/python -I $S/run/drive.py http://127.0.0.1:$PORT/ $IN $R $GENE ${SHOTS:+--shots}
echo "drive rc=$?"
touch $R/STOP; wait $MPID; echo "memmon rc=$?"
cat $R/run.json
echo "=== end $(date -Is)"
