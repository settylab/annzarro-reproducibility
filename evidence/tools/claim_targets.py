"""Where the site shows each claim: from a claim's sources to page anchors, and back.

targets(entry) maps every source of a claims.yaml entry to the place on the site that details or
draws it (a measurement chart, a ceiling-benchmarker panel, a matrix cell, a figure section, a tool
page), by fixed rules below. reverse() inverts that for the pages: a chart or section lists the
claims it backs. check() is build.py --check's rule: every claim must have at least one target,
unless all its sources are the manuscript itself or evidence/claim_targets.yaml says why it has
no visualization.

Anchors used here are written by the page modules (25_measurements.py, 50_figures.py, build.py
tool pages); evidence/tools/site_smoke.py checks after a build that every link resolves.
"""
from __future__ import annotations

import csv
import fnmatch
import re
from functools import lru_cache
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TC = "benchmark/tool_ceiling"
EVENTS = ("first_plot", "recolour", "recolour_cat", "part_step", "balance")
SCALE_GROUPS = {"all": "every cell", "ceil": "every cell", "sub": "default subset", "conf95": "every cell, point size 1",
                "conf95auto": "every cell, automatic point size"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def tc_anchor(tool, variant):
    if re.search(r"noguard|guard_?off", str(variant)):       # the guard-off runs are one paragraph, not charts
        return "guard-off-edge"
    return f"tc-{slug(tool)}-{slug(variant)}"


def scale_anchor(event, group):
    return f"timing-{slug(event)}-{slug(group)}"


def hpc_anchor(cid):
    return f"hpc-{slug(cid)}"


HPC_LIST = ("benchmarks/hpc.md", "claims", "HPC benchmark: claims")
HPC_RERUN = "J3/T"     # the HPC re-measure (HPC worker), named in every waiting HPC claim's note

# The current HPC runs the site draws (benchmarks/hpc.md), each with its section anchor. Earlier runs
# (j3_v040, the 0.1.1 benchmark/hpc/results) are superseded; j4_v041_local is not a claim source.
HPC_RUNS = {"benchmark/scale/results/hpc/full/j5_v041/": ("j5", "HPC: J5, the Tahoe-100M ladder"),
            "benchmark/scale/results/hpc/full/t_v041_hpctemp_reduced/": ("t", "HPC: T, the public set on $SCRATCH"),
            "benchmark/scale/results/hpc/full/t2_v041_hpctemp_extra/": ("t2", "HPC: T2, the extra set on $SCRATCH")}


def hpc_run(entry):
    """The anchors of the current HPC runs a claim reads, e.g. ['t'] or ['j5']."""
    return sorted({a for s in _srcs(entry) for d, (a, _) in HPC_RUNS.items() if (_path(s) or "").startswith(d)})


def is_hpc(entry):
    """A claim that reads the HPC benchmark (benchmark/hpc/, a current HPC run) or waits for its re-measure."""
    return (any((_path(s) or "").startswith("benchmark/hpc/") for s in _srcs(entry)) or bool(hpc_run(entry))
            or HPC_RERUN in str(entry.get("note", "")))


def hpc_pending(entry):
    """An HPC claim that is not final: interim or unsourced until the re-measure lands."""
    return is_hpc(entry) and entry.get("status") != "ok"


def hpc_claims():
    """[(id, entry)] of every HPC claim, in ledger order."""
    return [(k, e) for k, e in _claims().items() if isinstance(e, dict) and is_hpc(e)]


def _srcs(entry):
    s = entry.get("source")
    return [x for x in (s if isinstance(s, list) else [s]) if isinstance(x, dict)]


def _path(s):
    return s.get("csv") or s.get("jsonl") or s.get("json") or s.get("file")


@lru_cache(None)
def _figures():
    """[(figure id, every path the figure's entry names)] from evidence/figures.yaml."""
    out = []
    for f in yaml.safe_load((REPO / "evidence/figures.yaml").read_text())["figures"]:
        paths = [f.get("script", "")] + list(f.get("outputs") or []) + list(f.get("other_outputs") or [])
        paths += [i["path"] for i in f.get("inputs") or []] + [r["path"] for r in f.get("related") or []]
        paths += [u.get("script", "") for u in f.get("upstream") or []] + list(f.get("code") or [])
        out.append((f["id"], [p for p in paths if p]))
    return out


@lru_cache(None)
def _tools():
    """{notes path: tool id} and {tool id} from evidence/matrix/tools/*.yaml."""
    notes, ids = {}, set()
    for p in (REPO / "evidence/matrix/tools").glob("*.yaml"):
        t = yaml.safe_load(p.read_text())
        ids.add(t["id"])
        notes[t["notes"].split("#")[0]] = t["id"]
    return notes, ids


@lru_cache(None)
def _subset_variants():
    import ast
    for n in ast.parse((REPO / TC / "summarize.py").read_text()).body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "SUBSET_OF":
            return {v for (_, v) in ast.literal_eval(n.value)}
    return set()


@lru_cache(None)
def _merge():
    import ast
    for n in ast.parse((REPO / TC / "summarize.py").read_text()).body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "MERGE":
            return ast.literal_eval(n.value)
    return {}


@lru_cache(None)
def _registry():
    p = REPO / "evidence/claim_targets.yaml"
    return yaml.safe_load(p.read_text()) if p.exists() else {}


def _one(w):
    return w[0] if isinstance(w, list) and w else w


def source_target(s, cid):
    """(page, anchor, label) for one source, or None."""
    if "matrix" in s:
        tool, col = s["matrix"].split(".", 1)
        return (f"tools/{tool}.md", f"col-{col}", f"matrix: {tool} · {col}")
    p, w = _path(s) or "", s.get("where") or {}
    if p == f"{TC}/ceilings.csv":
        if w.get("tool") and w.get("variant"):
            return ("measurements/tool-ceiling.md", tc_anchor(_one(w["tool"]), _one(w["variant"])),
                    f"tool ceiling: {_one(w['tool'])} · {_one(w['variant'])}")
        return ("measurements/tool-ceiling.md", "", "tool ceiling: every tool")
    if p == f"{TC}/results.csv":
        tool, var = _one(w.get("tool")), _one(w.get("variant"))
        if var in _subset_variants():
            return ("measurements/scale.md", "subset-reach", "scale: subset reach")
        if tool and var:
            var = _merge().get((tool, var), var)
            return ("measurements/tool-ceiling.md", tc_anchor(tool, var), f"tool ceiling: {tool} · {var}")
        return ("measurements/tool-ceiling.md", "", "tool ceiling")
    if p in (f"{TC}/server_profile_1b.csv", f"{TC}/subset_request_times.csv"):
        return ("benchmarks/hpc.md", "server-1b", "server: the 1B run")
    m = re.fullmatch(r"benchmark/scale/results/browser_v\d+_(events|summary)\.csv", p)
    if m and w.get("tag"):
        group = str(_one(w["tag"])).split("_")[0]
        if group in SCALE_GROUPS:
            group = "all" if group == "ceil" else group
            if w.get("event") in EVENTS:
                return ("measurements/scale.md", scale_anchor(w["event"], group),
                        f"scale: {w['event'].replace('_', ' ')}, {SCALE_GROUPS[group]}")
            if str(s.get("column", "")).endswith("_gb"):
                return ("measurements/scale.md", f"memory-{group}", f"scale: memory, {SCALE_GROUPS[group]}")
            return ("measurements/scale.md", scale_anchor("first_plot", group), f"scale: first plot, {SCALE_GROUPS[group]}")
    if re.fullmatch(r"benchmark/scale/results/prewarm\w*_v\d+\.jsonl", p):
        return ("measurements/scale.md", "name-index", "scale: first search by name")
    if p.startswith("figures/scale/"):
        return ("figures/index.md", "scale", "figure: scale")
    if p == "benchmark/scale/NOTES.md":
        return ("measurements/scale.md", "", "scale: every run")
    if p == "figures/PERFORMANCE_NOTES.md":
        return ("figures/index.md", "performance", "figure: performance")
    if p.startswith("notes/comparison/demos/scale_probe/"):
        _, ids = _tools()
        tid = next((t for t in sorted(sorted(ids), key=len, reverse=True) if t.split("-")[0] in cid), None)   # ties by name: a set's order differs per run
        if tid:
            return (f"tools/{tid}.md", "", f"tool page: {tid}")
    if p.startswith("benchmark/hpc/results/"):
        return HPC_LIST
    for d, (anchor, label) in HPC_RUNS.items():
        if p.startswith(d):
            return ("benchmarks/hpc.md", anchor, label)
    if p == "benchmark/hpc/FINDINGS.md":
        return ("benchmarks/hpc.md", "", "HPC benchmark")
    if p in (f"{TC}/README.md", f"{TC}/NOTES.md"):
        return ("measurements/rules.md", "", "rules behind the results")
    notes, ids = _tools()
    if p in notes:
        return (f"tools/{notes[p]}.md", "audit-notes", f"tool page: {notes[p]}")
    if p == "notes/sources/scsva_2019.txt" or p.startswith("notes/comparison/scsva/"):
        return ("comparison/not-comparable.md", "scsva", "not comparable: scSVA")
    m = re.fullmatch(r"notes/comparison/demos/([\w-]+)/.*", p)
    if m:
        tid = next((t for t in sorted(ids) if t.startswith(m.group(1))), None)
        if tid:
            return (f"tools/{tid}.md", "", f"tool page: {tid}")
    m = re.fullmatch(r"evidence/matrix/tools/([\w-]+)\.yaml", p)
    if m:
        return (f"tools/{m.group(1)}.md", "", f"tool page: {m.group(1)}")
    if p.startswith("notes/sources/annzarro_"):
        return ("tools/annzarro.md", "", "tool page: annzarro")
    for fid, paths in _figures():
        if any(fnmatch.fnmatch(p, q) or fnmatch.fnmatch(q, p) or p == q for q in paths):
            return ("figures/index.md", fid, f"figure: {fid}")
    return None


@lru_cache(None)
def _claims():
    return yaml.safe_load((REPO / "evidence/claims.yaml").read_text())["claims"]


def _entry(cid):
    return _claims().get(cid, {})


def targets(cid, entry=None):
    """Unique (page, anchor, label) targets of a claim, in source order."""
    entry = entry or _entry(cid)
    if hpc_pending(entry):              # its sources are the 0.1.1 series, which the site does not show
        return [("benchmarks/hpc.md", hpc_anchor(cid), "HPC: waits for J3/T")]
    out = [HPC_LIST] if is_hpc(entry) else []
    for s in _srcs(entry):
        t = source_target(s, cid)
        if t and t not in out:
            out.append(t)
    return out


def no_visual(cid, entry=None):
    """The reason a claim has no target, or None: its sources are the manuscript only, or the registry says."""
    entry = entry or _entry(cid)
    reg = {e["claim"]: e["why"] for e in (_registry().get("no_visualization") or [])}
    if cid in reg:
        return reg[cid]
    srcs = _srcs(entry)
    if not srcs and entry.get("compute"):
        return "arithmetic on the numbers it states, no data source"
    if srcs and all((_path(s) or "").startswith("manuscript/") for s in srcs):
        return "a statement about the manuscript itself"
    return None


def reverse():
    """{(page, anchor): [claim ids]} over every claim."""
    out = {}
    for cid, e in _claims().items():
        if isinstance(e, dict):
            for page, anchor, _ in targets(cid, e):
                out.setdefault((page, anchor), []).append(cid)
    return out


def backs_html(page, anchor, rel):
    """'Claims shown here: a, b' with links to the ledger rows, for a section or chart."""
    ids = sorted(reverse().get((page, anchor), []))
    if not ids:
        return ""
    link = rel(page, "claims.md")
    return ('<p class="ev-backs">Claims shown here: '
            + ", ".join(f'<a href="{link}#{i}">{i}</a>' for i in ids) + "</p>")


def rows_without_target(page_text):
    """Claim ids whose row in a rendered claims page says neither where it is shown nor why not."""
    out = []
    for chunk in re.split(r'<h6 class="cl-h" id="', page_text)[1:]:
        cid = chunk.split('"', 1)[0]
        cell = "".join(chunk.split("</td>", 3)[:3])
        if "cl-shown" not in cell:
            out.append(cid)
    return out


def check():
    errs = []
    reg_ids = {e["claim"] for e in (_registry().get("no_visualization") or [])}
    for cid in sorted(reg_ids - set(_claims())):
        errs.append(f"evidence/claim_targets.yaml: {cid} is not a claim")
    for cid, e in _claims().items():
        if not isinstance(e, dict) or not _srcs(e):
            continue
        if not targets(cid, e) and not no_visual(cid, e):
            errs.append(f"{cid}: no page shows it ({', '.join(sorted({_path(s) or 'matrix' for s in _srcs(e)}))}); "
                        f"add a rule in evidence/tools/claim_targets.py or a reason in evidence/claim_targets.yaml")
    return errs


if __name__ == "__main__":
    e = check()
    print("\n".join(e) or "every claim has a target or a reason")
    raise SystemExit(1 if e else 0)
