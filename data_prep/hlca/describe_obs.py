#!/usr/bin/env python
"""Obs column list with dtypes and category counts (ann_level_1..5, tissue, disease, donor_id, study) of a store."""
import json, sys
import anndata as ad, zarr
st = sys.argv[1]
obs = ad.io.read_elem(zarr.open_group(st, mode="r", use_consolidated=True)["obs"])
cols = {c: str(obs[c].dtype) for c in obs.columns}
counts = {}
for c in ["ann_level_1", "ann_level_2", "ann_level_3", "ann_level_4", "ann_level_5", "tissue", "disease", "donor_id", "study"]:
    if c in obs:
        vc = obs[c].value_counts(dropna=False)
        counts[c] = {"n_categories": int((vc > 0).sum()), "counts": {str(k): int(v) for k, v in vc.items()}}
out = {"n_obs": int(obs.shape[0]), "n_columns": len(cols), "columns": cols, "category_counts": counts}
json.dump(out, open(st.rstrip("/") + ".obs_summary.json", "w"), indent=1)
print(json.dumps({"n_obs": out["n_obs"], "n_columns": out["n_columns"], "n_categories": {k: v["n_categories"] for k, v in counts.items()}}, indent=1))
