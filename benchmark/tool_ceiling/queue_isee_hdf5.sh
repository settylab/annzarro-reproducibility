#!/bin/bash
# iSEE 7b (HDF5-backed SCE) up the ladder on the laptop. The SCE .rds is built
# beforehand (to_sce_hdf5.R; not measured: input rule). Stops at the first failure
# or when the server passes the 32 GiB budget.
cd "$(dirname "$0")"
PY=.venv/bin/python RC=$ENVS_ROOT/rceiling/bin/Rscript D=$DATA_ROOT/tool_ceiling_data L="/usr/bin/lockf -k $HOME/.annzarro-bench.lock"
mkdir -p $D/sce_h5
for n in 1000000 2000000 5000000 10000000 20000000 50000000 95624334; do
  f=$D/h5ad/tahoe_first$n.h5ad rds=$D/sce_h5/first$n.rds
  [ -f $f ] || { echo "no h5ad $n"; break; }
  [ -f $rds ] || $L $RC to_sce_hdf5.R $f $rds > logs/sce_h5_$n.log 2>&1 || { echo "build failed $n"; break; }
  $PY run.py --web --tool isee --variant hdf5 --n $n -- $PY web_task.py isee hdf5 $rds {out} --n $n --port 8948
  row=$(grep "^isee_hdf5_run_${n}_r0," results.csv | tail -1)
  st=$(echo "$row" | cut -d, -f8); srv=$(echo "$row" | cut -d, -f16)
  echo "$n $st server=$srv"
  [ "$st" = ok ] || break
  python3 -c "import sys; sys.exit(0 if float('${srv:-0}') <= 32 else 1)" || break
done
