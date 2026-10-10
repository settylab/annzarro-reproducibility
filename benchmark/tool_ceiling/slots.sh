#!/bin/bash
# Time-share with comparison-auditor's GUI sessions: PAUSE_SLOT from :00 to :15 of
# every hour (GUI only), clear from :15 to :60 (tool_ceiling runs). Also keeps
# PAUSE_LOW (only the remote AnnZarro ladder may run) while queue_remote.sh runs.
# Stops when tool_ceiling_data/SLOTS_STOP exists. Log: logs/pause_windows.log.
D=$DATA_ROOT/tool_ceiling_data
L=benchmark/tool_ceiling/logs/pause_windows.log
log() { echo "$(date -u +%FT%TZ) $*" >> $L; }
first=1
while [ ! -f $D/SLOTS_STOP ]; do
  m=$((10#$(date +%M)))
  if [ $m -lt 15 ]; then
    [ -e $D/PAUSE_SLOT ] || { touch $D/PAUSE_SLOT; log "slot pause on (GUI :00-:15)"; }
  else
    [ -e $D/PAUSE_SLOT ] && { rm -f $D/PAUSE_SLOT; log "slot pause off"; }
    if [ $first = 1 ] && [ -e $D/PAUSE ]; then rm -f $D/PAUSE; log "manual pause lifted (time-share starts)"; fi
    first=0
  fi
  if pgrep -f queue_remote.sh >/dev/null; then
    [ -e $D/PAUSE_LOW ] || { touch $D/PAUSE_LOW; log "low-priority pause on (remote ladder first)"; }
  else
    [ -e $D/PAUSE_LOW ] && { rm -f $D/PAUSE_LOW; log "low-priority pause off"; }
  fi
  sleep 20
done
rm -f $D/PAUSE_SLOT $D/PAUSE_LOW; log "slots stopped"
