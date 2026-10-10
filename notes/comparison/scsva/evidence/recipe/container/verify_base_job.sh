#!/bin/bash
# Unprivileged checks of the Dockerfile's layers (a full fakeroot build is refused by this sandbox):
#   1) base image digest pulls; OS release; R version; default CRAN repo
#   2) apt step: apt-sources.sh fallback logic + `apt-get -s install` simulation of the package list
set -uo pipefail
A=$SCRATCH/annzarro-scale; D=$A/scsva/recipe/container
source /app/lmod/lmod/init/bash; module load Apptainer/1.1.6
export APPTAINER_CACHEDIR=$A/sifcache APPTAINER_TMPDIR=$A/siftmp
SB=$A/scsva/rocker363_sandbox
[ -d $SB ] || apptainer build --sandbox $SB docker://rocker/r-ver@sha256:9414f76c5f91f24617b5275b8fe4f4ff1313b3b10698a525cac0063c01f2ca6d
W=$A/scsva/aptsim; rm -rf $W; mkdir -p $W/lists/partial $W/cache/archives/partial
apptainer exec --bind $W:/aptsim $SB bash -c '
  head -3 /etc/os-release; R --version | head -1; Rscript -e "print(getOption(\"repos\"))"
  O="-o Dir::State::Lists=/aptsim/lists -o Dir::Cache=/aptsim/cache -o Debug::NoLocking=1 -o Dir::State::status=/var/lib/dpkg/status"
  echo "--- apt-get update with the image sources"; apt-get $O update; echo "rc=$?"
  cat /etc/apt/sources.list /etc/apt/sources.list.d/* 2>/dev/null
' 2>&1
echo "--- archive fallback simulation"
. $SB/etc/os-release
cat > $W/archive.list <<L
deb http://archive.debian.org/debian $VERSION_CODENAME main
deb http://archive.debian.org/debian-security $VERSION_CODENAME/updates main
L
apptainer exec --bind $W:/aptsim $SB bash -c '
  O="-o Dir::State::Lists=/aptsim/lists -o Dir::Cache=/aptsim/cache -o Debug::NoLocking=1 -o Dir::Etc::SourceList=/aptsim/archive.list -o Dir::Etc::SourceParts=/nonexistent -o Acquire::Check-Valid-Until=false"
  apt-get $O update; echo "update rc=$?"
  apt-get $O -s install --no-install-recommends ca-certificates curl bzip2 git libcairo2-dev libxt-dev libmagick++-dev libcurl4-openssl-dev libssl-dev libxml2-dev libz-dev fonts-dejavu-core fontconfig | tail -5; echo "simulate rc=${PIPESTATUS[0]}"
' 2>&1
