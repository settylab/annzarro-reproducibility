"""Scanpy / Seurat export P (evidence-curator, 2026-10-04): a code-output image, in the style of
notes/comparison/demos/scanpy-seurat/matrix_check.py (matplotlib figure saved as JPEG, sidecar source: manual).
Run with .venv/bin/python <this file> (under gap_run.sh with the other captures).

Left: the code cell that runs sc.pl.umap(..., save="_compartment.png") and what it printed, plus the file it wrote.
Right: that PNG, read back from disk. Boxes are the matplotlib text/axes extents measured after drawing
(Artist.get_window_extent), written to the sidecar by this script, not read off the image by eye.
Seurat is not installed on this laptop, so only Scanpy runs.
"""
import contextlib
import hashlib
import io
import os
import warnings
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import scanpy as sc  # noqa: E402
import anndata as ad  # noqa: E402
import yaml  # noqa: E402
from PIL import Image  # noqa: E402

BM = "$DEMO_ROOT/_data/bm_demo.h5ad"
S = "$TMPDIR/evidence/gap-capture/scanpy_export"
OUT = Path("notes/comparison/screens/scanpy-seurat/g01_export_umap_save_png_by_code.jpg")
DRIVER = "evidence/screens/gaps/capture_scanpy_seurat.py"
TODAY = date.today().isoformat()
os.makedirs(S, exist_ok=True)
for f in os.listdir(S):
    os.remove(os.path.join(S, f))

from importlib.metadata import version
SCV, ADV = version("scanpy"), version("anndata")
a = sc.read_h5ad(BM, backed="r")
code = ['import scanpy as sc',
        f'adata = sc.read_h5ad("bm_demo.h5ad", backed="r")   # {a.n_obs:,} cells',
        f'sc.settings.figdir = "{os.path.basename(S)}/"',
        'sc.pl.umap(adata, color="Compartment", save="_compartment.png", show=False)']
sc.settings.figdir = S
buf = io.StringIO()
sc.settings.logfile = buf  # scanpy's own log line ("saving figure to file ...") goes here
with warnings.catch_warnings(record=True) as w, contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    warnings.simplefilter("always")
    sc.pl.umap(a, color="Compartment", save="_compartment.png", show=False)
plt.close("all")
printed = [ln.replace(S, os.path.basename(S)).strip() for ln in buf.getvalue().splitlines() if ln.strip()]
warned = [str(x.message).splitlines()[0][:150] for x in w if "save" in str(x.message).lower() or "figure" in str(x.message).lower()]
files = sorted(f for f in os.listdir(S) if f.endswith(".png"))
print("printed:", printed, "warnings:", warned, "files:", files)
png = os.path.join(S, files[0]) if files else None
size = os.path.getsize(png) if png else 0
a.file.close()

out_lines = [f"# output ({TODAY}, scanpy {SCV}, anndata {ADV})"] + [ln[:110] for ln in printed[:3]] \
    + [f"Warning: {x[:105]}" for x in warned[:1]] + [f"$ ls -l {os.path.basename(S)}/", f"{files[0] if files else '(no file)'}   {size:,} bytes"]

fig = plt.figure(figsize=(15, 6.4), dpi=90)
axc = fig.add_axes([0.01, 0.02, 0.52, 0.96]); axc.axis("off")
axc.add_patch(plt.Rectangle((0, 0.52), 1, 0.46, color="#f3f4f6", transform=axc.transAxes))
axc.add_patch(plt.Rectangle((0, 0.0), 1, 0.50, color="#111111", transform=axc.transAxes))
axc.text(0.015, 0.95, "In [1]:", family="monospace", fontsize=10, color="#1f5fa8", va="top", transform=axc.transAxes)
code_t = axc.text(0.015, 0.89, "\n".join(code), family="monospace", fontsize=9.2, color="#1d2733", va="top", linespacing=1.6, transform=axc.transAxes)
out_t = axc.text(0.015, 0.47, "\n".join(out_lines), family="monospace", fontsize=9.2, color="#e6e6e6", va="top", linespacing=1.6, transform=axc.transAxes, wrap=True)
axi = fig.add_axes([0.56, 0.04, 0.42, 0.88])
axi.axis("off")
if png:
    axi.imshow(Image.open(png))
axi.set_title(f"{files[0] if files else 'no file'} read back from disk ({size:,} bytes)", fontsize=10)
fig.canvas.draw()
H = fig.canvas.get_width_height()[1]


def ext(artist):
    b = artist.get_window_extent(renderer=fig.canvas.get_renderer())
    return [round(b.x0) - 4, round(H - b.y1) - 4, round(b.width) + 8, round(b.height) + 8]


boxes = {"code": ext(code_t), "out": ext(out_t), "img": ext(axi)}
bio = io.BytesIO()
fig.savefig(bio, format="png", dpi=90)
plt.close(fig)
im = Image.open(bio).convert("RGB")
assert im.size[1] == H, (im.size, H)
im.save(OUT, quality=85)
W = im.size[0]
for k, (x, y, w_, h_) in boxes.items():
    x, y = max(0, x), max(0, y)
    boxes[k] = [x, y, min(w_, W - x), min(h_, H - y)]
meta = {"version": 1, "image": OUT.name, "tool": "scanpy-seurat",
        "software": f"scanpy {SCV}, anndata {ADV} (code output; Seurat not run)",
        "data": f"bm_demo.h5ad ({a.n_obs:,} cells)", "captured": TODAY, "by": "evidence-curator", "driver": DRIVER,
        "source": "manual", "image_sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
        "coordinates": "matplotlib Artist.get_window_extent of the code text, the output text and the image axes, measured by the driver",
        "proves": [{"column": "export", "mark": "P",
                    "caption": f"code output, scanpy {SCV} ({TODAY}): a plot is written to an image file only by code, sc.pl.umap(..., save=...) or plt.savefig; there is no GUI, so P"}],
        "callouts": [{"n": 1, "box": boxes["code"], "label": "the export is a line of code: sc.pl.umap(..., save='_compartment.png')"},
                     {"n": 2, "box": boxes["out"], "label": f"what it printed, and the file it wrote ({size:,} bytes)"},
                     {"n": 3, "box": boxes["img"], "label": "the written PNG, read back"}]}
OUT.with_name(OUT.stem + ".annot.yaml").write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=100))
print("wrote", OUT, boxes)
