#!/usr/bin/env python
"""Procedure Steps 5-10 of the AnnZarro protocol: turn the Kompot-processed h5ad
into an AnnZarro-ready Zarr (v2) store.

  Step 5  load, discover Kompot output keys from uns[...]['last_run_info']['field_names']
  Step 6  cell x cell matrices in obsp (sparse kernel already there; add a dense
          multi-step diffusion affinity for the "kernel walk" view)
  Step 7  gene x gene Spearman correlation of Kompot-smoothed expression in varp
  Step 8  X -> CSC (fast gene-column reads)
  Step 9  write Zarr format 2
  Step 10 rewrite dense layers / obsp / varp as float32 with (1024, 1024) chunks,
          then RE-CONSOLIDATE metadata (mandatory, see VALIDATION.md)

Usage:
    python data_prep/prepare_annzarro_store.py \
        --input data/murine_bone_marrow_aging_processed.h5ad \
        --output data/bm_aging.zarr
"""
import argparse
import json
import shutil
import time
from pathlib import Path

import anndata as ad
import numpy as np
import scipy.sparse as sp
import zarr
from scipy.stats import rankdata

TIMINGS = {}


def kompot_field_names(adata, kind):
    """uns[kind]['last_run_info'] is a JSON *string* in kompot 0.8 (dict in older
    versions); decode it before indexing ['field_names']."""
    info = adata.uns[kind]["last_run_info"]
    if isinstance(info, (str, bytes)):
        info = json.loads(info)
    return dict(info["field_names"])


def step(name):
    """Context manager that records wall time for a step."""
    class _T:
        def __enter__(self):
            self.t = time.perf_counter()
            print(f"\n=== {name} ===", flush=True)

        def __exit__(self, *a):
            dt = time.perf_counter() - self.t
            TIMINGS[name] = round(dt, 2)
            print(f"--- {name}: {dt:.1f} s", flush=True)
    return _T()


def spearman_columns(S):
    """Spearman correlation between the columns (genes) of S (rows = observations).
    Constant columns (rank std 0) would give NaN; they are set to all-zero so their
    correlation is 0 (the diagonal entry too) and the varp contains no NaN."""
    t = time.perf_counter()
    R = rankdata(S, axis=0).astype(np.float32)
    print(f"  rankdata {S.shape}: {time.perf_counter()-t:.1f} s")
    sd = R.std(0)
    const = sd == 0
    print(f"  constant genes (std 0 -> would be NaN): {int(const.sum())}")
    R -= R.mean(0)
    R /= np.where(const, 1.0, sd)
    t = time.perf_counter()
    C = (R.T @ R) / np.float32(R.shape[0])
    print(f"  R.T @ R: {time.perf_counter()-t:.1f} s; peak extra memory ~ {R.nbytes/1e9 + C.nbytes/1e9:.1f} GB")
    del R
    np.clip(C, -1.0, 1.0, out=C)
    assert C.dtype == np.float32 and not np.isnan(C).any()
    return C, dict(n_constant=int(const.sum()), shape=list(C.shape))


def describe(m):
    if sp.issparse(m):
        return f"{type(m).__name__} {m.shape} {m.dtype} nnz={m.nnz}"
    return f"{type(m).__name__} {getattr(m, 'shape', None)} {getattr(m, 'dtype', None)}"


def dir_size(p):
    return sum(f.stat().st_size for f in Path(p).rglob("*") if f.is_file())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default="data/murine_bone_marrow_aging_processed.h5ad")
    ap.add_argument("--output", default="data/bm_aging.zarr")
    ap.add_argument("--chunks", type=int, nargs=2, default=(1024, 1024))
    ap.add_argument("--walk-steps", type=int, default=None,
                    help="t for the dense T^t diffusion affinity (default: chosen automatically)")
    ap.add_argument("--no-dense-walk", action="store_true", help="skip the dense obsp affinity")
    ap.add_argument("--no-fc-corr", action="store_true", help="skip varp['spearman_fold_change']")
    ap.add_argument("--report", default=None, help="write a JSON report (keys, timings) here")
    args = ap.parse_args()
    chunks = tuple(args.chunks)
    report = {}

    # ------------------------------------------------------------------ Step 5
    with step("step5_load_and_discover"):
        adata = ad.read_h5ad(args.input)
        print(adata)
        de_fields = kompot_field_names(adata, "kompot_de")
        da_fields = kompot_field_names(adata, "kompot_da")
        print("kompot_de field_names:", json.dumps(de_fields, indent=1, default=str))
        print("kompot_da field_names:", json.dumps(da_fields, indent=1, default=str))
        for slot in ("layers", "obsp", "varp"):
            for k, v in getattr(adata, slot).items():
                print(f"  {slot}[{k!r}]: {describe(v)}")
        # discovered keys (no hard-coding of condition names)
        FC_KEY = de_fields["fold_change_key"]
        SMOOTH_KEYS = [de_fields["smoothed_key_1"], de_fields["smoothed_key_2"]]
        LFC_KEY = de_fields["mean_lfc_key"]
        MAHAL_KEY = de_fields["mahalanobis_key"]
        DA_Z_KEY = da_fields["zscore_key"]
        for k in [FC_KEY, *SMOOTH_KEYS]:
            assert k in adata.layers, f"layer {k} missing - was kompot.cleanup() run?"
        for k in (LFC_KEY, MAHAL_KEY):
            assert k in adata.var, k
        assert DA_Z_KEY in adata.obs, DA_Z_KEY
        report["discovered"] = dict(FC_KEY=FC_KEY, SMOOTH_KEYS=SMOOTH_KEYS, LFC_KEY=LFC_KEY,
                                    MAHAL_KEY=MAHAL_KEY, DA_Z_KEY=DA_Z_KEY,
                                    DA_LFC_KEY=da_fields["lfc_key"],
                                    IS_DE_KEY=de_fields.get("is_de_key"))
        print("discovered:", report["discovered"])

    # ------------------------------------------------------------------ Step 6
    with step("step6_obsp_kernel"):
        if "DM_Kernel" not in adata.obsp and "connectivities" not in adata.obsp:
            # only needed if the input lacks a kernel
            import palantir
            palantir.utils.run_diffusion_maps(adata, pca_key="X_pca_harmony", n_components=40)
        print("obsp present:", list(adata.obsp.keys()))
        if not args.no_dense_walk:
            # Row-stochastic transition matrix T (palantir stores it as DM_Similarity);
            # recompute from the kernel so we do not depend on that convention.
            K = sp.csr_matrix(adata.obsp["DM_Kernel"], dtype=np.float64)
            d = np.asarray(K.sum(1)).ravel()
            T = sp.diags(1.0 / d) @ K
            # Choose t so a walk from a typical cell covers a few hundred cells:
            # the effective support 1/sum(p^2) of row i of T^t.
            rng = np.random.default_rng(0)
            probe = rng.choice(adata.n_obs, 200, replace=False)
            P = np.zeros((len(probe), adata.n_obs))
            P[np.arange(len(probe)), probe] = 1.0
            support = {}
            for t in range(1, 33):
                P = (T.T @ P.T).T  # P <- P T
                support[t] = float(np.median(1.0 / (P ** 2).sum(1)))
            print("median effective support of T^t rows:",
                  {t: round(s) for t, s in support.items() if t in (1, 2, 4, 8, 12, 16, 24, 32)})
            t_walk = args.walk_steps or min(t for t, s in support.items() if s >= 300)
            print(f"using t = {t_walk}")
            W = T.toarray()
            M = W.copy()
            for _ in range(t_walk - 1):
                M = M @ W
            M = M.astype(np.float32)
            WALK_KEY = f"diffusion_walk_t{t_walk}"
            adata.obsp[WALK_KEY] = M
            report["walk"] = dict(key=WALK_KEY, t=t_walk, support_median=support)
            del W, M

    # ------------------------------------------------------------------ Step 7
    with step("step7_varp_spearman"):
        # (a) smoothed expression, both conditions stacked (cells_Young ; cells_Old):
        #     co-variation along the cell-state manifold -> mostly lineage programs.
        S = np.vstack([np.asarray(adata.layers[k], dtype=np.float32) for k in SMOOTH_KEYS])
        C, info = spearman_columns(S)
        del S
        adata.varp["spearman_smoothed"] = C
        report["spearman_smoothed"] = info
        del C
        if not args.no_fc_corr:
            # (b) Kompot fold-change layer: genes whose AGE EFFECT co-varies across
            #     cell states -> co-regulated ageing responses (e.g. MHC-I/II modules).
            C, info = spearman_columns(np.asarray(adata.layers[FC_KEY], dtype=np.float32))
            adata.varp["spearman_fold_change"] = C
            report["spearman_fold_change"] = info
            del C

    # ------------------------------------------------------------------ Step 8
    with step("step8_X_to_csc"):
        print("X before:", describe(adata.X))
        adata.X = sp.csc_matrix(adata.X)
        print("X after:", describe(adata.X))

    # ------------------------------------------------------------------ Step 9
    with step("step9_write_zarr_v2"):
        if Path(args.output).exists():
            shutil.rmtree(args.output)
        ad.settings.zarr_write_format = 2
        adata.write_zarr(args.output)
        print(f"wrote {args.output}: {dir_size(args.output)/1e9:.2f} GB")

    # ------------------------------------------------------------------ Step 10
    with step("step10_rechunk_float32"):
        # use_consolidated=False is REQUIRED: write_zarr consolidates metadata and
        # zarr refuses to edit a consolidated store otherwise.
        g = zarr.open_group(args.output, mode="r+", use_consolidated=False)
        rewritten = []
        for slot in ("layers", "obsp", "varp"):
            for key, arr in getattr(adata, slot).items():
                if sp.issparse(arr) or np.ndim(arr) != 2:
                    continue
                t = time.perf_counter()
                ad.io.write_elem(g[slot], key, np.asarray(arr, dtype=np.float32),
                                 dataset_kwargs={"chunks": chunks})
                rewritten.append(f"{slot}/{key}")
                print(f"  rewrote {slot}/{key} {np.shape(arr)}: {time.perf_counter()-t:.1f} s")
        # REQUIRED: refresh .zmetadata, otherwise readers see the old dtype/chunks
        zarr.consolidate_metadata(args.output)
        report["rewritten"] = rewritten

    # ------------------------------------------------------------------ verify
    with step("verify"):
        root = zarr.open_group(args.output, mode="r")
        rows = []
        for slot in ("X", "layers", "obsp", "varp", "obsm"):
            if slot not in root:
                continue
            items = [("X", root["X"])] if slot == "X" else list(root[slot].members())
            for name, node in items:
                path = "X" if slot == "X" else f"{slot}/{name}"
                attrs = dict(node.attrs)
                enc = attrs.get("encoding-type")
                if isinstance(node, zarr.Group) and enc in ("csr_matrix", "csc_matrix"):
                    shape, dtype, ch = tuple(attrs["shape"]), node["data"].dtype, node["data"].chunks
                elif isinstance(node, zarr.Group):  # e.g. dataframe-encoded obsm
                    shape, dtype, ch = (), "group", ()
                else:
                    shape, dtype, ch = node.shape, node.dtype, node.chunks
                rows.append(dict(path=path, encoding=enc, shape=list(shape), dtype=str(dtype),
                                 chunks=list(ch), bytes=dir_size(Path(args.output) / path)))
        for r in rows:
            print(f"  {r['path']:<55} {r['encoding']:<11} {str(tuple(r['shape'])):<16} {r['dtype']:<8} "
                  f"chunks={tuple(r['chunks'])!s:<14} {r['bytes']/1e6:9.1f} MB")
        report["arrays"] = rows
        report["store_bytes"] = dir_size(args.output)
        print(f"store total: {report['store_bytes']/1e9:.2f} GB")
        # round-trip through anndata to prove the store is readable
        b = ad.read_zarr(args.output)
        assert b.layers[FC_KEY].dtype == np.float32
        assert np.allclose(b.varp["spearman_smoothed"][:5, :5],
                           np.asarray(adata.varp["spearman_smoothed"][:5, :5]))
        print("anndata.read_zarr round trip OK:", b.shape)

    report["timings_s"] = TIMINGS
    print("\nTimings (s):", json.dumps(TIMINGS, indent=1))
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1, default=str))


if __name__ == "__main__":
    main()
