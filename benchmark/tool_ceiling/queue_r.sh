#!/bin/bash
# iSEE and ShinyCell up the N ladder. Inputs: the SingleCellExperiment .rds
# (to_sce.R) and the ShinyCell app (shinycell_build.R), each a measured
# conversion run (2 h limit). Stops a tool at its first non-ok step.
cd "$(dirname "$0")"
D=$DATA_ROOT/tool_ceiling_data
RT=$DEMO_ROOT/_mamba/envs/rtools/bin/Rscript
PY=.venv/bin/python
LADDER="${LADDER:-1000000 2000000 5000000 10000000 20000000 50000000 95624334}"
mkdir -p $D/sce $D/shinycell
h5ad() { local f=$D/h5ad/tahoe_first$1.h5ad; until [ -f $f ]; do sleep 60; done; echo $f; }
last_ok() { tail -1 results.csv | cut -d, -f8 | grep -qx ok; }
conv() { local t=$1 v=$2 n=$3; shift 3; $PY run.py --tool $t --variant $v --phase convert --n $n --timeout 7200 -- "$@"; }
sce() {  # builds the .rds once; charged to the tool that needs it first
  local f=$D/sce/first$2.rds
  [ -f $f ] || conv $1 to_sce $2 $RT to_sce.R $(h5ad $2) $f
  [ -f $f ]
}
for tool in ${TOOLS:-isee shinycell}; do
  for n in $LADDER; do
    sce $tool $n || break
    if [ $tool = isee ]; then
      $PY run.py --web --tool isee --variant default --n $n -- $PY web_task.py isee default $D/sce/first$n.rds {out} --n $n --port 8935
    else
      app=$D/shinycell/first$n
      if [ ! -f $app/sc1meta.rds ]; then
        conv shinycell makeShinyApp $n $RT shinycell_build.R $D/sce/first$n.rds $app
        last_ok || break
      fi
      $PY run.py --web --tool shinycell --variant default --n $n -- $PY web_task.py shinycell default $app {out} --n $n --port 8936
    fi
    last_ok || break
  done
done
