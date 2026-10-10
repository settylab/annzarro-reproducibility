## Local demos

Seven tools run on this laptop under `$DEMO_ROOT/`, each in its own environment. Six serve on 127.0.0.1 only, on ports 8901 to 8907. The seventh, napari-spatialdata, is a desktop window. Every server was started, checked with `curl` and stopped on 2026-10-03. None is left running, because a benchmark is timing on this machine. Installs and checks ran under the shared bench lock (`/usr/bin/lockf -k ~/.annzarro-bench.lock`).

The scripts are copied into this repository under [`notes/comparison/demos/`](demos/), so the setup can be reviewed and rebuilt.

### Shared dataset

All tools that accept it get the same data: the paper's bone marrow demo (8,090 cells × 16,285 genes, Young/Mid/Old mice), taken from `data/bm_aging_showcase.zarr`. This lets you compare like with like.

| File | Made by | Contents |
|---|---|---|
| `$DEMO_ROOT/_data/bm_demo.h5ad` (356 MB) | [`make_demo.py`](demos/_data/make_demo.py), paper `.venv` | X = log counts (CSR), `layers/counts`, 13 obs columns, obsm UMAP / PCA / diffusion / force-directed, obsp `connectivities`, `distances` and dense `diffusion_distance` (8,090 × 8,090) |
| `$DEMO_ROOT/_data/bm_demo_sce.rds` | [`build_sce.R`](demos/_data/build_sce.R) | The same as a SingleCellExperiment: `logcounts`, colData, UMAP and PCA, the kNN graph as `colPairs`, and one dense matrix row (`diffusion_distance_to_4236`, the paper's focused monocyte) as a colData column |
| `$DEMO_ROOT/vitessce/store/bm_demo.zarr` | [`make_store.py`](demos/vitessce/make_store.py) | AnnData zarr v2, with X dense and chunked per 10 genes, as Vitessce expects |

The store's own X is MAGIC-like and fully dense, so the demo uses `layers/logged_counts` as X. Each demo keeps the obsp matrices on purpose. Whether a tool offers them anywhere is the check for matrix columns 1 and 4.

### Start, stop, check

Start a demo with `$DEMO_ROOT/<tool>/start.sh`, which runs in the foreground, and stop it with Ctrl-C or `$DEMO_ROOT/<tool>/stop.sh`. To start one, poll until it answers and stop it again, run `$DEMO_ROOT/verify.sh <tool> <port> <path>`.

| Tool | Version | Env | URL | Data | Checked 2026-10-03 |
|---|---|---|---|---|---|
| Cirrocumulus | 1.1.61 | `uv` venv, Python 3.11 | http://127.0.0.1:8901 | bm_demo.h5ad (`cirro launch`) | `/` and `/api/schema` 200 after 2 s. Schema: 16,285 features, embeddings `X_umap` and `X_draw_graph_fa`, no obsp. |
| iSEE | 2.18.0 (Bioc 3.20, R 4.4.3) | micromamba env `_mamba/envs/rtools` | http://127.0.0.1:8902 | bm_demo_sce.rds | UI 200 after 6 s |
| CELLxGENE Annotate | 1.3.0 | `uv` venv, Python 3.10 | http://127.0.0.1:8903 | bm_demo.h5ad (`cellxgene launch`; annotations saved to `cellxgene/annotations/`) | `/api/v0.2/schema` 200 after about 30 s. Layouts diffusion, draw_graph_fa, pca, umap; no obsp. |
| Vitessce | hosted app (4.x) + local data | `serve.py` (static files, Range, CORS) | https://vitessce.io/?url=http://127.0.0.1:8904/config.json | bm_demo.zarr + [`config.json`](demos/vitessce/make_store.py) (two scatterplots, cell sets, gene list, heatmap) | config and `.zmetadata` 200, CORS headers present. **Rendering in the hosted app was not checked.** |
| UCSC Cell Browser | cellbrowser 1.2.20 | `uv` venv, Python 3.11 | http://127.0.0.1:8906/?ds=bm_demo | static build of bm_demo.h5ad | `dataset.json` 200; byte-range request on `exprMatrix.bin` 206 |
| ShinyCell | 2.1.0 (GitHub `5c61db7`) | micromamba env `_mamba/envs/rtools` | http://127.0.0.1:8907 | app built from bm_demo_sce.rds by [`build.R`](demos/shinycell/build.R) (97 MB) | UI 200 after 2 s |
| napari-spatialdata | 0.7.2 (napari 0.9.2, spatialdata 0.8.0, PyQt6) | `uv` venv, Python 3.12 | desktop window | the paper's Visium mouse brain demo (`data/spatial_demo.zarr`, 2,693 spots), wrapped as SpatialData by [`make_sdata.py`](demos/napari-spatialdata/make_sdata.py) | window opened, SpatialData and View docks present, `cells` layer loaded, window closed |

A 200 from these checks shows that the server answers and the data load. It does not show that a plot draws. I did not open the GUIs in a browser, because that would have competed with the benchmark for CPU. Opening each URL once is the first step of each tool's validation checklist.

### Tools without a local demo

- **CELLxGENE Explorer, SCope, Single Cell Portal, UCSC portal, Vitessce demos, ShinyCell demos.** Online demos answer; see each tool's file.
- **Kana** runs entirely in the browser. Open https://www.kanaverse.org/kana/, choose New Analysis, then H5AD, and pick `$DEMO_ROOT/_data/bm_demo.h5ad`. The file is read locally and nothing is uploaded.
- **Loupe Browser** is proprietary and needs a 10x account to download. Nothing was installed. See [loupe.md](loupe.md) for the download page and what the docs establish.
- **Scanpy / Seurat** are libraries. The paper `.venv` already has scanpy and anndata.

### Workarounds you will meet if you rebuild

- Homebrew `mamba`/`micromamba` 2.5.0 is broken on this machine (missing `libsimdjson.30.dylib`). A standalone micromamba 2.9.0 lives in `$DEMO_ROOT/_bin/bin/micromamba`, with root prefix `$DEMO_ROOT/_mamba`. Nothing system-wide was changed.
- `cbImportScanpy` writes colour-file paths that include the output directory (`"cb_in/Age_colors.tsv"`), so `cbBuild` then fails. The fix is to strip the prefix in `cb_in/cellbrowser.conf` and run `cbBuild -o ../html` from inside `cb_in`. Marker-database downloads from `cells-test.gi.ucsc.edu` failed; this does not matter here.
- cellbrowser's own `cbBuild -p` server binds every interface. `serve.py` binds 127.0.0.1 instead.
- napari's PyQt5 backend is deprecated and segfaulted under `QT_QPA_PLATFORM=offscreen`, so the venv uses PyQt6.

### Disk use

`$DEMO_ROOT` takes 9.5 GB. That covers the envs (micromamba R env 2.0 GB, napari venv 1.1 GB), the shared data (about 0.9 GB with the CSV and MTX exports), copies of the h5ad inside the Cell Browser build, and the shallow source clones the per-tool audits cite. To remove everything, delete `$DEMO_ROOT`.
