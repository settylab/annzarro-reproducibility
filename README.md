# AnnZarro: evidence and benchmark code

This repository holds the evidence and the benchmark code behind the AnnZarro paper
(Otto, Baasri and Setty; AnnZarro is at [settylab/annzarro](https://github.com/settylab/annzarro)).
The paper is on bioRxiv: <https://doi.org/10.64898/2026.10.10.758158>.
It has three parts.

1. **The evidence site** (`evidence/`). A static site that links every mark of the paper's feature
   matrix (Fig. 1c), every benchmark number and every figure to the files it comes from.
   It is built from this repository alone.
2. **Benchmark code and results** (`benchmark/`). The laptop performance benchmark, the Tahoe-100M scale
   benchmark, the memory-ceiling benchmark of the compared tools, and the HPC server benchmark, with
   their result tables and the scripts that produced them.
3. **Figure and data-preparation code** (`figures/`, `data_prep/`). The scripts that draw the paper's
   figures from the result files, and the scripts that turn the public demo data into an AnnZarro store.

`notes/comparison/` holds the audit notes, demo scripts and annotated screenshots for the compared tools.

**Benchmark results and more:** <https://settylab.github.io/annzarro-reproducibility/>
(the evidence site, built from this repository). It holds the feature matrix with the
evidence for every mark, the benchmarks and measurements with their result tables, the claims ledger that ties every
number in the paper to its source file, and the provenance of each figure. To build it yourself, see the next section.

**How to cite.** Otto, D. J., Baasri, S. and Setty, M. AnnZarro: scalable, interactive exploration of cell-by-cell and
gene-by-gene relationships in single-cell data. bioRxiv (2026), doi:10.64898/2026.10.10.758158
(<https://doi.org/10.64898/2026.10.10.758158>). `CITATION.cff` has the machine-readable form.

## Layout

| path | what |
|---|---|
| `evidence/build.py` | builds the site: YAML and notes and result tables into Markdown, then MkDocs |
| `evidence/matrix/` | Fig. 1c: columns, one YAML file per tool with its marks and evidence, reference records |
| `evidence/claims.yaml` | the claims ledger: every number and comparison in the paper, with the file it is recomputed from |
| `evidence/tools/` | the checkers and helpers (`claims.py`, `site_smoke.py`, `linkcheck.py`, `annotate.py`, ...) |
| `evidence/screens/` | AnnZarro screenshots and their annotation sidecars |
| `benchmark/` | laptop performance benchmark (`generate_data.py`, `run_benchmark.py`, `results/`) |
| `benchmark/scale/` | Tahoe-100M scale benchmark and the plot-ceiling runs |
| `benchmark/tool_ceiling/` | how many cells each compared tool draws within a memory budget |
| `benchmark/hpc/` | server-side benchmark at atlas scale on an HPC cluster |
| `figures/` | figure scripts; `figures/numbers/` holds the numbers they print |
| `data_prep/` | demo-dataset preparation and its validation |
| `manuscript/figures/` | the figure files the site embeds |

## Build the site

Python 3.11 (3.12 also works), Linux or macOS, `git`. The site's provenance badges read `git log`,
so use a full clone, not `--depth 1`.

```sh
python3.11 -m venv .venv-site
.venv-site/bin/pip install -r evidence/requirements.txt
.venv-site/bin/python evidence/build.py --site        # about two minutes
open evidence/_build/site/index.html                  # works from file://
```

`evidence/HOSTING.md` describes serving and rebuilding. `python evidence/build.py --hosted OUT` writes the
hosted layout (no `repo/` mirror, WebP images, links to this repository at the build's commit) that the
GitHub Pages workflow in `.github/workflows/pages.yml` uses. The workflow does nothing until the repository
variable `PAGES_ENABLED` is `true`.

## Checks

```sh
.venv-site/bin/python evidence/tools/claims.py --strict   # every number in the paper recomputed from its source file
.venv-site/bin/python evidence/build.py --check           # figure, matrix, claim sources, figure numbers, sidecars
.venv-site/bin/python evidence/tools/site_smoke.py --expect 63   # pages, matrix, links, claims page
```

`claims.py` and `build.py --check` read the paper's LaTeX (`manuscript/*.tex`, `manuscript/sections/`,
`manuscript/figures/fig_*.tex`): claims bind to `%claim{...}` markers in it. Only the LaTeX sources are here,
not the PDFs or submission files.

## Placeholders in paths

Result files and scripts record where a run happened. Machine-specific locations are written as
placeholders; set them to your own directories to rerun:

| placeholder | meaning |
|---|---|
| `$DATA_ROOT` | where the large stores live (the Tahoe-100M stores, synthetic stores, lab data) |
| `$SCRATCH` | the HPC scratch filesystem used for the server benchmark |
| `$DEMO_ROOT` | the directory holding the compared tools' demo installations |
| `$ENVS_ROOT` | virtual environments of the compared tools |
| `$ANNZARRO_SRC` | a checkout of [settylab/annzarro](https://github.com/settylab/annzarro) at the tag a result names |
| `$TMPDIR` | scratch space for a run |

HPC nodes appear as `compute-node`, the live demo node as `demo-server`. Process listings kept next to
some results (`ps_*.txt`) list the benchmark's own processes only; the count of omitted lines is at the end
of each file. Three unpublished lab datasets appear under shape-only labels (`spatial-A`, `atlas-1.17M-scvi`,
`atlas-1.17M-raw`, `atlas-scPLM`). Dataset names and sample ids of other unpublished data are relabelled the same way.

## Rerun the benchmarks

Every benchmark pins the AnnZarro build it measures (the tag and commit are in each result's environment file).
The paper's numbers are AnnZarro v0.4.1, tag `v0.4.1`.

| benchmark | start here | hardware of the published run | notes |
|---|---|---|---|
| Laptop performance (latency, payload and server memory per click at 10k to 1M cells; chunk shape; sparse layouts) | `benchmark/README.md` | Apple M3 Max, 16 cores, 128 GB RAM, internal SSD, macOS 26.5 | about 1.5 h of measurement and up to 70 GB disk; `generate_data.py`, `run_benchmark.py`, `make_plots.py`; seeded |
| Scale: Tahoe-100M nested stores, first plot, recolour, browser memory, subset checks | `benchmark/scale/NOTES.md`; scripts `build_tahoe.py`, `bench_http.py`, `bench_browser.py`, `bench_subset.py`, `umap_tahoe.py` | same laptop; headless Chromium (Playwright), WebGL through ANGLE Metal | the stores are built from the public release (below); the 95.6M store is about 294 GB with its panel layer |
| Plot ceiling past 95.6M cells (synthetic stores) | `benchmark/scale/ceiling/`; `build_stores.py`, `ceiling.py` | same laptop | synthetic data only; no biological result comes from it |
| Memory ceiling of the compared tools | `benchmark/tool_ceiling/README.md`, `NOTES.md`; `summarize.py` rebuilds `ceilings.csv` and the curve from `results.csv` | same laptop; client memory budget 16 GiB (also 8 and 32 GiB) | measured, not enforced: `phys_footprint` sampled every 50 ms; `docker/validate.sh` cross-checks the libraries under a hard limit |
| Server at atlas scale on HPC | `benchmark/hpc/README.md`; Slurm scripts in `benchmark/hpc/slurm/` | whole HPC compute nodes (Intel Xeon Gold 6254), NFSv4.1 scratch, one sync gunicorn worker | needs Slurm and a filesystem of your own; results are in `benchmark/hpc/results/` and `benchmark/scale/results/hpc/` |
| Demo dataset and panel sets | `data_prep/README.md`, `data_prep/VALIDATION.md` | Apple-silicon Mac, 16 cores, 128 GB | the download is network-bound; the scripts then take minutes |
| Figures | `figures/*.py` | any machine with the figure requirements | each script's docstring names its inputs and outputs |

Timed laptop runs held an exclusive lock, so no two benchmarks overlapped, and the process listings and
memory state before a run are kept next to its result. Cold numbers on an Apple NVMe SSD are a lower bound
for a cluster deployment (`benchmark/README.md`).

## Data

Large stores are **not** in this repository. The result tables record how each was built.

- **Bone-marrow demo data** (8,090 cells, the store every local demo uses): Zenodo
  [10.5281/zenodo.15587768](https://doi.org/10.5281/zenodo.15587768), Fred Hutch, CC BY 4.0.
  `data_prep/download_data.sh` fetches it and checks the published md5.
- **Tahoe-100M** (95,624,334 cells, the scale benchmarks): Hugging Face
  [`tahoebio/Tahoe-100M`](https://huggingface.co/datasets/tahoebio/Tahoe-100M), CC0-1.0.
  `benchmark/scale/build_tahoe.py` builds the nested stores from its parquet shards.
- **A UMAP of every Tahoe-100M cell**: the coordinates made for the paper, deposited on Zenodo; the record's
  README is `benchmark/scale/results/zenodo_umap_README.md`, the script `benchmark/scale/zenodo_umap.py`.
  Zenodo record [10.5281/zenodo.23277102](https://doi.org/10.5281/zenodo.23277102) (concept DOI; it resolves to the latest version).
- **AnnZarro showcase store**: the store the paper's showcase figures were drawn from, deposited on Zenodo in the same record
  ([10.5281/zenodo.23277102](https://doi.org/10.5281/zenodo.23277102), concept DOI).
- **Release assets**: files too large for git (the 40 MB heap profile `base_gene_5M_total.heapprofile`, the
  other Tahoe-100M plot views of `figures/scale/`, and the screenshots of the plot-ceiling runs) are
  attached to the release of this repository.

## Licences and citation

Code: MIT (`LICENSE`). Text, figures and data tables: CC BY 4.0 (`LICENSE-CONTENT`). Screenshots of other
tools and other third-party material keep their own terms; see `THIRD_PARTY.md`.
`CITATION.cff` and `.zenodo.json` hold the citation metadata.
