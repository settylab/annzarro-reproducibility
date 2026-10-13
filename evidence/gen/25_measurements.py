"""Measurements: every run behind the scale and ceiling results, drawn from the CSVs at build time.

Three pages (section "Measurements"):

    measurements/rules.md         the rules that turn runs into results, with their constants
    measurements/tool-ceiling.md  the one Tool ceiling page: the ceilings table and the guard-off edge (gen/20_tool_ceiling.py),
                                  then one panel per tool and variant: client and server
                                  peaks of every run against N, the budgets, the derived Fig. 1c value, then the clean-time rule and method
    measurements/scale.md         AnnZarro, current release (Fig. 7): first plot and recolour times of every
                                  rep, the memory-guard edge, subset reach to 1B (the 1B server trace is on benchmarks/hpc.md)

Nothing is copied by hand: the rules' constants are read from benchmark/tool_ceiling/summarize.py
(imported, so the page uses the very functions that write ceilings.csv), and every point is a row of
a CSV in the repository. Charts are inline SVG (evidence/tools/svgplot.py); hovering a point shows
its run id and numbers. Each chart has its data table and a link to the CSV.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import math
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

NAV = [("Measurements", "Tool ceiling", "measurements/tool-ceiling.md"),
       ("Measurements", "Rules behind the results", "measurements/rules.md"),
       ("Measurements", "AnnZarro scale: every run", "measurements/scale.md")]

TC = "benchmark/tool_ceiling"
SC = "benchmark/scale/results"
GIB = 2 ** 30


def _load_tcp(repo):
    spec = importlib.util.spec_from_file_location("tc_page_20", repo / "evidence/gen/20_tool_ceiling.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TCP = None


def _summarize(repo):
    """benchmark/tool_ceiling/summarize.py, imported: its constants and functions are the rules."""
    spec = importlib.util.spec_from_file_location("tc_summarize", repo / TC / "summarize.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return math.nan


def _num(v, nd=2):
    return "–" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{nd}f}"


def _bytes(v):
    x = _f(v)
    return "bytes not recorded" if math.isnan(x) else f"{int(x):,} bytes"


def _tbl(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(x).replace("|", "/").replace("\n", " ") for x in r) + " |" for r in rows]
    return "\n".join(out)


def _details(summary, inner):
    return f'\n??? note "{summary}"\n\n' + "\n".join("    " + ln for ln in inner.splitlines()) + "\n"


# ----------------------------------------------------------------------------------------- runs
def classify(S, repo):
    """Every row of results.csv with the status the rules give it, or the reason it does not count.

    Returns rows (dicts) with: id, tool, panel (tool, variant after MERGE / remote merge), n, phase,
    client, server, total (GiB), status, mode, counted (bool), why (exclusion reason)."""
    raw = list(csv.DictReader(open(repo / TC / "results.csv")))
    counted = {r["id"]: r for r in S.load()}           # harness, overlap and remote-cap filters applied
    # the server budget and hang labels, per panel, exactly as ceilings() applies them
    by = defaultdict(list)
    for r in counted.values():
        if r["phase"] == "run":
            by[(r["tool"], r["variant"])].append(r)
    judged = {}
    for key, rs in by.items():
        for r in S.apply_server_budget(rs, S.SERVER_BUDGET_GIB):
            judged[r["id"]] = r
    flags = {r["id"]: r for r in S.mark_overlaps([dict(x) for x in raw])}
    remote_ok = {(r["tool"], r["variant"][7:], int(r["n"])) for r in raw
                 if r["variant"].startswith("remote_") and r["tool"] != "annzarro" and r["status"] == "ok"}
    out = []
    for r in raw:
        var = S.MERGE.get((r["tool"], r["variant"]), r["variant"])
        if r["tool"] != "annzarro" and var.startswith("remote_"):
            var = var[7:]
        web = bool(r["fp_client_gb"])
        row = {"id": r["id"], "tool": r["tool"], "variant": r["variant"], "panel": (r["tool"], var),
               "n": int(r["n"]), "phase": r["phase"], "time": r["time"],
               "client": _f(r["fp_client_gb"] if web else r["fp_total_gb"]),
               "server": _f(r["fp_server_gb"]) if web else math.nan, "total": _f(r["fp_total_gb"]),
               "status": r["status"], "mode": r["failure_mode"], "counted": True, "why": "", "metric": "phys_footprint",
               "software": _software(r.get("versions"), r.get("note")),
               "remote": r["variant"].startswith("remote_")}
        if r["id"] in S.OVERRIDES:
            row["status"], row["mode"] = S.OVERRIDES[r["id"]]
        if r["id"] in S.HARNESS_FAILURES:
            row.update(counted=False, why="harness failure: " + S.HARNESS_FAILURES[r["id"]])
        elif (r["tool"], r["variant"]) in S.SUPERSEDED or (r["tool"], var) in S.SUPERSEDED:
            row.update(counted=False, why="superseded build: " + S.SUPERSEDED.get((r["tool"], r["variant"]),
                                                                                   S.SUPERSEDED.get((r["tool"], var), "")))
        elif r["id"] not in counted:
            f = flags.get(r["id"], {})
            if not f.get("clean_memory", True):
                row.update(counted=False, why="overlapped a user session (memory not clean): " + "; ".join(f.get("overlaps", []))[:200])
            elif r["status"] == "cap" and (r["tool"], var, int(r["n"])) in remote_ok:
                row.update(counted=False, why="laptop hit its 48 GiB cap; this size was measured with the server on the HPC (remote row)")
            else:
                row.update(counted=False, why="not counted by summarize.load()")
        if r["id"] in judged:
            j = judged[r["id"]]
            row["status"], row["mode"] = j["status"], j["failure_mode"]
            if j.get("server_note"):
                row["server"], row["metric"] = j["fp_server"], "RSS (" + j["server_note"] + ")"
        out.append(row)
    return out


def machine_cap(repo):
    """(current cap GiB, earlier cap GiB or None) from run.py's --cap-gb default and its comment."""
    t = (repo / TC / "run.py").read_text()
    m = re.search(r'"--cap-gb", type=float, default=(\d+(?:\.\d+)?)\)(?:\s*#[^\n]*?\((\d+) until ([^)]*)\))?', t)
    if not m:
        raise RuntimeError("run.py: no --cap-gb default")
    return float(m.group(1)), (float(m.group(2)) if m.group(2) else None), (m.group(3) or "")


def run_cap(repo, run_time, cap, cap_old):
    """The cap a run was made under: the earlier cap for runs before the commit that raised it
    (git log of run.py's --cap-gb default; run times are local, as in results.csv)."""
    if not cap_old:
        return cap
    import subprocess
    from datetime import datetime
    out = subprocess.run(["git", "-C", str(repo), "log", "--format=%cI", f"-Sdefault={cap:g})", "--",
                          f"{TC}/run.py"], capture_output=True, text=True).stdout.split()
    if not out:
        return cap
    changed = datetime.fromisoformat(out[-1]).replace(tzinfo=None)
    return cap_old if datetime.fromisoformat(run_time) < changed else cap


def declined(r):
    """A deliberate refusal by the tool (AnnZarro's memory guard), not a crash."""
    return "guard_refusal" in f"{r['status']} {r['mode']}"


def human_status(r, cap=None):
    if declined(r):
        return "declined by the memory guard (by design: refused to draw rather than let the tab run out of memory)"
    return {"ok": "ok", "cap": f"stopped at the machine cap{f' ({cap:g} GiB)' if cap else ''}: peak above it",
            "server_budget": "over the server budget", "hang": "hang (no progress)",
            "timeout": "timed out"}.get(r["status"], f"failed ({r['status']})")


def _dedupe(t):
    """'cap cap' -> 'cap' (status and mode are the same word for some rows)."""
    w = t.split(" ", 1)
    return w[0] if len(w) == 2 and w[0] == w[1] else t


NAMES = {"kana": "Kana", "napari": "napari-spatialdata", "tissuumaps": "TissUUmaps", "manivault": "ManiVault Studio",
         "loupe": "Loupe Browser"}


def _md_inline(s):
    """**bold** to <b> for a figcaption (raw HTML: Markdown is not parsed there)."""
    import html as _h
    import re as _re
    return _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _h.escape(s, quote=False)).replace("\n", "<br>")


def _software(versions, note):
    """'AnnZarro v0.3.1 1391357' from a run's note, else the versions JSON ('scanpy 1.12.4, anndata 0.13.4')."""
    m = re.search(r"AnnZarro (v[\d.]+(?:-\w+)?) ([0-9a-f]{7})", note or "")
    if m:
        return f"AnnZarro {m.group(1)} ({m.group(2)})"
    try:
        v = json.loads(versions or "{}")
    except ValueError:
        return ""
    if v.get("annzarro"):
        return f"AnnZarro {v['annzarro']}"
    return ", ".join(f"{k} {x}" for k, x in v.items()        # the tool's own versions, not the harness's
                     if k not in ("browser", "chromium", "Rscript", "python") and not re.search(r"[/:]", str(x)))


def tip(r, extra=""):
    parts = [r["id"], f"N = {r['n']:,}", f"status: {r['status']}" + (f" ({r['mode']})" if r["mode"] else "")]
    for k in ("client", "server", "total"):
        if not math.isnan(r[k]):
            parts.append(f"{k} {r[k]:.2f} GiB")
    if r["metric"] != "phys_footprint":
        parts.append("server metric: " + r["metric"])
    if r.get("software"):
        parts.append("software: " + r["software"])
    if not r["counted"]:
        parts.append("NOT COUNTED: " + r["why"])
    if extra:
        parts.append(extra)
    return "\n".join(parts)


# ------------------------------------------------------------------------------------- page 1
def rules_page(ctx, S, page):
    link, prov = ctx.link_repo, ctx.prov_badge
    harness = _tbl(["run", "why it is not an attempt"], sorted(S.HARNESS_FAILURES.items()))
    superseded = _tbl(["tool", "variant", "why"], [(t, v, w) for (t, v), w in sorted(S.SUPERSEDED.items())])
    notes = (ctx.REPO / TC / "NOTES.md").read_text()
    a, b = notes.find("**Input rule"), notes.find("**Server budget")
    input_rule = notes[a:b].strip() if a >= 0 and b > a else "(not found in NOTES.md)"
    rsrv = _tbl(["tool", "variant", "N", "server", "metric"],
                [(t, v, f"{n:,}", f"{g:.1f} GiB", note) for (t, v, n), (g, note) in sorted(S.REMOTE_SERVER.items())])
    hang_cpu = _memmon_const(ctx.REPO, "HANG_CPU")
    hang_s = _memmon_const(ctx.REPO, "HANG_S", "run.py")
    ladder = sorted(_memmon_const(ctx.REPO, "LADDER", "queue_bisect.py") or [])
    import claim_targets as CT
    cap, cap_old, cap_until = machine_cap(ctx.REPO)
    body = f"""# Rules behind the results

{CT.backs_html(page, "", ctx.rel)}

Every number on the measurement pages follows from the runs by the rules on this page. The
constants below are read from the benchmark's own code when the site is built
({link(page, f"{TC}/summarize.py", "summarize.py")}, {link(page, f"{TC}/run.py", "run.py")},
{link(page, f"{TC}/memmon.py", "memmon.py")}), so the page cannot drift from what produced
`ceilings.csv`. Method: {link(page, f"{TC}/README.md", "README.md")}; decisions:
{link(page, f"{TC}/NOTES.md", "NOTES.md")}.

## Budgets

| budget | value | measured as | applies to |
|---|---|---|---|
| client | **{S.BUDGETS[1]} GiB** (also reported at {S.BUDGETS[0]} and {S.BUDGETS[2]} GiB) | `phys_footprint` peak, summed over every browser process (browser, renderer, GPU); for a library (Scanpy, Seurat) the whole R or Python process | the Fig. 1c value: the largest N whose client stays within it |
| server | **{S.SERVER_BUDGET_GIB:.0f} GiB**, flat, the same for every tool, AnnZarro included | `phys_footprint` concurrent peak of the server process tree (50 ms samples); process-tree RSS where the server ran on an HPC node (labelled) | a server above it at size N stops the tool at the previous size that passed |
| data preparation | **not measured** (input rule, below) | – | every tool is given its input already prepared |
| laptop safety cap | **{cap:g} GiB** (`run.py --cap-gb`) | the whole process tree | a machine guard, not a budget: a run that reaches it is killed (status `cap`) |

**Why these values.** What the benchmark's own records say: the client budget is the figure's
question, the largest N a tool draws within {S.BUDGETS[1]} GiB, and {S.BUDGETS[0]} and
{S.BUDGETS[2]} GiB are reported beside it because each tool climbs the ladder past
{S.BUDGETS[1]} GiB, so one curve answers all three (README). The server budget is a flat
{S.SERVER_BUDGET_GIB:.0f} GiB, the same for every tool (NOTES). The
{cap:g} GiB cap is a machine guard on a shared 128 GB laptop, not a budget (README, NOTES). The records
give no reason for choosing {S.BUDGETS[1]} GiB or the cap's value.

**What an arrow means.** On the charts an up-arrow at the cap line is a run killed at the cap (drawn
at the cap that run ran under{f": {cap:g} GiB, or {cap_old:g} GiB for the runs made under that cap" if cap_old else f": {cap:g} GiB"}): its true peak is
above that and unknown. Because every cap is above the 32 GiB server budget, such a
run is over the budget either way.

**Units.** Memory is binary throughout: 1 GiB = 2^30 bytes, so 16 GiB = 17.2 GB. Data sizes
(stores, payloads, files) are decimal: 1 GB = 10^9 bytes. Where a peak was reported in GB,
it is converted to GiB on the page and labelled with its metric (process-tree RSS).

## From runs to a result

1. **Ladder.** Each tool climbs N = {", ".join(f"{n / 1e6:g}M" for n in ladder)} (then 95.6M and
   synthetic sizes above it), and stops at its first failure.
2. **Bisection.** Around the 16 GiB crossing, the geometric midpoint is run until the bracketing Ns
   are within 1.25×; then two more repeats at the largest passing N and the smallest failing N
   ({link(page, f"{TC}/queue_bisect.py", "queue_bisect.py")}).
3. **Success at N** = both colourings (cell line and one gene) drawn for every cell, checked by the
   tool's own counter or the WebGL point count, within 30 min.
4. **Largest tested.** If the largest N run passed, the value is a lower bound ("≥"), never a limit
   (`kind_16gb` = "lower bound: largest N tested").
5. **Server.** A server peak above {S.SERVER_BUDGET_GIB:.0f} GiB turns an otherwise passing run into
   `server_budget` and stops the tool at the previous size. A tool that cannot read a valid input
   at N is an input path limit. [[fig:overview]]c draws one glyph for the largest N drawn in full, whatever
   stopped the tool at the next size; the reason is in each row. Only measured rows count: an N that was
   not run is never assumed.

## The hang rule

A web run in which the client and server together use less than **{hang_cpu:g} CPU-seconds over
{hang_s} s** of wall time is ended as a hang (no drawing, loading or computing). Before a hang counts it
is checked for a harness wait (the driver waiting for a signal the tool never gives although it has
drawn). A size with at least **{S.HANG_ATTEMPTS} hang attempts** is not renderable for that tool:
a client stop.

## Runs that do not count

Runs on other AnnZarro builds, harness failures (a driver that waited for a signal the tool never
gives) and runs that overlapped a user session are not counted and drawn nowhere. The file
{link(page, f"{TC}/results.csv", "results.csv")} holds every run, and `summarize.HARNESS_FAILURES` in
{link(page, f"{TC}/summarize.py", "summarize.py")} names the harness failures with their reasons.

## Input rule

From {link(page, f"{TC}/NOTES.md", "NOTES.md")}, verbatim:

{input_rule}


Server values measured on the HPC node that served the tool:

{rsrv}

## Inputs

| file | provenance |
|---|---|
| rules | {prov(f"{TC}/summarize.py")} |
| runs | {prov(f"{TC}/results.csv")} |
| method | {prov(f"{TC}/README.md")} |
| decisions | {prov(f"{TC}/NOTES.md")} |
"""
    return body


def _memmon_const(repo, name, fname="memmon.py"):
    import ast
    for node in ast.parse((repo / TC / fname).read_text()).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            try:
                return ast.literal_eval(node.value)
            except ValueError:
                return None
    return None


# ------------------------------------------------------------------------------------- page 2
def ceiling_page(ctx, S, svg, rows, page):
    """One panel per row of ceilings.csv (the versions the paper reports), counted runs only."""
    import claim_targets as CT
    link, prov, site_file, rel = ctx.link_repo, ctx.prov_badge, ctx.site_file, ctx.rel
    ceil = {(r["tool"], r["variant"]): r for r in csv.DictReader(open(ctx.REPO / TC / "ceilings.csv"))}
    runs = [r for r in rows if r["phase"] == "run" and r["counted"]]
    cap, cap_old, cap_until = machine_cap(ctx.REPO)
    for r in runs:
        r["cap"] = run_cap(ctx.REPO, r["time"], cap, cap_old) if r["status"] == "cap" else None
    subsets = defaultdict(list)          # parent row -> its subset variants (summarize.SUBSET_OF)
    for (t, v), parent in S.SUBSET_OF.items():
        subsets[(t, parent)].append(v)
    ns = [r["n"] for r in runs] or [1e6]
    X = svg.Axis(10 ** math.floor(math.log10(min(ns))), 10 ** math.ceil(math.log10(max(ns))), log=True,
                 fmt=svg.n_fmt, label="cells (N, log)")
    Y = lambda: svg.Axis(0.05, 128, log=True, ticks=sorted({0.5, 2, 8, 16, 32}), fmt=svg.gib,  # noqa: E731
                         label="peak GiB (log)")
    order = {t: i for i, t in enumerate(S.TOOLS)}
    cur_az = current_annzarro(ctx.REPO)
    panels = sorted((p for p in ceil if (p[0] != "annzarro" or not cur_az or p[1] in cur_az)
                     and p[1] not in TCP.EDGE_VARIANTS),       # the guard-off runs are one paragraph (20_tool_ceiling)
                    key=lambda p: (order.get(p[0], 99), p[0], p[1]))
    # a tool whose server was rerun on the release tag: its server values come from that rerun only
    tag_of = {}                         # a row whose server was rerun separately: {(tool, variant): [rerun panels]}
    out = []
    for p in panels:
        tool, var = p
        rs = sorted((r for r in runs if r["panel"] == p), key=lambda r: (r["n"], r["id"]))
        tag = sorted((r for r in runs if r["panel"] in tag_of.get(p, [])), key=lambda r: (r["n"], r["id"]))
        srv_rows = tag if tag else rs
        c = ceil[p]
        title = f"{NAMES.get(tool) or S.NAMES.get(tool, tool)} · {var}"
        ch = svg.Chart(X, Y(), title=title, width=460, height=270, desc=f"{title}: peak memory of every run against N")
        ch.hline(16, "client budget 16 GiB")
        ch.hline(S.SERVER_BUDGET_GIB, f"server budget {S.SERVER_BUDGET_GIB:.0f} GiB")
        ch.hline(cap, f"laptop cap {cap:g} GiB", cls="ev-ref ev-cap", left=True)
        if cap_old and any(r.get("cap") == cap_old for r in rs):
            ch.hline(cap_old, f"machine cap of those runs: {cap_old:g} GiB", cls="ev-ref ev-cap", left=True)
        stop = None
        if c.get("max_n_16gb"):
            srv_rendered = c["figure_value"].startswith("server-rendered")
            b16 = int(c["max_n_server_budget"] if srv_rendered and c.get("max_n_server_budget") else c["max_n_16gb"])
            ff = int(c["first_fail_n"]) if c.get("first_fail_n") else None
            above = sorted((r for r in rs + tag if r["n"] > b16 and (
                r["status"] != "ok" or (not srv_rendered and r["client"] > 16)
                or (srv_rendered and r["server"] > S.SERVER_BUDGET_GIB))), key=lambda r: r["n"])
            if above:                   # at that size, a confirmed failure mode beats a pending one
                same = [r for r in above if r["n"] == above[0]["n"]]
                r0 = next((r for r in same if "pending" not in r["mode"]), same[0])
                stop = (r0["n"], human_status(r0, r0.get("cap")) if r0["status"] != "ok" else
                        (f"client {r0['client']:.2f} GiB > 16 GiB" if not srv_rendered else
                         f"server {r0['server']:.2f} GiB > {S.SERVER_BUDGET_GIB:.0f} GiB"), r0["id"])
            elif ff:
                stop = (ff, c["first_fail"], "")
            val = "server-rendered" if srv_rendered else c["figure_value"]
            why = (f"[[fig:overview]]c value: {c['figure_value']}\n"
                   + (f"largest N with the server within {S.SERVER_BUDGET_GIB:.0f} GiB: {b16:,}" if srv_rendered
                      else f"largest N with client ≤ 16 GiB: {b16:,}") + f"\nkind: {c['kind_16gb']}"
                   + (f"\nstopped at {stop[0]:,}: {stop[1]} {stop[2]}" if stop else ""))
            if stop:
                ch.vband(b16, stop[0], tip=why)
            ch.vline(b16, f"[[fig:overview]]c: {val}", tip=why)
        cli, srv = defaultdict(list), defaultdict(list)
        def shape(r):
            return "declined" if declined(r) else svg.shape_of(r["status"])

        for r in rs + tag:
            if r["status"] == "cap":
                ch.point(r["n"], r["cap"], "arrow", "ev-s1",
                         tip(r, f"stopped at the machine cap of {r['cap']:g} GiB: peak above it"))
                continue
            ch.point(r["n"], r["client"], shape(r), "ev-s1",
                     tip(r, f"series: client every cell · {human_status(r)}"))
            if r["status"] == "ok" and not math.isnan(r["client"]):
                cli[r["n"]].append(r["client"])
        for r in srv_rows:
            if r["status"] == "cap" or math.isnan(r["server"]) or r["server"] <= 0.02:
                continue
            ch.point(r["n"], r["server"], shape(r), "ev-s2",
                     tip(r, f"series: server every cell · {human_status(r)}" + (" (separate server rerun)" if r in tag else "")))
            if r["status"] in ("ok", "server_budget"):
                srv[r["n"]].append(r["server"])
        ch.line([(n, st.median(v)) for n, v in sorted(cli.items())], "ev-s1")
        ch.line([(n, st.median(v)) for n, v in sorted(srv.items())], "ev-s2")
        # the row's subset series (summarize.SUBSET_OF): client dashed, server dotted, one colour per subset
        sub_series = []
        for k, sv in enumerate(sorted(subsets.get(p, []), key=lambda v: (v.endswith("1m"), v))):
            sr = sorted((r for r in runs if r["variant"] == sv), key=lambda r: r["n"])
            if not sr:
                continue
            cls = ("ev-s3", "ev-s4")[k % 2]
            name = "1M subset" if sv.endswith("1m") else ("automatic (default) subset" if tool == "annzarro" else "subset")
            sc, ss = defaultdict(list), defaultdict(list)
            for r in sr:
                ch.point(r["n"], r["client"], shape(r), cls, tip(r, f"series: client, {name} · {human_status(r)}"), r=3)
                if not math.isnan(r["server"]) and r["server"] > 0.02:
                    ch.point(r["n"], r["server"], "ring" if r["status"] == "ok" else shape(r), cls,
                             tip(r, f"series: server, {name} · {human_status(r)}"), r=3)
                if r["status"] == "ok":
                    sc[r["n"]].append(r["client"])
                    if not math.isnan(r["server"]):
                        ss[r["n"]].append(r["server"])
            ch.line([(n, st.median(v)) for n, v in sorted(sc.items())], cls, dash=True)
            ch.line([(n, st.median(v)) for n, v in sorted(ss.items())], cls, dot=True)
            sub_series.append((name, sv, cls, sr))
        # a memory-guard refusal: what it is and why, from the refusal's own text (first_fail_detail)
        guard_note = ""
        dec_runs = sorted((r for r in rs + tag if declined(r)), key=lambda r: r["n"])
        if dec_runs:
            d0 = dec_runs[0]
            ch.text(d0["n"], 0.12, "declined by the memory guard", anchor="end", cls="ev-note")
            m = re.search(r"Needs ~([\d.]+) GB of browser JS memory; ([\d.]+) GB free with (\d+) plots? open \(of ([\d.]+) GB",
                          c.get("first_fail_detail") or "")
            okn = max((r["n"] for r in rs if r["status"] == "ok"), default=None)
            commit = (re.search(r"\(([0-9a-f]{7})\)", S.FINAL.get(p, "")) or [None, None])[1]
            mg = (f"https://github.com/settylab/annzarro/blob/{commit}/static/js/utils/memory-guard.js" if commit else
                  "https://github.com/settylab/annzarro/blob/main/static/js/utils/memory-guard.js")
            repo = ctx.REPO
            rv = _release(repo)[0]["version"]
            hcp = f"benchmark/scale/results/heapcap_v{''.join(re.findall(r'[0-9]', rv))}.jsonl"   # the release's heap probe
            hrec = json.loads((repo / hcp).read_text().splitlines()[0]) if (repo / hcp).exists() else None
            hm = re.search(r"used (\d+) lim (\d+)", (hrec or {}).get("heap", {}).get("last", [""])[0]) if hrec else None
            hsf = site_file(hcp)
            hc = rel("measurements/tool-ceiling.md", hsf) if hsf else f"https://github.com/settylab/annzarro-reproducibility/blob/main/{hcp}"
            need = (f"Here that was ~{m.group(1)} GB of JS heap, with {m.group(2)} GB free of {m.group(4)} GB "
                    f"({m.group(3)} plot open). " if m else "")
            guard_note = (
                f'<p class="ev-guard"><b>Memory guard declined at {d0["n"]:,} cells (by design).</b> Before drawing, '
                f"AnnZarro estimates the browser memory the plot needs. {need}It refused instead of letting the tab run "
                f"out of memory and crash, and the page stays usable"
                + (f"; {okn:,} cells is the largest size drawn" if okn else "") + ". "
                f"The guard is about the JavaScript (V8) heap, not the {S.BUDGETS[1]} GiB client budget: Chrome caps a "
                + (f"tab's V8 heap at about 4 GiB (jsHeapSizeLimit {int(hm.group(2)) / 1e9:.2f} GB in Chromium {hrec['version']}), "
                   f"and the probe tab died at {int(hm.group(1)) / 1e9:.2f} GB used" if hm else "tab's V8 heap at about 4 GiB")
                + f", well before the whole browser reaches {S.BUDGETS[1]} GiB. Sources: "
                f'<a href="{mg}">memory-guard.js</a> (the estimate and the limit), the heap-limit measurement '
                f'<a href="{hc}">{Path(hcp).name}</a>'
                + (', and the runs without the guard: <a href="#guard-off-edge">guard off</a>' if any(
                    r["tool"] == tool and re.search(r"guard_?off|noguard", r["variant"]) for r in runs) else "")
                + ".</p>")
        # why no run crosses a budget, per series, where none does
        notes = []
        def crossing(series):
            return any(r["status"] == "ok" and r["client"] > 16 for r in series) or any(
                (not math.isnan(r["server"])) and r["server"] > S.SERVER_BUDGET_GIB for r in series) or any(
                r["status"] in ("cap", "server_budget") for r in series)
        every = rs + tag
        if every and not crossing(every):
            okr = [r for r in every if r["status"] == "ok"]
            dec = sorted((r for r in every if declined(r)), key=lambda r: r["n"])
            if dec and okr:
                top = max(okr, key=lambda r: r["n"])
                notes.append(f"Every cell: no run crosses a budget. The memory guard declines at {dec[0]['n']:,} cells "
                             f"(by design), before the client reaches 16 GiB; at {top['n']:,} the client used "
                             f"{top['client']:.1f} GiB" + (f" and the server {top['server']:.1f} GiB" if not math.isnan(top['server']) else "") + ".")
            elif okr and all(r["status"] == "ok" for r in every):
                top = max(okr, key=lambda r: r["n"])
                notes.append(f"Every cell: no run crosses a budget up to {top['n']:,} cells, the largest size tested "
                             f"(client {top['client']:.1f} GiB" + (f", server {top['server']:.1f} GiB" if not math.isnan(top['server']) else "")
                             + "): a lower bound.")
        for name, sv, cls, sr in sub_series:
            okr = [r for r in sr if r["status"] == "ok"]
            if okr and not crossing(sr) and all(r["status"] == "ok" for r in sr):
                top = max(okr, key=lambda r: r["n"])
                notes.append(f"{name[0].upper() + name[1:]}: still under both budgets at {top['n']:,} cells, the largest size "
                             f"tested (client {top['client']:.1f} GiB, server {top['server']:.1f} GiB): a lower bound.")
        table = _tbl(["run", "N", "outcome", "client GiB", "server GiB", "raw status"],
                     [(r["id"], f"{r['n']:,}", human_status(r, r.get("cap")), _num(r["client"]),
                       _num(r["server"]) if (r in srv_rows) else "(tag rerun)", f"{r['status']} {r['mode']}".strip()[:160])
                      for r in rs + tag + [x for _, _, _, sr in sub_series for x in sr]])
        derived = (f"**[[fig:overview]]c: {c['figure_value'] or '–'}** · {c['kind_16gb']}"
                   + (f" · stopped at {stop[0]:,} ({stop[1]})" if stop and f"{stop[0]:,}" not in c["kind_16gb"] else ""))
        if tag:
            derived += " · server values from a separate rerun of the same release"
        sw = sorted({r["software"] for r in rs + tag + [x for _, _, _, sr in sub_series for x in sr] if r.get("software")})
        if tool == "annzarro" and sw:
            derived += "\nMeasured with " + "; ".join(sw) + "."
        elif sw and len(sw) <= 2:
            derived += "\nSoftware: " + "; ".join(sw) + "."
        if notes:
            derived += "\n" + " ".join(notes)
        pk = [("ev-s1", "client, every cell")] + ([("ev-s2", "server, every cell")] if srv else [])
        pd = [x for name, _, cls, _ in sub_series for x in ((cls, "ev-dash", f"client, {name}"), (cls, "ev-dot", f"server, {name} (hollow)"))]
        out.append((tool, title, ch.render(pk, pd), derived, table, CT.tc_anchor(tool, var), guard_note))
    legend = svg.legend_html([("ev-s1", "client, every cell"), ("ev-s2", "server, every cell")], skip=("ring",),
                             dashes=[("ev-s3", "ev-dash", "client, automatic (default) subset"),
                                     ("ev-s3", "ev-dot", "server, automatic (default) subset (hollow points)"),
                                     ("ev-s4", "ev-dash", "client, 1M subset"), ("ev-s4", "ev-dot", "server, 1M subset (hollow points)")])
    blocks, tools_in = [], []
    for o in out:
        if o[0] not in tools_in:
            tools_in.append(o[0])
    for t in tools_in:
        group = [o for o in out if o[0] == t]
        figs = "".join(f'<figure class="ev-fig" id="{a}">{s}<figcaption>{_md_inline(d)}'
                       f'{CT.backs_html("measurements/tool-ceiling.md", a, rel)}</figcaption></figure>'
                       for _, _, s, d, _, a, _ in group)
        figs += "".join(g for *_, g in group if g)
        blocks.append(f"### {NAMES.get(t) or S.NAMES.get(t, t)}\n\n" f'<div class="ev-charts">{figs}</div>\n'
                      + "".join(_details(f"Runs: {title}", table) for _, title, _, _, table, a, _ in group))
    csv_link = site_file(f"{TC}/results.csv")
    head, ceilings, tail = TCP.parts(ctx)
    head = head.replace("@@BACKS@@", CT.backs_html("measurements/tool-ceiling.md", "", rel))
    body = ("---\nhide:\n  - toc\n---\n\n"
            "<style>.md-grid { max-width: 90rem; } .md-typeset table:not([class]) th, .md-typeset table:not([class]) td "
            "{ padding: 0.5em 0.3em; } .md-typeset table:not([class]) th { font-size: 0.6rem; line-height: 1.25; min-width: 3rem; }</style>\n\n") + head + ceilings + f"""
## Every run {{#every-run}}

Every run behind [[fig:overview]]c's measured cells, per tool and variant, on the versions the paper reports.
Blue: client peak; orange: server peak; the lines join the medians at each N. The [[fig:overview]]c value is
marked on each panel, and the shaded band runs from it to the run that stopped the tool (hover it
for the rule, [rules](rules.md); hover any point for its run id and numbers).

Data: {f"[results.csv]({rel(page, csv_link)})" if csv_link else link(page, f"{TC}/results.csv", "results.csv")} and
{link(page, f"{TC}/ceilings.csv", "ceilings.csv")} ({prov(f"{TC}/results.csv")}).

{legend}

Dashed lines: the 16 GiB client budget and the {S.SERVER_BUDGET_GIB:.0f} GiB server budget; dotted:
the {cap:g} GiB laptop cap{f" (runs made under a {cap_old:g} GiB cap are drawn at that cap)" if cap_old else ""}. Server peaks measured on an HPC node are process-tree RSS (labelled in the
tooltip); every other value is `phys_footprint`.

""" + "\n\n".join(blocks) + "\n\n" + tail
    return body


# ------------------------------------------------------------------------------------- page 3
def _release(repo):
    """AnnZarro's current release from evidence/superseded.yaml, and whether a file is one of its sources."""
    import fnmatch
    import yaml
    reg = yaml.safe_load((repo / "evidence/superseded.yaml").read_text())
    cur = reg.get("current") or []
    return reg["release"]["annzarro"], lambda path: any("where" not in e and fnmatch.fnmatch(path, e["file"])
                                                         for e in cur if "file" in e)


def current_annzarro(repo):
    """AnnZarro's ceilings rows the registry names as current (evidence/superseded.yaml), e.g. ['v040',
    'v040_noguard']; every ceilings row if the registry names none."""
    import yaml
    reg = yaml.safe_load((repo / "evidence/superseded.yaml").read_text())
    out = []
    for e in reg.get("current") or []:
        w = e.get("where") or {}
        if e.get("csv") == f"{TC}/ceilings.csv" and w.get("tool") == "annzarro":
            v = w.get("variant")
            out += v if isinstance(v, list) else [v]
    return [v for v in out if v]


def scale_page(ctx, S, svg, rows, page):
    link, prov, site_file, rel = ctx.link_repo, ctx.prov_badge, ctx.site_file, ctx.rel
    repo = ctx.REPO
    cur_rows = current_annzarro(repo)
    cur = next((v for v in cur_rows if "noguard" not in v), None) or next(
        r["variant"] for r in csv.DictReader(open(repo / TC / "ceilings.csv")) if r["tool"] == "annzarro")
    ver = "v" + ".".join(cur[1:]) if re.fullmatch(r"v\d{3}", cur) else cur      # annzarro/v031 -> v0.3.1
    release, _ = _release(repo)
    if release["version"] == ver:
        ver_commit = release["commit"][:7]
    else:                               # the registry has not caught up with the ceilings row yet
        ver_commit = next((r["build"].split()[1] for r in csv.DictReader(open(repo / TC / "server_profile_1b.csv"))
                           if r.get("build", "").split()[:1] == [ver]), "?")
    # the browser series runs on the release the registry names (it can be ahead of the ceilings row)
    rel_ver = release["version"]
    rel_tag = "v" + "".join(re.findall(r"\d", rel_ver))           # v0.4.0 -> v040
    evf = f"{SC}/browser_{rel_tag}_events.csv"
    ev = list(csv.DictReader(open(repo / evf))) if (repo / evf).exists() else []
    for e in ev:
        e["n"] = int(e["n_cells"])
        e["s"] = _f(e["seconds"])
    nsx = sorted({e["n"] for e in ev})
    X = svg.Axis(5e5, 2e8, log=True, fmt=svg.n_fmt, label="cells in the store (log)")
    tags = {f"all_{rel_tag}": "every cell", f"sub_{rel_tag}": "default 100,000-cell subset", f"ceil_{rel_tag}": "every cell (ceiling runs)"}
    import claim_targets as CT
    page_md = "measurements/scale.md"
    groups = {"all": (f"all_{rel_tag}", f"ceil_{rel_tag}"), "sub": (f"sub_{rel_tag}",), "conf95": (f"conf95_{rel_tag}",),
              "conf95auto": (f"conf95auto_{rel_tag}",)}
    labels = {"first_plot": "first plot", "recolour": "recolour by another gene", "recolour_cat": "recolour by cell line",
              "part_step": "step to the next part", "balance": "subset balanced across cell lines"}
    charts, tables = [], []
    for event in CT.EVENTS:
        label = labels[event]
        for g, gtags in groups.items():
            pts = [e for e in ev if e["event"] == event and e["tag"] in gtags]
            if not pts:
                continue
            ys = [e["s"] for e in pts if not math.isnan(e["s"])] or [1]
            Y = svg.Axis(max(0.05, min(ys) / 1.5), max(ys) * 1.5, log=True,
                         ticks=[t for t in (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100) if min(ys) / 1.5 <= t <= max(ys) * 1.5],
                         fmt=lambda v: f"{v:g}", label="seconds (log)")
            ch = svg.Chart(X, Y, title=f"{label}: {CT.SCALE_GROUPS[g]}", width=440, height=250,
                           desc=f"AnnZarro {rel_ver} {label}, {CT.SCALE_GROUPS[g]}: every rep")
            med = defaultdict(lambda: defaultdict(list))
            for e in pts:
                cls = "ev-s1" if e["color"] == "gene" else "ev-s2"
                shape = "circle" if e["status"] == "ok" else "cross"
                ch.point(e["n"], e["s"], shape, cls,
                         f"{e['tag']} · {e['store']} · rep {e['rep']}\nN = {e['n']:,} · colour {e['color']}\n"
                         f"{event}: {e['s']:.2f} s · status {e['status']}\nrenderer {e['renderer_rss_gb']} GB RSS, "
                         f"V8 peak {e['v8_used_peak_gb']} GB · large-plot mode {e['large_mode']}", r=3)
                if e["status"] == "ok" and not math.isnan(e["s"]):
                    med[e["color"]][e["n"]].append(e["s"])
            for col, cls in (("gene", "ev-s1"), ("cat", "ev-s2")):
                ch.line([(n, st.median(v)) for n, v in sorted(med[col].items())], cls)
            anchor = CT.scale_anchor(event, g)
            svg_html = ch.render([("ev-s1", "colored by gene"), ("ev-s2", "colored by cell line")])
            charts.append(f'<figure class="ev-fig" id="{anchor}">{svg_html}'
                          f'<figcaption>{CT.backs_html(page_md, anchor, rel)}</figcaption></figure>')
            tables.append(_tbl(["tag", "N", "colour", "rep", "seconds", "status", "renderer RSS GB", "V8 peak GB"],
                               [(e["tag"], f"{e['n']:,}", e["color"], e["rep"], _num(e["s"]), e["status"],
                                 e["renderer_rss_gb"], e["v8_used_peak_gb"]) for e in sorted(pts, key=lambda e: (e["n"], e["color"], e["rep"]))]))
    timing = '<div class="ev-charts">' + "".join(charts) + "</div>"
    # browser and server memory of every run, per group (renderer, GPU, server RSS)
    mem_charts = []
    for g, gtags in groups.items():
        pts = [e for e in ev if e["tag"] in gtags]
        vals = [_f(e[k]) for e in pts for k in ("renderer_rss_gb", "gpu_rss_gb", "server_rss_gb") if not math.isnan(_f(e[k]))]
        if not vals:
            continue
        M = svg.Chart(X, svg.Axis(0.05, max(vals) * 2, log=True, ticks=[0.1, 0.5, 1, 2, 4, 8, 16, 32], fmt=svg.gib,
                                  label="GB RSS (log)"),
                      title=f"memory of every event: {CT.SCALE_GROUPS[g]}", width=440, height=250,
                      desc=f"AnnZarro {rel_ver} renderer, GPU and server RSS of every event, {CT.SCALE_GROUPS[g]}")
        for k, cls, lab in (("renderer_rss_gb", "ev-s1", "renderer"), ("gpu_rss_gb", "ev-s3", "GPU"), ("server_rss_gb", "ev-s2", "server")):
            med = defaultdict(list)
            for e in pts:
                v = _f(e[k])
                if math.isnan(v):
                    continue
                M.point(e["n"], v, "circle", cls, f"{e['tag']} · {e['event']} · rep {e['rep']}\nN = {e['n']:,}\n{lab} RSS {v:.2f} GB", r=2.2)
                med[e["n"]].append(v)
            M.line([(n, max(v)) for n, v in sorted(med.items())], cls)
        anchor = f"memory-{g}"
        mem_html = M.render([("ev-s1", "renderer"), ("ev-s3", "GPU"), ("ev-s2", "server")])
        mem_charts.append(f'<figure class="ev-fig" id="{anchor}">{mem_html}'
                          f'<figcaption>{CT.backs_html(page_md, anchor, rel)}</figcaption></figure>')
    memory = '<div class="ev-charts">' + "".join(mem_charts) + "</div>" if mem_charts else ""
    # memory-guard edge: the current AnnZarro row's runs from the tool ceiling, 50M and up
    edge = sorted((r for r in rows if r["tool"] == "annzarro" and r["panel"] == ("annzarro", cur)
                   and r["phase"] == "run" and r["counted"] and r["n"] >= 50_000_000), key=lambda r: (r["n"], r["id"]))
    E = svg.Chart(svg.Axis(4e7, 2.5e8, log=True, ticks=[5e7, 1e8, 1.5e8, 2e8], fmt=svg.n_fmt, label="cells (log)"),
                  svg.Axis(0, 20, ticks=[0, 4, 8, 12, 16, 20], fmt=svg.gib, label="client peak GiB"),
                  title=f"memory-guard edge: every cell, {ver}", width=560, height=280,
                  desc="AnnZarro memory-guard edge: client peak of every run, refusals as crosses")
    E.hline(16, "client budget 16 GiB", left=True)
    guard_rows = []
    for r in edge:
        text = S.guard_text(r["id"]) if r["status"] != "ok" else ""
        E.point(r["n"], r["client"] if not math.isnan(r["client"]) else 0.3,
                svg.shape_of(r["status"]), "ev-s1",
                tip(r, ("guard: " + text) if text else ""))
        guard_rows.append((r["id"], f"{r['n']:,}", r["status"], _num(r["client"]),
                           (text or r["mode"] or "")[:220]))
    # subset reach to 1B: the current row's subset variants (summarize.SUBSET_OF)
    subvars = {v for (t, v), parent in S.SUBSET_OF.items() if t == "annzarro" and parent == cur}
    sub = sorted((r for r in rows if r["tool"] == "annzarro" and r["counted"] and r["variant"] in subvars),
                 key=lambda r: (r["n"], r["id"]))
    U = svg.Chart(svg.Axis(1e8, 2e9, log=True, ticks=[1e8, 2e8, 5e8, 1e9, 2e9], fmt=svg.n_fmt, label="cells in the store (log)"),
                  svg.Axis(0.05, 64, log=True, ticks=[0.1, 0.5, 2, 8, 16, 32], fmt=svg.gib, label="peak GiB (log)"),
                  title="subset reach: client and server, to 1B", width=560, height=280,
                  desc="AnnZarro subset reach: client and server peak against N up to 1 billion cells")
    U.hline(16, "client budget 16 GiB")
    U.hline(S.SERVER_BUDGET_GIB, f"server budget {S.SERVER_BUDGET_GIB:.0f} GiB")
    series = defaultdict(lambda: defaultdict(list))
    for r in sub:
        k = "1M subset" if r["variant"].endswith("sub1m") else "default subset"
        cls = "ev-s3" if k == "1M subset" else "ev-s1"
        U.point(r["n"], r["client"], svg.shape_of(r["status"]), cls, tip(r, f"series: client, {k}"))
        U.point(r["n"], r["server"], svg.shape_of(r["status"]), "ev-s2", tip(r, f"series: server, {k}"))
        if r["status"] == "ok":
            series[cls][r["n"]].append(r["client"])
            series["ev-s2"][r["n"]].append(r["server"])
    for cls, d in series.items():
        U.line([(n, st.median(v)) for n, v in sorted(d.items())], cls)
    sub_rows = [(r["id"], f"{r['n']:,}", r["status"], _num(r["client"]), _num(r["server"]), r["mode"]) for r in sub]
    # 1B server over time: the current release's memmon trace (client + server footprint, ~1 s samples)
    prof = []
    for rid in (f"annzarro_{cur}_sub_run_1000000000_r0",):
        p = repo / TC / "raw" / f"{rid}.mem.json"
        if p.exists():
            m = json.loads(p.read_text())
            prof.append((rid, [(t, b / GIB) for t, b in m["trace"]], m["peaks"]))
    tmax = max((t for _, tr, _ in prof for t, _ in tr), default=100)
    T = svg.Chart(svg.Axis(0, tmax * 1.02, fmt=lambda v: f"{v:g}", label="seconds since the run started"),
                  svg.Axis(0, 28, ticks=[0, 4, 8, 12, 16, 20, 24, 28], fmt=svg.gib, label="client + server GiB"),
                  title=f"1B cells, default subset: memory over time ({ver})", width=560, height=260,
                  desc=f"AnnZarro {ver} at 1 billion cells: client plus server footprint over time")
    for rid, tr, peaks in prof:
        cls = "ev-s2"
        T.line(tr, cls)
        if tr:
            tp, gp = max(tr, key=lambda x: x[1])
            T.text(tp - 1, gp + 0.6, f"sampled peak {gp:.1f} GiB (run peak: server "
                   f"{peaks['server']['fp_peak'] / GIB:.1f} GiB)", anchor="end", cls=f"ev-note {cls}")
        for t, g in tr[::3]:
            T.point(t, g, "circle", cls, f"{rid}\nt = {t:.0f} s: {g:.2f} GiB (client + server, memmon trace)\n"
                                          f"run peaks: server {peaks['server']['fp_peak'] / GIB:.2f} GiB, "
                                          f"client {peaks['client']['fp_peak'] / GIB:.2f} GiB", r=2.2)
    sp_all = [r for r in csv.DictReader(open(repo / TC / "server_profile_1b.csv"))      # the release's own rows
              if r.get("build", "").split()[:1] == [ver]]
    sp = [r for r in sp_all if not math.isnan(_f(r["seconds"]))]
    sp_whole = [r for r in sp_all if math.isnan(_f(r["seconds"]))]
    P = svg.Chart(svg.Axis(0, max(_f(r["seconds"]) for r in sp) * 1.15, fmt=lambda v: f"{v:g}", label="seconds"),
                  svg.Axis(-0.5, len(sp) - 0.5, ticks=list(range(len(sp))), fmt=lambda i: sp[int(i)]["request"][:30] if 0 <= int(i) < len(sp) else "",
                           label=""),
                  title="1B: one request at a time (fresh server)", width=560, height=60 + 26 * len(sp),
                  desc="AnnZarro 1B subset requests one at a time: time and server peak")
    P.m["l"] = 175
    for i, r in enumerate(sp):
        P.point(_f(r["seconds"]), i, "circle", "ev-s2",
                f"{r['request']}: {r['seconds']} s\nserver peak {r['server_peak_gib']} GiB, after {r['server_after_gib']} GiB\n"
                f"{_bytes(r['bytes'])}")
        P.text(_f(r["seconds"]), i, f"  peak {r['server_peak_gib']} GiB", cls="ev-note")
    srt = [r for r in csv.DictReader(open(repo / TC / "subset_request_times.csv")) if r["run"].startswith(f"annzarro_{cur}_")]
    reqs = [f"{r['event']}: {r['request']}" for r in srt]
    vmax = max((_f(r["ttfb_s"]) for r in srt), default=1)
    R = svg.Chart(svg.Axis(0.05, max(vmax * 2, 1), log=True, ticks=[0.1, 0.5, 1, 5, 10, 50, 100], fmt=lambda v: f"{v:g}",
                           label="time to first byte, s (log)"),
                  svg.Axis(-0.5, len(srt) - 0.5, ticks=list(range(len(srt))),
                           fmt=lambda i: reqs[int(i)][:34] if 0 <= int(i) < len(reqs) else "", label=""),
                  title=f"1B, per request: time to first byte ({ver})", width=560, height=70 + 26 * len(srt),
                  desc=f"AnnZarro {ver} at 1 billion cells: time to first byte of each request")
    R.m["l"] = 190
    for i, r in enumerate(srt):
        R.point(max(_f(r["ttfb_s"]), 0.05), i, "circle", "ev-s2",
                f"{r['run']}\n{r['event']}: {r['request']}\nTTFB {r['ttfb_s']} s, total {r['total_s']} s, "
                f"{_bytes(r['bytes'])}", r=3)
    files = {k: site_file(k) for k in (evf, f"{TC}/server_profile_1b.csv",
                                       f"{TC}/subset_request_times.csv", f"{TC}/results.csv")}
    dl = lambda k, t: f"[{t}]({rel(page, files[k])})" if files.get(k) else link(page, k, t)
    body = f"""# AnnZarro scale: every run ({rel_ver})

{CT.backs_html(page_md, "", rel)}

[[fig:scale]]'s data, every rep: AnnZarro {rel_ver} ({release['commit'][:7]}) on prefixes of Tahoe-100M (the first N cells) up to
95.6M, and synthetic stores above it for the memory-guard edge and the subset reach (recipes in
{link(page, f"{TC}/NOTES.md", "NOTES.md")}). Hover any point for the run, store and numbers.

## First plot, recolour, part step and balanced subset, every rep {{#timing}}

Blue: coloured by a gene; orange: by cell line. Lines join the medians. Data:
{dl(evf, Path(evf).name) if ev else "(the " + ver + " series has not landed yet)"}{(" (" + prov(evf) + ")") if ev else ""}.

{svg.legend_html([("ev-s1", "gene"), ("ev-s2", "cell line")], shapes=False)}

{timing}
""" + _details("Every rep (first plot and recolours)", "\n\n".join(tables)) + f"""

## Browser and server memory {{#memory}}

The renderer, GPU and server resident memory recorded at every event of every run (lines: the
largest at each N). Blue: renderer; green: GPU; orange: server.

{memory}

## Memory-guard edge {{#guard-edge}}

Every AnnZarro {ver} run at 50M cells and above with every cell drawn: a pass is a filled
circle, a refusal by the memory guard a cross (its own text in the tooltip and the table).

{svg.grid([E.render([('ev-s1', 'client peak of one run')])])}
{CT.backs_html(page_md, "guard-edge", rel)}
""" + _details("Runs at the edge, with the guard's refusal text",
               _tbl(["run", "N", "status", "client GiB", "guard text or mode"], guard_rows)) + f"""

## Subset reach to 1 billion cells {{#subset-reach}}

With the default subset (100,000 cells) and a 1,000,000-cell subset, the client stays small at
every size; the server grows with the store. All runs on {ver} ({ver_commit}).

{svg.legend_html([("ev-s1", "client, default subset"), ("ev-s3", "client, 1M subset"), ("ev-s2", "server")], shapes=False)}

{svg.grid([U.render([('ev-s1', 'client, default subset'), ('ev-s3', 'client, 1M subset'), ('ev-s2', 'server')])])}
{CT.backs_html(page_md, "subset-reach", rel)}
""" + _details("Subset runs", _tbl(["run", "N", "status", "client GiB", "server GiB", "note"], sub_rows)) + f"""

## The 1B server, over time {{#server-1b}}

{("The memmon trace of the 1B default-subset run on " + ver + " (client + server footprint, one sample a second; the run's server peak is in the tooltip). ") if prof else ""}The same requests one at a time against a fresh server ({dl(f"{TC}/server_profile_1b.csv", "server_profile_1b.csv")}), and the time
to first byte of each request in the browser runs ({dl(f"{TC}/subset_request_times.csv", "subset_request_times.csv")}).

{svg.grid(([T.render([('ev-s2', 'client + server')])] if prof else []) + ([P.render([('ev-s2', 'one request')])] if sp else []) + ([R.render([('ev-s2', 'one request')])] if srt else []))}
{CT.backs_html(page_md, "server-1b", rel)}

""" + "".join(f"{r['run']}: {r['request']}: server peak {r['server_peak_gib']} GiB, {r['server_after_gib']} GiB after.\n" for r in sp_whole) + """
""" + (_details("Requests one at a time (server_profile_1b.csv)",
               _tbl(["request", "seconds", "server peak GiB", "after GiB", "bytes"],
                    [(r["request"], r["seconds"] or "–", r["server_peak_gib"], r["server_after_gib"], r["bytes"] or "–") for r in sp_all]))
           if sp_all else "") \
        + (_details("Time to first byte per request (subset_request_times.csv)",
                   _tbl(["run", "event", "request", "TTFB s", "total s", "bytes"],
                        [(r["run"], r["event"], r["request"], r["ttfb_s"], r["total_s"], r["bytes"]) for r in srt]))
           if srt else "")
    # first search by name: the release's prewarm series (server-side cell-name index built in the background, or not)
    pwf = f"{SC}/prewarm50M_{rel_tag}.jsonl"
    if (repo / pwf).exists():
        pw = [json.loads(l) for l in (repo / pwf).read_text().splitlines() if l.strip()]
        hi = max(r["lookup_s"] for r in pw) * 1.3
        N = svg.Chart(svg.Axis(-0.5, 1.5, ticks=[0, 1], fmt=lambda i: ("prewarm off", "prewarm on")[int(i)] if i in (0, 1) else "", label=""),
                      svg.Axis(0, hi, ticks=[x for x in (0, 1, 2, 4, 6, 8, 10) if x <= hi], fmt=lambda v: f"{v:g}", label="first name search, s"),
                      title=f"First search by name, {ctx.fmt_n(pw[0]['n'])} cells ({rel_ver})", width=360, height=240,
                      desc="seconds to the first cell-name search 30 s after the plot opened, with and without the prewarm")
        for i, on in enumerate((False, True)):
            reps = [r for r in pw if bool(r["prewarm"]) == on]
            for j, r in enumerate(reps):
                N.point(i + (j - (len(reps) - 1) / 2) * 0.08, r["lookup_s"], "circle", "ev-s1" if on else "ev-s2",
                        f"prewarm {'on' if on else 'off'} · rep {j}\nsearch {r['lookup_s']} s at {r['lookup_at_s']} s"
                        f"\nserver RSS peak after {r['server_rss_peak_after'] / 2**30:.2f} GiB", r=3)
        body += f"""

## First search by name {{#name-index}}

The first search for a cell by name, 30 s after the plot of the {ctx.fmt_n(pw[0]['n'])}-cell store opened, with the
server's background cell-name index (prewarm) on and off, {len(pw)} runs on {rel_ver}
({dl(pwf, Path(pwf).name)}).

{svg.grid([N.render([('ev-s1', 'prewarm on'), ('ev-s2', 'prewarm off')])])}
{CT.backs_html(page_md, "name-index", rel)}
"""
    return body


def build(ctx):
    repo, DOCS = ctx.REPO, ctx.DOCS
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "evidence/tools"))
    from evidence.tools import svgplot as svg
    global TCP
    TCP = _load_tcp(repo)
    S = _summarize(repo)
    rows = classify(S, repo)
    pages = {"measurements/rules.md": rules_page(ctx, S, "measurements/rules.md"),
             "measurements/tool-ceiling.md": ceiling_page(ctx, S, svg, rows, "measurements/tool-ceiling.md"),
             "measurements/scale.md": scale_page(ctx, S, svg, rows, "measurements/scale.md")}
    # the 1B server section belongs with the other server measurements (benchmarks/hpc.md, gen/40_hpc.py)
    sc = pages["measurements/scale.md"]
    a, b = sc.find("## The 1B server, over time {#server-1b}"), sc.find("## First search by name")
    if a >= 0 and b > a:
        ctx.SERVER_1B = sc[a:b].rstrip() + "\n"
        pages["measurements/scale.md"] = (sc[:a] + "The 1B server's trace over time and its request tables are with the other server runs on "
                                          "[Server at atlas scale](../benchmarks/hpc.md#server-1b).\n\n" + sc[b:])
    else:
        ctx.SERVER_1B = ""
    for p, body in pages.items():
        (DOCS / p).parent.mkdir(parents=True, exist_ok=True)
        (DOCS / p).write_text(body)
