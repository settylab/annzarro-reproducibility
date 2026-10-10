#!/usr/bin/env python
"""Bring evidence/matrix/tools/*.yaml in line with figures/fig_comparison.py TOOLS.

For every figure row: figure.{row,label,largest_documented} and each cell's `mark` follow the
figure; an audit `proposed` equal to the new mark is dropped, a different one is kept and
reported. Tools not in the figure get figure: null and keep their audit marks as `proposed`.
Prints every mark that changed, for the commit message. `build.py --check` must pass after.

Usage: sync_figure.py [--dry-run]
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
D = REPO / "evidence/matrix/tools"
ROWS = {  # figure row label -> tool file id
    "AnnZarro": "annzarro", "CELLxGENE Explorer": "cellxgene-explorer", "CELLxGENE Annotate": "cellxgene-annotate",
    "Vitessce": "vitessce", "Cirrocumulus": "cirrocumulus", "iSEE": "isee", "UCSC Cell Browser": "ucsc-cell-browser",
    "Single Cell Portal": "single-cell-portal", "ShinyCell2": "shinycell", "Kana": "kana",
    "napari-spatialdata": "napari-spatialdata", "Loupe Browser (docs)": "loupe", "Loupe Browser": "loupe", "SCope": "scope",
    "ManiVault Studio": "manivault", "TissUUmaps 3": "tissuumaps", "VizIt": "vizit",
    "Scanpy / Seurat code": "scanpy-seurat",
}


def str_presenter(dumper, data):
    style = "|" if "\n" in data else (">" if len(data) > 100 else None)
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    yaml.add_representer(str, str_presenter)
    cols = [c["id"] for c in yaml.safe_load((REPO / "evidence/matrix/columns.yaml").read_text())["columns"]]
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import figmarks
    tools = figmarks.figure_tools()            # as drawn: the scale reading applied
    fig = {}
    for i, (name, marks, scale) in enumerate(tools):
        if name not in ROWS:
            sys.exit(f"figure row {name!r} has no entry in ROWS; add it")
        fig[ROWS[name]] = (name, marks.replace(" ", ""), scale, i + 1)
    report = []
    for f in sorted(D.glob("*.yaml")):
        text = f.read_text()
        header = "".join(l for l in text.splitlines(True) if l.startswith("#"))
        d = yaml.safe_load(text)
        cells = d["cells"]
        if d["id"] in fig:
            name, marks, scale, row = fig[d["id"]]
            d["figure"] = {"row": row, "label": name, "largest_documented": scale}
            for cid, m in zip(cols, marks):
                c = cells.setdefault(cid, {"reason": "(no audit cell; mark from the figure)", "checked": None})
                before = c.get("mark")
                verdict = c.get("proposed") or before
                c["mark"] = m
                if c.get("proposed") == m:
                    c.pop("proposed")
                elif c.get("proposed"):
                    report.append(f"{d['id']}.{cid}: figure {m}, audit proposes {c['proposed']} (kept)")
                if (verdict or "-") != m:
                    report.append(f"{d['id']}.{cid}: {verdict or '-'} -> {m}")
        else:
            d["figure"] = None
            for c in cells.values():
                if "mark" in c:
                    c.setdefault("proposed", c.pop("mark"))
        for cid in [c for c in cells if c not in cols]:          # columns no longer in the figure
            d.setdefault("retired_cells", {})[cid] = cells[cid]
        d["cells"] = {cid: cells[cid] for cid in cols if cid in cells}
        if not a.dry_run:
            f.write_text(header + yaml.dump(d, sort_keys=False, allow_unicode=True, width=100))
    print("\n".join(report) or "no mark changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
