# Hosting the evidence site

The site is built from a clone of this repository alone: no network, no local paths, no
benchmark or capture tools. Everything it shows (matrix, evidence, screenshots, benchmark
results, figures) is committed.

## Build from a fresh clone

Requirements: Linux or macOS, Python 3.11 (3.12 also works), `git`, `rsync`. A full clone
(not `--depth 1`): the provenance badges read `git log`.

```sh
git clone https://github.com/settylab/annzarro-reproducibility.git
cd annzarro-reproducibility
python3.11 -m venv .venv-site
.venv-site/bin/pip install -r evidence/requirements.txt
.venv-site/bin/python evidence/build.py --site
```

Outputs, inside the clone:

| path | what |
|---|---|
| `evidence/_build/site/` | the static site; serve this directory (any static server, e.g. `python -m http.server -d evidence/_build/site`) |
| `evidence/_build/docs/` | the generated Markdown it was built from |

The site is relative-linked throughout (`use_directory_urls: false`), so it works under any
sub-path and from `file://`. A rebuild replaces both directories in place (rsync), so a server
started inside `_build/site` keeps serving and picks up the new build at once.

The host builds with Python 3.11, so the build scripts must not use 3.12-only syntax (for example a
quote reused inside an f-string expression, PEP 701). `build.py --check` runs
`evidence/tools/py311check.py` over the build scripts: a tokenizer scan for that pattern on 3.12+, and a
parse with a Python 3.11 interpreter when one is found (`python3.11`, or `uv python find 3.11`).

Do not create a `.venv` in the clone root: on the authors' laptop that is the figures' own
environment, and the build would use it to draw Fig. 1c. On a fresh clone the build draws the
figure with its own interpreter (override with `EVIDENCE_FIG_PYTHON`).

## Smoke check after a build

```sh
.venv-site/bin/python evidence/tools/site_smoke.py --expect 63
```

It checks, offline:

1. every generated page has its HTML page, and at least the expected number of HTML pages
   (`--expect`, the number below; more only prints a note);
2. every page has a rendered body;
3. `build.py --check`: the evidence YAML's marks are the marks Fig. 1c draws; the column
   labels and groups, row order and documented sizes are the figure's; and the built matrix
   page is the figure's (a hash of the drawn figure, every legend string, the scale header,
   every strip description and documented size);
4. no broken local link (`evidence/tools/linkcheck.py`, local files only).

Exit status 0 when all pass.

Expected page count: **63** HTML pages (29 site pages, two of them redirects from moved URLs, and 34 rendered copies
of repository Markdown files; the SCope record, now benchmark/tool_ceiling/measured/scope (not_measured/scope until 2026-10-08),
became a page with e0f41ea). The smoke fails on fewer pages and only notes more (a newly linked note
becomes a page), so adding a page never blocks a deploy. The count changes when pages are added; update it here in the same
commit. The site shows committed files only (`build.py` copies and links git-tracked files), so a
clean clone and a working tree build the same pages.


## Rebuild when `main` changes

Rebuild whenever `main` moves. A commit can change the figure, its data, the evidence files or
the benchmark results, and the site must follow all of them; when in doubt, rebuild on every new
commit (a build takes about two minutes):

```sh
git fetch origin && git reset --hard origin/main
.venv-site/bin/python evidence/build.py --site && .venv-site/bin/python evidence/tools/site_smoke.py
```

`build.py --check` fails while the built matrix differs from the figure, so a failed smoke
check after a rebuild means the site does not show the paper's current Fig. 1c (or a build step
failed): report it with the smoke check's output.

On the authors' laptop, `evidence/tools/watch_rebuild.sh` does the same for local commits.
