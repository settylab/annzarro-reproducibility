## AnnZarro

### What it is

AnnZarro is a read-only viewer for AnnData stores (zarr, or a local h5ad) built around the two
relationship slots other viewers skip: a stored cells × cells matrix (`obsp`) or genes × genes
matrix (`varp`) becomes a colour or an axis, and the focused cell or gene picks which row is shown.
A Flask server opens the store lazily and answers `/api/v1/data/...` requests with one slice each
(a gene column, a cell row, a pairwise row); the browser client (plain JavaScript, Plotly,
DataTables) draws tiled cell plots, gene plots and tables that follow one focused cell and one
focused gene. The same code runs as a desktop app (Electron with a frozen server), a personal
server (`annzarro start`) or a lab server (gunicorn, login, shared panel sets).

**Primary paper.** This manuscript. AnnZarro has no earlier publication, so every `paper` slot of
its matrix row is `n/a`.

**Repository.** [settylab/annzarro](https://github.com/settylab/annzarro), pinned at the v0.4.1 tag
= `78c9da657ecbff30163fd29055f0e6b10e915c5c` (2026-10-07, "Release v0.4.1 (#86)"). Every code link in
[`evidence/matrix/tools/annzarro.yaml`](../matrix/tools/annzarro.yaml) is a permalink at this commit.
The links were first written against `606f0bc` (2026-10-03), repinned to the v0.3.0 tag `3fb6826`,
v0.3.1 `1391357`, v0.4.0 `49e2a19` and then v0.4.1, each time by finding every cited range again by
its content. From v0.4.0 to v0.4.1, 55 of 66 ranges are byte-identical (25 of them at shifted lines);
11 changed and were re-read by hand. All still support their mark: added lines inside the cited code
(a focus handler that waits for its panel's axes, more endpoints, a subset dialog that disables
balance on columns with too many categories, typed table-filter conditions, a share link that waits
briefly for the store's fingerprint) or reworded tests, and no removed behaviour.

**Docs.** [annzarro.readthedocs.io](https://annzarro.readthedocs.io/en/latest/) (checked 2026-10-07).
Read the Docs `stable` was built from the release commit `78c9da6` (RTD build API, finished
2026-10-07 19:47 UTC); `latest` is two commits past the tag (`07166ac`, citation metadata only).

### How to validate it yourself

1. Install the pinned commit: `git -C <annzarro checkout> archive v0.4.1 | tar -x -C annzarro_src`, then `uv venv .venv && SETUPTOOLS_SCM_PRETEND_VERSION=0.4.1 uv pip install -p .venv/bin/python "annzarro_src[remote]"` (an archive has no git history, so the version must be given).
2. Put `bm_aging_showcase.zarr` and `spatial_demo.zarr` (this repo's `data/`, see `data/bm_aging_showcase.FIELDS.md`) in a directory and run `annzarro start --data-dir <dir> --host 127.0.0.1 --port 8920 --no-browser`; open http://127.0.0.1:8920.
3. Add a Cell Plot; open its controls; set Color to `obsp` / `diffusion_distance`. Set X and Y to `obsp` / `umap_distance` and `diffusion_distance` in a second Cell Plot (columns 1, 4).
4. Add a Gene Plot; Color = `varp` / `spearman_fold_change`; click a gene; every varp panel follows (columns 2, 3). Click a cell in a Cell Plot; every obsp panel follows.
5. Open the layer menu of any Color selector: `X` is the first entry (column 4; contradicts `docs/data/slot-map.md`).
6. Add a Cell Table, click Add Condition, build `highres_celltype = HSC` AND a group with OR; in each plot set Filter by Table to it (columns 7, selection).
7. Click the "All cells" badge: the subset dialog (column 18). Read `core/subset.py` L66-69 for the 200,000-cell default (column 17).
8. Plot Options -> Export -> PNG / SVG (column 12). Share Link, then open the copied link in a private window (column 11).
9. Serve the store over HTTP (`python -m http.server 8923 --bind 127.0.0.1` in its parent directory) and type `http://127.0.0.1:8923/bm_aging_showcase.zarr` into the Dataset picker; count the chunk GETs in the web server's log for one gene (columns 5, 16).
10. Start a second server with a config holding `auth: {enabled: true, user_file: <file>}`, add two users with `annzarro user --config <cfg> add`, save a panel set as one and load it as the other (column 14).
11. Open https://github.com/settylab/annzarro/releases/tag/v0.4.1 and check the desktop assets (column 13).
12. Or run everything at once: `evidence/screens/annzarro/capture.py --annzarro .venv/bin/annzarro --version <v> --sha <sha> --scratch <dir>` with a Playwright Python (on a benchmark machine, through `notes/comparison/demos/scale_probe/gap_run.sh`), then `evidence/tools/annotate.py check evidence/screens/annzarro/*.annot.yaml`.
