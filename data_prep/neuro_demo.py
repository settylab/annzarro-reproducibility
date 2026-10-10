"""Build an AnnZarro-ready zarr store linking C. elegans neuron-class transcriptomes
(CeNGEN, Taylor et al. 2021) to the hermaphrodite connectome (Varshney et al. 2011).

obs unit = neuron class (CeNGEN cell type). Expression is measured per class; synapse
counts are summed over the individual neurons of each class. Used for Fig. 4d
(figures/fig2_cell_by_cell.py).

Licences: Varshney et al. 2011 is CC BY; the CeNGEN tables (cengenDataSC) are GPL-3.0,
so a deposited store is released under GPL-3.0 with this script; Wang et al. 2024 is CC BY 4.0.

Standalone: downloads every input from its public URL into --raw (verifying sha256),
then writes --out. Requires: anndata>=0.12, zarr, scanpy, pyreadr, pandas, openpyxl, xlrd.

    python data_prep/neuro_demo.py [--raw DIR] [--out PATH.zarr]

Defaults: data/neuro_demo/raw and data/neuro_demo/celegans_connectome_cengen.zarr.

Tested with anndata 0.13.4, zarr 3.4.0, scanpy 1.11.x, Python 3.12 (2026-10-05).
"""
import argparse
import hashlib
import json
import re
import subprocess
import urllib.request
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import pyreadr
import scanpy as sc

HERE = Path(__file__).resolve().parent.parent / "data" / "neuro_demo"
_p = argparse.ArgumentParser()
_p.add_argument("--raw", type=Path, default=HERE / "raw")
_p.add_argument("--out", type=Path, default=HERE / "celegans_connectome_cengen.zarr")
_args = _p.parse_args()
RAW = _args.raw
OUT = _args.out
SEED = 0

CENGEN_SHA = "32d20a26381897134fc255e8502f04f9cbd85771"   # AlexWeinreb/cengenDataSC, 2021-09-27
SOURCES = {  # file: (url, sha256 or None if the source is updated in place)
    "NeuronConnect.xls": (
        "https://www.wormatlas.org/images/NeuronConnect.xls",
        "120c2c6332050a2d1494c19c687f447ed65620ad0db5f8b732189aa10e5162f1"),
    "cengen_TPM.rda": (
        f"https://raw.githubusercontent.com/AlexWeinreb/cengenDataSC/{CENGEN_SHA}/data/cengen_TPM.rda",
        "b0ba599492b7079c542751d8d7e968dff0d6e78b23de4dabc353243078cc79d5"),
    "cengen_sc_2.rda": (
        f"https://raw.githubusercontent.com/AlexWeinreb/cengenDataSC/{CENGEN_SHA}/data/cengen_sc_2.rda",
        "78ecf3cec9dc9bec15544e421d09360e34e7542c83abf5e921b543dfa16b7615"),
    "cengenDataSC_LICENSE.md": (
        f"https://raw.githubusercontent.com/AlexWeinreb/cengenDataSC/{CENGEN_SHA}/LICENSE.md",
        "585e25ef8f5946a52bf2aed68d5becfc38be94a8663aa01c1b31d88aa57f1de3"),
    "elife-95402-supp2-v1.xlsx": (
        "https://cdn.elifesciences.org/articles/95402/elife-95402-supp2-v1.xlsx",
        "ad5175b5e53748acf77c6dfff1b5efcf15ed4364091239bd2def0095544eb18c"),
    # NCBI regenerates gene_info daily; only gene symbols come from it (cosmetic var names).
    # Accessed 2026-10-05, sha256 7a990c0957177e42939d0672de8e0175e22e3a97bf491214d25bd7d4200bc832
    "Caenorhabditis_elegans.gene_info.gz": (
        "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Invertebrates/Caenorhabditis_elegans.gene_info.gz",
        None),
}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


RAW.mkdir(parents=True, exist_ok=True)
for _name, (_url, _want) in SOURCES.items():
    _f = RAW / _name
    if not _f.exists():
        print("downloading", _url)
        try:   # curl first: wormatlas.org serves an incomplete TLS chain that Python's ssl rejects
            subprocess.run(["curl", "-fsSL", "-o", str(_f), _url], check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            urllib.request.urlretrieve(_url, _f)
    _got = _sha(_f)
    if _want and _got != _want:
        raise SystemExit(f"checksum mismatch for {_name}: {_got} != {_want}")
    if not _want:
        print(f"note: {_name} sha256 {_got} (not pinned)")

# ---------------------------------------------------------------- expression
tpm = list(pyreadr.read_r(RAW / "cengen_TPM.rda").values())[0]
thr = list(pyreadr.read_r(RAW / "cengen_sc_2.rda").values())[0]  # threshold 2 (medium), binary
tpm = tpm.loc[thr.index, thr.columns]          # drops the two "*_stressed" columns
expr = tpm * thr                                # = the cengen.org "medium threshold 2" table
# AWC_ON / AWC_OFF are stochastic L/R identities; the connectome cannot say which of AWCL/AWCR
# is ON in that animal, so merge them (mean TPM) into one class "AWC".
expr["AWC"] = expr[["AWC_ON", "AWC_OFF"]].mean(axis=1)
expr = expr.drop(columns=["AWC_ON", "AWC_OFF"])
classes = list(expr.columns)

# ---------------------------------------------------------------- connectome
con = pd.read_excel(RAW / "NeuronConnect.xls")
con.columns = ["n1", "n2", "type", "nbr"]
con["n1"] = con["n1"].str.upper()   # one row spells AVFL/AVFR in lower case
con["n2"] = con["n2"].str.upper()
con = con[(con.n1 != "NMJ") & (con.n2 != "NMJ")]


def neuron_to_class(n: str) -> str | None:
    """Map an individual neuron name (White et al. 1986 convention) to a CeNGEN type."""
    m = re.fullmatch(r"(DA|DB|VA|VB|VC|VD|DD|AS)(\d\d)", n)
    if m:
        fam, i = m.group(1), int(m.group(2))
        if fam == "DA":
            return "DA9" if i == 9 else "DA"
        if fam == "DB":
            return "DB01" if i == 1 else "DB"
        if fam == "VA":
            return "VA12" if i == 12 else "VA"
        if fam == "VB":
            return {1: "VB01", 2: "VB02"}.get(i, "VB")
        if fam == "VC":
            return "VC_4_5" if i in (4, 5) else "VC"
        if fam in ("VD", "DD"):
            return "VD_DD"
        return "AS"
    special = {
        "IL2DL": "IL2_DV", "IL2DR": "IL2_DV", "IL2VL": "IL2_DV", "IL2VR": "IL2_DV",
        "IL2L": "IL2_LR", "IL2R": "IL2_LR",
        "RMDDL": "RMD_DV", "RMDDR": "RMD_DV", "RMDVL": "RMD_DV", "RMDVR": "RMD_DV",
        "RMDL": "RMD_LR", "RMDR": "RMD_LR",
        "RMED": "RME_DV", "RMEV": "RME_DV", "RMEL": "RME_LR", "RMER": "RME_LR",
        "AWCL": "AWC", "AWCR": "AWC",
    }
    if n in special:
        return special[n]
    if n in classes:                      # e.g. ASEL, ASER, AVG, DVA, PVT
        return n
    for suf in ("DL", "DR", "VL", "VR", "L", "R", "D", "V"):
        if n.endswith(suf) and n[: -len(suf)] in classes:
            return n[: -len(suf)]
    return None


neurons = sorted(set(con.n1) | set(con.n2))
n2c = {n: neuron_to_class(n) for n in neurons}
unmapped = sorted(n for n, c in n2c.items() if c is None)
print("connectome neurons:", len(neurons), "unmapped:", unmapped)

# neuron-level matrices first (for the sanity checks)
idx = {n: i for i, n in enumerate(neurons)}
N = len(neurons)
chem_n = np.zeros((N, N))
chem_recv_n = np.zeros((N, N))
gap_n = np.zeros((N, N))
for r in con.itertuples():
    i, j = idx[r.n1], idx[r.n2]
    if r.type in ("S", "Sp"):        # n1 presynaptic to n2
        chem_n[i, j] += r.nbr
    elif r.type in ("R", "Rp"):      # n1 postsynaptic to n2
        chem_recv_n[j, i] += r.nbr
    elif r.type == "EJ":
        gap_n[i, j] += r.nbr
checks = {
    "neuron_level_chemical_total_S_plus_Sp": float(chem_n.sum()),
    "neuron_level_chemical_total_R_plus_Rp": float(chem_recv_n.sum()),
    "neuron_level_send_vs_receive_max_abs_diff": float(np.abs(chem_n - chem_recv_n).max()),
    "neuron_level_gap_junction_entries_sum": float(gap_n.sum()),
    "neuron_level_gap_asymmetric_pairs": int((np.triu(gap_n != gap_n.T)).sum()),
}
# symmetrise gap junctions: the file lists each junction from both sides; where the two
# records disagree, take the larger (documented in README)
gap_n = np.maximum(gap_n, gap_n.T)
checks["neuron_level_gap_junctions_after_symmetrising"] = float(np.triu(gap_n).sum())

# classes present in both data sets
keep = [c for c in classes if c in set(n2c.values())]
missing_conn = [c for c in classes if c not in keep]
print("classes with expression but no connectome neurons (dropped):", missing_conn)
A = np.zeros((N, len(keep)))   # neuron -> class membership
for n, c in n2c.items():
    if c in keep:
        A[idx[n], keep.index(c)] = 1
chem = A.T @ chem_n @ A
# a junction between two members of the same class (e.g. AVAL-AVAR) is listed from both
# sides, so it lands twice on the class diagonal; count it once. Three neuron-level
# self-junctions in the file (RIBL-RIBL, RIBR-RIBR, VA08-VA08) are listed once and kept as is.
gap_self = np.diag(np.diag(gap_n))
gap_cross = A.T @ (gap_n - gap_self) @ A
gap_cross[np.diag_indices_from(gap_cross)] *= 0.5
gap = gap_cross + A.T @ gap_self @ A
checks["class_level_chemical_total"] = float(chem.sum())
checks["class_level_gap_junctions_total_upper_incl_diag"] = float(np.triu(gap).sum())

# ---------------------------------------------------------------- AnnData
genes = pd.read_csv(RAW / "Caenorhabditis_elegans.gene_info.gz", sep="\t")
genes["wb"] = genes.dbXrefs.str.extract(r"WormBase:(WBGene\d+)")
sym = genes.dropna(subset=["wb"]).drop_duplicates("wb").set_index("wb").Symbol

E = expr[keep].T                                   # classes x genes, TPM (thresholded)
var = pd.DataFrame(index=E.columns)
var["gene_symbol"] = [sym.get(g, g) for g in var.index]
var["wbgene"] = var.index

nt = pd.read_excel(RAW / "elife-95402-supp2-v1.xlsx", header=None).iloc[4:, [2, 20]]
nt.columns = ["neuron", "nt"]
nt = nt.dropna()
nt["neuron"] = nt.neuron.astype(str).str.strip()


def clean_nt(v: str) -> str:
    v = v.replace("*", "").replace(" - NEW", "").strip()
    return "unknown" if v.lower().startswith("unknown") else v


nt_map = {}
for name, v in zip(nt.neuron, nt.nt.astype(str).map(clean_nt)):
    # Wang et al. write motor neurons as DA1, DB1/3, VC4; the connectome uses DA01, DB01
    for part in name.split("/"):
        m = re.fullmatch(r"([A-Z]+)(\d+)", part) if "/" in name else re.fullmatch(r"([A-Z]+)(\d+)", name)
        key = f"{m.group(1)}{int(m.group(2)):02d}" if m else name
        if "/" in name and not m:
            continue
        nt_map.setdefault(key, v)
        if "/" not in name:
            break

obs = pd.DataFrame(index=pd.Index(keep, name="neuron_class"))
obs["neuron_class"] = keep
members = {c: sorted(n for n, cc in n2c.items() if cc == c) for c in keep}
obs["neurons"] = [",".join(members[c]) for c in keep]
obs["n_neurons"] = [len(members[c]) for c in keep]


def class_nt(c):
    vals = sorted({nt_map[n] for n in members[c] if n in nt_map})
    return "/".join(vals) if vals else "unknown"


obs["neurotransmitter"] = pd.Categorical([class_nt(c) for c in keep])
obs["chemical_out_total"] = chem.sum(1)
obs["chemical_in_total"] = chem.sum(0)
obs["gap_junction_total"] = gap.sum(1)

adata = ad.AnnData(X=np.log1p(E.values).astype(np.float32), obs=obs, var=var)
adata.layers["TPM_threshold2"] = E.values.astype(np.float32)
adata.var_names = [f"{s}" for s in adata.var.gene_symbol]
adata.var_names_make_unique()

# embedding
sc.pp.highly_variable_genes(adata, n_top_genes=2000, flavor="seurat")
tmp = adata[:, adata.var.highly_variable].copy()
sc.pp.scale(tmp, max_value=10)
sc.tl.pca(tmp, n_comps=20, random_state=SEED)
sc.pp.neighbors(tmp, n_neighbors=8, n_pcs=20, random_state=SEED)
sc.tl.umap(tmp, min_dist=0.4, random_state=SEED)
adata.obsm["X_pca"] = tmp.obsm["X_pca"].astype(np.float32)
adata.obsm["X_umap"] = tmp.obsm["X_umap"].astype(np.float32)

adata.obsp["chemical_synapses"] = chem.astype(np.float32)        # row = presynaptic (outputs)
adata.obsp["chemical_synapses_in"] = chem.T.copy().astype(np.float32)  # row = postsynaptic (inputs)
adata.obsp["gap_junctions"] = gap.astype(np.float32)             # symmetric

cats = adata.obs.neurotransmitter.cat.categories
palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2",
           "#7f7f7f", "#bcbd22", "#17becf", "#393b79", "#637939", "#8c6d31", "#843c39"]
adata.uns["neurotransmitter_colors"] = [("#bbbbbb" if c == "unknown" else palette[i % len(palette)])
                                        for i, c in enumerate(cats)]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


adata.uns["provenance"] = {
    "expression": "CeNGEN (Taylor et al. 2021, doi:10.1016/j.cell.2021.06.023); cengenDataSC "
                  "commit 32d20a2, GPL-3.0; TPM per neuron type masked by threshold 2; X = log1p(TPM)",
    "connectome": "Varshney et al. 2011 (doi:10.1371/journal.pcbi.1001066, CC BY); WormAtlas "
                  "NeuronConnect.xls (2006-02-02 version); counts of synapses summed over class members",
    "neurotransmitter": "Wang et al. 2024 eLife (doi:10.7554/eLife.95402, CC BY), Supplementary File 2",
    "embedding": f"2000 HVG (seurat), scale(max 10), PCA 20, neighbors k=8, UMAP min_dist 0.4, seed {SEED}",
    "sha256": json.dumps({n: sha(RAW / n) for n in SOURCES}),
}
adata.uns["sanity_checks"] = json.dumps(checks)
adata.uns["unmapped_connectome_neurons"] = json.dumps(unmapped)
adata.uns["classes_dropped_no_connectome"] = json.dumps(missing_conn)

ad.settings.zarr_write_format = 2
if OUT.exists():
    import shutil
    shutil.rmtree(OUT)
adata.write_zarr(OUT)

# ---------------------------------------------------------------- sanity check on disk
b = ad.read_zarr(OUT)
g = b.obsp["gap_junctions"]
print(b)
print("obsp shapes:", {k: v.shape for k, v in b.obsp.items()})
print("gap symmetric:", bool(np.allclose(g, g.T)))
print("chem_in == chem.T:", bool(np.allclose(b.obsp["chemical_synapses_in"], b.obsp["chemical_synapses"].T)))
print("checks:", json.dumps(checks, indent=1))
ava = list(b.obs_names).index("AVA")
row = b.obsp["chemical_synapses"][ava]
top = np.argsort(-row)[:8]
print("AVA outputs, top partners:", [(b.obs_names[i], int(row[i])) for i in top])
rowg = g[ava]
print("AVA gap junction partners:", [(b.obs_names[i], int(rowg[i])) for i in np.argsort(-rowg)[:8]])
print("classes without NT match:", [c for c in b.obs_names if not any(n in nt_map for n in members[c])])
print("NT categories:", b.obs.neurotransmitter.value_counts().to_dict())
