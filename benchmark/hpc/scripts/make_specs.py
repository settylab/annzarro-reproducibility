#!/usr/bin/env python
"""Write the case specs (JSON) consumed by bench_http.py / bench_raw.py.

Shapes and chunk sizes are read from each store's .zarray metadata, so the specs
always describe the store actually being benchmarked.

Usage: make_specs.py <spec-name> <out.json> [--root DIR] [--fs LABEL]
"""
import argparse
import json
import os
import re

LIVER = "$DATA_ROOT/lab-data/data/processed_zarr"
BENCH = "$SCRATCH/annzarro-bench"
ANNZARRO_DIR = os.path.join(BENCH, "src", "annzarro")


def zarray(store, arr):
    return json.load(open(os.path.join(store, arr, ".zarray")))


def n_obs_vars(store):
    """n_obs from obs/_index, n_vars from var/_index (AnnData zarr v2 layout)."""
    return (zarray(store, "obs/_index")["shape"][0], zarray(store, "var/_index")["shape"][0])


def cases_for(store, fs, tag, *, x=True, sparse_layers=(), dense_layers=(), dense_rows=True,
              obsm=(), obs=(), obsp_csr=(), obsp_dense=(), varp_dense=(), cells=True):
    if not os.path.isdir(store):
        print(f"make_specs: skipping absent store {store}")
        return []
    n, m = n_obs_vars(store)
    out = []

    def add(kind, route, params=None, axis_len=None, chunk=1, evict=(), expect=None, suffix=""):
        out.append(dict(case_id=f"{tag}:{kind}{suffix}", kind=kind, dataset=store, fs=fs,
                        route=route, params=params or {}, axis_len=axis_len, chunk=chunk,
                        evict=list(evict), expect_len=expect))

    if x:
        add("X_gene_col", "/api/v1/data/X", {"cols": "{idx}"}, m, 1, ["X"], n)
    for L in sparse_layers:
        add("sparse_layer_gene_col", f"/api/v1/data/layer/{L}", {"cols": "{idx}"}, m, 1,
            [f"layers/{L}"], n, f":{L}")
    for L in dense_layers:
        ch = zarray(store, f"layers/{L}")["chunks"]
        add("dense_layer_gene_col", f"/api/v1/data/layer/{L}", {"cols": "{idx}"}, m, ch[1],
            [f"layers/{L}"], n, f":{L}")
        if dense_rows:
            add("dense_layer_cell_row", f"/api/v1/data/layer/{L}", {"rows": "{idx}"}, n, ch[0],
                [f"layers/{L}"], m, f":{L}")
    for k in obsm:
        a = zarray(store, f"obsm/{k}")
        add("obsm_col", f"/api/v1/data/obsm/{k}", {"cols": "{idx}"}, a["shape"][1], a["chunks"][1],
            [f"obsm/{k}"], n, f":{k}")
    for c in obs:
        add("obs_col", "/api/v1/data/obs", {"columns": c}, None, 1, [f"obs/{c}"], n, f":{c}")
    for k in obsp_csr:
        add("obsp_csr_row", f"/api/v1/data/obsp/{k}", {"rows": "{idx}"}, n, 1, [f"obsp/{k}"], n, f":{k}")
    for k in obsp_dense:
        ch = zarray(store, f"obsp/{k}")["chunks"]
        add("obsp_dense_row", f"/api/v1/data/obsp/{k}", {"rows": "{idx}"}, n, ch[0], [f"obsp/{k}"], n,
            f":{k}")
    for k in varp_dense:
        ch = zarray(store, f"varp/{k}")["chunks"]
        add("varp_dense_row", f"/api/v1/data/varp/{k}", {"rows": "{idx}"}, m, ch[0], [f"varp/{k}"], m,
            f":{k}")
    if cells:
        add("cell_names", "/api/v1/data/cells", {}, None, 1, ["obs/_index"], n)
    return out


def spec(name, cases, experiment, repeats=5, warm=5):
    return dict(name=name, experiment=experiment, repeats=repeats, warm_repeats=warm, seed=20261001,
                annzarro_dir=ANNZARRO_DIR, cases=cases)


def build(name, root, fs):
    r = root or LIVER
    if name == "smoke":
        s = os.path.join(r, "spatial-A.zarr")
        return spec(name, cases_for(s, fs, "spatial-A", dense_layers=["kompot_de_Xenium_smoothed"],
                                    obsm=["X_umap"], obs=["celltype"], obsp_dense=["dist_spatial"],
                                    varp_dense=["gene_corr_pearson_lognorm"]),
                    "smoke", repeats=2, warm=2)
    if name == "fsarm":
        # Filesystem arm: the same 8 spatial-A endpoints against a store at --root (a full store
        # path: the served original on $DATA_ROOT, or a subset copy on $SCRATCH or node tmpfs).
        s = root or os.path.join(LIVER, "spatial-A.zarr")
        cs = cases_for(s, fs, f"fsarm_{fs}", dense_layers=["kompot_de_Xenium_smoothed"],
                       obsm=["X_umap"], obs=["celltype"], obsp_dense=["dist_spatial"],
                       varp_dense=["gene_corr_pearson_lognorm"])
        for c in cs:  # identical indices on every filesystem arm
            c["seed_key"] = c["case_id"].split(":", 1)[1]
        return spec(name, cs, "fsarm")
    if name == "real":
        cs = []
        cs += cases_for(os.path.join(r, "atlas-1.17M-scvi.zarr"), fs, "atlas-1.17M-scvi",
                        sparse_layers=["lognorm"], dense_layers=["kompot_smooth_all_smoothed"],
                        dense_rows=False, obsm=["X_umap", "X_scVI"], obs=["cell_type", "kompot_da_lfc"],
                        obsp_csr=["connectivities"])
        cs += cases_for(os.path.join(r, "atlas-1.17M-raw.zarr"), fs, "atlas-1.17M-raw",
                        obs=["cell_type"])
        cs += cases_for(os.path.join(r, "atlas-scPLM.zarr"), fs, "scPLM",
                        dense_layers=["kompot_smooth_all_smoothed"], dense_rows=False,
                        obsm=["X_umap"], obs=["cell_type", "nCount_RNA"])
        return spec(name, cs, "real")
    if name == "real_rows":
        # One cell row of a (n_cells, 4)-chunked dense layer decompresses the WHOLE layer;
        # separated so its multi-minute requests run in their own job.
        cs = []
        for st, tag in [("atlas-1.17M-scvi.zarr", "atlas-1.17M-scvi"),
                        ("atlas-scPLM.zarr", "scPLM")]:
            cs += [c for c in cases_for(os.path.join(r, st), fs, tag,
                                        dense_layers=["kompot_smooth_all_smoothed"], x=False,
                                        cells=False) if c["kind"] == "dense_layer_cell_row"]
        return spec(name, cs, "real")
    if name == "chunksweep":
        # Rechunked copies of spatial-A layers/kompot_de_Xenium_smoothed (rechunk_layer.py) on
        # the --root filesystem, plus the served original (75000, 64) on $DATA_ROOT.
        layer = "kompot_de_Xenium_smoothed"
        sweep = root or os.path.join(BENCH, "data", "chunksweep")
        cs = []
        for st in sorted(os.listdir(sweep)):
            if st.endswith(".zarr"):
                tag = "sweep_" + st.replace("spatial-A-xenium_smoothed_", "").replace(".zarr", "")
                cs += cases_for(os.path.join(sweep, st), fs, tag, x=False, dense_layers=[layer],
                                cells=False)
        if root is None:
            cs += cases_for(os.path.join(LIVER, "spatial-A.zarr"), "fhfast",
                            "sweep_served_allx64", x=False, dense_layers=[layer], cells=False)
        return spec(name, cs, "chunksweep")
    if name == "atlas":
        # Fix at scale: kompot_smooth_all_smoothed of the 1.17M atlas and scPLM 460k, in the
        # served (n_cells, 4) layout and in (1024, 1024), both copies on $SCRATCH. Indices are
        # paired across layouts via seed_key.
        d = root or os.path.join(BENCH, "data", "atlas_rechunked")
        cs = []
        for st in sorted(os.listdir(d)):
            if not st.endswith(".zarr"):
                continue
            tag = st[:-5].replace("_kompot_smooth_", "@")
            for c in cases_for(os.path.join(d, st), fs, tag, x=False,
                               dense_layers=["kompot_smooth_all_smoothed"], cells=False):
                c["seed_key"] = tag.split("@")[0] + ":" + c["case_id"].split(":", 1)[1]
                c["chunk"] = 1024  # index-picking granularity only: same picks in both layouts
                cs.append(c)
        return spec(name, cs, "atlas")
    if name == "pairwise":
        pw = root or os.path.join(BENCH, "data", "pairwise")
        cs = []
        for st in sorted(os.listdir(pw)):
            if st.startswith("kernel_") and st.endswith(".zarr"):
                cs += cases_for(os.path.join(pw, st), fs, st[:-5], x=False, obsp_dense=["gaussian_kernel"],
                                cells=False)
            elif st.startswith("dist_") and st.endswith(".zarr"):
                cs += cases_for(os.path.join(pw, st), fs, st[:-5], x=False, obsp_dense=["diffmap_distance"],
                                cells=False)
            elif st.startswith("corr_") and st.endswith(".zarr"):
                cs += cases_for(os.path.join(pw, st), fs, st[:-5], x=False,
                                varp_dense=["gene_corr_pearson"], cells=False)
        for c in cs:
            # Row-chunk variants (rechunk_rows.py, "<name>_r<R>.zarr") pair with their base matrix:
            # same seed_key and the same index-picking granularity, so identical rows are read.
            tag, rest = c["case_id"].split(":", 1)
            c["seed_key"] = re.sub(r"_r\d+$", "", tag) + ":" + rest
            c["chunk"] = 64
        return spec(name, cs, "pairwise")
    raise SystemExit(f"unknown spec {name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("out")
    ap.add_argument("--root", default=None)
    ap.add_argument("--fs", default="fhfast")
    a = ap.parse_args()
    s = build(a.name, a.root, a.fs)
    with open(a.out, "w") as fh:
        json.dump(s, fh, indent=1)
    print(f"{a.out}: {len(s['cases'])} cases")
