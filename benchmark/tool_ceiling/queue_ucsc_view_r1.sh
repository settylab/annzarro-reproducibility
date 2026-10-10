#!/bin/bash
# UCSC 5M viewer again (r1): r0 overlapped a user session (memory-unclean). The site
# itself (html_5000000) is the r0 build's output, which does not depend on timing.
cd "$(dirname "$0")"
D=$DATA_ROOT/tool_ceiling_data PY=.venv/bin/python
$PY run.py --web --tool ucsc --variant default --n 5000000 --run 1 -- $PY web_task.py ucsc default $D/ucsc/html_5000000 {out} --n 5000000 --port 8941
