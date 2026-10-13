"""Measurements > Tool ceiling: cells drawn within a client memory budget.

A page module: build.py imports every evidence/gen/*.py in name order, calls
build(ctx) with ctx = the build module (helpers: DOCS, REPO, csv, re, Counter,
link_repo, prov_badge, site_file, rel, md_table, fmt_n, rewrite_note_links),
and adds NAV to the site navigation as (section, title, page).
"""
import csv
import re

import yaml
from collections import Counter

NAV = []         # the page itself (measurements/tool-ceiling.md) is written by 25_measurements.py, which calls parts()
PAGE = "measurements/tool-ceiling.md"


EDGE_VARIANTS = ("v041_noguard", "v041_noguard_edge")


def _short_failure(chk):
    """'Array buffer allocation failed in <where>' from the first console error of a check in task.json."""
    for line in chk.get("console") or []:
        if not line.startswith("error:"):
            continue
        msg = re.search(r"RangeError: ([^\n]+)", line)
        frames = re.findall(r"at (\S+(?: \S+)?) \(([^)]*)\)", line)
        ctor = next((f for f, u in frames if f.startswith("new ")), "")
        where = next(((f, u) for f, u in frames if u.startswith("http")), None)
        loc = ""
        if where:
            fn, url = where
            loc = f" in {fn if not fn.startswith('t.') else ctor.replace('new ', '') + ' copy'}, {url.split('/')[-1].split(':')[0]}"
        return (msg.group(1) if msg else line[7:60]) + loc
    return chk.get("status", "")


def edge_section(ctx, page, d, ceil, results, link_repo, prov_badge, md_table, fmt_n):
    """AnnZarro with the memory guard off, in one short paragraph (anchor guard-off-edge). Every number is read
    from results.csv, the ceilings row and the raw task.json of the failing runs. The attempts stay in results.csv."""
    REPO = ctx.REPO
    import json
    import claim_targets as CT
    rows_in = [r for r in results if r["tool"] == "annzarro" and r["variant"] in EDGE_VARIANTS]
    if not rows_in:
        return ""
    def task(r):
        tj = REPO / d / "raw" / f'{r["id"]}.task.json'
        return json.loads(tj.read_text()) if tj.exists() else {}
    edge = [r for r in rows_in if r["variant"] == "v041_noguard_edge" and r["failure_mode"] not in ("hang", "gene: stalled")]
    ok_both = max(int(r["n"]) for r in edge if r["status"] == "ok")
    ok_gene = max(int(r["n"]) for r in edge if not r["failure_mode"].startswith("gene:"))
    row = next((r for r in ceil if r["tool"] == "annzarro" and r["variant"] == "v041_noguard_edge"), None)
    if row:       # the sentence must agree with ceilings.csv, never with a number typed here
        assert int(row["max_n_ok"]) == ok_both and int(row["max_n_gene_drawn"]) == ok_gene, (row["max_n_ok"], ok_both, ok_gene)
    cat_fail = min(int(r["n"]) for r in edge if r["failure_mode"].startswith("cat:"))
    gene_fail = min(int(r["n"]) for r in edge if r["failure_mode"].startswith("gene:"))
    msg = lambda kind, n: next(_short_failure(task(r).get("checks", {}).get(kind, {})) for r in edge
                               if int(r["n"]) == n and r["failure_mode"].startswith(kind + ":"))
    return f"""<div id="guard-off-edge" markdown="1">

**With the memory guard off**, AnnZarro v0.4.1 draws every cell colored by category and by gene up to
**{fmt_n(ok_both)}** and every cell colored by gene alone up to **{fmt_n(ok_gene)}**. The category recolor fails at
{fmt_n(cat_fail)} ({msg("cat", cat_fail)}), and the first plot by gene at {fmt_n(gene_fail)} ({msg("gene", gene_fail)}). These runs
are not in Fig. 1c; the attempts are rows of {link_repo(page, f"{d}/results.csv", "results.csv")} (variants
`{"`, `".join(EDGE_VARIANTS)}`).
{CT.backs_html(page, "guard-off-edge", ctx.rel)}
</div>
"""


def build(ctx):
    """Writes nothing: 25_measurements.py assembles the single Tool ceiling page from parts()."""


def parts(ctx):
    """(head, ceilings, tail): the page's Markdown before the per-run charts, the ceilings and guard-off
    sections, and the clean-time rule and method after them."""
    REPO = ctx.REPO
    link_repo, prov_badge, site_file, rel, md_table, fmt_n, rewrite_note_links = (
        ctx.link_repo, ctx.prov_badge, ctx.site_file, ctx.rel, ctx.md_table, ctx.fmt_n, ctx.rewrite_note_links)
    page = PAGE
    d = "benchmark/tool_ceiling"
    ceil = list(csv.DictReader(open(REPO / d / "ceilings.csv")))
    results = list(csv.DictReader(open(REPO / d / "results.csv")))
    # only the cited release's AnnZarro rows (the mirrored results.csv is cut the same way, build.write_current_rows)
    keep_vars = ctx.current_annzarro_variants()
    results = [r for r in results if r["tool"] != "annzarro" or r["variant"] in keep_vars]
    over = {r["id"]: r for r in csv.DictReader(open(REPO / d / "overlaps.csv"))}
    status = Counter((r["phase"], r["status"]) for r in results)
    clean = sum(1 for r in results if over.get(r["id"], {}).get("clean_time") == "True")
    unflagged = [r["id"] for r in results if r["id"] not in over]
    def n(v, lower=False):
        return "–" if not v else ("≥ " if lower else "") + fmt_n(v)
    rows = []
    for r in ceil:
        lower = r.get("kind_16gb", "").startswith("lower bound")      # no failure above: largest N tested
        rows.append((r["tool"], r["variant"], r["rendering"],
                     n(r["max_n_8gb"]), f'**{n(r["max_n_16gb"], lower)}**', n(r["max_n_32gb"], lower),
                     n(r["max_n_ok"], lower), n(r.get("max_n_gene_drawn")), n(r["max_n_server_budget"]),
                     ("server remote, not measured here" if r["variant"].startswith("remote") else (r["server_gb_at_max_n_ok"] or "–")),
                     n(r["first_fail_n"]) + f' ({r["first_fail"].split()[0]})' if r["first_fail_n"] else "–",
                     r["n_runs"]))
    # AnnZarro as a local app: browser and server share the laptop (the largest N run, both variants)
    local = {}
    for r in results:
        if r["tool"] == "annzarro" and r["phase"] == "run" and r["status"] == "ok" and not r["variant"].startswith("remote"):
            k = r["variant"]
            if k not in local or int(r["n"]) > int(local[k]["n"]):
                local[k] = r
    def gb(x):
        return f"{float(x):.1f} GiB" if x else "?"
    # AnnZarro's current variants are those the registry names (evidence/superseded.yaml); earlier builds are not shown
    reg = yaml.safe_load((REPO / "evidence/superseded.yaml").read_text())
    cur_vars = set()
    for e in reg.get("current") or []:
        w = e.get("where") or {}
        if e.get("csv") == f"{d}/results.csv" and w.get("variant"):
            cur_vars |= set(w["variant"] if isinstance(w["variant"], list) else [w["variant"]])

    def line(v, r):
        return (f'{v}: at {fmt_n(r["n"])} cells, client {gb(r["fp_client_gb"])} + server {gb(r["fp_server_gb"])}'
                f' = {float(r["fp_client_gb"]) + float(r["fp_server_gb"]):.1f} GiB on one machine')
    both = {v: r for v, r in local.items() if r.get("fp_client_gb") and r.get("fp_server_gb")}
    local_txt = "; ".join(line(v, r) for v, r in sorted(both.items()) if v in cur_vars) or "none on the current release yet"
    pending = [r for r in ceil if not r.get("row_status", "final").startswith("final")]
    banner = ('' if not pending else
              '!!! warning "Provisional rows"\n'
              f'    {len(pending)} of {len(ceil)} rows of `ceilings.csv` are not final yet (`row_status`): '
              + "; ".join(f'{r["tool"]} {r["variant"]}: {r["row_status"]}' for r in pending) + ".\n")
    readme = (REPO / d / "README.md").read_text()
    readme = re.sub(r"^# .*\n", "", readme, count=1)
    readme = re.sub(r"^(#+) ", lambda m: "#" + m.group(1) + " ", readme, flags=re.M)
    readme = rewrite_note_links(readme, f"{d}/README.md", page, {})
    # the rules (cap, timeout, budgets, input, server budget, hang) are on measurements/rules.md: link, do not repeat
    readme, k1 = re.subn(r"- Safety cap: a run is killed.*?(?=\n- Headless Chromium)",
                         "- The safety cap, the timeouts, the budgets, the input rule and the hang rule are on [Rules behind the results](rules.md).",
                         readme, count=1, flags=re.S)
    readme, k2 = re.subn(r"\nUnits: memory is in GiB.*?Details: NOTES\.md\.\n",
                         "\nUnits: memory is in GiB (2^30 bytes) throughout. The budgets, the input rule, the server budget and the hang rule "
                         "are on [Rules behind the results](rules.md).\n", readme, count=1, flags=re.S)
    # the README's status line names a CSV column; say it in words (the provisional rows get their own banner above)
    readme, k3 = re.subn(r"\nStatus: final for every row of `ceilings.csv` \(column `row_status`\)\. AnnZarro is measured on v0.4.1 \(NOTES.md,\n\"Build under test\"\); results from older AnnZarro builds are kept in HISTORY.md and are\nnot cited.\n",
                         "\nAnnZarro is measured on v0.4.1; results from older AnnZarro builds are not shown.\n"
                         , readme, count=1)
    assert k3 == 1, "README status line changed; update the replacement in 20_tool_ceiling.py"
    assert k1 == 1 and k2 == 1, "README rules text changed; update the replacement in 20_tool_ceiling.py"
    curve = site_file(f"{d}/ceiling_curve.png")
    versions = sorted({r["versions"] for r in results if r["versions"] not in ("", "{}")})
    edge_md = edge_section(ctx, page, d, ceil, results, link_repo, prov_badge, md_table, fmt_n)
    body = f"""# Tool ceiling: cells drawn within a memory budget

@@BACKS@@

This one page holds the ceilings table, every run behind them (per tool and variant), the clean-time rule
and the method. Every number on it is computed from the result files listed next.

!!! abstract "Whose memory each number is"
    - **Client**: for a web tool, every Chromium process (browser, renderer, GPU), with the
      tool's server treated as remote; for a library (Scanpy, Seurat), the whole R or Python
      process, which has no separate server. The budgets (8, 16 and 32 GiB; 16 GiB = 17.2 GB, 1 GiB = 2^30 bytes) apply to the client. This page reports the benchmark's own numbers in GiB; the paper quotes measured memory in decimal GB (converted, e.g. 11.8 GiB = 12.7 GB).
    - **Server**: the tool's own server process(es), measured in the same run and reported
      beside the client. For **server-rendered** tools (iSEE, ShinyCell) the browser only
      shows an image, so the server is what limits.
    - **Total**: client + server, which matters when both run on one machine (a local app).
    - **≥ N** means the largest N tested passed: a lower bound, not a limit.
    - **Data**: every tool gets the same cells: prefixes of Tahoe-100M (the first N cells of the
      95.6M-cell store) up to 95.6M, and synthetic stores above 95.6M (recipes:
      {link_repo(page, "benchmark/scale/NOTES.md", "benchmark/scale/NOTES.md", "#ceiling-for-drawing-every-cell-synthetic-stores-beyond-956m")},
      {link_repo(page, "benchmark/tool_ceiling/NOTES.md", "benchmark/tool_ceiling/NOTES.md")}).
      Screenshots and demonstration images elsewhere on this site show real data only.
    - **AnnZarro as a local app** (browser and server on the same laptop), current release: {local_txt}.

{banner}
## Source files

| file | provenance |
|---|---|
| ceilings | {prov_badge(f"{d}/ceilings.csv")} |
| per-run results | {prov_badge(f"{d}/results.csv")} |
| clean-time flags | {prov_badge(f"{d}/overlaps.csv")} |
| curve | {prov_badge(f"{d}/ceiling_curve.png")} |
| method | {prov_badge(f"{d}/README.md")} |
| summariser | {prov_badge(f"{d}/summarize.py")} |

## Ceilings {{#ceilings}}

Largest N whose client footprint stays within each budget, in GiB (only measured N count; an N
that was not run is never assumed). Server-rendered tools (iSEE, ShinyCell) are limited by
their server; see the server column (server within its {ceil[0]["server_budget_gib"] if ceil else "32"} GiB budget) in {link_repo(page, f"{d}/ceilings.csv", "ceilings.csv")}.

{md_table(rows, ["tool", "variant", "rendering", "client ≤ 8 GiB", "client ≤ 16 GiB", "client ≤ 32 GiB",
                  "largest N drawn (any memory)", "largest N, gene coloring only (any memory)", f"server ≤ {ceil[0]['server_budget_gib'] if ceil else '32'} GiB", "server GiB at largest N", "first failure", "runs"])}

≥ marks the largest N tested: no failure was found above it, so it is not a limit. "Largest N, gene
coloring only" is filled where the first plot (colored by gene) draws every cell at an N above the
largest N that also draws every cell colored by category; "–" means the two agree. The guard-off
rows are explained in the paragraph below. Preparing a dataset for the UCSC Cell Browser needs very large
memory, which no ceiling here includes: see [its entry](../tools/ucsc-cell-browser.md).

The figure puts every tool on one memory axis, so the ceilings can be compared at a glance; the charts under
"Every run" show each run of each variant.

![Peak client footprint against N, one panel per tool]({rel(page, curve) if curve else ""})

{edge_md}
## Runs and the clean-time rule

{len(results)} rows in `results.csv`: """ + ", ".join(f"{n} {ph} {st}" for (ph, st), n in sorted(status.items())) + f""".
A row's timing counts only when its interval overlaps no logged session of other work on
the machine (`summarize.mark_overlaps`); memory peaks are not affected. **{clean}** rows
are clean{f"; {len(unflagged)} rows have no flag yet (run `summarize.py`)" if unflagged else ""}.
The window log the rule reads is kept in the repository,
{link_repo(page, f"{d}/logs/windows.log", "logs/windows.log")} ({prov_badge(f"{d}/logs/windows.log")}),
so the rule can be re-run from the repository alone; `summarize.py` refreshes that copy from the
live log first when `$TOOL_CEILING_WINDOWS_SRC` names one.

Versions recorded per run (distinct sets): {len(versions)}. Every run's raw memory trace
and task record are under {link_repo(page, f"{d}/raw", "raw/")}.

## Method (from the benchmark's README)

{readme}
"""
    head, rest = body.split("## Ceilings {#ceilings}", 1)
    mid, tail = rest.split("## Runs and the clean-time rule", 1)
    return head, "## Ceilings {#ceilings}" + mid, "## Runs and the clean-time rule" + tail


