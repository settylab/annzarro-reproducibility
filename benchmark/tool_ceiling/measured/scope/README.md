# SCope: measured

SCope 1.8.2 (9ae5207, the build its public site serves; the image loads the same `assets/SCope-1.8.2.9ae5207.js`)
was measured on 2026-10-07/08 with the same task and rules as every other web tool: open the UMAP of the first N
cells of Tahoe-100M, colour it by cell line and by MALAT1, every cell drawn, the client's peak memory against the
16 GiB budget. **Result: every cell drawn at 1M; at 2M the Chromium renderer crashed in both attempts while the
embedding was being drawn, well under the budget. Ceiling 1M, first failure 2M (renderer crash).**

| run | cells | outcome | client peak (GiB) | server container peak (GiB) | notes |
| --- | --- | --- | --- | --- | --- |
| scope_default_run_1000000_r0 | 1,000,000 | ok, all 1,000,000 drawn for both colourings | 4.03 | 0.97 | load 2.7 s; cell line 12.7 s; MALAT1 10.9 s |
| scope_default_run_2000000_r0 | 2,000,000 | renderer crash ("Page.evaluate: Target crashed") at 38.6 s, before any colouring | 4.74 | 0.41 | |
| scope_default_run_2000000_r1 | 2,000,000 | renderer crash again at 36.2 s, before any colouring | 4.73 | 0.60 | JS-heap series below |

The repeat at 2M sampled the JS heap every 2 s (`heap_series_2M_r1.jsonl`): the last sample before the crash, at
27.4 s while the embedding was loading, showed 49.8 MB used of a 4.40 GB jsHeapSizeLimit (CDP usedSize 28.9 MB); the
next sample, at 29.5 s, failed because the renderer was gone. The renderer therefore died with a nearly empty V8
heap while SCope's PIXI viewer built its 2,000,000 sprites, so the limit is outside the JS heap (renderer or GPU
memory, or a WebGL limit); which one is not established. The crash is not a timeout or slowness, so under the
emulation rule below it sets the ceiling.

Evidence shots of the 1M rung (`scope_default_run_1000000_r0_cat.png`, `_gene.png`): the whole embedding in view (the
task zooms out two wheel notches about the canvas centre; SCope has no fit button), the cookie banner declined.

## How it was run

- Task: `benchmark/tool_ceiling/scope_task.py`, driven by `run.py --web` (memmon on the Chromium processes, as for
  every web tool), one `run-timed` call per rung. The container is started fresh per rung with only that rung's loom
  in SCope's data folder.
- Every cell drawn: SCope's viewer keeps one PIXI sprite per cell in a ParticleContainer; its child count and the
  viewer's coordinate index length are read from the React component and must equal N after each colouring.
- Colourings: the loom's `cell_line_id` annotation (searched and picked as an annotation; legend of 50 cell lines) and
  the gene MALAT1.
- Server memory: SCope's server runs inside Docker's Linux VM, invisible to memmon; its memory is the container's
  cgroup usage from `docker stats`, sampled every 2 s (`server_container_peak_gib` in the task JSON).
- Emulation: the image is linux/amd64 (the Dockerfile installs x86_64 software), run under Docker's emulation on this
  arm64 laptop. Rule (coordinator): a stop explained by emulation slowness gives a lower bound, not the ceiling; a crash
  not caused by time counts.
- Input: the shared `tahoe_first<N>.h5ad` converted to .loom by `benchmark/tool_ceiling/to_loom.py` (loompy 3.0.8;
  dense genes x cells matrix with loompy's chunking and gzip; ra Gene, ca CellID, ca Embedding = X_umap, and
  cell_line_id declared as a SCope annotation in the MetaData attribute). Input preparation, not measured.
- Disk: the 5M loom (11.4 GB) took free disk to about 35 GiB, below the 40 GiB reserve; the operator approved that
  exception for the 5M rung. The 5M rung never ran (the ladder stops at the first failure) and the 5M loom was deleted.

## Deviations from the as-published build (all in the build environment; SCope's code and lock files unchanged)

Final image `scope:1.8.2-9ae5207-final`, id sha256:dd89d344b6c3954d153e374ab0300f214da47b84500e6c870d89f0a82b61a04f
(linux/amd64), built from 9ae520733138f3cf4315ad1a681863fa4126cec4 with `Dockerfile.final` (diff against the
repository's Dockerfile in `Dockerfile.final.diff`; log `docker_build_final.txt`). The nine changes:

1. `FROM debian:bullseye` (published: `debian:latest`, now Debian 13, which NodeSource does not serve Node.js 14 for).
2. apt sources on archive.debian.org (debian, bullseye-updates, bullseye-security) with `Acquire::Check-Valid-Until "false"`.
3. Node.js v14.21.3 from the nodejs.org tarball, sha256 05c08a107c50572ab39ce9e8663a2a2d696b5d262d5bd6f98d84b997ce932d9a
   checked (published: NodeSource `setup_14.x`).
4. Miniforge3 26.7.2-0 from the conda-forge/miniforge release, sha256
   281b0ac7d550802efc81af633225a5e6116d29ae72f3ab4eae7168c3931a4c05 checked (published: Miniconda latest, whose
   default channels now require accepting Anaconda's Terms of Service; none were accepted).
5. `/opt/conda/.condarc` lists only conda-forge and nodefaults.
6. Poetry 1.1.15 (the 2021 line; today's unpinned Poetry 2.5.1 rejects SCope's pyproject) in its own conda-forge env
   on Python 3.10, put on PATH; SCope itself keeps the Dockerfile's `scope` env on Python 3.8.3.
7. `"setuptools<70"` in that Poetry env (setuptools 84 breaks Poetry 1.1's packaging 20.9).
8. `ENV VIRTUALENV_SETUPTOOLS=69.5.1`, so the virtualenv Poetry creates for SCope is seeded with a setuptools that
   works with the lock file's packaging 20.4 (today's setuptools fails building the numpy_groupies sdist).
9. `RUN cd /app/opt/scopeserver/bindserver && npm ci`: installs the websocket bind server's own locked dependencies
   (protobufjs 5.0.3, grpc 1.24.5). The root package-lock marks them "bundled", the folder's node_modules is not in
   git, and the published Dockerfile never installs it; without it server.js loads the root protobufjs 6 and crashes
   ("protobuf.loadProtoFile is not a function").

Run-time configuration (not build changes):

- `DATABASE_URL=sqlite:////root/.local/share/SCope/scope.sqlite` (the value from SCope's own `opt/.env`, which the
  server looks for at `../.env` relative to its working directory);
- a config file (SCOPE_CONFIG) as the repository's `config.json` but with `localHostAddress` 0.0.0.0, so Docker's
  published ports reach the servers;
- the frontend (`/app/index.html` and `assets/`) served by Python's http.server on port 55850, where the published
  docker-compose puts Apache in front;
- `start.sh`'s `alembic upgrade head` step skipped: it fails because `scopedb/alembic/versions` is an empty folder not
  in git; the server starts without it (`poetry run hypercorn --bind 0.0.0.0 main:scope_api`).

## Build history (2026-10-06/07)

The first sentence below is the not-measured record as it stood after the first two tries.

SCope 1.8.2 (9ae5207, the build its public site serves) could not be built locally on 2026-10-06: its only install route, the repository's Dockerfile, failed on Debian 13 (NodeSource has no Node.js 14) and, with the base pinned to Debian 11, on 404s from the Debian security archive.

1. `docker_build_debian13.txt`: the Dockerfile as published. Step 4/17, `curl -sL https://deb.nodesource.com/setup_14.x | bash -`, exits 1: "Your distribution, identified as "trixie", is not currently supported".
2. `docker_build_debian11_pinned.txt`: only `FROM debian:bullseye`. Step 3/17, `apt-get install`, exits 100: 30 packages "404 Not Found" from http://deb.debian.org/debian-security/pool/updates/main/ ("E: Unable to fetch some archives"), possibly a mirror state on that date.
3. `docker_build_envpatch.txt` (`Dockerfile.envpatch`, `.diff`): + archive.debian.org and Node.js from nodejs.org. Step 9/17, `conda create`, exits 1: "CondaToSNonInteractiveError: Terms of Service have not been accepted" (a licence decision left to the operator; not accepted).
4. `docker_build_miniforge.txt` (`Dockerfile.miniforge`, `.diff`): + Miniforge. Step 16/17, `poetry install`, exits 1: "The Poetry configuration is invalid: - tool.poetry.homepage must be uri" (Poetry 2.5.1).
5. `docker_build_poetry11.txt` (`Dockerfile.poetry11`, `.diff`): `conda install "poetry=1.1.*"` into the base env. Step 11/17, solver conflict: no Poetry 1.1 for the base env's Python 3.14.
6. `docker_build_py310poetry.txt`: Poetry 1.1 in its own Python 3.10 env. Step 11/17, `poetry --version` crashes: "TypeError: canonicalize_version() got an unexpected keyword argument 'strip_trailing_zero'" (setuptools 84 with packaging 20.9).
7. `docker_build_try7.txt` (`Dockerfile.try7`): + `"setuptools<70"`. Step 16/17, `poetry install`, fails building the numpy_groupies 0.9.11 sdist with the same TypeError, inside the virtualenv Poetry creates for SCope.
8. `docker_build_try8.txt`: + `ENV VIRTUALENV_SETUPTOOLS=69.5.1`. All 17 steps pass; the server starts but the bind server crashes on protobufjs 6.
9. `docker_build_final.txt` (`Dockerfile.final`): + the bind server's `npm ci`. All 18 steps pass; serves and draws.

## Size of the loom inputs

Measured with to_loom.py (loompy 3.0.8):

| cells | .loom size | conversion time |
| --- | --- | --- |
| 0.25M | 0.14 GB | 12.5 s |
| 1M | 0.83 GB | 52.6 s |
| 2M | 2.38 GB | 118.6 s |
| 5M | 11.4 GB | 419-423 s |
| 10M | 40.9 GB | 1380.3 s |

The size grows faster than the cell count, so on this laptop's disk (40 GiB reserve) the loom route would have
stopped at 5M; the renderer crash at 2M came first.
