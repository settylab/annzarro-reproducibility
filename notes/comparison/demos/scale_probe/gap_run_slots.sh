#!/bin/sh
# The out-of-repo copy of this runner as it stood from 2026-10-04 15:14 until run_locked.sh replaced it (21:55):
# the odd/even-hour slot version used by the afternoon gap sessions. Kept as the record of what ran.
# gap_run.sh <cmd...>: run one GUI session (browser/server) in the shared GUI time-share.
# Schedule (agreed with the evidence curator, 2026-10-04): GUI sessions start only at minutes :00-:11, in
# ODD local hours (13:00, 15:00, ...); the evidence curator takes even hours. Waiting happens WITHOUT the
# lock; the .gui.lock is taken only at slot start (60 s timeout, else skip to the next slot), and never
# while a timed tool_ceiling run (memmon.py) is going. Each window is logged to windows.log (UTC).
cd "$(dirname "$0")"
timed() { ps -axo command | grep -E 'memmon\.py' | grep -v grep; }
inwin() { m=$(date +%M); h=$(date +%H); [ "${m#0}" -lt 12 ] && [ $(( ${h#0} % 2 )) -eq ${GAP_PARITY:-1} ]; }  # GAP_PARITY=0 for even hours (evidence curator)
if [ -z "$GAP_LOCKED" ]; then
  while true; do
    while ! inwin || [ -n "$(timed)" ]; do sleep 5; done
    # wait for the lock at most until :11 of this slot, so several queued sessions can share one slot
    rem=$(( (11 - ${m:-0}) * 60 )); m=$(date +%M); m=${m#0}; rem=$(( (11 - m) * 60 )); [ $rem -lt 30 ] && rem=30
    GAP_LOCKED=1 /usr/bin/lockf -t $rem "$HOME/annzarro_compare/.gui.lock" env GAP_LOCKED=1 "$0" "$@" && exit 0
    rc=$?; [ $rc -ne 75 ] && exit $rc   # 75 = lock timeout: skip to the next slot
    sleep 720
  done
fi
inwin || { echo "slot closed before start" >&2; exit 75; }
start=$(date -u '+%Y-%m-%dT%H:%M:%S')
"$@" &
pid=$!
seen=""
while kill -0 $pid 2>/dev/null; do t=$(timed | head -1 | cut -c1-120); [ -n "$t" ] && seen="$t"; sleep 2; done
wait $pid; rc=$?
end=$(date -u '+%Y-%m-%dT%H:%M:%S')
echo "$start $end rc=$rc cmd=$(echo "$*" | cut -c1-80) overlapped_timed=${seen:-none}" >> windows.log
tail -1 windows.log
exit $rc
