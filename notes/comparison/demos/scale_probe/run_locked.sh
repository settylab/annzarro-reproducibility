#!/bin/sh
# run_locked.sh [--screen] <cmd...>: run one capture session under the bench lock (never overlaps a measurement),
# plus the screen lock for sessions with a visible window. Logs the UTC window to windows.log.
# (Replaces gap_run.sh's clock slots, per the coordinator's rule of 2026-10-04.)
cd "$(dirname "$0")"
if [ "$1" = "--screen" ]; then shift; PRE="/usr/bin/lockf -k $HOME/.annzarro-screen.lock"; TAG="bench,screen"; else PRE=""; TAG="bench"; fi
exec $PRE /usr/bin/lockf -k "$HOME/.annzarro-bench.lock" sh -c '
  start=$(date -u "+%Y-%m-%dT%H:%M:%S"); "$@"; rc=$?
  echo "$start $(date -u "+%Y-%m-%dT%H:%M:%S") rc=$rc cmd=$(echo "$*" | cut -c1-80) locks='"$TAG"'" >> windows.log; exit $rc' _ "$@"
