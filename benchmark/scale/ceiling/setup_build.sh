#!/bin/bash
# A clean, benchmarkable AnnZarro build: a detached worktree at REV with verified vendor assets and its
# own venv (editable install). Prints the annzarro executable. Usage: setup_build.sh REV NAME
set -e
# one caller at a time (scale-benchmarker and ceiling-benchmarker share builds): concurrent calls wait, then reuse
[ -n "$SETUP_BUILD_LOCKED" ] || SETUP_BUILD_LOCKED=1 exec /usr/bin/lockf -k $HOME/.annzarro-setup-build.lock "$0" "$@"
REV=${1:?REV}; NAME=${2:?NAME}
REPO=$ANNZARRO_SRC
W=$REPO/$ANNZARRO_SRC
git -C $REPO fetch -q github --tags
[ -d $W ] || git -C $REPO worktree add -q --detach $W $REV
[ "$(git -C $W rev-parse HEAD)" = "$(git -C $REPO rev-parse $REV^{commit})" ] || { echo "worktree $W is not at $REV" >&2; exit 1; }
cd $W
python3 scripts/vendor_assets.py >/dev/null
python3 scripts/vendor_assets.py --check >&2
[ -x .venv-bench/bin/annzarro ] || { uv venv -q --python 3.13 .venv-bench && VIRTUAL_ENV=$W/.venv-bench nice -n 19 uv pip install -q -e . ; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "worktree $W is dirty" >&2; exit 1; }
echo $W/.venv-bench/bin/annzarro
