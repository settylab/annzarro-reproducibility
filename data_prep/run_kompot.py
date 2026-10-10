#!/usr/bin/env python
"""Reproduce the Kompot getting-started tutorial (examples/01_getting_started.ipynb,
kompot 0.8) as a script and write the processed h5ad used by the AnnZarro protocol.

Deviations from the notebook, all deliberate:
  * We do NOT call kompot.cleanup(adata) before writing. The notebook removes the
    imputed (smoothed) and fold-change layers to save space; the AnnZarro protocol
    needs exactly those layers (fold-change layer, per-condition smoothed expression).
  * Plotting and STRING enrichment cells are skipped (no effect on stored results).
  * A fixed numpy seed is set for reproducibility of landmark selection.

Usage:
    python data_prep/run_kompot.py \
        --input data/murine_bone_marrow_aging.h5ad \
        --output data/murine_bone_marrow_aging_processed.h5ad
"""
import argparse
import json
import time
from pathlib import Path

import anndata as ad
import numpy as np

# Tutorial configuration (cell 2 of 01_getting_started.ipynb)
GROUPING_COLUMN = "Age"
CONDITIONS = ["Young", "Old"]  # first condition is the reference
DIMENSIONALITY_REDUCTION = "DM_EigenVectors"
LAYER_FOR_EXPRESSION = "logged_counts"
PCA_KEY = "X_pca_harmony"
N_DM_COMPONENTS = 40


def kompot_field_names(adata, kind):
    """uns[kind]['last_run_info'] is a JSON *string* in kompot 0.8 (dict in older
    versions); decode it before indexing ['field_names']."""
    info = adata.uns[kind]["last_run_info"]
    if isinstance(info, (str, bytes)):
        info = json.loads(info)
    return dict(info["field_names"])


def log(msg, t0=None):
    s = f"[{time.strftime('%H:%M:%S')}] {msg}"
    if t0 is not None:
        s += f"  ({time.perf_counter() - t0:.1f} s)"
    print(s, flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/murine_bone_marrow_aging.h5ad")
    p.add_argument("--output", default="data/murine_bone_marrow_aging_processed.h5ad")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--timings", default=None, help="optional JSON file to write step timings")
    args = p.parse_args()

    np.random.seed(args.seed)
    import kompot
    import palantir

    timings = {}
    T = time.perf_counter()

    t0 = time.perf_counter()
    adata = ad.read_h5ad(args.input)
    timings["read_h5ad"] = time.perf_counter() - t0
    log(f"loaded {adata.n_obs} cells x {adata.n_vars} genes", t0)
    log(f"conditions: {adata.obs[GROUPING_COLUMN].value_counts().to_dict()}")

    # Diffusion maps (tutorial: palantir.utils.run_diffusion_maps(adata, pca_key=..., n_components=40))
    t0 = time.perf_counter()
    palantir.utils.run_diffusion_maps(adata, pca_key=PCA_KEY, n_components=N_DM_COMPONENTS)
    timings["diffusion_maps"] = time.perf_counter() - t0
    log("diffusion maps done; obsp keys: " + ", ".join(adata.obsp.keys()), t0)

    # Differential abundance (tutorial defaults)
    t0 = time.perf_counter()
    kompot.da(
        adata,
        groupby=GROUPING_COLUMN,
        condition1=CONDITIONS[0],
        condition2=CONDITIONS[1],
        obsm_key=DIMENSIONALITY_REDUCTION,
    )
    timings["kompot_da"] = time.perf_counter() - t0
    log("kompot.da done", t0)

    # Differential expression (tutorial: GPSettings(batch_size=0))
    t0 = time.perf_counter()
    kompot.de(
        adata,
        groupby=GROUPING_COLUMN,
        condition1=CONDITIONS[0],
        condition2=CONDITIONS[1],
        layer=LAYER_FOR_EXPRESSION,
        obsm_key=DIMENSIONALITY_REDUCTION,
        gp=kompot.GPSettings(batch_size=0),
    )
    timings["kompot_de"] = time.perf_counter() - t0
    log("kompot.de done", t0)

    # Report what Kompot recorded (this is what Procedure Step 5 discovers)
    for kind in ("kompot_da", "kompot_de"):
        fn = kompot_field_names(adata, kind)
        log(f"{kind} field_names:\n" + json.dumps({k: v for k, v in fn.items()}, indent=2, default=str))

    # NOTE: no kompot.cleanup(adata) -- the protocol needs the imputed/fold-change layers.
    t0 = time.perf_counter()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(args.output)
    timings["write_h5ad"] = time.perf_counter() - t0
    timings["total"] = time.perf_counter() - T
    log(f"wrote {args.output} ({Path(args.output).stat().st_size / 1e9:.2f} GB)", t0)
    log("timings (s): " + json.dumps({k: round(v, 1) for k, v in timings.items()}))
    if args.timings:
        Path(args.timings).write_text(json.dumps(timings, indent=2))


if __name__ == "__main__":
    main()
