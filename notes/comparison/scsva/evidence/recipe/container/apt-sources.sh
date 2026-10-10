#!/bin/bash
# rocker/r-ver:3.6.3 is Debian; if its release has moved to archive.debian.org, point apt there.
set -e
. /etc/os-release
if ! apt-get update >/dev/null 2>&1; then
  echo "apt-get update failed for $VERSION_CODENAME; switching to archive.debian.org"
  echo "deb http://archive.debian.org/debian $VERSION_CODENAME main" > /etc/apt/sources.list
  echo "deb http://archive.debian.org/debian-security $VERSION_CODENAME/updates main" >> /etc/apt/sources.list
  rm -f /etc/apt/sources.list.d/*
  echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99archive
fi
