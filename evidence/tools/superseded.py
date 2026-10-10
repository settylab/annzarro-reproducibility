"""No green claim may rest on a superseded source (evidence/superseded.yaml; build.py --check).

check() returns one error per (claim, source) where a claim with status ok
  - uses a source that matches a superseded entry (file glob, or a table row matching `where`;
    plus every results.csv variant in benchmark/tool_ceiling/summarize.py SUPERSEDED and the
    ceilings_superseded.csv / conversions_superseded.csv files), or
  - uses an AnnZarro measurement source that does not match a `current` entry, i.e. one not
    measured on the release the registry names.
"""
from __future__ import annotations

import ast
import fnmatch
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
REG = REPO / "evidence/superseded.yaml"


def _auto(reg):
    out = list(reg.get("superseded") or [])
    tree = ast.parse((REPO / "benchmark/tool_ceiling/summarize.py").read_text())
    for n in tree.body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "SUPERSEDED":
            sup = ast.literal_eval(n.value)
            for (tool, var), why in sup.items():
                out.append({"csv": "benchmark/tool_ceiling/results.csv", "where": {"tool": tool, "variant": var},
                            "why": f"superseded build: {why}"})
    for f in ("ceilings_superseded.csv", "conversions_superseded.csv"):
        out.append({"file": f"benchmark/tool_ceiling/{f}", "why": "superseded rows"})
    return out


def _path(src):
    return src.get("csv") or src.get("jsonl") or src.get("json") or src.get("file")


def _rows(src):
    """The rows a table source selects (claims.py's own reader and filter)."""
    import claims as C
    rows, _ = C.read_rows(src)
    return [r for r in rows if C.match_where(r, src.get("where"))]


def _where_ok(row, where):
    for k, want in (where or {}).items():
        wants = want if isinstance(want, list) else [want]
        if not any(fnmatch.fnmatch(str(row.get(k, "")), str(w)) for w in wants):
            return False
    return True


def _matches(src, entry, mode):
    """mode 'any': some selected row matches (superseded); 'all': every selected row does (current)."""
    p = _path(src) or ""
    if "file" in entry and "where" not in entry:
        return fnmatch.fnmatch(p, entry["file"])
    if entry.get("csv") != p or not ("csv" in src or "jsonl" in src):
        return False
    rows = _rows(src)
    if not rows:
        return False
    hit = [_where_ok(r, entry.get("where")) for r in rows]
    return any(hit) if mode == "any" else all(hit)


def check():
    import sys
    sys.path.insert(0, str(REPO / "evidence/tools"))
    reg = yaml.safe_load(REG.read_text())
    sup, cur, meas = _auto(reg), reg.get("current") or [], reg.get("annzarro_measurements") or []
    claims = yaml.safe_load((REPO / "evidence/claims.yaml").read_text())["claims"]
    exempt = {e["claim"] for e in reg.get("exempt") or []}
    errs = []
    for cid, c in claims.items():
        if not isinstance(c, dict) or c.get("status", "ok") != "ok" or cid in exempt:
            continue
        srcs = c.get("source")
        for s in (srcs if isinstance(srcs, list) else [srcs]):
            if not isinstance(s, dict) or "matrix" in s or not _path(s):
                continue
            try:
                bad = next((e for e in sup if _matches(s, e, "any")), None)
                if bad:
                    errs.append(f"{cid}: source {_path(s)} {s.get('where') or ''} is superseded ({bad.get('why', '')})")
                    continue
                if any(_matches(s, e, "any") for e in meas) and not any(_matches(s, e, "all") for e in cur):
                    errs.append(f"{cid}: AnnZarro source {_path(s)} {s.get('where') or ''} is not on the current "
                                f"release ({reg['release']['annzarro']['version']})")
            except Exception as e:      # an unreadable source is claims.py's error to report
                errs.append(f"{cid}: source {_path(s)} could not be read ({type(e).__name__}: {e})")
    return errs


if __name__ == "__main__":
    e = check()
    print("\n".join(e) or "no green claim on a superseded or non-current source")
    raise SystemExit(1 if e else 0)
