# How many points one Cell Plot can draw (browser ceiling)

Synthetic AnnData zarr stores of 1M to 95,624,334 cells (`build_stores.py`), one Cell
Plot with `"subset": null`, headless Chromium (Playwright) on an M3 Max with 128 GB.
Client code under test: AnnZarro `dominik/fast-transfer` f5bd7d6 (baseline) and
`dominik/plot-ceiling` (settylab/annzarro#62).

| script | what |
| --- | --- |
| `build_stores.py` | the stores: one 95.6M master, smaller ones as hard-linked prefixes |
| `ceiling.py` | the app: first plot, recolour, zoom, drag pan, V8 heap / ArrayBuffers, renderer / GPU / server RSS, per-request timings |
| `harness.html`, `harness.py` | Plotly scattergl alone on the same binary responses (trace cut, typed vs plain arrays, per-point colour) |
| `heapcap.py` | the tab's V8 heap and ArrayBuffer limits for a set of flags |
| `profile_alloc.py` | V8 sampling heap profile of one load, by allocation site (`profiles/*.txt`) |
| `zoomprof.py` | CPU profile of `Plotly.relayout` zooms |
| `summarize.py` | markdown tables from `results/*.jsonl` |
| `queue*.sh` | the run orders used |

Results are JSON lines in `results/`; runs before 2026-10-03 overlapped other benchmark
and build jobs on the same machine, so their times are indicative only. Screenshots
except four, the unminified Plotly bundle and the churn heap profile are not committed
(`.gitignore`).
