"""Code-output and terminal shots (evidence-curator, 2026-10-04): each runs the script in code2/ that it shows, then renders
the script and its real output as an HTML page, screenshots it with Playwright and records DOM boxes.

Run under notes/comparison/demos/scale_probe/gap_run.sh with
  benchmark/scale/ceiling/.venv/bin/python <this file> [scanpy] [napari] [shinycell] [isee] [select]

scanpy     h01 remote P (read_lazy on a public s3:// AnnData zarr, the S3 GETs from s3fs's log),
           h02 lazy P (backed="r" and read_lazy on bm_demo.h5ad), h03 share P (the script is the state).
select     scanpy-seurat h04 selection P: a boolean mask on UMAP_1 re-plotted by hand on the UMAP and the FA layout
           (code2/scanpy_select.py); Seurat's CellSelector likewise returns cell names that other plots use only via code.
napari     h01 remote P: the CLI treats an https URL as a local path and stops.
shinycell  h01 lazy Y (proposed): the app's own one-gene HDF5 read and the one chunk it touches.
isee       h01 lazy P: bm_demo's assay written to HDF5 (HDF5Array) and read one row on demand, as the bigdata
           vignette describes. HDF5Array 1.34.0 is not in the rtools env (its package managers fail to load), so it
           was built from Bioconductor 3.20 source into a scratch library (RLIB below).
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capture2lib import SCRATCH, TODAY, log, pv, shot, step, term_page  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = HERE + "/code2/"
DRIVER = "evidence/screens/gaps/capture2_code.py"
REMOTE_PY = "$DEMO_ROOT/scanpy-seurat/.venv-remote/bin/python"
PAPER_PY = ".venv/bin/python"
PW_PY = "benchmark/scale/ceiling/.venv/bin/python"
RSCRIPT = "$DEMO_ROOT/_mamba/envs/rtools/bin/Rscript"
RLIB = SCRATCH + "rlib"
DATA = "$DEMO_ROOT/_data"
os.makedirs(SCRATCH + "work", exist_ok=True)


def run(cmd, cwd, env=None, timeout=240):
    e = dict(os.environ, PYTHONWARNINGS="ignore", **(env or {}))
    t = time.time()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=e, timeout=timeout)
    out = [ln for ln in (r.stdout + r.stderr).splitlines()
           if ln.strip() and "colorout" not in ln and "During startup" not in ln and "Warning" not in ln
           and not ln.startswith(("  warnings.warn", "1: In ", "2: In ", "3: In ", "4: In "))]
    log("ran", " ".join(cmd)[-90:], "rc", r.returncode, f"{time.time() - t:.1f}s")
    for ln in out:
        log("   |", ln[:160])
    return out, r.returncode


def hl(lines, keys):
    return [(ln, True) if any(k in ln for k in keys) else ln for ln in lines]


def scanpy(p):
    sw_r = "anndata 0.13.4, zarr 3.4.0, s3fs 2026.9.0 (code; Scanpy has no GUI)"
    out, rc = run([REMOTE_PY, "-W", "ignore", CODE + "scanpy_remote.py"], SCRATCH + "work")
    term_page(p, title="Code output: anndata reads a remote s3:// AnnData zarr lazily (Scanpy's data layer)",
              sub=f"{sw_r}; run {TODAY} on the laptop, anonymous access to the public lamindata bucket. "
                  "The S3 requests are taken from s3fs's own debug log (logging handler in the script).",
              blocks=[("code", "evidence/screens/gaps/code2/scanpy_remote.py", open(CODE + "scanpy_remote.py").read()),
                      ("out", None, hl(out, ["opened s3://", "one gene", "GET X/"]))],
              note="Remote reading exists, but only by code and with optional packages (fsspec, s3fs, xarray, dask) that a plain Scanpy install lacks: P.")
    shot(p, "scanpy-seurat", "h01_remote_read_lazy_s3_by_code.jpg",
         [pv("remote", "P", f"code output, anndata 0.13.4 / zarr 3.4.0 ({TODAY}): read_lazy opens an anonymous s3:// AnnData zarr and fetches one gene's chunks over S3 on demand; by code only, so P")],
         [(1, "#code0", "the code: read_lazy on an s3:// URL"), (2, "#hl1_0", "opened the remote store"),
          (3, "[id^=hl1_] >> nth=2", "one gene: only X chunks fetched (S3 GET log)"), (4, "#note", "code only, optional packages")],
         software=sw_r, driver=DRIVER, data="s3://lamindata/.lamindb/CFcQxNjzSRzWZrVh.anndata.zarr (public, 46,086 cells)",
         url="s3://lamindata/.lamindb/CFcQxNjzSRzWZrVh.anndata.zarr")

    out, rc = run([REMOTE_PY, "-W", "ignore", CODE + "scanpy_lazy.py"], DATA)
    term_page(p, title="Code output: backed and lazy reading of an h5ad (Scanpy's data layer)",
              sub=f"anndata 0.13.4, run {TODAY} on bm_demo.h5ad (8,090 cells; obsp holds a dense 8,090 x 8,090 diffusion_distance). "
                  "Max RSS from resource.getrusage.",
              blocks=[("code", "evidence/screens/gaps/code2/scanpy_lazy.py", open(CODE + "scanpy_lazy.py").read()),
                      ("out", None, hl(out, ["X: _CSRDataset", "one gene:", "read_lazy X:"]))],
              note="X stays on disk and one gene is read on demand, but backed mode loads obs, obsm and obsp whole (RSS jumps on open), and everything is by code: P.")
    shot(p, "scanpy-seurat", "h02_lazy_backed_and_read_lazy_by_code.jpg",
         [pv("lazy", "P", f"code output, anndata 0.13.4 ({TODAY}): read_h5ad(backed='r') keeps X on disk and reads one gene on demand, read_lazy gives a dask X; backed mode still loads obsp whole and it is all code, so P")],
         [(1, "#code0", "the code: backed='r', then read_lazy"), (2, "[id^=hl1_] >> nth=0", "X is an on-disk _CSRDataset"),
          (3, "[id^=hl1_] >> nth=1", "one gene read from disk"), (4, "[id^=hl1_] >> nth=2", "read_lazy: X is a dask Array"), (5, "#note", "obsp loaded whole; code only")],
         software="anndata 0.13.4 (code; Scanpy has no GUI)", driver=DRIVER, data="bm_demo.h5ad (8,090 cells)", url="file://" + DATA + "/bm_demo.h5ad")

    wd = SCRATCH + "work/share"
    os.makedirs(wd, exist_ok=True)
    for f in os.listdir(wd):
        os.remove(os.path.join(wd, f))
    subprocess.run(["cp", CODE + "scanpy_view.py", wd + "/view.py"])
    lines = []
    for i in (1, 2):
        o, rc = run([PAPER_PY, "-W", "ignore", "view.py", f"run{i}.png"], wd, env={"DEMO_DATA": DATA})
        lines += [f"$ python view.py run{i}.png"] + o
    o, _ = run(["md5", "-r", "run1.png", "run2.png"], wd)
    lines += ["$ md5 -r run1.png run2.png"] + [(ln, True) for ln in o]
    o, _ = run(["ls", "-l"], wd)
    lines += ["$ ls -l"] + o
    term_page(p, title="Code output: in Scanpy the shareable 'view state' is the script",
              sub=f"scanpy 1.11.5, anndata 0.12.19, matplotlib (Agg), run {TODAY}. The same script run twice writes byte-identical PNGs; "
                  "nothing else stores a view (no link, no state file).",
              blocks=[("code", "view.py (evidence/screens/gaps/code2/scanpy_view.py)", open(CODE + "scanpy_view.py").read()),
                      ("out", None, lines), ("img", "run1.png, the view the script reproduces", wd + "/run1.png")],
              note="Sharing a view means sending the script and the data and re-running it: P by the code rule.")
    shot(p, "scanpy-seurat", "h03_share_script_is_the_state.jpg",
         [pv("share", "P", f"code output, scanpy 1.11.5 ({TODAY}): the only view state is the script; re-running it gives a byte-identical figure, there is no link or state file, so P")],
         [(1, "#code0", "the script is the whole view state"), (2, "[id^=hl1_] >> nth=0", "two runs, identical md5"), (3, "#img2", "the reproduced view"),
          (4, "#note", "share = send the script and the data")],
         software="scanpy 1.11.5, anndata 0.12.19 (code; Scanpy has no GUI)", driver=DRIVER, data="bm_demo.h5ad (8,090 cells)", url="file://" + wd)


def napari(p):
    nd = "$DEMO_ROOT/napari-spatialdata"
    py = nd + "/.venv/bin/python"
    out, rc = run([py, "-m", "napari_spatialdata", "view", "https://example.org/remote.zarr"], nd, timeout=120)
    out = out[-8:]
    src = "/".join(subprocess.run([py, "-c", "import napari_spatialdata,os;print(os.path.dirname(napari_spatialdata.__file__))"],
                                  capture_output=True, text=True).stdout.strip().split("/"))
    g, _ = run(["grep", "-n", "Path(p_str).resolve()\\|assert p.exists()", src + "/__main__.py"], nd)
    lines = ["$ python -m napari_spatialdata view https://example.org/remote.zarr"] + hl(out, ["does not exist"]) + [f"(exit status {rc})", "",
             "$ grep -n 'Path(p_str).resolve()\\|assert p.exists()' napari_spatialdata/__main__.py"] + hl(g, ["assert p.exists()"])
    term_page(p, title="Terminal: napari-spatialdata's CLI treats a URL as a local path",
              sub=f"napari 0.9.2, napari-spatialdata 0.7.2, spatialdata 0.8.0; run {TODAY} in $DEMO_ROOT/napari-spatialdata.",
              blocks=[("out", None, lines)],
              note="The viewer's own entry point cannot open a remote store; a remote zarr reaches it only through Python, "
                   "Interactive(sd.read_zarr(url)) (spatialdata reads remote zarr): P.")
    shot(p, "napari-spatialdata", "h01_remote_cli_url_is_local_path.jpg",
         [pv("remote", "P", f"terminal, napari-spatialdata 0.7.2 ({TODAY}): 'view https://...' resolves the URL as a local path and stops; remote zarr only through Python, so P")],
         [(1, "[id^=hl0_] >> nth=0", "the URL turned into a local path that does not exist"), (2, "[id^=hl0_] >> nth=-1", "the CLI asserts the path exists"),
          (3, "#note", "remote only through Python")],
         software="napari 0.9.2, napari-spatialdata 0.7.2, spatialdata 0.8.0 (CLI)", driver=DRIVER, data="https://example.org/remote.zarr (any URL)",
         url="file://" + nd)


def shinycell(p):
    app = "$DEMO_ROOT/shinycell/app"
    g, _ = run(["grep", "-n", "H5File\\$new\\|h5data\\$read", "server.R"], app)
    r, _ = run([RSCRIPT, CODE + "shinycell_read.R"], app)
    c, _ = run([PW_PY, CODE + "shinycell_chunk.py"], app)
    term_page(p, title="Terminal: ShinyCell reads expression one gene (one HDF5 chunk) at a time",
              sub=f"ShinyCell 2.1.0 app built by build.R from bm_demo (8,090 cells x 16,285 genes), $DEMO_ROOT/shinycell/app; run {TODAY}. "
                  "hdf5r in the rtools env (R 4.4.3), h5py 3.16.0 for the chunk index.",
              blocks=[("out", None, ["$ grep -n 'H5File$new\\|h5data$read' server.R   # the generated app opens the file per plot"] + g[:6]
                       + ["", "$ Rscript shinycell_read.R   # the app's own read call for one gene"] + hl(r, ["chunk dims", "h5data$read"])
                       + ["", "$ python shinycell_chunk.py   # which bytes that read touches"] + hl(c, ["Mpo chunk"]))],
              note="Each plot opens sc1gexpr.h5 and reads the genes it shows; with one gene per chunk that is one chunk "
                   "(a fraction of a percent of the file). Metadata (sc1meta.rds) is read whole at start.")
    shot(p, "shinycell", "h01_lazy_one_gene_one_hdf5_chunk.jpg",
         [pv("lazy", "Y", f"terminal, ShinyCell 2.1.0 ({TODAY}): expression is stored one gene per HDF5 chunk and the app's read for one gene touches only that chunk")],
         [(1, "#out0", "server.R reads per plot; the read call; the chunk index"), (2, "[id^=hl0_] >> nth=0", "chunk dims 1 x 8,090: one gene per chunk"),
          (3, "[id^=hl0_] >> nth=-1", "one gene = one chunk of the file"), (4, "#note", "metadata loads whole")],
         software="ShinyCell 2.1.0 (generated app), hdf5r, h5py 3.16.0", driver=DRIVER, data="sc1gexpr.h5 (bm_demo, 8,090 cells x 16,285 genes)",
         url="file://" + app, note="Terminal replay of the app's read path (the call in server.R) outside the running Shiny server.")


def isee(p):
    out, rc = run([RSCRIPT, CODE + "isee_lazy.R"], SCRATCH + "work", env={"RLIB": RLIB, "OUT": SCRATCH + "work", "DEMO_DATA": DATA}, timeout=300)
    out = [ln for ln in out if not ln.startswith(("Tracing function", '[1] "h5mread"'))]
    term_page(p, title="R console: an iSEE input whose assay is an HDF5-backed DelayedArray, read one gene at a time",
              sub=f"iSEE 2.18.0, HDF5Array 1.34.0 (Bioconductor 3.20), R 4.4.3; run {TODAY}. The bone marrow demo's logcounts are written "
                  "to HDF5 as the iSEE bigdata vignette does; h5mread is traced to list every HDF5 read.",
              blocks=[("code", "evidence/screens/gaps/code2/isee_lazy.R", open(CODE + "isee_lazy.R").read()),
                      ("out", None, hl(out, ["file-backed", "object.size", "rows 10420"]))],
              note="iSEE takes such an object unchanged and its panels read assay rows on demand. But the user must build the "
                   "file-backed object in R; the app cannot do it, and colData and reducedDims stay in memory: P.")
    shot(p, "isee", "h01_lazy_hdf5_assay_read_on_demand.jpg",
         [pv("lazy", "P", f"R console, iSEE 2.18.0 / HDF5Array 1.34.0 ({TODAY}): an HDF5-backed assay (2.5 kB in R) is read one gene row on demand; the user must build it in code, so P")],
         [(1, "#code0", "the code: writeHDF5Array, then one gene"), (2, "[id^=hl1_] >> nth=0", "assay is an HDF5Matrix"),
          (3, "[id^=hl1_] >> nth=1", "2.5 kB in R, the matrix stays on disk"), (4, "[id^=hl1_] >> nth=-1", "one HDF5 read of row 10420 (Mpo)"),
          (5, "#note", "built in code, so P")],
         software="iSEE 2.18.0, HDF5Array 1.34.0 (Bioconductor 3.20), R 4.4.3", driver=DRIVER,
         data="bm_demo_sce.rds (8,090 cells), logcounts written to HDF5", url="file://" + SCRATCH + "work",
         note="The audited demo's assay is an in-memory dgCMatrix; this shot builds the file-backed object of the bigdata vignette in an R console (HDF5Array built into a scratch library). The Shiny app was not started.")


def select(p):
    wd = SCRATCH + "work/select"
    os.makedirs(wd, exist_ok=True)
    for f in os.listdir(wd):
        os.remove(os.path.join(wd, f))
    subprocess.run(["cp", CODE + "scanpy_select.py", wd + "/select.py"])
    out, rc = run([PAPER_PY, "-W", "ignore", "select.py", "selection.png"], wd, env={"DEMO_DATA": DATA})
    if rc != 0 or not os.path.exists(wd + "/selection.png"):
        log("select: script failed, no shot")
        return
    term_page(p, title="Code output: in Scanpy a selection is a mask in code, and each view is re-plotted to show it",
              sub=f"scanpy 1.11.5, anndata 0.12.19, matplotlib (Agg), run {TODAY} on bm_demo.h5ad (8,090 cells). There is no lasso: "
                  "the selection is a boolean mask written in code, and the UMAP and FA plots show it only because the script redraws both.",
              blocks=[("code", "select.py (evidence/screens/gaps/code2/scanpy_select.py)", open(CODE + "scanpy_select.py").read()),
                      ("out", None, ["$ python select.py selection.png"] + hl(out, ["selected ", "highlighted in"])),
                      ("img", "selection.png: the same mask drawn on X_umap and X_draw_graph_fa", wd + "/selection.png")],
              note="Selecting cells and seeing them in other plots works only by code: a mask, then one plotting call per view. "
                   "Seurat is the same: CellSelector (satijalab.org/seurat/reference/cellselector) returns the selected cell names, "
                   "which other plots use only through code. P by the code rule.")
    shot(p, "scanpy-seurat", "h04_selection_mask_replotted_by_code.jpg",
         [pv("selection", "P", f"code output, scanpy 1.11.5 ({TODAY}): a selection is a boolean mask typed in code and shows in the UMAP and FA plots only "
                               "because the script re-plots both; Seurat's CellSelector likewise returns cell names used through code, so P")],
         [(1, "#code0", "the selection is a mask written in code"), (2, "[id^=hl1_] >> nth=0", "cells selected by the mask"),
          (3, "#img2", "each view re-plotted by hand with the mask"), (4, "#note", "code only; Seurat CellSelector the same")],
         software="scanpy 1.11.5, anndata 0.12.19 (code; Scanpy has no GUI)", driver=DRIVER, data="bm_demo.h5ad (8,090 cells)", url="file://" + wd)


JOBS = {"scanpy": scanpy, "napari": napari, "shinycell": shinycell, "isee": isee, "select": select}
want = sys.argv[1:] or list(JOBS)
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, channel="chromium")
    page = b.new_page(viewport={"width": 1400, "height": 900})
    for j in want:
        step(j, lambda: JOBS[j](page))
    b.close()
log("done")
