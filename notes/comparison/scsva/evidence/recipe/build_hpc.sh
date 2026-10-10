#!/bin/bash
# scSVA HPC build: Lmod R 3.6.2 (fh1) + private R lib + micromamba Python 3.6 / vaex-core 2.0.3
set -euo pipefail
S=$SCRATCH/annzarro-scale/scsva
source /app/lmod/lmod/init/bash
module load R/3.6.2-foss-2019b-fh1
module list 2>&1
export R_LIBS_USER=$S/rlib
# CRAN snapshot dated to the R 3.6 era (Posit Package Manager, frozen 2020-04-20)
SNAP=https://packagemanager.posit.co/cran/2020-04-20
[ -d $S/rlib/googleComputeEngineR ] || Rscript -e "install.packages(c('colorRamps','tableHTML','shinyjqui','shinyAce','googleComputeEngineR'), lib='$S/rlib', repos='$SNAP', Ncpus=2)"
Rscript -e ".libPaths(c('$S/rlib',.libPaths())); ip<-installed.packages(); print(ip[c('colorRamps','tableHTML','shinyjqui','shinyAce','googleComputeEngineR'),c('Version','LibPath')])"
# Python side
export MAMBA_ROOT_PREFIX=$S/mamba CONDA_PKGS_DIRS=$S/mamba/pkgs
rm -rf $S/pyenv; $HOME/.linuxbrew/bin/micromamba create -y -p $S/pyenv -f $S/recipe/scsva-py.yml
$S/pyenv/bin/python -I -c "import vaex, numpy, OpenGL, sys; print('python', sys.version.split()[0], 'vaex', vaex.__version__, 'numpy', numpy.__version__)"
$HOME/.linuxbrew/bin/micromamba env export -p $S/pyenv --explicit > $S/recipe/scsva-py.linux-64.explicit.txt
# scSVA itself from the pinned commit (no network install; local clone)
R CMD INSTALL --library=$S/rlib $S/src/scSVA
Rscript -e ".libPaths(c('$S/rlib',.libPaths())); library(scSVA); cat('scSVA', as.character(packageVersion('scSVA')), '\n')"
Rscript -e ".libPaths(c('$S/rlib',.libPaths())); writeLines(capture.output(sessionInfo()), '$S/recipe/R_sessionInfo_build.txt'); ip<-installed.packages(); write.csv(ip[,c('Package','Version','LibPath')], '$S/recipe/R_installed_packages.csv', row.names=FALSE)"
echo BUILD_OK
