# evidence/: the record behind the paper's claims

Status: in use. Built from `main` and hosted as the evidence site for the paper; this repository carries the sources, the data the site reads and all benchmark code.

Source for a static site (MkDocs Material, offline-capable) that links every mark of
Fig. 1c, every benchmark number and every figure to its evidence. Everything a page shows
is generated from files in this repository; the generated Markdown and site live in
`_build/` and are not committed.

| path | what |
|---|---|
| `matrix/columns.yaml` | Fig. 1c columns in figure order: id, group, label, definition, status |
| `matrix/tools/<tool>.yaml` | one tool's marks and their evidence (schema below) |
| `pages/` | hand-written pages and site assets |
| `build.py` | YAML + notes + benchmark CSVs -> `_build/docs`; `--site` runs mkdocs; `--check` compares the YAML with `figures/fig_comparison.py` |
| `tools/import_notes.py` | one-shot seed of the YAML from `notes/comparison/` and the figure |

## Build

```sh
uv venv evidence/.venv && uv pip install -p evidence/.venv -r evidence/requirements.txt
evidence/.venv/bin/python evidence/build.py --site
open evidence/_build/site/index.html     # works from file://; or mkdocs serve -f evidence/_build/mkdocs.yml
```

MkDocs is pinned below 2.0 (2.0 drops the plugin system Material relies on). The content
is plain Markdown plus our generator, so a later move to Zensical or a plain generator
touches only `mkdocs.yml`.

## Visual proof: screenshot sidecars

Every mark needs an annotated screenshot. N marks too: the menu or list where the feature
would be, shown without it. Annotations are never drawn by hand. A YAML sidecar next to the
raw shot (`<stem>.annot.yaml`) holds the boxes, arrows, numbered callouts, the caption and
which tool/column/mark it proves; `tools/annotate.py` renders it, and the build renders all
sidecars into the site. Raw shots are never modified. Format: the docstring of
`tools/annotate.py`. Driver scripts call `annotate.record(page, shot, ...)` right after the
screenshot so boxes come from element bounding boxes (`source: dom`); `source: manual` is
for shots taken before sidecars existed. Examples: `annotations/isee/` (one N, one Y).

What counts as visual proof, per column type (published on the site's Columns page; source
`matrix/columns.yaml` `visual_proof_rules`): the running app for GUI columns, with the menu
where a feature would be for an N; documentation screenshots or a terminal shot of a static
build for desktop/hosted/static; an annotated Network panel or request log for lazy/remote;
documentation screenshots marked "docs, not the app" for Loupe. One sidecar per image:
`build.py --check` fails on two (a manual one left beside a DOM re-shoot) and on a manual
sidecar whose image changed since its boxes were drawn (`image_sha256`).

The build's [coverage page](_build/site/coverage.html) lists every mark lacking visual
proof or any reference, and reference-quality warnings (docs without a checked date or an
archive.org snapshot, papers without a section or figure, code without line ranges).

## Tool file schema

```yaml
id: isee                       # file name and page slug
name: iSEE
figure:                        # null if the tool is not a row of Fig. 1c
  row: 5
  label: iSEE                  # exactly the row name in fig_comparison.py TOOLS
  largest_documented: 68.6k    # the figure's size column
notes: notes/comparison/isee.md
cells:
  <column id>:                 # ids from columns.yaml
    mark: P                    # what the figure draws (absent for non-figure tools)
    proposed: N                # audit proposal awaiting a decision (absent if none)
    reason: one sentence, shown on hover in the matrix
    detail: full evidence text, Markdown
    evidence:                  # REQUIRED: visual proof and at least one reference
      - {kind: code, repo: iSEE/iSEE, commit: <40-hex>, path: R/constants.R, lines: 26-31, url: <permalink>}
      - {kind: docs, url: ..., label: what it shows, checked: 2026-10-04, archive: <web.archive.org snapshot>}
      - {kind: paper, url: https://doi.org/..., label: ..., where: section or figure, checked: ..., archive: ...}
      - {kind: screenshot | script | note, path: <repo path>[#anchor]}   # raw shot; counts as "raw", not proof
    na:                        # only where a kind cannot exist, with the reason
      paper: Loupe Browser has no paper
    reproduce: [notes/comparison/demos/isee/focus_check_cell.py]
    checked: {date: 2026-10-03, by: comparison-auditor, how: running app | source and docs | live demo}
proposed_columns:              # candidate columns not yet in the figure
  selection: {proposed: Y, reason: ..., evidence: [...], checked: {...}}
```
