# Evidence behind the AnnZarro paper

!!! note "How this record was made"
    This record was collected with AI assistance: AI coding agents (Claude, Anthropic), working
    under the authors' direction, took the screenshots, wrote the annotations, ran the benchmarks
    and drafted the notes and references. The authors reviewed the material to make sure that
    every central claim of the paper is substantiated. If you find an issue or an error, please
    contact the authors: Dominik J. Otto ([dotto@fredhutch.org](mailto:dotto@fredhutch.org)) and
    Manu Setty ([msetty@fredhutch.org](mailto:msetty@fredhutch.org)).
    [More on how this record was made](#how-this-record-was-made).

This site holds the record behind every comparative and quantitative statement in the
AnnZarro paper: each mark of the feature matrix ([[fig:overview]]c) with its sources, each benchmark
with its method, environment and raw rows, and each figure with the script and data that
made it.

**Cite.** Otto, D. J., Baasri, S. and Setty, M. *AnnZarro: scalable, interactive exploration of cell-by-cell and
gene-by-gene relationships in single-cell data.* bioRxiv (2026),
[doi:10.64898/2026.10.10.758158](https://doi.org/10.64898/2026.10.10.758158).

It is built from files in this repository and nothing else. Every page names the files and
commits it was built from, and flags any input with uncommitted changes.

| Section | What it answers |
|---|---|
| [Feature matrix](matrix.md) | Why does a tool get Y, P or N in a column? Where is the code, the documentation or the screenshot? How do I check it myself? |
| [Columns](columns.md) | What exactly does each column score? |
| [Tool ceiling](measurements/tool-ceiling.md) | How many cells does each tool draw within 8, 16 and 32 GB of client memory? |

## How to read a matrix mark

- **Y** documented and working in the GUI; **P** partial, or reachable only by writing code;
  **N** searched in docs and source, not found (not a proof of absence); **?** not verified.
- Every mark records who checked it, when and how (source and docs, a live demo, or the
  running application).
- Code is cited as permalinks at pinned commits, so the evidence does not move when the
  projects do.

## How this record was made

The material on this site (screenshots of every tool, their annotations, the benchmark runs,
the notes and the references) was collected with AI coding agents (Claude, Anthropic) working
under the authors' direction, as stated in the manuscript's "Use of AI assistance" section. The
agents worked in roles (coordinator, comparison auditor, evidence curator, manuscript writer,
benchmark runners); notes and annotations name the role, not the individual agent. The authors
reviewed the material to make sure that every central claim of the paper is substantiated. Every
screenshot annotation, number and reference on this site can be checked against the files and
commits it names. If you find an issue or an error, please contact the authors: Dominik J. Otto
([dotto@fredhutch.org](mailto:dotto@fredhutch.org)) and Manu Setty
([msetty@fredhutch.org](mailto:msetty@fredhutch.org)).

## Data and licences

- Bone-marrow demo data (the 8,090-cell store every local demo uses): Zenodo
  [10.5281/zenodo.15587768](https://doi.org/10.5281/zenodo.15587768), Fred Hutch, CC BY 4.0 (2025-06-03).
- Tahoe-100M (scale benchmarks): CC0-1.0.
- Screenshots of other tools are shown as scholarly comparison; each annotated image carries a
  credit line (software, its licence, the dataset shown and its licence).
- This site's text and figures: CC BY 4.0. The notes it draws on were written by AI agents working
  under the authors' direction; roles, not agent names, are used throughout.

## Build it yourself

```sh
uv venv evidence/.venv && uv pip install -p evidence/.venv -r evidence/requirements.txt
evidence/.venv/bin/python evidence/build.py --site
open evidence/_build/site/index.html          # or: mkdocs serve -f evidence/_build/mkdocs.yml
```
