"""Benchmarks > HPC: the current HPC runs (T and J5, drawn from their CSVs) and the claims that still wait.

The runs and their anchors come from claim_targets.HPC_RUNS; every claim that reads one links to its
section, and the claims list is built from evidence/claims.yaml (claim_targets.hpc_claims). Earlier
series (J3 on v0.4.0, the 0.1.1 benchmark/hpc/results) are superseded and stay in git only. Node
names and scratch paths in the CSVs are not printed (publication scrub); the CSVs are named, not linked.
"""
import csv
import html
import json
import re
import statistics as st
import sys
from collections import defaultdict

NAV = [("Benchmarks", "Server at atlas scale", "benchmarks/hpc.md")]

FULL = "benchmark/scale/results/hpc/full"
J5 = f"{FULL}/j5_v041/results_j5"
# Request-level runs drawn as tables: (directory, anchor, heading, what the stores are). Each shows the
# parts (subdirectories with an http.csv) that a claim reads; before any claim reads it, every part.
RUNS = [(f"{FULL}/t_v041_hpctemp_reduced", "t", "T: the public set on the scratch filer",
         "Public stores derived from Tahoe-100M"),
        (f"{FULL}/t2_v041_hpctemp_extra", "t2", "T2: the extra public set on the scratch filer",
         "Public stores derived from Tahoe-100M (dense kernels and distances at 50,000 and 100,000 cells, the 1.17M-cell prefix)")]
PART_TITLE = {"pairwise_public": "Dense pairwise rows",
              "grid": "Chunk shape: one gene column and one cell row of a dense layer"}
J5_CLICKS = [("gene_high_all", "gene column of X, a gene in most cells", "ev-s2"),
             ("gene_mid_all", "gene column of X, a gene in fewer cells", "ev-s1"),
             ("cell_row_csr_all", "cell row of X", "ev-s3"),
             ("obs_num_all", "whole numeric obs column (total_counts), all cells", "ev-s4")]
# Not drawn: the ladder's obs_cat_* clicks request categorical columns as JSON strings (no
# categorical=codes), which the app never sends.


def build(ctx):
    sys.path.insert(0, str(ctx.REPO / "evidence/tools"))
    import claim_targets as CT
    page = "benchmarks/hpc.md"
    claims = ctx.rel(page, "claims.md")
    hpc = CT.hpc_claims()
    pending = [k for k, e in hpc if CT.hpc_pending(e)]
    text = lambda s: html.escape(re.sub(r"\\pending\{([^}]*)\}", r"[pending: \1]", str(s)))
    label = {a: l.split(": ", 1)[-1].split(",")[0] for a, l in CT.HPC_RUNS.values()}

    def state(k, e):
        if k in pending:
            return "waits for the re-measure"
        runs = CT.hpc_run(e)
        return "final" + (" (" + ", ".join(f'<a href="#{a}">{label[a]}</a>' for a in runs) + ")" if runs else "")
    rows = "\n".join(
        f'<tr><td><span id="{CT.hpc_anchor(k)}"></span><a href="{claims}#{k}">{k}</a></td>'
        f'<td><code>{e.get("status", "")}</code></td><td>{text(e.get("text", ""))}</td>'
        f'<td><code>{e.get("file", "").replace("manuscript/", "")}</code></td>'
        f'<td>{state(k, e)}</td></tr>'
        for k, e in hpc)
    run_secs = "\n\n".join(s for s in (run_section(ctx, page, CT, *r) for r in RUNS) if s)
    j5_sec = j5_section(ctx, page, CT)
    waiting = (f"{len(pending)} claims are still `interim` or `unsourced` and the paper prints them as "
               f"pending placeholders: " + ", ".join(f"[{k}]({claims}#{k})" for k in pending) + "."
               if pending else "No HPC claim is waiting.")
    body = f"""# Server at atlas scale: the HPC runs and the 1B run

!!! {"warning" if pending else "note"} "{"Partly pending" if pending else "Measured"}: the HPC re-measure"
    The HPC runs on the remote HPC orchestrator measure what one click costs the AnnZarro server
    (latency, payload and peak resident memory) on whole HPC nodes, with the stores on a shared NFS
    scratch filer. The runs below are the ones `evidence/superseded.yaml` lists as current; earlier
    series (J3 on v0.4.0 and the AnnZarro 0.1.1 HPC series) are not shown. {waiting}

{run_secs}

{j5_sec}

{getattr(ctx, "SERVER_1B", "")}
## The paper's HPC claims {{#claims}}

{CT.backs_html(page, "claims", ctx.rel)}

Each claim in the manuscript whose source is an
HPC run or that waits for the HPC re-measure. Each row links to its ledger entry, which recomputes
the value and says what closes it.

<table>
<thead><tr><th>claim</th><th>status</th><th>manuscript says</th><th>file</th><th></th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
"""
    (ctx.DOCS / page).parent.mkdir(parents=True, exist_ok=True)
    (ctx.DOCS / page).write_text(body)


def _env_line(e):
    cpu = e.get("cpu") or {}
    mem = re.search(r"(\d+)\s*kB", str(e.get("mem_total", "")))
    return (f"{cpu.get('model_name', '?').replace('Intel(R) Xeon(R) ', 'Xeon ').replace(' CPU', '')}, "
            f"{cpu.get('nproc_allowed', '?')} CPUs allowed (a whole node)"
            + (f", {int(mem.group(1)) * 1024 / 2**30:.0f} GiB RAM" if mem else "")
            + f"; AnnZarro {e.get('packages', {}).get('annzarro', '?')}"
            + (f" (tag {e['annzarro_release_tag']}, `{e.get('annzarro_release_commit', '')[:7]}`)" if e.get("annzarro_release_tag") else ""))


def run_section(ctx, page, CT, root, anchor, heading, stores):
    """One request-level run, from each part's http.csv and environment record (read at build time)."""
    base = ctx.REPO / root
    parts = sorted(p.parent for p in base.rglob("http.csv")) if base.exists() else []
    cited = {d for d in parts if any((CT._path(s) or "").startswith(d.relative_to(ctx.REPO).as_posix() + "/")
                                       for _, e in CT._claims().items() if isinstance(e, dict) for s in CT._srcs(e))}
    parts = [d for d in parts if d in cited] or parts
    if not parts:
        return ""
    envs = sorted(parts[0].glob("http.env_*.json"))
    env = json.loads(envs[0].read_text()) if envs else {}
    cold = (env.get("cold_protocol") or {})
    out = [f"""## {heading} {{#{anchor}}}

{CT.backs_html(page, anchor, ctx.rel)}

{stores}, on an NFSv4.1 scratch filer; {_env_line(env)}.
**Cold:** {html.escape(cold.get("definition", "a fresh server and the node's page cache evicted"))}.
**Eviction:** {html.escape(cold.get("eviction", "–"))}. Every row of each table is computed from the
part's `http.csv` (in the repository under `{root}/`): medians over the cold and warm repeats; peak is
the server's resident high-water mark during the cold requests, idle its resident memory before them.
"""]
    for d in parts:
        rows = [r for r in csv.DictReader(open(d / "http.csv")) if r.get("status") == "200"]
        by = defaultdict(lambda: defaultdict(list))
        for r in rows:
            by[r["case_id"]][r["phase"]].append(r)
        f = lambda xs, k: [float(x[k]) for x in xs if x.get(k) not in ("", None)]
        med = lambda v, nd=3: f"{st.median(v):.{nd}f}" if v else "–"
        tbl = []
        for case, ph in sorted(by.items()):
            c, w = ph.get("cold", []), ph.get("warm", [])
            tbl.append((f"`{case}`", len(c), med(f(c, "latency_s")), len(w), med(f(w, "latency_s")),
                        med([v / 1e6 for v in f(c, "payload_bytes")], 2), med(f(c, "n_values"), 0),
                        med(f(c, "server_hwm_mb"), 0), med(f(c, "server_baseline_rss_mb"), 0)))
        out.append(f"### {PART_TITLE.get(d.name, d.name.replace('_', ' '))}\n\n" + ctx.md_table(
            tbl, ["case", "cold n", "cold median s", "warm n", "warm median s", "payload MB", "values",
                  "peak MiB", "idle MiB"]) + "\n")
    return "\n".join(out)


def j5_section(ctx, page, CT):
    """J5: per-click server latency over the Tahoe-100M ladder, every cold request, from its CSV."""
    sys.path.insert(0, str(ctx.REPO))
    from evidence.tools import svgplot as svg
    f = f"{J5}/http_hpc_filerwarm.csv"
    if not (ctx.REPO / f).exists():
        return ""
    allrows = list(csv.DictReader(open(ctx.REPO / f)))
    rows = [r for r in allrows if r["status"] == "200"]
    env = json.loads((ctx.REPO / f"{J5}/http_hpc_filerwarm_environment.json").read_text())
    by = defaultdict(list)
    for r in rows:
        by[(r["interaction"], r["condition"], int(r["n_cells"]))].append(float(r["latency_s"]))
    ns = sorted({int(r["n_cells"]) for r in rows})
    keys = {k for k, _, _ in J5_CLICKS}
    lat = [v for (i, c, _), vs in by.items() for v in vs if c == "cold" and i in keys]
    lo, hi = max(min(lat) / 1.5, 0.01), max(lat) * 1.5
    ch = svg.Chart(svg.Axis(ns[0] / 1.3, ns[-1] * 1.3, log=True, ticks=ns, fmt=ctx.fmt_n, label="cells in the store"),
                   svg.Axis(lo, hi, log=True, ticks=[x for x in (0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100) if lo <= x <= hi],
                            fmt=lambda v: f"{v:g}", label="server latency, s (log)"),
                   title=f"J5: one click, cold, AnnZarro {env['packages']['annzarro']}", width=620, height=320,
                   desc="server latency per click over the Tahoe-100M ladder on one HPC node, every cold request")
    table = []
    for key, lab, cls in J5_CLICKS:
        med = []
        for n in ns:
            vs = by.get((key, "cold", n), [])
            for j, v in enumerate(vs):
                ch.point(n * (1 + (j - 1) * 0.04), v, "circle", cls, f"{lab}\n{ctx.fmt_n(n)} cells, cold request {j}: {v:.3f} s", r=2.6)
            if vs:
                med.append((n, st.median(vs)))
            w = by.get((key, "warm", n), [])
            table.append((lab, ctx.fmt_n(n), len(vs), f"{st.median(vs):.3f}" if vs else "–",
                          len(w), f"{st.median(w):.3f}" if w else "–"))
        ch.line(med, cls)
    skipped = len(allrows) - len(rows)
    return f"""## J5: the Tahoe-100M ladder on one HPC node (AnnZarro {env['packages']['annzarro']}) {{#j5}}

{CT.backs_html(page, "j5", ctx.rel)}

The Tahoe-100M-derived stores of [[fig:scale]] (1M to 95.6M cells) served by AnnZarro
{env['packages']['annzarro']} on one HPC node ({env['n_cpu']} CPUs, {env['ram_bytes'] / 2**30:.0f} GiB RAM;
stores on an NFSv4.1 scratch filer), {env['reps']} cold requests per click and size (a fresh server
and the node's page cache evicted with `posix_fadvise(DONTNEED)` on every store file before each)
and {env['warm']} warm. Every cold request is a point; lines join the medians. Data: `{f}`
({len(rows)} requests; {skipped} more skipped by the harness's slow rule or `--skip`). The filer's own
cache is not controlled.

{svg.grid([ch.render([(c, l) for _, l, c in J5_CLICKS])])}

<details class="ev-detail" markdown><summary>Medians per click and size</summary>

{ctx.md_table(table, ["click", "cells", "cold n", "cold median s", "warm n", "warm median s"])}

</details>
"""
