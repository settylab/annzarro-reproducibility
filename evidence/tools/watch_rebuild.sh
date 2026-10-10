#!/bin/sh
# Rebuild the served evidence site whenever a commit touches what it shows.
#
#   EVIDENCE_PY=<python with mkdocs-material (evidence/requirements.txt)> evidence/tools/watch_rebuild.sh [poll_s]
#
# Every poll_s seconds (default 60) it compares HEAD with the last commit it built. If the
# commits in between touch the matrix, the figure, the figure's data or the evidence files,
# it runs build.py --site under the bench lock (the build is heavy) and then build.py --check,
# which fails when the served matrix differs from Fig. 1c. One line per event goes to
# evidence/_build/watch.log. Stop it with kill; it holds no lock between builds.
REPO=$(cd "$(dirname "$0")/../.." && pwd)
PY=${EVIDENCE_PY:?set EVIDENCE_PY to a python with mkdocs-material}
POLL=${1:-60}
LOG=$REPO/evidence/_build/watch.log
PATHS="evidence figures/fig_comparison.py figures/style.py benchmark/tool_ceiling benchmark/scale/results benchmark/hpc/results notes/comparison manuscript/sections/figs_results.tex manuscript/body.tex manuscript/main.tex"
cd "$REPO" || exit 1
built=$(sed -n 's/.*fig1c-built \([0-9a-f]*\).*/\1/p' "$LOG" 2>/dev/null | tail -1)
[ -n "$built" ] || built=none
while :; do
    head=$(git rev-parse HEAD)
    if [ "$head" != "$built" ]; then
        if [ "$built" = none ] || ! git cat-file -e "$built" 2>/dev/null || [ -n "$(git diff --name-only "$built" "$head" -- $PATHS | grep -v '^evidence/_build/' | head -1)" ]; then
            echo "$(date '+%F %T') rebuild for $(git log -1 --format=%h "$head")" >> "$LOG"
            /usr/bin/lockf -k "$HOME/.annzarro-bench.lock" "$PY" evidence/build.py --site >> "$LOG.build" 2>&1
            rc=$?
            .venv/bin/python evidence/build.py --check >> "$LOG.build" 2>&1
            ck=$?
            echo "$(date '+%F %T') fig1c-built $head site rc=$rc check rc=$ck" >> "$LOG"
        else
            echo "$(date '+%F %T') fig1c-built $head (no relevant change)" >> "$LOG"
        fi
        built=$head
    fi
    sleep "$POLL"
done
