# scSVA install recipe

scSVA = klarman-cell-observatory/scSVA, commit `c9e8fd6b280910eadf9daba35badcf6933c7f353`
(2019-03-26, DESCRIPTION Version 0.2.0). Licence: the repo HAS a `LICENSE` file (GPL-3,
"Copyright © 2018 The Broad Institute"), but `DESCRIPTION` says `License: BSD 3-clause`. The
two disagree; GitHub's licence detector reports NOASSERTION.

## A. What was built and run here (HPC, verified)

Fred Hutch HPC, Ubuntu 18.04 nodes, built by `build_hpc.sh` (Slurm job 10168106, BUILD_OK).

| piece | version | from |
|---|---|---|
| R | 3.6.2 (`R/3.6.2-foss-2019b-fh1` Lmod module) | module; ships 29 of the 34 R packages DESCRIPTION declares (Depends + Imports) |
| 5 missing R pkgs | colorRamps 2.3, tableHTML 2.0.0, shinyjqui 0.3.3, shinyAce 0.4.1, googleComputeEngineR 0.3.0 | CRAN snapshot `https://packagemanager.posit.co/cran/2020-04-20` into a private lib |
| Python | 3.6.15 | micromamba, `scsva-py.yml` |
| vaex | vaex-core 2.0.3, vaex-hdf5 0.6.0; numpy 1.16.6 | conda-forge (`scsva-py.yml`; full lock: `scsva-py.linux-64.explicit.txt`) |
| scSVA | 0.2.0 at c9e8fd6 | `R CMD INSTALL` of a local clone |

Full R inventory: `R_installed_packages.csv`, `R_sessionInfo_build.txt`.

One fix was needed: conda-forge's noarch `python-utils` 3.x installs under Python 3.6 but uses
`:=` (3.8+ syntax), so `import vaex` died with a SyntaxError (vaex 2 → progressbar2 →
python-utils). Pinned `python-utils=2.5.6`, `progressbar2=3.55`.

Start (as `run/run_job.sh` does):

    module load R/3.6.2-foss-2019b-fh1
    export R_LIBS_USER=<scsva>/rlib PATH=<scsva>/pyenv/bin:$PATH RETICULATE_PYTHON=<scsva>/pyenv/bin/python
    Rscript -e "shiny::runApp(system.file('scSVA', package='scSVA'), host='127.0.0.1', port=PORT, launch.browser=FALSE)"

`global.R` picks Python with `system("which python3")` on Linux (and
`source ~/.bash_profile; which python3` on macOS), so the vaex env must be first on PATH.
It prints a harmless `which gsutil` warning (Cloud tab only).

## B. Portable recipe for the laptop (`container/`)

`container/Dockerfile` (and the same steps as `container/scsva.def` for Apptainer):
`rocker/r-ver:3.6.3@sha256:9414f76c…ca6d` + apt libs + micromamba Python env (`scsva-py.yml`,
identical to A) + the declared R packages from the same 2020-04-20 CRAN snapshot + rhdf5 from
Bioconductor 3.10 + scSVA at c9e8fd6. Port 3838.

    docker build --platform linux/amd64 -t scsva:c9e8fd6 container/
    docker run --platform linux/amd64 --rm -p 3838:3838 -v <inputs>:/data:ro scsva:c9e8fd6

**Verification status — read this.** The Dockerfile was NOT built end to end here: this
sandbox refuses the fakeroot `%post` step (`Failed to set mount propagation: Operation not
permitted`, job 10168177). What WAS verified: the base digest pulls (job 10168251); the
Python env and the R package set/versions are the ones that built and ran in A (except that R
is 3.6.3 instead of 3.6.2, and the 29 module packages come from the snapshot instead of the
module; versions can differ slightly). The apt step was simulated against the pulled rootfs
with the host's apt-get (`verify_base.txt`): the image's own buster sources are dead
(deb.debian.org has no buster Release file any more, rc 100), so `apt-sources.sh` switches to
archive.debian.org, where `apt-get -s install` of the package list resolves (141 new
packages, rc 0, signatures checked against the image's keyring). The image's default CRAN repo
(MRAN snapshot 2020-04-24) is also dead; `install_r.R` sets the Posit snapshot explicitly.
Expect the first laptop build to be the real test, and expect it to be slow under emulation
(about 40 R packages compile from source, including Rhdf5lib's bundled HDF5).

## macOS arm64

- **Natively: no.** R 3.6 has no arm64 macOS build (CRAN arm64 starts at R 4.1.0), and
  conda-forge has no osx-arm64 vaex-core below 4.1 (and only for Python ≥ 3.8); scSVA needs
  pre-4.x vaex (README) and was written against vaex 1–2.
- **Under Rosetta, natively (osx-64 conda): untested.** conda-forge has osx-64 vaex-core 2.0.x
  for py36, but no conda R 3.6 environment with the full Shiny stack solves (`dryrun-*.log`:
  tableHTML and others exist only for R ≥ 4.3 on conda-forge).
- **In Docker (linux/amd64 under Rosetta emulation): the recommended route.** rocker/r-ver:3.6.3
  is amd64-only, so Docker Desktop's Rosetta emulation is required. Memory and timing measured
  under emulation are not native numbers; say so in the figure.
