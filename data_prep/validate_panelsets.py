#!/usr/bin/env python
"""Validate the demo panel sets against a running local AnnZarro server.

1. POST each <view>.json to /api/v1/sessions/import, GET /sessions/load, check the
   round trip is lossless and the panel set appears in /sessions/list.
2. For every data reference in every panel (axes, colour, table columns), issue the
   request the front end would issue and check it returns the right shape with
   finite values (cell/gene names resolved via /data/cells and /data/genes).
3. Round-trip each <view>.view.json through AnnZarro's own static/js/utils/deeplink.js
   (encodeView/decodeView/normalizeView/layoutHasPanels) in Node, and check every
   tile id in the hierarchy has a panelConfig with the matching type prefix.
"""
import argparse
import json
import math
import subprocess
from pathlib import Path

import requests

HERE = Path(__file__).parent / "demo_panelsets"
VIEWS = ["A_kernel_walk", "B_volcano_spearman", "C_foldchange_umap", "D_locked_vs_focused_cell", "E_table_filter"]


def finite_frac(vals):
    flat = []
    def walk(x):
        if isinstance(x, list):
            for y in x:
                walk(y)
        else:
            flat.append(x)
    walk(vals)
    ok = [v for v in flat if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v))]
    return len(flat), len(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8010")
    ap.add_argument("--annzarro-src", default=str(Path.home() / "gits/annzarro"))
    ap.add_argument("--out", default="data/panelset_validation.json")
    args = ap.parse_args()
    api = f"{args.base}/api/v1"
    s = requests.Session()
    report = {}

    for v in VIEWS:
        pset = json.loads((HERE / f"{v}.json").read_text())
        ds = pset["dataset"]
        res = {}
        # ---- 1. import / load round trip
        with open(HERE / f"{v}.json", "rb") as fh:
            r = s.post(f"{api}/sessions/import", files={"file": (f"{v}.json", fh, "application/json")},
                       data={"overwrite": "true"})
        res["import_status"] = r.status_code
        name = r.json().get("sanitized_name")
        r2 = s.get(f"{api}/sessions/load", params={"name": name})
        loaded = r2.json()
        res["load_status"] = r2.status_code
        res["roundtrip_equal"] = loaded["panelConfigs"] == pset["panelConfigs"] and loaded["constants"] == pset["constants"]
        res["in_list"] = any(x["name"] == name for x in s.get(f"{api}/sessions/list").json())

        # ---- 2. resolve every data reference
        cells = s.get(f"{api}/data/cells", params={"dataset_path": ds}).json()
        genes = s.get(f"{api}/data/genes", params={"dataset_path": ds}).json()
        cells = cells.get("cells", cells) if isinstance(cells, dict) else cells
        genes = genes.get("genes", genes) if isinstance(genes, dict) else genes
        cidx = {c: i for i, c in enumerate(cells)}
        gidx = {g: i for i, g in enumerate(genes)}
        checks = []
        for pid, p in pset["panelConfigs"].items():
            cfg, ptype = p["config"], p["type"]
            plot = "cells" if ptype.startswith("cell") else "genes"
            refs = [cfg.get(a) for a in ("x", "y", "color") if isinstance(cfg.get(a), dict)]
            refs += cfg.get("columns", [])
            for ref in refs:
                t, key, col = ref["type"], ref["key"], ref.get("column", "")
                if t in ("obs", "var"):
                    url, params = f"{api}/data/{t}", {"columns": key}
                elif t in ("obsm", "varm"):
                    url, params = f"{api}/data/{t}/{key}", {"cols": col}
                elif t == "obsp":
                    url, params = f"{api}/data/obsp/{key}", {"rows": cidx[col]}
                elif t == "varp":
                    url, params = f"{api}/data/varp/{key}", {"rows": gidx[col]}
                elif t == "layer" and plot == "cells":
                    url, params = f"{api}/data/layer/{key}", {"cols": gidx[col]}
                elif t == "layer" and plot == "genes":
                    url, params = f"{api}/data/layer/{key}", {"rows": cidx[col]}
                else:
                    checks.append(dict(panel=pid, ref=ref, ok=False, why="unknown type"))
                    continue
                rr = s.get(url, params={"dataset_path": ds, **params})
                body = rr.json()
                data = body.get("data")
                if t in ("obs", "var") and isinstance(data, dict):
                    data = data.get(key)
                n, nfin = finite_frac(data) if isinstance(data, list) else (0, 0)
                expect = len(cells) if plot == "cells" else len(genes)
                categorical = t in ("obs", "var") and n == expect and nfin < n
                ok = rr.status_code == 200 and n == expect and (nfin == n or categorical)
                checks.append(dict(panel=pid, ref=f"{t}:{key}:{col}", status=rr.status_code, n=n,
                                   n_finite=nfin, expected=expect, ok=ok))
        res["data_refs"] = checks
        res["all_refs_ok"] = all(c["ok"] for c in checks)

        # ---- 3. deep link through the app's own module
        js = f"""
import {{ encodeView, decodeView, normalizeView, layoutHasPanels, collectTileIds, panelTypeFromTileId }}
  from '{args.annzarro_src}/static/js/utils/deeplink.js';
import fs from 'fs';
const view = JSON.parse(fs.readFileSync('{HERE / (v + ".view.json")}', 'utf8'));
const rt = normalizeView(decodeView(encodeView(view)));
const ids = collectTileIds(rt.layout.hierarchy);
const typesOk = ids.every(id => rt.layout.panelConfigs[id] && panelTypeFromTileId(id) === id.split('-').slice(0,2).join('-'));
console.log(JSON.stringify({{ roundtrip: JSON.stringify(rt.layout) === JSON.stringify(view.layout),
  hasPanels: layoutHasPanels(rt.layout), tiles: ids, types: ids.map(panelTypeFromTileId), typesOk }}));
"""
        p = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True)
        try:
            res["deeplink"] = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            res["deeplink"] = {"error": (p.stderr or p.stdout)[-500:]}
        report[v] = res
        dl = res["deeplink"]
        print(f"{v}: import={res['import_status']} load={res['load_status']} roundtrip={res['roundtrip_equal']} "
              f"listed={res['in_list']} refs_ok={res['all_refs_ok']} ({len(checks)} refs) deeplink={dl}")
        for c in checks:
            if not c["ok"]:
                print("   FAILED REF", c)
    Path(args.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
