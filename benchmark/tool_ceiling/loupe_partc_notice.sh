#!/bin/bash
# Sidecar to the running Loupe watcher (left untouched). It keeps the Part C notice on the
# watcher's status file, and while the watcher waits for an input build it adds an explicit
# "waiting for <N> .cloupe build (Part C may run now)" line, so the desktop session can tell that
# state from "locks held; next_<N>_<k> written". It adds the hand-over line to stop, then exits.
D=$HOME/annzarro_compare/loupe/session_v031
F=$D/watcher_status.txt
NOTE="Part C (next_validation) may run while the watcher waits for a build; otherwise after stop."
while true; do
  if [ -e "$F" ]; then
    first=$(head -1 "$F")
    want=""
    case "$first" in
      *"input file is still being built"*)
        n=$(echo "$first" | sed -E 's/.*size ([0-9]+):.*/\1/')
        want="waiting for $n .cloupe build (Part C may run now)" ;;
    esac
    if { [ -n "$want" ] && [ "$(tail -1 "$F")" != "$want" ]; } || ! grep -qF "$NOTE" "$F"; then
      { echo "$first"; grep -v -e "^$" "$F" | sed 1d | grep -vF -e "Part C" -e "next_validation file will appear"; echo "$NOTE"; [ -n "$want" ] && echo "$want"; true; } > "$F.side" && mv "$F.side" "$F"   # the waiting line last: the Part C prompt reads the last line
    fi
  fi
  if [ -e "$D/stop" ]; then
    grep -qF "next: Part C" "$D/stop" || echo "next: Part C, see next_validation" >> "$D/stop"
    exit 0
  fi
  sleep 1
done
