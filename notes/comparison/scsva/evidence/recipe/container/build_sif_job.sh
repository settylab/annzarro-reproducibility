#!/bin/bash
set -uo pipefail
D=$SCRATCH/annzarro-scale/scsva/recipe/container
A=$SCRATCH/annzarro-scale
source /app/lmod/lmod/init/bash; module load Apptainer/1.1.6
export APPTAINER_CACHEDIR=$A/sifcache
export APPTAINER_TMPDIR=$LOCAL_SCRATCH/${SLURM_JOB_ID}; mkdir -p $APPTAINER_TMPDIR 2>/dev/null || export APPTAINER_TMPDIR=$A/siftmp
hostname; apptainer --version; date -Is
cd $D
apptainer build --fakeroot --force $A/scsva/scsva_c9e8fd6.sif scsva.def; rc=$?
echo "build rc=$rc"; date -Is
[ $rc -eq 0 ] && apptainer exec $A/scsva/scsva_c9e8fd6.sif bash -c 'cat /etc/os-release | head -2; R --version | head -1; python -c "import vaex,sys;print(sys.version.split()[0], vaex.__version__)"; Rscript -e "library(scSVA);cat(as.character(packageVersion(\"scSVA\")),\"\n\")"; cat /opt/R_packages.csv' > $D/sif_inventory.txt 2>&1
sha256sum $A/scsva/scsva_c9e8fd6.sif 2>/dev/null
exit $rc
