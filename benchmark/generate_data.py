#!/usr/bin/env python
"""Generate synthetic, structured AnnData zarr stores for the AnnZarro benchmark.

All stores are written in zarr format v2 (AnnZarro's reader requires
``.zgroup``/``.zarray`` metadata) with anndata's default compressor
(Blosc lz4, clevel 5, byte shuffle).  Data are deterministic given ``--seed``.

The values are not random noise.  Every matrix is a smooth function of a
low-dimensional latent cell state, so that compression ratios resemble real
derived data (Kompot fold-change / smoothed layers, Gaussian kernels, gene
correlation matrices, UMI counts):

* latent cell state ``Z`` (n x 10): 20 clusters, each a curved trajectory.
* dense layer ``fc``  (cells x genes, float32): ``tanh(Z W) + N(0, 0.05)``,
  i.e. a smooth fold-change-like surface with measurement-level noise.
* dense ``obsp/kernel_*`` (cells x cells, float32): Gaussian kernel on ``Z``
  with a length scale that puts the median kernel value at 1e-3.
* dense ``varp/corr_*`` (genes x genes, float32): correlation matrix from
  rank-30 gene loadings plus gene-specific noise.
* sparse ``obsp/connectivities`` (CSR): symmetrised 15-NN graph on ``Z``.
* sparse ``X`` (cells x 20,000 genes): UMI-like counts with gene-specific
  detection rates (mean density 5 %, ~1,000 detected genes per cell).

Dataset families (sub-commands)::

    scale    data/bench/scale/cells_<n>.zarr   obs, var, obsm/X_umap,
             obsp/connectivities, layers/fc (5,000 genes, --chunks)
    sweep    data/bench/sweep/n<n>/<tag>.zarr  layers/fc at one chunk shape each
    obsp     data/bench/pairwise/obsp_<n>.zarr obsp/kernel_<tag> (dense, n x n)
    varp     data/bench/pairwise/varp_<g>.zarr varp/corr_<tag> (dense, g x g)
    sparse   data/bench/sparse/X_<n>_<csr|csc>.zarr  sparse X

Run ``python generate_data.py all`` to build everything used in the laptop
benchmark, or a sub-command for one family (see ``--help``).  The ``obsp`` and
``varp`` families are kept for completeness but were not run for the paper:
dense pairwise matrices are benchmarked on real data in ``benchmark/hpc``.

Chunk tags: ``default`` means
"let zarr/anndata choose" (what ``AnnData.write_zarr`` does), ``c<h>x<w>``
means explicit chunks (h, w); ``h`` may be ``N`` meaning all rows.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
import warnings
from pathlib import Path

import anndata as ad
import numcodecs
import numpy as np
import pandas as pd
import scipy.sparse as sp
import zarr

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
ad.settings.zarr_write_format = 2

ROOT = Path(__file__).resolve().parents[1] / "data" / "bench"
SEED = 20261001
N_LATENT = 10
N_CLUSTERS = 20
# anndata's default compressor for zarr v2 output
COMPRESSOR = numcodecs.Blosc(cname="lz4", clevel=5, shuffle=numcodecs.Blosc.SHUFFLE)
ARRAY_ATTRS = {"encoding-type": "array", "encoding-version": "0.2.0"}
NOISE_BLOCK = 1024  # rows per independently-seeded noise block (chunk-shape independent)

SCALE_SIZES = [10_000, 30_000, 100_000, 300_000, 1_000_000]
SCALE_GENES = 5_000
SWEEP_TAGS = [
    "default", "c1024x1024", "cNx64", "c4096x256", "c256x4096", "c2048x128",
    "c1024x64", "c512x32", "c256x16", "c4096x16", "c256x256",
]
OBSP_SIZES = [5_000, 10_000, 20_000, 50_000]
OBSP_TAGS = ["default", "c1024x1024", "c64xN"]
OBSP_SWEEP_N = 20_000
OBSP_SWEEP_TAGS = ["c4096x4096", "c256xN", "c16xN"]
VARP_SIZES = [2_000, 5_000, 10_000, 20_000]
VARP_TAGS = ["default", "c1024x1024", "c64xN"]
SPARSE_SIZES = [100_000, 1_000_000]
SPARSE_GENES = 20_000


# --------------------------------------------------------------------------- utils
def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def parse_tag(tag: str, shape: tuple[int, int]):
    """Chunk tag -> chunks tuple (None for zarr's default guess)."""
    if tag == "default":
        return None
    h, w = tag[1:].split("x")
    h = shape[0] if h == "N" else int(h)
    w = shape[1] if w == "N" else int(w)
    return (min(h, shape[0]), min(w, shape[1]))


def rng_for(seed: int, *keys: int) -> np.random.Generator:
    return np.random.default_rng([seed, *keys])


def latent_cells(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Latent state Z (n x 10, float32) and cluster labels.

    Cells lie on 20 curved 1-D trajectories in 10-D with small spread.
    """
    rng = rng_for(seed, 1, n)
    centers = rng.normal(0, 3.0, size=(N_CLUSTERS, N_LATENT))
    dirs = rng.normal(0, 1.0, size=(N_CLUSTERS, N_LATENT))
    curv = rng.normal(0, 0.5, size=(N_CLUSTERS, N_LATENT))
    weights = rng.dirichlet(np.full(N_CLUSTERS, 2.0))
    lab = rng.choice(N_CLUSTERS, size=n, p=weights)
    t = rng.uniform(-1, 1, size=(n, 1))
    z = centers[lab] + t * dirs[lab] + t**2 * curv[lab] + rng.normal(0, 0.3, size=(n, N_LATENT))
    return z.astype(np.float32), lab.astype(np.int32)


def gene_loadings(g: int, seed: int) -> np.ndarray:
    rng = rng_for(seed, 2, g)
    return (rng.normal(0, 1, size=(N_LATENT, g)) / np.sqrt(N_LATENT) * 0.3).astype(np.float32)


def block_noise(a: int, b: int, ncol: int, sigma: float, seed: int, key: int) -> np.ndarray:
    """Gaussian noise for rows [a, b) that does not depend on the write blocking."""
    out = np.empty((b - a, ncol), dtype=np.float32)
    first, last = a // NOISE_BLOCK, (b - 1) // NOISE_BLOCK
    for blk in range(first, last + 1):
        r0, r1 = blk * NOISE_BLOCK, (blk + 1) * NOISE_BLOCK
        noise = rng_for(seed, key, blk).standard_normal((NOISE_BLOCK, ncol), dtype=np.float32)
        s0, s1 = max(a, r0), min(b, r1)
        out[s0 - a:s1 - a] = noise[s0 - r0:s1 - r0] * sigma
    return out


def skeleton(path: Path, n_obs: int, n_vars: int, z: np.ndarray | None, lab: np.ndarray | None,
             obsm: dict | None = None, obsp: dict | None = None, X=None) -> None:
    """Write obs/var (+ optional obsm/obsp/X) with anndata, zarr v2."""
    obs = pd.DataFrame(index=pd.Index([f"cell_{i:07d}" for i in range(n_obs)], dtype=str))
    if z is not None:
        score = z[:, 0]
        obs["score"] = ((score - score.mean()) / score.std()).astype(np.float32)
        obs["cluster"] = pd.Categorical([f"cluster_{c:02d}" for c in lab])
    var = pd.DataFrame(index=pd.Index([f"gene_{j:05d}" for j in range(n_vars)], dtype=str))
    adata = ad.AnnData(X=X, obs=obs, var=var, obsm=obsm or {}, obsp=obsp or {})
    if path.exists():
        shutil.rmtree(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    adata.write_zarr(path)


def umap_like(z: np.ndarray, seed: int) -> np.ndarray:
    proj = rng_for(seed, 3).normal(size=(N_LATENT, 2)).astype(np.float32)
    return (z @ proj).astype(np.float32)


def write_dense(path: Path, key: str, shape: tuple[int, int], chunks, fill, block_rows: int | None = None) -> dict:
    """Create a dense float32 array at ``path/key`` and fill it by row blocks.

    ``fill(a, b)`` returns rows [a, b) as float32.  Returns array info.
    """
    root = zarr.open_group(str(path), mode="a", zarr_format=2)
    parent, name = key.rsplit("/", 1)
    grp = root.require_group(parent)
    if name in grp:
        del grp[name]
    kwargs = dict(name=name, shape=shape, dtype="f4", compressors=COMPRESSOR, fill_value=0.0,
                  attributes=ARRAY_ATTRS)
    if chunks is not None:
        kwargs["chunks"] = chunks
    arr = grp.create_array(**kwargs)
    ch = arr.chunks[0]
    if block_rows is None:
        # ~512 MB blocks, a whole number of chunk rows
        target = max(1, (512 * 2**20) // (shape[1] * 4))
        block_rows = max(ch, (target // ch) * ch)
    t0 = time.time()
    for a in range(0, shape[0], block_rows):
        b = min(shape[0], a + block_rows)
        arr[a:b, :] = fill(a, b)
    zarr.consolidate_metadata(str(path), zarr_format=2)
    log(f"  wrote {path.name}/{key} shape={shape} chunks={arr.chunks} in {time.time() - t0:.1f}s")
    return {"key": key, "shape": list(shape), "chunks": list(arr.chunks)}


def du_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def record(path: Path, info: dict) -> None:
    """Append dataset metadata to data/bench/manifest.json."""
    man_path = ROOT / "manifest.json"
    man = json.loads(man_path.read_text()) if man_path.exists() else {}
    info = dict(info, disk_bytes=du_bytes(path), path=str(path))
    man[str(path.relative_to(ROOT))] = info
    man_path.write_text(json.dumps(man, indent=1, sort_keys=True))


# ---------------------------------------------------------------------- generators
def layer_fill(z: np.ndarray, w: np.ndarray, seed: int):
    def fill(a, b):
        out = 2.0 * np.tanh(z[a:b] @ w)  # log2 fold-change-like, range (-2, 2)
        out += block_noise(a, b, w.shape[1], 0.05, seed, 11)
        return out.astype(np.float32, copy=False)
    return fill


def knn_connectivities(z: np.ndarray, k: int = 15) -> sp.csr_matrix:
    from scipy.spatial import cKDTree
    n = z.shape[0]
    tree = cKDTree(z)
    d, idx = tree.query(z, k=k + 1, workers=-1)
    d, idx = d[:, 1:], idx[:, 1:]
    sigma = np.median(d[:, -1])
    w = np.exp(-(d / sigma) ** 2).astype(np.float32)
    a = sp.csr_matrix((w.ravel(), idx.ravel(), np.arange(0, n * k + 1, k)), shape=(n, n))
    a = a.maximum(a.T).tocsr()
    a.sort_indices()
    return a.astype(np.float32)


def make_scale(n: int, chunks_tag: str, seed: int) -> None:
    path = ROOT / "scale" / f"cells_{n}.zarr"
    log(f"scale n={n} -> {path}")
    z, lab = latent_cells(n, seed)
    conn = knn_connectivities(z)
    skeleton(path, n, SCALE_GENES, z, lab, obsm={"X_umap": umap_like(z, seed)},
             obsp={"connectivities": conn})
    shape = (n, SCALE_GENES)
    info = write_dense(path, "layers/fc", shape, parse_tag(chunks_tag, shape),
                       layer_fill(z, gene_loadings(SCALE_GENES, seed), seed))
    record(path, {"family": "scale", "n_cells": n, "n_genes": SCALE_GENES, "layer": info,
                  "chunk_tag": chunks_tag, "knn_nnz": int(conn.nnz)})


def make_sweep(n: int, tags: list[str], seed: int) -> None:
    z, lab = latent_cells(n, seed)
    w = gene_loadings(SCALE_GENES, seed)
    shape = (n, SCALE_GENES)
    for tag in tags:
        path = ROOT / "sweep" / f"n{n}" / f"{tag}.zarr"
        log(f"sweep n={n} tag={tag} -> {path}")
        skeleton(path, n, SCALE_GENES, z, lab)
        info = write_dense(path, "layers/fc", shape, parse_tag(tag, shape), layer_fill(z, w, seed))
        record(path, {"family": "sweep", "n_cells": n, "n_genes": SCALE_GENES, "layer": info,
                      "chunk_tag": tag})


def kernel_fill(z: np.ndarray, seed: int):
    zz = z.astype(np.float64)
    sq = (zz**2).sum(1)
    rng = rng_for(seed, 4)
    i = rng.integers(0, len(z), 20_000)
    j = rng.integers(0, len(z), 20_000)
    med = np.median(((zz[i] - zz[j]) ** 2).sum(1))
    two_ls2 = med / np.log(1000.0)  # median kernel value = 1e-3

    def fill(a, b):
        d2 = sq[a:b, None] + sq[None, :] - 2.0 * zz[a:b] @ zz.T
        np.maximum(d2, 0, out=d2)
        return np.exp(-d2 / two_ls2).astype(np.float32)
    return fill


def make_obsp(n: int, tags: list[str], seed: int) -> None:
    path = ROOT / "pairwise" / f"obsp_{n}.zarr"
    log(f"obsp n={n} -> {path}")
    z, lab = latent_cells(n, seed)
    skeleton(path, n, 100, z, lab, obsm={"X_umap": umap_like(z, seed)})
    infos = []
    for tag in tags:
        shape = (n, n)
        infos.append(write_dense(path, f"obsp/kernel_{tag}", shape, parse_tag(tag, shape),
                                 kernel_fill(z, seed), block_rows=None))
    record(path, {"family": "obsp", "n_cells": n, "arrays": infos, "chunk_tags": tags})


def corr_fill(g: int, seed: int):
    rng = rng_for(seed, 5, g)
    load = rng.normal(0, 1, size=(g, 30)) * rng.gamma(1.0, 1.0, size=(1, 30))
    load = np.hstack([load, rng.normal(0, 1.5, size=(g, 1))])  # gene-specific variance
    load /= np.linalg.norm(load, axis=1, keepdims=True)
    load_r = load[:, :30]

    def fill(a, b):
        c = load_r[a:b] @ load_r.T
        out = c.astype(np.float32)
        # exact self-correlation on the diagonal
        idx = np.arange(a, b)
        out[idx - a, idx] = 1.0
        return out
    return fill


def make_varp(g: int, tags: list[str], seed: int) -> None:
    path = ROOT / "pairwise" / f"varp_{g}.zarr"
    log(f"varp g={g} -> {path}")
    skeleton(path, 100, g, None, None)
    infos = []
    for tag in tags:
        shape = (g, g)
        infos.append(write_dense(path, f"varp/corr_{tag}", shape, parse_tag(tag, shape), corr_fill(g, seed)))
    record(path, {"family": "varp", "n_genes": g, "arrays": infos, "chunk_tags": tags})


def sparse_counts(n: int, g: int, seed: int) -> sp.csr_matrix:
    """UMI-like counts, CSR, mean density 5 %."""
    rng = rng_for(seed, 6, g)
    p_gene = rng.lognormal(0, 1.2, size=g)
    p_gene = np.clip(p_gene / p_gene.mean() * 0.05, 0, 0.95).astype(np.float32)
    lam = (p_gene * 20).astype(np.float32)
    blocks = []
    block = 20_000
    for bi, a in enumerate(range(0, n, block)):
        b = min(n, a + block)
        r = rng_for(seed, 7, bi)
        size = r.lognormal(0, 0.3, size=(b - a, 1)).astype(np.float32)
        mask = r.random((b - a, g), dtype=np.float32) < np.minimum(p_gene[None, :] * size, 0.98)
        rows, cols = np.nonzero(mask)
        vals = (1 + r.poisson(lam[cols])).astype(np.float32)
        blocks.append(sp.csr_matrix((vals, (rows, cols)), shape=(b - a, g), dtype=np.float32))
    x = sp.vstack(blocks, format="csr")
    x.sort_indices()
    return x


def make_sparse(n: int, seed: int) -> None:
    log(f"sparse n={n}: generating counts")
    x = sparse_counts(n, SPARSE_GENES, seed)
    log(f"  nnz={x.nnz:,} density={x.nnz / (n * SPARSE_GENES):.3f}")
    for layout in ["csr", "csc"]:
        path = ROOT / "sparse" / f"X_{n}_{layout}.zarr"
        mat = x if layout == "csr" else x.tocsc()
        t0 = time.time()
        skeleton(path, n, SPARSE_GENES, None, None, X=mat)
        log(f"  wrote {path.name} in {time.time() - t0:.1f}s")
        data_chunks = zarr.open_group(str(path), mode="r")["X/data"].chunks
        gene_nnz = np.diff(x.tocsc().indptr) if layout == "csc" else None
        rec = {"family": "sparse", "n_cells": n, "n_genes": SPARSE_GENES, "layout": layout,
               "nnz": int(x.nnz), "data_chunks": list(data_chunks)}
        if gene_nnz is not None:
            np.save(path.with_suffix(".gene_nnz.npy"), gene_nnz)
        record(path, rec)
        del mat


def check_default_chunks() -> dict:
    """Confirm that 'default' equals what AnnData.write_zarr itself chooses."""
    path = ROOT / "_check_default.zarr"
    a = ad.AnnData(obs=pd.DataFrame(index=[str(i) for i in range(100_000)]),
                   var=pd.DataFrame(index=[str(i) for i in range(5_000)]))
    a.layers["fc"] = np.zeros((100_000, 5_000), dtype=np.float32)
    a.write_zarr(path)
    got = zarr.open_group(str(path), mode="r")["layers/fc"]
    out = {"anndata_chunks_100000x5000": list(got.chunks), "compressor": str(got.compressors)}
    shutil.rmtree(path)
    log(f"anndata default chunks: {out}")
    return out


# ---------------------------------------------------------------------------- CLI
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("family", choices=["all", "scale", "sweep", "obsp", "varp", "sparse", "check"])
    p.add_argument("--sizes", type=int, nargs="*", help="override sizes for the family")
    p.add_argument("--tags", nargs="*", help="override chunk tags (sweep/obsp/varp)")
    p.add_argument("--chunks", default="c2048x32", help="chunk tag for the scale-family layer")
    p.add_argument("--seed", type=int, default=SEED)
    a = p.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    fams = ["sweep", "scale", "sparse"] if a.family == "all" else [a.family]
    for fam in fams:
        if fam == "check":
            check_default_chunks()
        elif fam == "scale":
            for n in a.sizes or SCALE_SIZES:
                make_scale(n, a.chunks, a.seed)
        elif fam == "sweep":
            for n in a.sizes or [100_000]:
                make_sweep(n, a.tags or SWEEP_TAGS, a.seed)
        elif fam == "obsp":
            for n in a.sizes or OBSP_SIZES:
                tags = a.tags or (OBSP_TAGS + (OBSP_SWEEP_TAGS if n == OBSP_SWEEP_N else []))
                make_obsp(n, tags, a.seed)
        elif fam == "varp":
            for g in a.sizes or VARP_SIZES:
                make_varp(g, a.tags or VARP_TAGS, a.seed)
        elif fam == "sparse":
            for n in a.sizes or SPARSE_SIZES:
                make_sparse(n, a.seed)


if __name__ == "__main__":
    main()
