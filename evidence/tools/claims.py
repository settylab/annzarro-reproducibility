#!/usr/bin/env python
"""Claims ledger: every number and comparison in the manuscript, recomputed from its source.

The ledger is evidence/claims.yaml. The manuscript marks each claim with a LaTeX comment
on the claim's line or on its own line directly before it:

    %claim{scale.ceiling.175M}            one id
    %claim{a} %claim{b}  or  %claim{a,b}  several ids on one line

A marker binds to its own line if that line has text before the %, and to the next line
with text otherwise. The claim's `text` must occur in the bound line (or, for a marker
trailing a text line, in the line after it).

Entry schema (claims.yaml, `claims:` maps id -> entry):

    text:    exact phrase as in the tex ("175 million"); matched after light de-TeXing
    file:    manuscript/body.tex
    context: (optional) a longer phrase that is unique in the file, used to find the line
    kind:    number | comparison | qualitative
    source:  one source or a list; each yields one value
      {csv: path, where: {col: value | [values]}, column: name, agg: one|min|max|median|mean|sum|count|first|last,
       group_by: col, then: min|max|..., pattern: regex, format: "{:.1f} s"}
      {jsonl: path, ...same; column may be a dotted path}
      {json: path or glob, key: dotted.path, exclude: glob, agg: ..., pattern: regex}
      {file: path, anchor: "text that must occur", pattern: "regex with one group -> value"}
      {matrix: "<tool>.<column>", expect: Y | [Y, P]}       mark in evidence/matrix/tools/<tool>.yaml
    compute: (optional) Python expression over v (list of source values) -> value or tuple
    format:  (optional) template applied to the value(s): "{0:.0f} to {1:.0f} s"
    tolerance: (optional) absolute (0.05) or relative ("5%"), compared number by number
    status:  ok | interim | unsourced
    note:    free text

Checks (exit 1 on any error):
  - a marker whose id has no entry;
  - an entry without a marker, once the manuscript has any marker (before that: "unplaced");
  - an entry whose text is not found near its marker (or anywhere in its file);
  - a value that does not reproduce: recompute, format, compare with the text;
  - a matrix claim that disagrees with the YAML mark.
Warnings: numbers with units or scale words in prose that no entry covers.

Usage:
  python evidence/tools/claims.py            # check; exit 0 clean, 1 errors, 2 bad ledger
  python evidence/tools/claims.py --list     # marker list for the manuscript
  python evidence/tools/claims.py --json     # full results as JSON
  python evidence/tools/claims.py --strict   # unmarked numbers are errors too

Stdlib plus PyYAML only.
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import glob
import json
import math
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "evidence/claims.yaml"
MATRIX = REPO / "evidence/matrix/tools"
TEX_GLOBS = ["manuscript/*.tex", "manuscript/sections/*.tex"]

MARKER = re.compile(r"%\s*claim\{([^}]*)\}")


# --------------------------------------------------------------------------- tex helpers
def code_part(line):
    """The line before its first unescaped % (a % inside \\url{} or \\href{} is part of the URL)."""
    masked = re.sub(r"\\(?:url|href)\{[^}]*\}", lambda m: "x" * len(m.group(0)), line)
    m = re.search(r"(?<!\\)%", masked)
    return line[:m.start()] if m else line


def detex(s):
    """Light normalisation so a tex phrase and a formatted value compare equal."""
    s = s.replace("\\%", "%").replace("{,}", ",").replace("\\,", " ").replace("~", " ")
    s = s.replace("$\\times$", "×").replace("\\times", "×").replace("$", "")
    s = s.replace("---", "—").replace("--", "–")
    s = re.sub(r"(?<=\d)–(?=\d)", "-", s)   # a numeric range compares equal with an en dash or a hyphen
    s = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", s)   # a link compares as its shown text
    s = re.sub(r"\\(?:textbf|textit|emph|texttt|mathrm)\{([^}]*)\}", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def tex_files():
    out = []
    for g in TEX_GLOBS:
        out += sorted(REPO.glob(g))
    return out


@dataclass
class TexFile:
    rel: str
    lines: list
    code: list = field(default_factory=list)
    skip: set = field(default_factory=set)      # line numbers (1-based) not scanned for numbers

    @classmethod
    def load(cls, path):
        lines = path.read_text().split("\n")
        tf = cls(path.relative_to(REPO).as_posix(), lines, [code_part(l) for l in lines])
        inside = False
        begun = "\\begin{document}" not in path.read_text()
        for i, l in enumerate(lines, 1):
            if "\\begin{document}" in l:
                begun = True
            if not begun:
                tf.skip.add(i)
            if re.search(r"\\begin\{lstlisting\}", l):
                inside = True
            if inside:
                tf.skip.add(i)
            if re.search(r"\\end\{lstlisting\}", l):
                inside = False
        return tf

    def next_text_line(self, i):
        """1-based index of the first line at or after i with text before any %."""
        while i <= len(self.lines):
            if self.code[i - 1].strip():
                return i
            i += 1
        return None


def find_in_line(code, text):
    """Spans of text in a line, raw first, then de-TeXed (span is then approximate: whole line)."""
    spans = [(m.start(), m.end()) for m in re.finditer(re.escape(text), code)]
    if spans:
        return spans
    if detex(text) and detex(text) in detex(code):
        # locate by the first number of the text, so the span still covers it
        nums = re.findall(r"\d[\d,.]*", text)
        if nums:
            # a whole number, not the tail of a longer one ("5.6" inside "95.6")
            m = re.search(r"(?<![\d.,])" + re.escape(nums[0]) + r"(?![\d])", code)
            if m:
                j = m.start()
                return [(j, j + max(len(text), len(nums[0])))]
        return [(0, len(code))]
    return []


# --------------------------------------------------------------------------- sources
class SourceError(Exception):
    pass


def num(x):
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return x
    s = str(x).strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return x


def dotted(obj, key):
    """Dotted lookup that tolerates dots inside keys ("n_rho_gt_0.7") and list indices."""
    parts = key.split(".") if key else []
    i = 0
    while i < len(parts):
        if isinstance(obj, list):
            try:
                obj = obj[int(parts[i])]
            except (ValueError, IndexError):
                raise SourceError(f"no index {parts[i]!r}")
            i += 1
            continue
        if not isinstance(obj, dict):
            raise SourceError(f"cannot descend into {type(obj).__name__} at {'.'.join(parts[:i])!r}")
        for j in range(len(parts), i, -1):          # longest key first
            k = ".".join(parts[i:j])
            if k in obj:
                obj = obj[k]
                i = j
                break
        else:
            raise SourceError(f"no key {parts[i]!r} under {'.'.join(parts[:i]) or 'root'!r}")
    return obj


def apply_pattern(val, pattern):
    m = re.search(pattern, str(val))
    if not m:
        raise SourceError(f"pattern {pattern!r} not found")
    return num(m.group(1) if m.groups() else m.group(0))


AGG = {
    "min": min, "max": max, "sum": sum, "count": len, "first": lambda v: v[0], "last": lambda v: v[-1],
    "median": statistics.median, "mean": statistics.fmean,
}


def aggregate(vals, how, what):
    if not vals:
        raise SourceError(f"no rows match {what}")
    if how in (None, "one"):
        if len(vals) != 1:
            raise SourceError(f"{len(vals)} rows match {what}; give agg: or a narrower where:")
        return vals[0]
    if how not in AGG:
        raise SourceError(f"unknown agg {how!r}")
    return AGG[how](vals)


def match_where(row, where):
    for k, want in (where or {}).items():
        have = row.get(k)
        wants = want if isinstance(want, list) else [want]
        if not any(str(have) == str(w) or (num(have) == num(w) and not isinstance(num(have), str)) for w in wants):
            return False
    return True


_cache = {}


def read_rows(spec):
    if "csv" in spec:
        p = REPO / spec["csv"]
        if p not in _cache:
            with open(p) as f:
                _cache[p] = list(csv.DictReader(l for l in f if not l.startswith("#")))
        return _cache[p], spec["csv"]
    p = REPO / spec["jsonl"]
    if p not in _cache:
        _cache[p] = [json.loads(l) for l in open(p) if l.strip()]
    return _cache[p], spec["jsonl"]


def eval_table(spec):
    rows, path = read_rows(spec)
    rows = [r for r in rows if match_where(r, spec.get("where"))]
    col = spec.get("column")
    what = f"{path} where {spec.get('where')}"

    def val(r):
        if col is None:
            return 1
        v = dotted(r, col) if "jsonl" in spec else r.get(col)
        if v is None:
            raise SourceError(f"{path}: no column {col!r}")
        if v == "":
            return None
        if spec.get("pattern"):
            v = apply_pattern(v, spec["pattern"])
        return num(v)

    if spec.get("agg") == "count":
        return len(rows), rows
    if spec.get("group_by"):
        groups = {}
        for r in rows:
            x = val(r)
            if x is not None:
                groups.setdefault(r.get(spec["group_by"]), []).append(x)
        per = [aggregate(v, spec.get("agg", "max"), what) for v in groups.values()]
        return aggregate(per, spec.get("then", "max"), what), rows
    vals = [x for x in (val(r) for r in rows) if x is not None]
    return aggregate(vals, spec.get("agg"), what), rows


def eval_json(spec):
    paths = sorted(glob.glob(str(REPO / spec["json"])))
    if spec.get("exclude"):
        paths = [p for p in paths if not fnmatch.fnmatch(Path(p).name, spec["exclude"])]
    if not paths:
        raise SourceError(f"no file {spec['json']}")
    vals = []
    for p in paths:
        v = dotted(json.loads(Path(p).read_text()), spec.get("key", ""))
        if spec.get("pattern"):
            v = apply_pattern(v, spec["pattern"])
        vals.append(num(v))
    rel = [Path(p).relative_to(REPO).as_posix() for p in paths]
    return (aggregate(vals, spec.get("agg"), spec["json"]) if len(vals) > 1 or spec.get("agg") else vals[0]), rel


def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def eval_file(spec):
    p = REPO / spec["file"]
    if not p.exists():
        raise SourceError(f"no file {spec['file']}")
    text = p.read_text(errors="replace")
    line = None
    if spec.get("anchor"):
        a = spec["anchor"]
        i = text.find(a)
        if i < 0:
            j = norm_ws(text).lower().find(norm_ws(a).lower())
            if j < 0:
                raise SourceError(f"anchor {a!r} not in {spec['file']}")
            line = None
        else:
            line = text.count("\n", 0, i) + 1
    if spec.get("pattern"):
        m = re.search(spec["pattern"], text)
        if not m:
            raise SourceError(f"pattern {spec['pattern']!r} not in {spec['file']}")
        line = text.count("\n", 0, m.start()) + 1
        return num(m.group(1) if m.groups() else m.group(0)), (line, m.group(0))
    return True, (line, spec.get("anchor"))


def load_matrix():
    out = {}
    for p in MATRIX.glob("*.yaml"):
        t = yaml.safe_load(p.read_text())
        out[t["id"]] = t
    return out


def eval_matrix(spec, matrix):
    tool, _, col = spec["matrix"].partition(".")
    t = matrix.get(tool)
    if t is None:
        raise SourceError(f"no tool {tool!r} in evidence/matrix/tools")
    cell = (t.get("cells") or {}).get(col)
    if cell is None:
        raise SourceError(f"{tool} has no cell {col!r}")
    mark = cell.get("mark") or cell.get("proposed")
    return mark, cell.get("proposed") if cell.get("mark") else None


SAFE = {"math": math, "min": min, "max": max, "abs": abs, "round": round, "sum": sum, "len": len,
        "ceil": math.ceil, "range": range, "sorted": sorted, "any": any, "all": all, "floor": math.floor, "log2": math.log2, "sqrt": math.sqrt, "float": float, "int": int,
        "nan": float("nan")}


def describe(spec):
    for k in ("csv", "jsonl", "json", "file", "matrix"):
        if k in spec:
            return k, spec[k]
    return "?", "?"


# --------------------------------------------------------------------------- evaluation
@dataclass
class Result:
    id: str
    entry: dict
    status: str = ""            # reproduced | mismatch | interim | unsourced
    rendered: str | None = None
    values: list = field(default_factory=list)
    problems: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    sources: list = field(default_factory=list)  # [{kind, path, detail, line, rows}]
    markers: list = field(default_factory=list)  # [(file, marker line, bound line)]
    line: int | None = None                      # where the text is (bound line, else first search hit)
    candidates: list = field(default_factory=list)
    placed: bool = False


def render(entry, vals, srcs):
    fmt = entry.get("format")
    if fmt is None and len(srcs) == 1 and srcs[0].get("format"):
        fmt = srcs[0]["format"]
    if fmt is None and len(srcs) > 1 and all(s.get("format") for s in srcs):
        return " ".join(s["format"].format(v) for s, v in zip(srcs, vals))
    if fmt is None:
        return None
    if isinstance(vals, tuple):
        return fmt.format(*vals)
    return fmt.format(vals)


def numbers_in(s):
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*\.?\d*(?:[eE]-?\d+)?", detex(s))
            if re.search(r"\d", x)]


def within(a, b, tol):
    if isinstance(tol, str) and tol.endswith("%"):
        return abs(a - b) <= abs(b) * float(tol[:-1]) / 100
    return abs(a - b) <= float(tol)


def evaluate_entry(cid, entry, matrix):
    r = Result(cid, entry)
    srcs = entry.get("source") or []
    if isinstance(srcs, dict):
        srcs = [srcs]
    status = entry.get("status", "ok")
    if status == "unsourced" and not srcs:
        r.status = "unsourced"
        return r
    vals = []
    for s in srcs:
        kind, path = describe(s)
        info = {"kind": kind, "path": path, "spec": s, "line": None}
        try:
            if kind in ("csv", "jsonl"):
                v, rows = eval_table(s)
                info["rows"] = len(rows)
                info["detail"] = ", ".join(f"{k}={w}" for k, w in (s.get("where") or {}).items())
                info["detail"] += (f"; {s.get('column')}" if s.get("column") else "") + (f"; {s.get('agg', 'max')} per {s['group_by']}, then {s.get('then', 'max')}" if s.get("group_by")
                                   else f"; {s['agg']}" if s.get("agg") else "")
            elif kind == "json":
                v, files = eval_json(s)
                info["detail"] = s.get("key", "")
                info["files"] = files
            elif kind == "file":
                v, (line, matched) = eval_file(s)
                info["line"] = line
                info["detail"] = "“" + re.sub(r"\s+", " ", str(matched))[:160] + "”"
            elif kind == "matrix":
                v, proposed = eval_matrix(s, matrix)
                want = s.get("expect")
                wants = want if isinstance(want, list) else [want]
                info["detail"] = f"mark {v}" + (f", expected {'/'.join(map(str, wants))}" if want else "")
                tool, _, col = s["matrix"].partition(".")
                info["tool"], info["column"] = tool, col
                if want is not None and v not in wants:
                    r.problems.append(f"matrix {s['matrix']}: mark {v}, the text needs {'/'.join(map(str, wants))}")
                if want is not None and proposed and proposed not in wants:
                    r.warnings.append(f"matrix {s['matrix']}: pending proposal {proposed} would contradict the text")
            else:
                raise SourceError("source needs one of csv, jsonl, json, file, matrix")
            info["value"] = v
            vals.append(v)
        except (SourceError, OSError, KeyError, ValueError, TypeError) as e:
            info["error"] = str(e)
            r.problems.append(f"{kind} {path}: {e}")
        r.sources.append(info)
    r.values = vals
    if r.problems and len(vals) < len(srcs):
        r.status = "mismatch" if status != "unsourced" else "unsourced"
        return r
    value = vals[0] if len(vals) == 1 else tuple(vals)
    if entry.get("compute"):
        try:
            value = eval(str(entry["compute"]), dict(SAFE, v=vals, __builtins__={}))
        except Exception as e:  # noqa: BLE001  (ledger expressions are ours; report, don't crash)
            r.problems.append(f"compute {entry['compute']!r}: {e}")
            r.status = "mismatch"
            return r
    try:
        r.rendered = render(entry, value, srcs)
    except (ValueError, TypeError, IndexError) as e:
        r.problems.append(f"format: {e}")
    if r.rendered is not None:
        text = entry.get("text", "")
        if detex(r.rendered) != detex(text):
            # with a tolerance, compare number by number: the rendered phrase and the text come
            # from the same template, so their numbers line up; the recomputed value replaces
            # the rounded rendered number where one is available
            tol = entry.get("tolerance")
            want, have = numbers_in(text), numbers_in(r.rendered)
            got = [g for g in (list(value) if isinstance(value, tuple) else [value]) if isinstance(g, (int, float))]
            ok = (tol is not None and len(want) == len(have) and
                  re.sub(r"[\d.,]+", "#", detex(text)) == re.sub(r"[\d.,]+", "#", detex(r.rendered)) and
                  all(w == h or any(within(w, g, tol) for g in got) for w, h in zip(want, have)))
            if not ok:
                r.problems.append(f"recomputed {r.rendered!r}, text says {text!r}")
    if status == "unsourced":
        r.status = "unsourced"
    elif r.problems:
        r.status = "mismatch"
    else:
        r.status = "interim" if status == "interim" else "reproduced"
    return r


def scan_markers(texs):
    """{id: [(file, marker line, [candidate lines])]} and a list of (file, line, id) for every marker."""
    found, all_ = {}, []
    for tf in texs.values():
        for i, line in enumerate(tf.lines, 1):
            for m in MARKER.finditer(line):
                ids = [x.strip() for x in m.group(1).split(",") if x.strip()]
                if tf.code[i - 1].strip():
                    cands = [i] + ([tf.next_text_line(i + 1)] if tf.next_text_line(i + 1) else [])
                else:
                    nxt = tf.next_text_line(i + 1)
                    cands = [nxt] if nxt else []
                for cid in ids:
                    found.setdefault(cid, []).append((tf.rel, i, cands))
                    all_.append((tf.rel, i, cid))
    return found, all_


def locate(entry, tf):
    """Lines of tf whose text holds the claim (context first, then text)."""
    text = entry.get("text", "")
    ctx = entry.get("context")
    hits = []
    for i, code in enumerate(tf.code, 1):
        if ctx and not (ctx in code or detex(ctx) in detex(code)):
            continue
        if find_in_line(code, text):
            hits.append(i)
    return hits


# numbers with a unit or scale word; and "N of M"
UNIT = (r"(?:\\%|%|×|\$\\times\$|million|billion|thousand|TiB|GiB|GB|MB|kB|KB|MiB|bytes|B\b|ms\b|s\b|min\b|"
        r"M\b|k\b|cells?\b|genes?\b|datasets\b|parts\b|runs\b|values\b|points\b|chunks\b|lines\b|cores?\b|CPUs\b|"
        r"effective\b|cell lines\b|dense arrays\b|steps?\b|reference cells\b|nearest\b)")
NUM = r"(?<![\w.\\/#-])\d+(?:[,.]\d+)*"
RANGE = rf"{NUM}(?:\s*(?:--|-|–|to|and)\s*\d+(?:[,.]\d+)*)?"
NUM_RE = re.compile(rf"(?:{RANGE})(?:\s|~)*{UNIT}")
OF_RE = re.compile(rf"{NUM}\s+of\s+(?:\w+(?:'s)?\s+){{0,3}}?\d[\d,]*")
IGNORE_RE = re.compile(
    r"\\(?:cite|ref|label|url|href|includegraphics|input|setcounter|def|timing)\{[^}]*\}"
    r"|\\(?:begin|end)\{[^}]*\}(?:\[[^\]]*\])?(?:\{[^}]*\})*"
    r"|Steps?\s+\d+(?:\s*[-–,]\s*\d+)*(?:\s*(?:and|or)\s*\d+)?"
    r"|Figs?\.~?\\ref\{[^}]*\}|Supplementary Fig\.~?\\ref\{[^}]*\}"
    r"|\b(?:Python|zarr-python|zarr|anndata|scanpy|kompot|Chromium|AnnZarro|format|v)\s*\d+(?:\.\d+)*"
    r"|\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}"
    r"|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}"
    r"|\b(?:19|20)\d{2}\b"
    r"|https?://\S+")


def scan_numbers(tf, covered):
    """Unmarked numbers: (line, match, fragment) for numbers no entry covers."""
    out = []
    for i, code in enumerate(tf.code, 1):
        if i in tf.skip or not code.strip():
            continue
        if re.match(r"\s*\\(?:usepackage|documentclass|newcommand|providecommand|definecolor|lstset|setlength|bibliography)", code):
            continue
        masked = IGNORE_RE.sub(lambda m: " " * len(m.group(0)), code)
        spans = covered.get(i, [])
        seen = []
        for rx in (NUM_RE, OF_RE):
            for m in rx.finditer(masked):
                a, b = m.start(), m.end()
                if any(a < e and s < b for s, e in spans) or any(a < e and s < b for s, e in seen):
                    continue
                seen.append((a, b))
                frag = code[max(0, a - 50):min(len(code), b + 30)]
                out.append((i, code[a:b].strip(), frag.strip()))
    return sorted(out)


def load_ledger(path=LEDGER):
    data = yaml.safe_load(path.read_text()) or {}
    claims = data.get("claims") or {}
    if not isinstance(claims, dict):
        raise ValueError("claims.yaml: `claims:` must map id -> entry")
    return claims


def evaluate(ledger_path=LEDGER):
    """Everything the CLI and the site need."""
    claims = load_ledger(ledger_path)
    matrix = load_matrix()
    texs = {tf.rel: tf for tf in (TexFile.load(p) for p in tex_files())}
    found, all_markers = scan_markers(texs)
    markers_exist = bool(all_markers)
    errors, results = [], []
    covered = {}                                   # (file) -> {line: [spans]}
    for cid, entry in claims.items():
        r = evaluate_entry(cid, entry, matrix)
        tf = texs.get(entry.get("file", ""))
        if tf is None:
            r.problems.append(f"file {entry.get('file')!r} is not a scanned manuscript file")
        else:
            r.candidates = locate(entry, tf)
            marks = [m for m in found.get(cid, []) if m[0] == tf.rel]
            other = [m for m in found.get(cid, []) if m[0] != tf.rel]
            if other:
                r.problems.append(f"marker in {other[0][0]}:{other[0][1]}, entry says {tf.rel}")
            if marks:
                r.placed = True
                for f, ml, cands in marks:
                    ok = [c for c in cands if find_in_line(tf.code[c - 1], entry.get("text", ""))]
                    r.markers.append((f, ml, ok[0] if ok else (cands[0] if cands else None)))
                    if not ok:
                        r.problems.append(f"marker at {f}:{ml}: text {entry.get('text')!r} not on the marked line")
                    else:
                        r.line = ok[0]
            elif r.candidates:
                r.line = r.candidates[0]
                if len(r.candidates) > 1:
                    r.warnings.append("text occurs on lines " + ", ".join(map(str, r.candidates))
                                      + "; add context: to pin it")
            else:
                r.problems.append(f"text {entry.get('text')!r} not found in {tf.rel}")
            if markers_exist and not marks:
                r.problems.append("no %claim marker in the manuscript")
            if r.line:
                spans = find_in_line(tf.code[r.line - 1], entry.get("text", ""))
                covered.setdefault(tf.rel, {}).setdefault(r.line, []).extend(spans)
        if r.problems and r.status in ("reproduced", "interim"):
            r.status = "mismatch"
        results.append(r)
    for f, ml, cid in all_markers:
        if cid not in claims:
            errors.append(f"{f}:{ml}: marker %claim{{{cid}}} has no entry in evidence/claims.yaml")
    unmarked = []
    for tf in texs.values():
        for line, match, frag in scan_numbers(tf, covered.get(tf.rel, {})):
            unmarked.append({"file": tf.rel, "line": line, "match": match, "fragment": frag})
    return {"results": results, "errors": errors, "unmarked": unmarked, "markers_exist": markers_exist,
            "texs": texs, "claims": claims}


def counts(ev):
    c = {"claims": len(ev["results"])}
    for st in ("reproduced", "mismatch", "interim", "unsourced"):
        c[st] = sum(1 for r in ev["results"] if r.status == st)
    c["unplaced"] = sum(1 for r in ev["results"] if not r.placed)
    c["unmarked"] = len(ev["unmarked"])
    return c


# --------------------------------------------------------------------------- CLI
def fragment(code, text, width=35):
    j = code.find(text)
    if j < 0:
        return detex(code)[:width * 2]
    a, b = max(0, j - width), min(len(code), j + len(text) + width)
    return ("…" if a else "") + code[a:b].strip() + ("…" if b < len(code) else "")


def print_list(ev, out=sys.stdout):
    texs = ev["texs"]
    by_line = {}
    rows = []
    for r in ev["results"]:
        f = r.entry.get("file", "")
        tf = texs.get(f)
        line = r.line
        if r.placed:
            where = f"marked at {r.markers[0][0]}:{r.markers[0][1]}"
        elif line:
            where = f"own line before L{line}"
            by_line.setdefault((f, line), []).append(r.id)
        else:
            where = "TEXT NOT FOUND: fix the entry first"
        frag = fragment(tf.code[line - 1], r.entry.get("text", "")) if (tf and line) else ""
        amb = " AMBIGUOUS: also on " + ", ".join(f"L{c}" for c in r.candidates[1:]) if len(r.candidates) > 1 and not r.placed else ""
        rows.append((f, line or 0, r.id, where + amb, frag, r.entry.get("text", "")))
    rows.sort()
    print("# Claim markers: id, file:line, the text, the sentence fragment, where to put the marker", file=out)
    print("# Insert from the bottom of each file up, so line numbers stay valid.\n", file=out)
    for f, line, cid, where, frag, text in rows:
        print(f"{cid}\t{f}:{line}\t{text!r}\t{where}\n    {frag}", file=out)
    print("\n# Marker lines to insert (own line directly before the target line; bottom-up):", file=out)
    for (f, line), ids in sorted(by_line.items(), key=lambda kv: (kv[0][0], -kv[0][1])):
        print(f"{f}:{line}\t" + " ".join(f"%claim{{{i}}}" for i in ids), file=out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", action="store_true", help="print the marker list")
    ap.add_argument("--json", action="store_true", help="print results as JSON")
    ap.add_argument("--strict", action="store_true", help="unmarked numbers are errors")
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    a = ap.parse_args(argv)
    try:
        ev = evaluate(a.ledger)
    except (OSError, ValueError, yaml.YAMLError) as e:
        print(f"claims: cannot read the ledger: {e}", file=sys.stderr)
        return 2
    if a.list:
        print_list(ev)
        return 0
    if a.json:
        print(json.dumps({"counts": counts(ev), "errors": ev["errors"], "unmarked": ev["unmarked"],
                          "results": [{"id": r.id, "status": r.status, "rendered": r.rendered, "line": r.line,
                                       "file": r.entry.get("file"), "text": r.entry.get("text"), "placed": r.placed,
                                       "problems": r.problems, "warnings": r.warnings} for r in ev["results"]]},
                         indent=1, default=str))
        return 1 if (ev["errors"] or any(r.problems for r in ev["results"])) else 0
    bad = 0
    for e in ev["errors"]:
        print("ERROR", e)
        bad += 1
    for r in ev["results"]:
        loc = f"{r.entry.get('file')}:{r.line or '?'}"
        for p in r.problems:
            print(f"MISMATCH {r.id} ({loc}): {p}")
            bad += 1
        for w in r.warnings:
            print(f"warn {r.id} ({loc}): {w}")
    if not ev["markers_exist"]:
        print(f"note: no %claim markers yet; {counts(ev)['unplaced']} entries unplaced (run --list)")
    for u in ev["unmarked"]:
        print(f"unmarked {u['file']}:{u['line']}: {u['match']!r}  ({u['fragment']})")
    c = counts(ev)
    print("claims: " + ", ".join(f"{k} {v}" for k, v in c.items()))
    if a.strict and ev["unmarked"]:
        bad += len(ev["unmarked"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
