#!/bin/bash
# Operator decision (2026-10-05): the desktop session does not wait for the 20M .cloupe. Once Part C is
# done (last line "done" in validation/session_notes.txt) and 10M is drawn while 20M is not built, end
# the Loupe ladder: stop the watcher (it is only waiting for the input then, holding no lock) and write
# stop. The 20M build itself keeps going (its outcome is evidence about the input path).
# Usage: loupe_end_at_10m.sh WATCHER_PID SIDECAR_PID
D=$HOME/annzarro_compare/loupe/session_v031
V=$HOME/annzarro_compare/loupe/validation/session_notes.txt
while kill -0 $1 2>/dev/null; do
  if [ "$(tail -1 $V 2>/dev/null | tr -d '[:space:]')" = "done" ] && ls $D/drawn_10000000_* >/dev/null 2>&1 \
     && [ ! -e $D/cloupe/tahoe_first20000000.cloupe.done ] && ! ls $D/next_20000000_* >/dev/null 2>&1; then
    kill $2 $1
    printf 'size=20000000\nreason=>= 10M (lower bound); 20M input not built before the session ended\nPart C is done; nothing further follows. Quit Loupe and tell the operator.\n' > $D/stop.tmp && mv $D/stop.tmp $D/stop
    echo "$(date '+%F %T %Z') size 20000000: ladder ended by the operator's decision; 20M input not built before the session ended" > $D/watcher_status.txt
    echo "ended $(date '+%T')"; exit 0
  fi
  sleep 10
done
echo "watcher exited on its own $(date '+%T')"
