"""Fig. 1c rows as the figure draws them: TOOLS with the scale reading applied.

figures/fig_comparison.py keeps TOOLS under reading A and applies READING_B overrides when
SCALE_READING == "B" (scored()). This module reads those constants with ast (no matplotlib
import) and applies the same rule, so the evidence YAML is compared with what is drawn.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _py():
    """The Python that draws the figure (needs pandas and matplotlib): $EVIDENCE_FIG_PYTHON, else the
    repository's .venv when there is one (the laptop), else the interpreter running the build (a clean
    clone with evidence/requirements.txt installed)."""
    import os
    import sys
    env = os.environ.get("EVIDENCE_FIG_PYTHON")
    if env:
        return env
    venv = REPO / ".venv/bin/python"
    return str(venv) if venv.exists() else sys.executable


def _consts():
    tree = ast.parse((REPO / "figures/fig_comparison.py").read_text())
    out = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and \
                n.targets[0].id in ("TOOLS", "SCALE_READING", "READING_B", "_SCALE_POS"):
            out[n.targets[0].id] = ast.literal_eval(n.value)
    return out


def figure_tools():
    """[(row name, marks without spaces, as drawn), size label] in figure order."""
    c = _consts()
    reading, over, pos_of = c.get("SCALE_READING", "A"), c.get("READING_B", {}), c.get("_SCALE_POS", {})
    rows = []
    for name, marks, scale in c["TOOLS"]:
        vals = list(marks.replace(" ", ""))
        if reading == "B":
            for col, v in over.get(name, {}).items():
                vals[pos_of[col]] = v
        rows.append((name, "".join(vals), scale))
    return rows


def figure_measured():
    """{figure row: Fig. 1c's measured cell}, exactly as drawn: fig_comparison.measured() run in the
    repo's .venv (it needs pandas); falls back to the re-implementation below if that fails."""
    import json, subprocess
    py = _py()
    code = ("import json,sys; sys.path.insert(0,'.'); import matplotlib; matplotlib.use('Agg'); "
            "import figures.fig_comparison as f; "
            "print(json.dumps({n: f.measured(n) for n, _, _ in f.TOOLS}))")
    try:
        r = subprocess.run([str(py), "-c", code], cwd=REPO, capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            return {k: " ".join(v.split()) for k, v in json.loads(r.stdout.strip().splitlines()[-1]).items()}
    except Exception:
        pass
    return _figure_measured_fallback()


def _figure_measured_fallback():
    """Re-implementation of fig_comparison.measured() without pandas (as of ed30806)."""
    import csv
    c = _consts()
    tree_rows = {}
    src = (REPO / "figures/fig_comparison.py").read_text()
    for n in ast.parse(src).body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "MEASURED_ROWS":
            tree_rows = ast.literal_eval(n.value)
    ceil = {(r["tool"], r["variant"]): r for r in csv.DictReader(open(REPO / "benchmark/tool_ceiling/ceilings.csv"))}

    def cells(n):
        n = float(n)
        return f"{n / 1e6:.3g}M" if n >= 1e6 else f"{n / 1e3:.3g}k"
    out = {}
    synth = REPO / "benchmark/scale/results/ceiling_rerun.csv"    # fig_comparison.SYNTH
    for name, _, _ in c["TOOLS"]:
        rows = tree_rows.get(name)
        if not rows:
            out[name] = "not measured"
            continue
        if name == "AnnZarro":   # real data are a lower bound; the browser ceiling is the synthetic one
            r = ceil.get(tuple(rows[0])) or {}
            ok = [float(x["n_cells"]) for x in csv.DictReader(open(synth))
                  if str(x.get("clean", "")).lower() == "true" and x.get("status") == "ok"]
            out[name] = (f'{str(r.get("figure_value") or "?").replace(">=", "≥")} (real); '
                         + (f"{cells(max(ok))} synthetic" if ok else "no synthetic"))
            continue
        parts = []
        for key in map(tuple, rows):
            r = ceil.get(key)
            if r is None:
                parts.append("?")
            elif r["rendering"] == "server":
                lower = "lower bound" in (r.get("kind_16gb") or "")
                parts.append(f"server-rendered: {'≥' if lower else ''}{cells(r['max_n_server_16gb'])} (server)")
            else:
                parts.append(str(r.get("figure_value") or "?").replace(">=", "≥"))
        out[name] = " / ".join(parts)
    return out


def figure_strip():
    """{figure row: text of Fig. 1c's measured part of the cells strip, as drawn}.

    The strip draws the largest N drawn in full within 16 GiB as one glyph (8377c36; the kind, what
    stopped the tool at the next size, stays in the model for the hover text); an arrow marks a lower bound (our
    test bed stopped first); a row with no measured stop reads "hosted only"
    (hosted services that cannot load our data) or "n.m." (not measured yet). This mirrors
    strip_points() and HOSTED_ONLY by calling them in the repo's .venv."""
    import json, subprocess
    code = ("import json,sys; sys.path.insert(0,'.'); import matplotlib; matplotlib.use('Agg'); "
            "import figures.fig_comparison as f; out={}\n"
            "for n,_,doc in f.TOOLS:\n"
            "  pts=[p for p in f.strip_points(n, doc) if p[0]!='documented']\n"
            "  out[n]={'pts':[[k,float(v),bool(lo),lab] for k,v,lo,lab in pts],'hosted':n in getattr(f,'HOSTED_ONLY',set())}\n"
            "print(json.dumps(out))")
    r = subprocess.run([_py(), "-c", code], cwd=REPO, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        return None
    raw = json.loads(r.stdout.strip().splitlines()[-1])

    def cells(n):
        return f"{n / 1e6:.3g}M" if n >= 1e6 else f"{n / 1e3:.3g}k"
    out = {}
    for name, v in raw.items():
        if not v["pts"]:
            out[name] = "hosted only" if v["hosted"] else "n.m."
            continue
        parts = []
        for kind, n, lower, lab in v["pts"]:
            who = {"client": "stopped by the client", "server": "stopped by the server",
                   "input": "stopped by the input path"}.get(kind, kind)
            parts.append(f"{(lab + ' ') if lab else ''}{'≥' if lower else ''}{cells(n)}"
                         + (" (our test bed stopped first)" if lower else f" ({who})"))
        out[name] = " / ".join(parts)
    return out


_MODEL = None


def figure_model():
    """Fig. 1c exactly as drawn (evidence/tools/figmodel_dump.py run in the repo's .venv): rows with
    their drawn marks, mark footnotes, † flags, documented text and strip glyphs; the legend texts
    with their glyphs; the column groups and labels; the scale header. Raises if the figure cannot
    be drawn: the site has no fallback, so it can never show a matrix the figure does not."""
    global _MODEL
    if _MODEL is None:
        import json, subprocess
        r = subprocess.run([_py(), str(REPO / "evidence/tools/figmodel_dump.py")],
                           cwd=REPO, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError("figures/fig_comparison.py could not be drawn:\n" + r.stderr[-2000:])
        _MODEL = json.loads(r.stdout.strip().splitlines()[-1])
    return _MODEL


def model_hash(model) -> str:
    import hashlib, json
    return hashlib.sha256(json.dumps(model, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def strip_text(strip, legend) -> str:
    """One row's measured strip in words, in the figure's own legend wording (so the site cannot
    word a stop differently from the paper): each glyph kind reads as its legend entry."""
    import re

    def cells(n):
        return f"{n / 1e9:g}B" if n >= 1e9 else f"{n / 1e6:.3g}M" if n >= 1e6 else f"{n / 1e3:.3g}k"

    def phrase(kind):
        t = next((l["text"] for l in legend if l["glyph"] == kind), None)
        if t is None and kind in ("server", "input"):   # one measured glyph since the 2026-10-08 review
            t = next((l["text"] for l in legend if l["glyph"] == "client"), kind)
        t = t or kind
        return re.sub(r"\s*\((ring|budget)[^)]*\)$", "", t.split("; ")[-1]) if kind == "arrow" else t.split("; ")[-1]
    if not strip:
        return ""
    parts = [f"{(lab + ' ') if lab else ''}{'≥' if lo else ''}{cells(n)}: "
             f"{phrase('arrow') if lo else phrase(k)}"
             for k, n, lo, lab in strip["pts"] if k != "documented"]
    if strip.get("reach"):
        parts.append(f"opens with a subset up to {cells(strip['reach'])}")
    if not strip["measured_any"]:
        parts.insert(0, strip.get("note") or ("hosted only" if strip["hosted"] else "n.m."))
    return " / ".join(parts)
