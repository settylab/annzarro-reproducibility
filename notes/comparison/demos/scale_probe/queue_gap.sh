#!/bin/sh
cd "$(dirname "$0")"
for r in 1 2 3; do ./gap_run.sh .venv/bin/python probe_web.py ucsc_pansci "https://cells.ucsc.edu/?ds=mouse-pansci+all" --site ucsc --expect 21786931 --reps 1 --timeout 600 >> run_ucsc.log 2>&1; done
for r in 1 2 3; do ./gap_run.sh .venv/bin/python probe_web.py cxg_mouse_embryo_11M "https://cellxgene.cziscience.com/e/dcfd4feb-18a3-4b30-81d7-1b0c544a8ab3.cxg/" --site cxg --expect 11441407 --reps 1 --timeout 600 >> run_cxg.log 2>&1; done
echo queue done
