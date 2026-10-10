#!/bin/sh
# Runner history (2026-10-04): this version ran the morning gap sessions; from 15:14 the sessions ran the slot version
# gap_run_slots.sh (odd/even-hour GUI slots); at 21:55 both were replaced by run_locked.sh (bench lock, plus a screen lock
# for visible windows). Run instructions in the repo name this file as the gap runner.
# gap_run.sh <cmd...>: run an unlocked GUI check in a gap between timed benchmark runs.
# Waits until no timed driver (tool_ceiling run.py/web_task.py/memmon.py, scale ceiling.py/heapcap.py)
# has been running for 10 s, runs the command, and logs the UTC window plus any timed driver
# that started during it to windows.log (for the overlap list in benchmark/scale/NOTES.md).
# Our own GUI sessions are serialised among themselves (a separate lock file, not the bench lock).
if [ -z "$GAP_LOCKED" ]; then GAP_LOCKED=1 exec /usr/bin/lockf -k "$HOME/annzarro_compare/.gui.lock" env GAP_LOCKED=1 "$0" "$@"; fi
cd "$(dirname "$0")"
timed() { ps -axo command | grep -E 'memmon\.py' | grep -v grep; }  # every timed tool_ceiling run executes inside memmon.py
quiet=0
# Time-share (coordinator, 2026-10-04): GUI sessions only start at minutes :00-:11 of each hour, so they end
# by :15, when ceiling-benchmarker's timed runs resume; also never while a timed run (memmon.py) is going.
inwin() { m=$(date +%M); [ "${m#0}" -lt 12 ]; }
while [ $quiet -lt 10 ]; do if [ -n "$(timed)" ] || ! inwin; then quiet=0; else quiet=$((quiet+2)); fi; sleep 2; done
start=$(date -u '+%Y-%m-%dT%H:%M:%S')
"$@" &
pid=$!
seen=""
while kill -0 $pid 2>/dev/null; do t=$(timed | head -1 | cut -c1-120); [ -n "$t" ] && seen="$t"; sleep 2; done
wait $pid; rc=$?
end=$(date -u '+%Y-%m-%dT%H:%M:%S')
echo "$start $end rc=$rc cmd=$(echo "$*" | cut -c1-80) overlapped_timed=${seen:-none}" >> windows.log
tail -1 windows.log
