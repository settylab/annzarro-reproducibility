#!/usr/bin/env python
"""Generate AnnZarro panel sets (and matching deep links) for the five protocol views.

Two artefacts per view, because they do different things in AnnZarro today:
  <view>.json           panel-set file for "Panel sets > Import" (POST /api/v1/sessions/import).
                        Loading a panel set registers its panels as CLOSED panels (listed
                        in the panel selector); it does NOT load the dataset, set the focused
                        gene/cell, or arrange panels (session-manager.js::_applySessionPanels).
  <view>.view.json      deep-link `view` object (docs/deep-link-schema.md): dataset + focus +
                        full layout tree, opened via ?dataset_path=...#view=z1.<deflated view>,
                        the form AnnZarro's Share Link writes. This is the artefact that
                        reproduces a figure panel.
All panel ids are written into each panel's config, because registerClosedPanel only
keeps an id that is present in the config (otherwise it regenerates `type-Date.now()`,
which both breaks cell-plot -> cell-table filter links and can collide).

Usage:
    python data_prep/make_panelsets.py --dataset-path bm_aging.zarr

The links are portable: the default local server (http://127.0.0.1:8000, `annzarro start`)
and the store's file name, which the server looks up in its data directory. Replace the
host:port for another server; an absolute --dataset-path names a store outside the data
directory (a local single-user server only). Same form as the AnnZarro docs' tutorial links
(docs/_tools/shots.py start_link).
"""
import argparse
import base64
import json
import zlib
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).parent / "demo_panelsets"


def umap_axes():
    return dict(x={"type": "obsm", "key": "X_umap", "column": "0"},
                y={"type": "obsm", "key": "X_umap", "column": "1"},
                z=None)


def cell_plot(pid, title, color, **extra):
    cfg = dict(id=pid, title=title, **umap_axes(), color=color, pointSize=3, pointOpacity=0.8,
               colorScale="Viridis", highlightFocusedCell=True, hoverInfo=[{"type": "obs", "key": "_index"},
                                                                           {"type": "obs", "key": "highres_celltype"}])
    cfg.update(extra)
    return pid, "cell-plot", cfg


def gene_plot(pid, title, x, y, color, **extra):
    cfg = dict(id=pid, title=title, x=x, y=y, z=None, color=color, pointSize=5, pointOpacity=0.8,
               colorScale="Viridis", hoverInfo=[{"type": "var", "key": "_index"}])
    cfg.update(extra)
    return pid, "gene-plot", cfg


def tile(pid, controls=False):
    return {"type": "tile", "id": pid, "controlsVisible": controls}


def hsplit(a, b, pa=50, direction="horizontal"):
    return {"type": "split", "direction": direction,
            "panes": [{"percentage": pa, "controlsVisible": False}, {"percentage": 100 - pa, "controlsVisible": False}],
            "children": [a, b]}


def z1(obj):
    """AnnZarro's compressed fragment: z1.<base64url(deflate-raw(JSON))>."""
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return "z1." + base64.urlsafe_b64encode(c.compress(raw) + c.flush()).decode().rstrip("=")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-path", required=True, help="dataset path as the server will resolve it")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--examples", default=str(OUT / "examples.json"))
    args = ap.parse_args()
    ex = json.load(open(args.examples))
    K = ex["keys"]
    gene = ex["genes"]["focus"]["name"]
    hsc = ex["cells"]["HSC"]["name"]
    mono = ex["cells"]["Monocyte"]["name"]
    ct = ex["celltype_column"]
    fc, (sy, so) = K["FC_KEY"], K["SMOOTH_KEYS"]
    walk = K["WALK_KEY"]

    views = {}

    # A: kernel walk on UMAP, coloured by the obsp row of the focused cell (an HSC)
    views["A_kernel_walk"] = dict(
        constants={"focusedCell": hsc, "focusedGene": gene},
        panels=[cell_plot("cell-plot-A1", f"A | 5-step diffusion walk from focused cell",
                          {"type": "obsp", "key": walk, "column": hsc, "locked": False}, colorScale="Hot",
                          colorReversed=True),
                cell_plot("cell-plot-A2", "A | sparse DM_Kernel row of focused cell",
                          {"type": "obsp", "key": "DM_Kernel", "column": hsc, "locked": False}, colorScale="Hot",
                          colorReversed=True)],
        layout=lambda: hsplit(tile("cell-plot-A1", True), tile("cell-plot-A2")))

    # B: volcano (x mean_lfc, y mahalanobis) coloured by Spearman to the focused gene.
    # Worked example 2 (Step 20) and the gene-by-gene figure focus H2-Q7, not the example gene.
    b_gene = "H2-Q7"
    views["B_volcano_spearman"] = dict(
        constants={"focusedGene": b_gene, "focusedCell": hsc},
        panels=[gene_plot("gene-plot-B1", "B | volcano, colour = Spearman (smoothed) to focused gene",
                          {"type": "var", "key": K["LFC_KEY"], "column": ""},
                          {"type": "var", "key": K["MAHAL_KEY"], "column": ""},
                          {"type": "varp", "key": "spearman_smoothed", "column": b_gene, "locked": False},
                          colorScale="RdBu", colorMin=-1, colorMax=1, lockColorRange=True),
                gene_plot("gene-plot-B2", "B' | volcano, colour = Spearman (fold change) to focused gene",
                          {"type": "var", "key": K["LFC_KEY"], "column": ""},
                          {"type": "var", "key": K["MAHAL_KEY"], "column": ""},
                          {"type": "varp", "key": "spearman_fold_change", "column": b_gene, "locked": False},
                          colorScale="RdBu", colorMin=-1, colorMax=1, lockColorRange=True)],
        layout=lambda: hsplit(tile("gene-plot-B1", True), tile("gene-plot-B2")))

    # C: UMAP coloured by fold change of the focused gene + Young / Old smoothed expression.
    # Step 23: the two smoothed panels share one locked colour range, 0 to 3.77, the larger of
    # S100a9's two maxima (Young 3.77, Old 3.72), so their colours compare directly.
    shared = dict(colorMin=0, colorMax=3.77, lockColorRange=True)
    views["C_foldchange_umap"] = dict(
        constants={"focusedGene": gene, "focusedCell": hsc},
        panels=[cell_plot("cell-plot-C1", "C | Kompot fold change (Old vs Young) of focused gene",
                          {"type": "layer", "key": fc, "column": gene, "locked": False}, colorScale="RdBu",
                          centeringActive=True),
                cell_plot("cell-plot-C2", "C | Young smoothed expression",
                          {"type": "layer", "key": sy, "column": gene, "locked": False}, **shared),
                cell_plot("cell-plot-C3", "C | Old smoothed expression",
                          {"type": "layer", "key": so, "column": gene, "locked": False}, **shared)],
        layout=lambda: hsplit(tile("cell-plot-C1", True),
                              hsplit(tile("cell-plot-C2"), tile("cell-plot-C3"), 50, "vertical"), 50))

    # D: gene plot, fold change of a LOCKED cell (HSC) vs the FOCUSED cell (monocyte), coloured
    # by the focused gene's row of the fold-change correlation (Step 26)
    views["D_locked_vs_focused_cell"] = dict(
        constants={"focusedCell": mono, "focusedGene": gene},
        panels=[gene_plot("gene-plot-D1", "D | fold change: locked HSC (x) vs focused cell (y)",
                          {"type": "layer", "key": fc, "column": hsc, "locked": True},
                          {"type": "layer", "key": fc, "column": mono, "locked": False},
                          {"type": "varp", "key": "spearman_fold_change", "column": gene, "locked": False},
                          colorScale="RdBu", colorMin=-1, colorMax=1, lockColorRange=True),
                cell_plot("cell-plot-D2", "D | cell types (locate the two cells)",
                          {"type": "obs", "key": ct, "column": ""})],
        layout=lambda: hsplit(tile("gene-plot-D1", True), tile("cell-plot-D2"), 60))

    # E: cell table filter (cell type == HSC AND DA z-score > 2) masking a UMAP
    zcol = K["DA_Z_KEY"]
    views["E_table_filter"] = dict(
        constants={"focusedCell": hsc, "focusedGene": gene},
        panels=[("cell-table-E1", "cell-table", dict(
                    id="cell-table-E1", title="E | HSC with DA z-score > 2",
                    columns=[{"type": "obs", "key": ct, "column": ""},
                             {"type": "obs", "key": zcol, "column": ""},
                             {"type": "obs", "key": "Age", "column": ""}],
                    searchBuilderConfig={"criteria": [
                        {"condition": "=", "data": ct, "origData": f"obs_{ct}_main", "type": "string", "value": ["HSC"]},
                        {"condition": ">", "data": zcol, "origData": f"obs_{zcol}_main", "type": "num", "value": ["2"]}],
                        "logic": "AND"})),
                cell_plot("cell-plot-E2", "E | UMAP masked by table filter",
                          {"type": "obs", "key": zcol, "column": ""}, colorScale="RdBu", centeringActive=True,
                          tableFilter="cell-table-E1", hideNonSubset=False)],
        layout=lambda: hsplit(tile("cell-table-E1", True), tile("cell-plot-E2"), 45))

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    index = {}
    for name, v in views.items():
        panel_configs = {pid: {"id": pid, "type": typ, "title": cfg["title"], "config": cfg, "isSelectionTile": False}
                         for pid, typ, cfg in v["panels"]}
        pset = {"name": f"protocol_{name}", "timestamp": stamp, "dataset": args.dataset_path,
                "datasetName": "bm_aging", "constants": {**v["constants"], "taxonomyId": "10090"},
                "panelConfigs": panel_configs}
        (OUT / f"{name}.json").write_text(json.dumps(pset, indent=2))
        view = {"v": 1, "constants": {**v["constants"], "taxonomyId": "10090"},
                "layout": {"v": 1, "hierarchy": [v["layout"]()],
                           "controlState": {pid: False for pid, _, _ in v["panels"]},
                           "panelConfigs": {pid: cfg for pid, _, cfg in v["panels"]}}}
        (OUT / f"{name}.view.json").write_text(json.dumps(view, indent=2))
        from urllib.parse import quote
        url = f"{args.base_url}/?dataset_path={quote(args.dataset_path, safe='/')}#view={z1(view)}"
        index[name] = {"panel_set": f"{name}.json", "view": f"{name}.view.json", "url_length": len(url), "url": url}
        print(f"{name}: {len(v['panels'])} panels, deep link {len(url)} chars")
    (OUT / "deeplinks.json").write_text(json.dumps(index, indent=2))


if __name__ == "__main__":
    main()
