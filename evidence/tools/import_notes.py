#!/usr/bin/env python
"""Seed evidence/matrix/tools/<tool>.yaml from the audit notes (one-shot).

Reads, without changing any of them:
  figures/fig_comparison.py      TOOLS: the marks Fig. 1c draws now (-> mark)
  notes/comparison/_summary.md   "Proposed matrix" and the selection column (-> proposed)
  notes/comparison/<tool>.md     "Matrix row", "Scale group" and focus "Marks" (-> detail, evidence)

After the seed, the YAML files are the source and the notes are linked from
them. Re-running overwrites the YAML, so run it only before the files are
hand-edited (or with --only <tool> for a tool whose notes changed).

Usage: .venv/bin/python evidence/tools/import_notes.py [--only isee,cellxgene]
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refs  # noqa: E402  evidence/tools/refs.py: papers.yaml and archive.yaml

REPO = Path(__file__).resolve().parents[2]
NOTES = REPO / "notes/comparison"
OUT = REPO / "evidence/matrix/tools"
CHECKED = "2026-10-03"

# figure row name -> (id, notes file or None)
TOOLS = {
    "AnnZarro": ("annzarro", None),
    "CELLxGENE": ("cellxgene", "cellxgene.md"),
    "Vitessce": ("vitessce", "vitessce.md"),
    "Cirrocumulus": ("cirrocumulus", "cirrocumulus.md"),
    "iSEE": ("isee", "isee.md"),
    "UCSC Cell Browser": ("ucsc-cell-browser", "ucsc-cell-browser.md"),
    "ShinyCell": ("shinycell", "shinycell.md"),
    "Scanpy / Seurat code": ("scanpy-seurat", "scanpy-seurat.md"),
    "Single Cell Portal": ("single-cell-portal", "single-cell-portal.md"),
    "SCope": ("scope", "scope.md"),
    "Kana": ("kana", "kana.md"),
    "napari-spatialdata": ("napari-spatialdata", "napari-spatialdata.md"),
    "Loupe Browser": ("loupe", "loupe.md"),
}
SUMMARY_NAME = {"Scanpy / Seurat": "Scanpy / Seurat code"}
# column order of the audit's 16-mark strings in _summary.md
AUDIT_ORDER = ["cells", "genes", "focus", "slots", "lazy", "remote", "spatial", "filters", "annot", "de",
               "image", "share", "export", "desktop", "hosted", "static"]
SCALE_ITEMS = {"S2": "every_cell", "S3": "lazy", "S4": "subset"}
# every_cell and subset have no mark in the notes' mark tables, only prose (each note's Scale
# group, _summary.md "Scale group"). These are that prose read under columns.yaml every_cell
# reading A ("draws every cell by default"). A running-app "plots render | (every cell: Y)"
# mark in a note takes precedence.
SCALE_A = {
    "cellxgene": {"every_cell": "Y", "subset": "Y"},           # every cell drawn; subset to selection (view)
    "vitessce": {"every_cell": "Y", "subset": "N"},            # all drawn; no cell subset (highlight only)
    "cirrocumulus": {"every_cell": "Y", "subset": "P"},        # all drawn; partial (dim the rest, export ids)
    "isee": {"every_cell": "Y", "subset": "Y"},                # all by default; restrict to selection
    "ucsc-cell-browser": {"every_cell": "Y", "subset": "Y"},   # all drawn; hide / only show selected
    "shinycell": {"every_cell": "Y", "subset": "Y"},           # all drawn; subset by metadata group
    "scanpy-seurat": {"every_cell": "Y", "subset": "P"},       # all drawn by default; subset only by code
    "single-cell-portal": {"every_cell": "N", "subset": "Y"},  # 100k subsample by default; "100k or all" menu
    "scope": {"every_cell": "Y", "subset": "Y"},               # all drawn (PIXI); by annotation
    "kana": {"every_cell": "Y", "subset": "Y"},                # all drawn; subset and recompute at load
    "napari-spatialdata": {"every_cell": "P", "subset": "P"},  # points subsampled above 100k; subset by code
    "loupe": {"every_cell": "?", "subset": "Y"},               # not documented; Reanalyze subset
}
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
GH = re.compile(r"https://github\.com/([^/]+/[^/]+)/blob/([0-9a-f]{7,40})/([^#)]+)(?:#L(\d+)(?:-L(\d+))?)?")


def columns():
    return yaml.safe_load((REPO / "evidence/matrix/columns.yaml").read_text())["columns"]


def figure_tools():
    """Fig. 1c rows as drawn (scale reading applied; evidence/tools/figmarks.py)."""
    import figmarks
    return figmarks.figure_tools()


def md_tables(text):
    """Yield (heading, rows) for every pipe table; rows are lists of cells, header first."""
    heading, rows = None, []
    for line in text.splitlines() + [""]:
        if line.startswith("#") or (line.startswith("**") and line.endswith("**")):
            heading = line.strip("#* ").strip()
        if line.startswith("|"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                rows.append(cells)
        elif rows:
            yield heading, rows
            rows = []


def summary_proposed():
    text = (NOTES / "_summary.md").read_text()
    prop, sel = {}, {}
    for heading, rows in md_tables(text):
        if heading == "Proposed matrix":
            for name, _cur, proposed, *_ in rows[1:]:
                m = re.search(r"`([YPN? ]+)`", proposed)
                if m:
                    prop[SUMMARY_NAME.get(name, name)] = m.group(1).replace(" ", "")
        if heading and heading.startswith("Proposed column"):
            for name, mark, observed, shot in rows[1:]:
                sel[SUMMARY_NAME.get(name, name)] = (mark, observed, shot)
    return prop, sel


def evidence(text, base):
    """Classify every Markdown link in an evidence cell."""
    out, seen = [], set()
    for label, url in LINK.findall(text):
        if url in seen:
            continue
        seen.add(url)
        if url.startswith("http"):
            g = GH.match(url)
            if g:
                repo, sha, path, l0, l1 = g.groups()
                item = {"kind": "code", "repo": repo, "commit": sha, "path": path}
                if l0:
                    item["lines"] = f"{l0}-{l1}" if l1 else l0
                item["url"] = url
            elif "doi.org" in url:
                item = {"kind": "paper", "url": url}
            else:
                item = {"kind": "docs", "url": url}
        else:
            path = (base / url.split("#")[0]).resolve().relative_to(REPO).as_posix()
            kind = ("screenshot" if path.endswith((".jpg", ".png")) else
                    "script" if "/demos/" in path else "note")
            item = {"kind": kind, "path": path + (("#" + url.split("#")[1]) if "#" in url else "")}
        item["label"] = label
        out.append(item)
    return out


def first_sentence(text):
    plain = LINK.sub(r"\1", text).replace("**", "")
    plain = re.sub(r"^\([^)]*\)", "", plain).lstrip(" ,.")
    plain = re.sub(r"^(Observation|N|P|Y): (nothing to show; )?", "", plain)
    m = re.match(r"(.{25,}?[a-z0-9)`'\"]\.)(\s|$)", plain)
    s = (m.group(1) if m else plain).strip()
    return s if len(s) <= 220 else s[:217].rsplit(" ", 1)[0] + " ..."


def mark_of(cell, focus=None):
    """The mark in a mark cell: a bold mark wins ("**N** (proposed P)"); a cell that defers to
    the Focus section takes the focus bullet; else the first standalone Y/P/N/?."""
    b = re.search(r"\*\*([YPN?])\*\*", cell)
    if b:
        return b.group(1)
    if focus and "Focus section" in cell:
        return focus
    m = re.search(r"(?<![A-Za-z])([YPN?])(?![A-Za-z])", cell)
    return m.group(1) if m else None


def section(text, title):
    m = re.search(r"^### " + re.escape(title) + r".*?$(.*?)(?=^### |\Z)", text, re.S | re.M)
    return m.group(1) if m else ""


def drivers(text):
    """Driver scripts named in a section intro, as repo paths (only those that exist)."""
    out, base = [], None
    for tok in re.findall(r"[`(\[]((?:demos/)?[A-Za-z0-9_./-]+\.(?:py|sh|R))[`)\]]", text):
        if tok.startswith("demos/"):
            base = tok.rsplit("/", 1)[0]
        elif "/" not in tok and base:
            tok = f"{base}/{tok}"
        else:
            continue
        path = f"notes/comparison/{tok}"
        if (REPO / path).exists() and path not in out and "/_bin/" not in path:
            out.append(path)
    return out


def parse_notes(fname, cols):
    """Per column of one note: the three mark tables, the Scale rows and the focus bullet.

    Returns (cells, marks, focus, shots, scripts, app) where
      cells[cid]   = {"t1": evidence text, "t2": (observed, steps, evidence), "scale": text}
      marks[cid]   = {"t1": proposed mark, "t2": running-app mark}
      app          = {"date", "drivers", "docs_only"} of the "checked in the running app" section
    """
    text = (NOTES / fname).read_text()
    norm = lambda s: s.lower().replace("×", "x").strip()
    labels = {norm(c["audit_label"]): c["id"] for c in cols}

    def label_id(label):      # "all AnnData slots" and "cell x cell ..." are variants of the audit labels
        n = norm(label)
        return labels.get(n) or next((cid for a, cid in labels.items() if len(n) > 8 and a.startswith(n)), None)
    cells, marks = {}, {}
    m = re.search(r"(?:- `|\*\*)Column 3 \(strict\)[^`*]*?: ([YPN?])(?:`|\*\*)(.*?)(?=\n- `|\n\n|\n###|\Z)", text, re.S)
    focus = m.group(1) if m else None
    focus_text = re.sub(r"^\s*\([^)]*\)", "", m.group(2)).strip().lstrip(",. ") if m else ""
    for heading, rows in md_tables(text):
        head = [h.lower() for h in rows[0]]
        if head[:1] == ["column"] and "proposed" in head and "evidence" in head:          # table 1
            pr, ev = head.index("proposed"), head.index("evidence")
            for r in rows[1:]:
                cid = label_id(r[0])
                if cid and len(r) > ev:
                    cells.setdefault(cid, {})["t1"] = r[ev]
                    mk = mark_of(r[pr])
                    if mk:
                        marks.setdefault(cid, {})["t1"] = mk
        elif head[:3] == ["column", "mark", "observed"]:                                  # table 2
            for r in rows[1:]:
                r = r + [""] * (5 - len(r))
                num = re.match(r"(\d+)\s", r[0])
                if num:
                    cid = AUDIT_ORDER[int(num.group(1)) - 1]
                elif r[0].startswith("plots render"):
                    e = re.search(r"every cell: ([YPN?])", r[1])
                    if not e:
                        continue
                    cid = "every_cell"
                else:
                    continue
                mk = e.group(1) if cid == "every_cell" else mark_of(r[1], focus)
                if mk:
                    marks.setdefault(cid, {})["t2"] = mk
                if "see Focus section" not in r[2]:
                    cells.setdefault(cid, {})["t2"] = (r[2], r[3], r[4])
        elif head[:2] == ["item", "finding"]:
            for r in rows[1:]:
                key = r[0].split()[0]
                if key in SCALE_ITEMS:
                    cid = SCALE_ITEMS[key]
                    cells.setdefault(cid, {})["scale"] = r[1] + (" Evidence: " + r[2] if len(r) > 2 else "")
    if focus_text:
        cells.setdefault("focus", {})["focus"] = focus_text
    app_sec = section(text, "Matrix marks, checked in the running app")
    intro = app_sec.split("\n|", 1)[0]
    # "Contradictions found:" under the running-app table: "Column 12, shareable view state: Y -> **P**"
    # (the table's Mark cell may still carry the old mark; the contradiction is the verdict)
    for num, new in re.findall(r"[Cc]olumn (\d+), [^:\n]+: [YPN?] -> \**([YPN?])", app_sec):
        marks.setdefault(AUDIT_ORDER[int(num) - 1], {})["t2"] = new
    d = re.search(r"(\d{4}-\d\d-\d\d)", intro)
    app = {"date": d.group(1) if d else None, "drivers": drivers(intro),
           "docs_only": "was not run" in intro}
    shots = sorted({p for p in re.findall(r"\((screens/[^)]+\.(?:jpg|png))\)", section(text, "Focus"))})
    scripts = sorted({p for p in re.findall(r"\((demos/[^)#]+)\)", text)})
    return cells, marks, focus, shots, scripts, app


def str_presenter(dumper, data):
    style = "|" if "\n" in data else (">" if len(data) > 100 else None)
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


def compose_detail(c, app):
    """detail: the running-app observation first, then the source/docs evidence."""
    parts = []
    if "focus" in c:
        parts.append("**Focus, checked in the running app.** " + c["focus"])
    if "t2" in c:
        obs, steps, ev = c["t2"]
        head = "**Checked in the docs" if app.get("docs_only") else "**Checked in the running app"
        parts.append(f"{head} ({app.get('date') or CHECKED}).** {obs}"
                     + (f" *Steps:* {steps}" if steps.strip() else "")
                     + (f" *Evidence:* {ev}" if ev.strip() and ev.strip() != "observation" else ""))
    if "t1" in c:
        parts.append("**Source and docs.** " + c["t1"])
    if "scale" in c:
        parts.append("**Scale group.** " + c["scale"])
    return "\n\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--out", type=Path, default=OUT, help="write here instead (dry run)")
    args = ap.parse_args()
    only = set(filter(None, args.only.split(",")))
    cols = columns()
    ids = [c["id"] for c in cols]
    fig = {name: (marks.replace(" ", ""), scale) for name, marks, scale in figure_tools()}
    prop, sel = summary_proposed()
    yaml.add_representer(str, str_presenter)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    for order, (name, (tid, fname)) in enumerate(TOOLS.items()):
        if only and tid not in only:
            continue
        if fname is None:       # AnnZarro: audited by hand (evidence/notes/annzarro.md), never re-seeded
            continue
        note_text = (NOTES / fname).read_text()
        details, nmarks, focus, shots, scripts, app = parse_notes(fname, cols)
        doc = {"id": tid, "name": name.replace(" code", ""),
               "figure": {"row": order + 1, "label": name, "largest_documented": fig[name][1]} if name in fig else None,
               "notes": f"notes/comparison/{fname}",
               "cells": {}}
        figmarks = dict(zip(ids, fig[name][0])) if name in fig else {}
        prev_file = OUT / f"{tid}.yaml"     # hand-added evidence survives a re-seed
        prev = (yaml.safe_load(prev_file.read_text()) or {}).get("cells", {}) if prev_file.exists() else {}
        summary = dict(zip(AUDIT_ORDER, prop[name])) if name in prop else {}
        for cid in ids:
            # mark precedence: running-app table, focus bullet, Matrix row "Proposed",
            # _summary.md, then the Scale prose read under reading A
            nm = nmarks.get(cid, {})
            audit = (nm.get("t2") or (focus if cid == "focus" else None) or nm.get("t1")
                     or summary.get(cid) or SCALE_A.get(tid, {}).get(cid))
            cell = {}
            if cid in figmarks:
                cell["mark"] = figmarks[cid]
            if audit and audit != figmarks.get(cid):
                cell["proposed"] = audit
            if "mark" not in cell and "proposed" not in cell:
                continue
            c = details.get(cid, {})
            d = compose_detail(c, app)
            if d:
                lead = c.get("focus") or (c["t2"][0] if "t2" in c else "") or c.get("t1") or c.get("scale") or ""
                cell["reason"] = first_sentence(lead)
                cell["detail"] = d
                ev = evidence(d, NOTES)
                if ev:
                    cell["evidence"] = ev
            prefs = refs.paper_refs(tid, cid)
            if prefs:
                cell.setdefault("evidence", []).extend(prefs)
            elif refs.no_paper_reason(tid):
                cell.setdefault("na", {})["paper"] = refs.no_paper_reason(tid)
            have = {e.get("url") or e.get("path") for e in cell.get("evidence") or []}
            for e in (prev.get(cid) or {}).get("evidence") or []:
                key = e.get("url") or e.get("path") or ""
                # keep hand-added references (they carry `checked`) and links the note still cites
                if key not in have and e["kind"] in ("docs", "paper", "code") and (e.get("checked") or key in note_text):
                    cell.setdefault("evidence", []).append(e)
                    have.add(key)
            for k, v in ((prev.get(cid) or {}).get("na") or {}).items():
                cell.setdefault("na", {}).setdefault(k, v)                 # hand-set n/a reasons survive too
            for e in cell.get("evidence") or []:
                refs.enrich(e)
            if cid == "focus":
                cell.setdefault("evidence", []).extend(
                    {"kind": "screenshot", "path": f"notes/comparison/{p}"} for p in shots
                    if f"notes/comparison/{p}" not in have)
            rep = [f"notes/comparison/{s}" for s in scripts if "focus" in s] if cid == "focus" else []
            if "t2" in nm:
                rep += [x for x in app["drivers"] if x not in rep]
            if rep:
                cell["reproduce"] = rep
            on_app = "t2" in nm or cid == "focus"
            cell["checked"] = {"date": (app.get("date") if "t2" in nm else None) or CHECKED, "by": "comparison-auditor",
                               "how": ("docs" if app.get("docs_only") else "running app") if on_app else "source and docs"}
            doc["cells"][cid] = cell
        if name in sel:
            mark, observed, shot = sel[name]
            doc["proposed_columns"] = {"selection": {
                "proposed": mark, "reason": observed, "evidence": evidence(shot, NOTES),
                "checked": {"date": CHECKED, "by": "comparison-auditor", "how": "running app"}}}
        header = (f"# {name}: Fig. 1c marks and their evidence.\n"
                  f"# Seeded by evidence/tools/import_notes.py from {doc['notes']} and\n"
                  "# figures/fig_comparison.py; edit this file from now on (schema: evidence/README.md).\n")
        (out / f"{tid}.yaml").write_text(header + yaml.dump(doc, sort_keys=False, allow_unicode=True, width=100))
        print(tid, len(doc["cells"]), "cells")


if __name__ == "__main__":
    sys.exit(main())
