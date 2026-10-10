"""Benchmarks > Scale: Tahoe-100M on a laptop, every cell, and the browser ceiling.

Generated from benchmark/scale/ (NOTES.md, results/, ceiling/) and figures/scale/. Every
table below is computed from the result files on each build; the hand-typed tables of
NOTES.md are not reused. Helpers (Sanitizer, claims_table, fnum) come from
10_benchmarks_index.py.
"""
import csv
import html
import importlib.util
import json
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

NAV = [("Benchmarks", "Scale: Tahoe-100M", "benchmarks/scale.md")]

D = "benchmark/scale"
R = f"{D}/results"
FULL = 95624334


def _helpers():
    p = Path(__file__).with_name("10_benchmarks_index.py")
    spec = importlib.util.spec_from_file_location("bench_helpers", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def section(text, title):
    """Body of the Markdown section whose heading text is title (to the next heading of the same or higher level)."""
    lines = text.splitlines()
    for i, l in enumerate(lines):
        m = re.match(r"^(#+) (.*)$", l)
        if m and m.group(2).strip() == title:
            lvl, out = len(m.group(1)), []
            for l2 in lines[i + 1:]:
                m2 = re.match(r"^(#+) ", l2)
                if m2 and len(m2.group(1)) <= lvl:
                    break
                out.append(l2)
            return "\n".join(out).strip() + "\n", lvl
    raise KeyError(title)


def demote(text, by):
    return re.sub(r"^(#+) ", lambda m: "#" * min(6, len(m.group(1)) + by) + " ", text, flags=re.M)


def strip_tables(text, note):
    """Replace each hand-typed Markdown table by a pointer to the generated one."""
    out, in_t = [], False
    for l in text.splitlines():
        if l.lstrip().startswith("|"):
            if not in_t:
                out.append(f'<p class="ev-meta">[hand-typed table omitted; {note}]</p>')
            in_t = True
            continue
        in_t = False
        out.append(l)
    return "\n".join(out)


def build(ctx):
    H = _helpers()
    REPO, DOCS = ctx.REPO, ctx.DOCS
    page = "benchmarks/scale.md"
    san = H.Sanitizer(ctx)
    n_pre = H.Sanitizer(ctx).presanitize([D, "figures/scale", "benchmark/tool_ceiling/logs/windows.log"])   # separate instance: the page report counts the page only
    fnum, fmt_n, prov, link = H.fnum, ctx.fmt_n, ctx.prov_badge, ctx.link_repo
    rd = lambda p: list(csv.DictReader(open(REPO / p)))
    jl = lambda p: [json.loads(l) for l in open(REPO / p) if l.strip()]

    S = {(r["tag"], int(r["n_cells"]), r["color"], r["event"]): r for r in rd(f"{R}/browser_rerun_summary.csv")}
    EV = rd(f"{R}/browser_rerun_events.csv")
    HT = {(int(r["n_cells"]), r["interaction"], r["condition"]): r for r in rd(f"{R}/http_rerun_summary.csv")}
    C = rd(f"{R}/ceiling_rerun.csv")
    heaps = [(f, l) for f in (f"{R}/heapcap_rerun.jsonl", f"{R}/heapcap_rerun_maxold16384.jsonl") for l in jl(f)]
    env_http = json.loads((REPO / f"{R}/http_rerun_environment.json").read_text())
    views = {p.name.replace(".view.json", ""): json.loads(p.read_text())
             for p in sorted((REPO / "figures/scale").glob("*.view.json"))}
    names = jl(f"{D}/ceiling/results/prewarm50M_chunked.jsonl")
    notes = (REPO / f"{D}/NOTES.md").read_text()

    def summ(tag, n, color, ev):
        return S.get((tag, n, color, ev))

    def cell(r):
        if not r:
            return "–"
        if r["n_ok"] == "0":
            return f'**{r["fail_status"] or "fail"}** {r["n_total"]}/{r["n_total"]}'
        s = (f'{fnum(r["seconds_median"])}<br><small style="color:var(--md-default-fg-color--light);white-space:nowrap">'
             f'{fnum(r["seconds_min"])}–{fnum(r["seconds_max"])}</small>')
        tip = f'{r["n_ok"]} of {r["n_total"]} clean events ok'
        if r["n_ok"] != r["n_total"]:
            s += f' · {r["n_ok"]}/{r["n_total"]} ok ({r["fail_status"]})'
        return f'<span title="{tip}">{s}</span>'

    def memmax(tag, n, field):
        v = [float(r[field]) for k, r in S.items() if k[0] == tag and k[1] == n and r[field] not in ("", None)]
        return f"{max(v):.2f}" if v else "–"

    def ns(tag):
        return sorted({k[1] for k in S if k[0] == tag})

    def time_table(tag, rows, nlist=None):
        nlist = nlist or ns(tag)
        head = "| seconds: median, range below | " + " | ".join(fmt_n(n) for n in nlist) + " |\n|---|" + "---:|" * len(nlist)
        body = [f"| {lab} | " + " | ".join(cell(summ(tag, n, c, e)) for n in nlist) + " |" for lab, c, e in rows]
        return head + "\n" + "\n".join(body)

    MEM = [("V8 heap, on-heap", "v8_used_peak_max_gb"), ("ArrayBuffers", "v8_backing_peak_max_gb"),
           ("renderer RSS", "renderer_rss_max_gb"), ("GPU-process RSS", "gpu_rss_max_gb"), ("server RSS", "server_rss_max_gb")]

    def mem_table(tag, nlist=None):
        nlist = nlist or ns(tag)
        head = "| GB, max over the clean run | " + " | ".join(fmt_n(n) for n in nlist) + " |\n|---|" + "---:|" * len(nlist)
        return head + "\n" + "\n".join(f"| {lab} | " + " | ".join(memmax(tag, n, f) for n in nlist) + " |" for lab, f in MEM)

    # ----------------------------------------------------------------- clean / overlap bookkeeping
    spec = importlib.util.spec_from_file_location("summarize_rerun", REPO / f"{D}/summarize_rerun.py")
    sr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sr)
    ev_count = defaultdict(Counter)
    for r in EV:
        ev_count[r["tag"]]["events"] += 1
        ev_count[r["tag"]]["clean" if r["clean"] == "True" else "overlapped"] += 1
    clean_rows = "\n".join(f'| `{t}` | {c["events"]} | {c["clean"]} | {c["overlapped"]} |'
                           for t, c in sorted(ev_count.items()))
    http_raw = rd(f"{R}/http_rerun.csv")
    http_clean = sum(1 for r in http_raw if sr.clean_at(float(r["timestamp"]),
                                                        float(r["latency_s"]) if r["latency_s"] not in ("", "nan") else 0))

    # ----------------------------------------------------------------- tables
    sub_rows = [("first plot, gene", "gene", "first_plot"), ("first plot, category", "cat", "first_plot"),
                ("recolour, gene", "gene", "recolour"), ("recolour, category", "gene", "recolour_cat"),
                ("next part", "gene", "part_step"), ("next part (category plot)", "cat", "part_step"),
                ("balanced subset", "gene", "balance"), ("zoom", "gene", "zoom")]
    all_rows = [("first plot, gene", "gene", "first_plot"), ("first plot, category", "cat", "first_plot"),
                ("recolour, gene", "gene", "recolour"), ("recolour, category", "gene", "recolour_cat"),
                ("zoom", "gene", "zoom"), ("drag pan", "gene", "drag")]
    ceil_rows = [("first plot, gene", "gene", "first_plot"), ("first plot, category", "cat", "first_plot"),
                 ("recolour, gene", "gene", "recolour"), ("recolour, category", "gene", "recolour_cat"),
                 ("zoom, gene", "gene", "zoom"), ("drag pan, gene", "gene", "drag")]
    large = {n: S[("all_cold", n, "gene", "first_plot")]["large_mode"] for n in ns("all_cold")
             if ("all_cold", n, "gene", "first_plot") in S}
    large_line = ", ".join(f"{fmt_n(n)}: {'large-plot' if v == '1' else 'regular'}" for n, v in large.items())

    HT_ROWS = [("open, default subset", "open_total_sub", "cold"), ("open, subset off (with /data/cells)", "open_total_all", "cold"),
               ("of which /data/cells, every cell", "open_cells_all", "cold"), ("/data/cells, subset", "open_cells_sub", "cold"),
               ("subset compute (/data/subset)", "open_subset_sub", "cold"),
               ("gene column (MALAT1), subset, cold", "gene_high_sub", "cold"), ("gene column, subset, warm", "gene_high_sub", "warm"),
               ("gene column, all cells, cold", "gene_high_all", "cold"), ("gene column, all cells, warm", "gene_high_all", "warm"),
               ("gene column (rank 1000), all cells, cold", "gene_mid_all", "cold"),
               ("obs categorical (codes), subset, cold", "obs_cat_sub", "cold"), ("obs categorical, all, cold", "obs_cat_all", "cold"),
               ("obs categorical, all, warm", "obs_cat_all", "warm"), ("obs numeric (total_counts), all, cold", "obs_num_all", "cold"),
               ("obs numeric, all, warm", "obs_num_all", "warm"), ("embedding column, subset, cold", "emb_sub", "cold"),
               ("embedding column, all, cold", "emb_all", "cold"), ("embedding column, all, warm", "emb_all", "warm"),
               ("8 concurrent gene columns, subset", "burst8_sub", "cold"), ("8 concurrent gene columns, all", "burst8_all", "cold")]
    hn = sorted({k[0] for k in HT})

    def hcell(n, i, c):
        r = HT.get((n, i, c))
        if not r:
            return "–"
        s = fnum(r["latency_median_s"])
        if r["n_ok"] != r["n_total"]:
            s += f' ({r["n_ok"]}/{r["n_total"]} ok)'
        return f'<span title="min {fnum(r["latency_min_s"])}, max {fnum(r["latency_max_s"])}, n={r["n_total"]}">{s}</span>'

    def hbytes(i, c):
        r = HT.get((FULL, i, c))
        if not r or not r["bytes_median"] or float(r["bytes_median"]) == 0:
            return ""
        b = float(r["bytes_median"])
        return f"{b / 1e6:.1f} MB" if b >= 1e5 else f"{b / 1e3:.1f} kB"

    def hrss(n, suffix):
        v = [float(r["server_rss_peak_max_gb"]) for k, r in HT.items() if k[0] == n and k[1].endswith(suffix)]
        return f"{max(v):.2f}" if v else "–"

    http_table = ("| click, median s (hover: min, max) | " + " | ".join(fmt_n(n) for n in hn) + " | bytes at 95.6M |\n|---|"
                  + "---:|" * (len(hn) + 1) + "\n"
                  + "\n".join(f"| {lab} | " + " | ".join(hcell(n, i, c) for n in hn) + f" | {hbytes(i, c)} |" for lab, i, c in HT_ROWS)
                  + "\n| server RSS peak, subset session (GB) | " + " | ".join(hrss(n, "_sub") for n in hn) + " | |"
                  + "\n| server RSS peak, every-cell session (GB) | " + " | ".join(hrss(n, "_all") for n in hn) + " | |")

    # ceiling outcomes from every row (coordinator ruling: outcomes count from every row)
    oc = defaultdict(lambda: Counter())
    rss = defaultdict(list)
    for r in C:
        base = re.sub(r"_r\d+$", "", r["tag"])
        k = (int(r["n_cells"]), r["source"], base, r["color"])
        oc[k][r["status"]] += 1
        oc[k]["clean"] += r["clean"] == "True"
        if r["renderer_rss_peak_gb"]:
            rss[k].append(float(r["renderer_rss_peak_gb"]))
    out_rows = []
    for k in sorted(oc):
        c = oc[k]
        st_ = ", ".join(f"{s} {c[s]}" for s in sorted(c) if s != "clean")
        out_rows.append(f"| {fmt_n(k[0])} | `{k[1]}` | `{k[2]}` | {k[3]} | {st_} | {c['clean']} | "
                        f"{min(rss[k]):.1f}–{max(rss[k]):.1f} |" if rss[k] else "")
    ceil_n = [n for n in ns("ceil_rerun")]
    first_fail = min(k[0] for k, c in oc.items() if c.get("crash"))
    largest_ok = max(k[0] for k, c in oc.items() if c.get("ok") and k[1] == "ceiling.py")

    def hp(line):
        m = re.search(r"onheap (\d+) used (\d+) lim (\d+)", " ".join(line["heap"].get("last", [])))
        return m
    heap_rows = []
    for f, l in heaps:
        m = hp(l)
        heap_rows.append(f'| `{Path(f).name}` | {l["version"]} | `{" ".join(l["flags"]) or "(none)"}` | '
                         f'{"crashed" if l["heap"].get("crashed") else "no crash"} | '
                         f'{int(m.group(2)) / 1e9:.2f} | {int(m.group(3)) / 1e9:.2f} | '
                         f'{l["buffers"]["off"] / 1e9:.1f} | {html.escape(l["buffers"].get("err2", ""))} |' if m else "")
    heap_lim = int(hp(heaps[0][1]).group(3))

    conf = defaultdict(list)
    for r in EV:
        if r["tag"].startswith("confirm95") and r["event"] == "first_plot":
            conf[(r["tag"], r["color"])].append((int(r["rep"]), float(r["seconds"]), r["clean"]))
    conf_rows = "\n".join(f'| {"store warm" if "warm" in t else "store cold (clone)"} | ' + " | ".join(
        ", ".join(f"{s:.2f}" for _, s, _ in sorted(conf[(t, c)])) for c in ("cat", "gene")) + " |"
        for t in ("confirm95_warm", "confirm95_cold"))
    pw_rows = "\n".join(f'| {t} | {c} | {cell(summ(t, FULL, c, "first_plot"))} | {fnum(summ(t, FULL, c, "first_plot")["server_rss_max_gb"])} |'
                        for t in ("all95_noprewarm", "all95_prewarm_ctrl") for c in ("cat", "gene"))
    name_rows = "\n".join(f'| {"on" if d["prewarm"] else "off"} | {d["plot_drawn_s"]:.2f} | {d["lookup_at_s"]:.1f} | '
                          f'{d["lookup_s"]:.2f} | {d["server_rss_peak_after"] / 1e9:.2f} |' for d in names)

    # baseline (pre-#62/#63), transposed
    base = rd(f"{R}/summary.csv")
    BCOL = [("open, default subset (s)", "open_sub_s"), ("open, subset off (s)", "open_all_s"),
            ("gene column, subset, cold (s)", "gene_sub_cold_s"), ("gene column, all cells, cold (s)", "gene_all_cold_s"),
            ("cell row, CSR layer (s)", "cell_row_csr_s"), ("cell row, CSC scan (s)", "cell_row_csc_scan_s"),
            ("obs categorical, all (s)", "obs_cat_all_s"), ("embedding column, all (s)", "emb_all_s"),
            ("server peak RSS (GB)", "peak_rss_GB"), ("browser, subset: first plot (s)", "browser_subset_first_plot_s"),
            ("browser, subset: recolour (s)", "browser_subset_recolour_s"), ("browser, every cell: status", "browser_all_status"),
            ("browser, every cell: first plot (s)", "browser_all_first_plot_s"),
            ("browser, every cell: recolour (s)", "browser_all_recolour_s"), ("interactive", "interactive")]

    def bval(r, k):
        v = r[k]
        if k == "peak_rss_GB" and v:
            return f"{float(v) / 1e9 if float(v) > 1000 else float(v):.2f}"
        try:
            return fnum(v) if v not in ("", "True", "False") else (v or "–")
        except ValueError:
            return v
    base_table = ("| baseline, medians | " + " | ".join(fmt_n(r["n_cells"]) for r in base) + " |\n|---|" + "---:|" * len(base) + "\n"
                  + "\n".join(f"| {lab} | " + " | ".join(bval(r, k) for r in base) + " |" for lab, k in BCOL))
    builds = rd(f"{R}/builds_laptop.csv")
    build_rows = "\n".join(f'| {r["step"]} | {fmt_n(r["n_cells"])} | {int(r["nnz"]) / 1e9:.2f} | {int(r["seconds"]) / 60:.1f} | '
                           f'{int(r["peak_rss_bytes"]) / 1e9:.1f} | {r["csc_disk_gb"] or "–"} | {r["note"]} |' for r in builds)

    # ----------------------------------------------------------------- environment
    envs = {p: json.loads((REPO / p).read_text()) for p in
            [f"{R}/http_rerun_environment.json", f"{R}/http_laptop_environment.json",
             f"{R}/browser_laptop_environment.json", f"{R}/browser_laptop_nolimit_environment.json"]}
    ekeys = [("run date", lambda e: e.get("date", "")),
             ("AnnZarro commit measured", lambda e: f'`{e.get("annzarro_commit", "")[:7]}`'),
             ("annzarro version (bench venv)", lambda e: e["packages"].get("annzarro", "")),
             ("server reports (annzarro, zarr, numcodecs, flask)", lambda e: e["packages"].get("server", "not recorded")),
             ("client replayed", lambda e: (e.get("client") or {}).get("version", "2858fc5 (default)")),
             ("machine", lambda e: f'{e["cpu"]}, {e["n_cpu"]} cores, {int(e["ram_bytes"]) / 2**30:.0f} GB'),
             ("OS", lambda e: e["platform"]), ("Python", lambda e: e["python"].split()[0])] + [
        (k, (lambda k: lambda e: e["packages"].get(k) or "–")(k)) for k in ("zarr", "numcodecs", "anndata", "numpy", "flask", "werkzeug", "playwright")] + [
        ("browser", lambda e: e.get("browser", "–")), ("cold mode", lambda e: e.get("cold_mode", "")),
        ("reps / warm", lambda e: f'{e.get("reps")} / {e.get("warm")}'), ("time limit (s)", lambda e: str(e.get("timeout_s")))]
    env_table = ("| | " + " | ".join(f"`{Path(p).name}`" for p in envs) + " |\n|---|" + "---|" * len(envs) + "\n"
                 + "\n".join(f"| {lab} | " + " | ".join(str(f(e)) for e in envs.values()) + " |" for lab, f in ekeys))
    browsers = Counter((r["browser"], r["flags"]) for r in EV)
    gl = {json.loads(l).get("gl") for l in open(REPO / f"{R}/browser_rerun.jsonl")} - {None}
    sub_envs = sorted((REPO / f"{R}/subset_tests").glob("*_environment.json"))

    # ----------------------------------------------------------------- manuscript claims
    sc = lambda t, n, c, e: S[(t, n, c, e)]
    a95g, a95c = sc("all_cold", FULL, "gene", "first_plot"), sc("all_cold", FULL, "cat", "first_plot")
    s95g, s95c = sc("sub_cold", FULL, "gene", "first_plot"), sc("sub_cold", FULL, "cat", "first_plot")
    ps_g, ps_c = sc("sub_cold", FULL, "gene", "part_step"), sc("sub_cold", FULL, "cat", "part_step")
    bal = sc("sub_cold", FULL, "gene", "balance")
    rec = sc("sub_cold", FULL, "gene", "recolour")
    sub_rend = [float(r["renderer_rss_max_gb"]) for k, r in S.items() if k[0] == "sub_cold" and r["renderer_rss_max_gb"]]
    sub_srv = max(float(r["server_rss_max_gb"]) for k, r in S.items() if k[0] == "sub_cold" and r["server_rss_max_gb"])
    sub_gpu = max(float(r["gpu_rss_max_gb"]) for k, r in S.items() if k[0] == "sub_cold" and r["gpu_rss_max_gb"])
    all95 = [r for k, r in S.items() if k[0] == "all_cold" and k[1] == FULL]
    all95_rend = max(float(r["renderer_rss_max_gb"]) for r in all95 if r["renderer_rss_max_gb"])
    all95_gpu = max(float(r["gpu_rss_max_gb"]) for r in all95 if r["gpu_rss_max_gb"])
    all95_srv = max(float(r["server_rss_max_gb"]) for r in all95 if r["server_rss_max_gb"])
    all95_v8 = [float(r["v8_used_peak_max_gb"]) for r in all95 if r["v8_used_peak_max_gb"]]
    fp5 = [r for r in EV if r["tag"] == "all_cold" and r["n_cells"] == "5000000" and r["color"] == "gene"
           and r["event"] == "first_plot" and r["clean"] == "True"]
    a5 = sc("all_cold", 5000000, "gene", "first_plot")
    a10 = sc("all_cold", 10000000, "gene", "first_plot")
    cr = lambda n, c: [r for r in C if int(r["n_cells"]) == n and r["color"] == c and r["tag"] == "ceil_rerun"]
    clean_ok = {(n, c): sum(1 for r in cr(n, c) if r["clean"] == "True" and r["status"] == "ok")
                for n in (FULL, 150000000, 175000000) for c in ("gene", "cat")}
    p182 = [r for r in C if r["tag"].startswith("probe182_clean")]
    all182 = [r for r in C if int(r["n_cells"]) == 182000000]
    ab175 = max(float(r["v8_backing_peak_gb"]) for r in C if int(r["n_cells"]) == 175000000 and r["v8_backing_peak_gb"])
    v8_175 = max(float(r["v8_used_peak_gb"]) for r in C if int(r["n_cells"]) == 175000000 and r["v8_used_peak_gb"])
    bpp = [round(v8_175 * 1e9 / 175e6, 1), round(max(all95_v8) * 1e9 / FULL, 1)]
    size1 = {k: v["ready_s"] for k, v in views.items() if k.startswith("tahoe95M") and ("subset" in v["view"] and v["view"]["subset"] is None)
             and v["view"]["layout"]["panelConfigs"]["cell-plot-A"].get("pointSize") == 1.0}
    size5 = {k: v["ready_s"] for k, v in views.items() if k.startswith("tahoe95M") and ("subset" in v["view"] and v["view"]["subset"] is None)
             and k not in size1}
    conf_all = [s for v in conf.values() for _, s, _ in v]
    conf_cold = [s for (t, _), v in conf.items() if "cold" in t for _, s, _ in v]
    names_off = [d["lookup_s"] for d in names if not d["prewarm"]]
    names_on = [d["lookup_s"] for d in names if d["prewarm"]]
    rng = lambda xs, nd=2: f"{min(xs):.{nd}f}–{max(xs):.{nd}f}"
    ok_rows = lambda rs: f"{sum(r['status'] == 'ok' for r in rs)}/{len(rs)} ok"
    ev_reps = Counter((r["rep"], r["seq"]) for r in EV if r["tag"] == "sub_cold" and r["n_cells"] == str(FULL)
                      and r["color"] == "gene" and r["event"] == "recolour" and r["clean"] == "True")
    BT, AB, FR = "manuscript/body.tex", "manuscript/sections/abstract.tex", "manuscript/sections/figs_results.tex"
    src_sub = "`browser_rerun_summary.csv` tag `sub_cold`, 95.6M"
    src_all = "`browser_rerun_summary.csv` tag `all_cold`, 95.6M"
    claims = [
        dict(tex=AB, needle="in 5 to 13 s", data=f'first plot {fnum(min(float(a95g["seconds_min"]), float(a95c["seconds_min"])))}–{fnum(max(float(a95g["seconds_max"]), float(a95c["seconds_max"])))} s (gene and category, point size 5)',
             source=src_all + ", first_plot", verdict="match",
             why=f"at point size 1 / opacity 0.2 a warm-store rep took {min(conf_all):.2f} s (`confirm95_warm`), below 5 s"),
        dict(tex=AB, needle="opens in 3 s", data=f'{fnum(s95g["seconds_median"])} s gene, {fnum(s95c["seconds_median"])} s category',
             source=src_sub + ", first_plot", verdict="match"),
        dict(tex=BT, needle="the first plot appeared 3.0 s", data=f'{float(s95g["seconds_median"]):.3f} s', source=src_sub + " gene", verdict="match"),
        dict(tex=BT, needle="(2.5 s coloured by cell line)", data=f'{float(s95c["seconds_median"]):.3f} s', source=src_sub + " cat", verdict="match"),
        dict(tex=BT, needle="recolouring by another gene took 0.38 s", data=f'{float(rec["seconds_median"]):.3f} s', source=src_sub + " recolour", verdict="match"),
        dict(tex=BT, needle="stepping to the next of 957 parts 2.0 s",
             data=f'{float(ps_g["seconds_median"]):.3f} s (gene plot), {float(ps_c["seconds_median"]):.3f} s (category plot); {-(-FULL // 100000)} parts',
             source=src_sub + " part_step", verdict="match", why="1.95 rounds to 1.9 or 2.0 depending on the third digit; 2.0 is fair"),
        dict(tex=BT, needle="Each step takes 2.0 s", data=f'{float(ps_g["seconds_median"]):.3f} / {float(ps_c["seconds_median"]):.3f} s',
             source=src_sub + " part_step", verdict="match"),
        dict(tex=BT, needle="the 50 cell lines 3.2 s", data=f'{float(bal["seconds_median"]):.3f} s', source=src_sub + " balance", verdict="match"),
        dict(tex=BT, needle="applying it takes 3.2 s", data=f'{float(bal["seconds_median"]):.3f} s', source=src_sub + " balance", verdict="match"),
        dict(tex=BT, needle="medians of 3 or 6 cold runs", data=f'recolour: {len(ev_reps)} clean events = {len({k[0] for k in ev_reps})} cold runs × {len({k[1] for k in ev_reps})} recolours',
             source="`browser_rerun_events.csv` `sub_cold`, 95.6M, recolour", verdict="note",
             why="the 6 are 2 events in each of 3 cold runs, not 6 cold runs; same wording in the Fig. 7e caption"),
        dict(tex=FR, needle="or 6 (recolour, part step) cold runs", data="3 cold runs × 2 events", source="as above", verdict="note",
             why="say “3 cold runs (6 events for recolour and part step)”"),
        dict(tex=BT, needle="the first plot took 1.1 s at one million cells", data=f'{float(sc("sub_cold", 1000000, "gene", "first_plot")["seconds_median"]):.3f} s',
             source="`sub_cold` 1M gene", verdict="match"),
        dict(tex=BT, needle="The browser tab used 0.6 GB at every dataset size", data=f"renderer RSS max {min(sub_rend):.2f}–{max(sub_rend):.2f} GB per row; GPU process up to {sub_gpu:.2f} GB more",
             source="`sub_cold`, all N, `renderer_rss_max_gb`", verdict="note", why="“tab” is the renderer process only; with the GPU process the browser holds about 0.8 GB"),
        dict(tex=BT, needle="the server process at most 1.8 GB", data=f"{sub_srv:.3f} GB in the browser runs; {hrss(FULL, '_sub')} GB in the HTTP subset session at 95.6M",
             source="`sub_cold` `server_rss_max_gb`; `http_rerun_summary.csv` `*_sub`", verdict="note",
             why="“at most” holds for the browser session; the HTTP bench's subset session (8 concurrent columns, numeric obs) peaked higher"),
        dict(tex=BT, needle="the server process used at most 1.8 GB", data=f"{sub_srv:.3f} GB (browser); {hrss(FULL, '_sub')} GB (HTTP subset session)",
             source="as above", verdict="note", why="as above"),
        dict(tex=BT, needle="6.3-7.5 s after the page was opened at point size 1",
             data=f"point size 1 / opacity 0.2: {min(size1.values())}–{max(size1.values())} s; the 6.3 s view is at point size 5 (`{min(size5, key=size5.get)}`)",
             source="`figures/scale/tahoe95M_*.view.json` `ready_s`", verdict="mismatch",
             why=f"at point size 1 the range is {min(size1.values())}–{max(size1.values())} s"),
        dict(tex=BT, needle="6-8 s at point size 1 and opacity 0.2", data=f"confirm95 {rng(conf_all)} s (cold store {rng(conf_cold)} s); view.json {min(size1.values())}–{max(size1.values())} s",
             source="`browser_rerun_events.csv` `confirm95_*`; `*.view.json`", verdict="note",
             why=f"one warm-store rep took {min(conf_all):.2f} s; say 5-8 s, or cite cold-store runs only"),
        dict(tex=BT, needle="6.1-9.1 s coloured by a gene", data=f'{float(a95g["seconds_min"]):.3f}–{float(a95g["seconds_max"]):.3f} s', source=src_all + " gene", verdict="match"),
        dict(tex=BT, needle="5.4-12.7 s by cell line", data=f'{float(a95c["seconds_min"]):.3f}–{float(a95c["seconds_max"]):.3f} s', source=src_all + " cat", verdict="match"),
        dict(tex=BT, needle="the tab used up to 9.6 GB", data=f"renderer RSS {all95_rend:.2f} GB; GPU process {all95_gpu:.2f} GB more", source=src_all + ", every event",
             verdict="note", why="renderer only; the 9.55 GB peak is during a recolour, the first plot alone peaks at "
             f'{max(float(a95g["renderer_rss_max_gb"]), float(a95c["renderer_rss_max_gb"])):.2f} GB'),
        dict(tex=BT, needle="with every cell of Tahoe-100M in one plot 9.6 GB", data=f"{all95_rend:.2f} GB renderer", source=src_all, verdict="match"),
        dict(tex=BT, needle="and the server 13.7 GB", data=f"{all95_srv:.3f} GB", source=src_all + " `server_rss_max_gb`", verdict="match",
             why="mostly the cell-name prewarm: without it 2.6-3.4 GB (`all95_noprewarm`)"),
        dict(tex=BT, needle="drawing every cell in one plot took 13.7 GB", data=f"{all95_srv:.3f} GB", source=src_all, verdict="match"),
        dict(tex=BT, needle="took 30 s for 5 million cells", data=f'{float(a5["seconds_median"]):.2f} s ({fnum(a5["seconds_min"])}–{fnum(a5["seconds_max"])})',
             source="`all_cold` 5M gene first_plot", verdict="match"),
        dict(tex=BT, needle="filled 3.3 GB of the tab's 4.4 GB", data=f"first-plot V8 on-heap peak {max(float(r['v8_used_peak_gb']) for r in fp5):.3f} GB (reps {', '.join(r['v8_used_peak_gb'] for r in fp5)}); limit {heap_lim / 1e9:.3f} GB",
             source="`browser_rerun_events.csv` `all_cold` 5M gene; `heapcap_rerun.jsonl`", verdict="note",
             why="3.3 GB is the maximum of 3 reps; the other two peaked at 2.6 GB"),
        dict(tex=BT, needle="against 1.2 s (1.16-1.23 s) for 10 million", data=f'{float(a10["seconds_median"]):.3f} ({float(a10["seconds_min"]):.3f}–{float(a10["seconds_max"]):.3f}) s',
             source="`all_cold` 10M gene first_plot", verdict="match"),
        dict(tex=BT, needle="drew synthetic datasets of up to 175 million", data=f"largest N with a plot drawn: {fmt_n(largest_ok)}", source="`ceiling_rerun.csv`", verdict="match"),
        dict(tex=BT, needle="The first size that failed, 182 million", data=f"first crash at {fmt_n(first_fail)}; {sum(r['status'] == 'crash' for r in all182)}/{len(all182)} rows at 182M crash",
             source="`ceiling_rerun.csv`", verdict="match"),
        dict(tex=BT, needle="(1.94 GB at 95.6 million cells)", data=f"{min(all95_v8):.3f}–{max(all95_v8):.3f} GB", source=src_all + " `v8_used_peak_max_gb`", verdict="match"),
        dict(tex=BT, needle="about 20 bytes of heap per point", data=f"{bpp[1]} B/point at 95.6M, {bpp[0]} B/point at 175M", source="`all_cold` 95.6M; `ceiling_rerun.csv` 175M", verdict="match"),
        dict(tex=BT, needle="caps the tab's heap at 4.4 GB", data=f"`jsHeapSizeLimit` {heap_lim / 1e9:.3f} GB with and without `--max-old-space-size`", source="`heapcap_rerun*.jsonl`", verdict="match"),
        dict(tex=BT, needle="7.4 GB at 175 million cells", data=f"{ab175:.3f} GB", source="`ceiling_rerun.csv` 175M `v8_backing_peak_gb`", verdict="match"),
        dict(tex=BT, needle="Each size was drawn in 3 clean runs per colouring",
             data="; ".join(f"{fmt_n(n)} {c} {v}" for (n, c), v in clean_ok.items()), source="`ceiling_rerun.csv` `ceil_rerun`, clean ok", verdict="match"),
        dict(tex=BT, needle="182 million crashed in a clean probe for both colourings",
             data=", ".join(f"{r['color']} {r['status']} (clean={r['clean']})" for r in p182), source="`ceiling_rerun.csv` `probe182_clean`", verdict="match"),
        dict(tex=BT, needle="stops between 175 and 182 million", data=f"ok at {fmt_n(largest_ok)}, crash at {fmt_n(first_fail)}", source="`ceiling_rerun.csv`", verdict="match"),
        dict(tex=FR, needle="drawn 6.4 s after the page was opened", data=f'{views["tahoe95M_umap_all_cat"]["ready_s"]} s', source="`tahoe95M_umap_all_cat.view.json`", verdict="match"),
        dict(tex=FR, needle="99th percentile over all cells (7.2 s)", data=f'{views["tahoe95M_umap_cmax30_all_gene"]["ready_s"]} s', source="`tahoe95M_umap_cmax30_all_gene.view.json`", verdict="match"),
        dict(tex=FR, needle="(the full region was drawn in 6.3 s)", data=f'{views["tahoe95M_umap_default_all_zoom"]["ready_s"]} s', source="`tahoe95M_umap_default_all_zoom.view.json`", verdict="match"),
        dict(tex=BT, needle="6.3-6.8 s at 50 million cells; 0.8 s", data=f"first search without prewarm {rng(names_off)} s; with prewarm {rng(names_on)} s",
             source="`ceiling/results/prewarm50M_chunked.jsonl`", verdict="match",
             why="no AnnZarro commit is recorded in this file (see Environment)"),
    ]
    csum, ctab = H.claims_table(ctx, claims)

    # ----------------------------------------------------------------- method text from the notes
    data_sec = demote(section(notes, "Data")[0], 1)
    stores_sec = demote(section(notes, "Stores (`build_tahoe.py`)")[0], 1)
    cond_sec = demote(section(notes, "Conditions (what changed from the baseline)")[0], 1)
    files_sec = demote(section(notes, "Files and columns")[0], 1)
    base_cond = demote(section(notes, "Conditions")[0], 1)
    ceil_sec = demote(strip_tables(section(notes, "Ceiling for drawing every cell (synthetic stores beyond 95.6M)")[0],
                             "see the generated ceiling tables above"), 1)
    where95 = strip_tables("\n".join(notes.split("**Where the 95.6M first plot goes.**", 1)[1].split("### Server per click", 1)[0].splitlines()),
                           "see the generated confirm95 table above")
    interp = demote(section(notes, "Interpretation (release-0.3)")[0], 1)
    base_interp = demote(section(notes, "Interpretation (baseline)")[0], 1)
    repro = section(notes, "Reproduce")[0]
    hpc_pending = section(notes, "HPC (pending)")[0]
    ceil_readme = re.sub(r"^# .*\n", "", (REPO / f"{D}/ceiling/README.md").read_text(), count=1)
    fig_readme = demote((REPO / "figures/scale/README.md").read_text(), 3)
    commands = (REPO / "figures/scale/commands.txt").read_text()
    rw = lambda t, src: ctx.rewrite_note_links(t, src, page, {})

    # ----------------------------------------------------------------- plots
    figs = []
    preview = None
    fs = REPO / "manuscript/figures/fig_scale.png"
    if fs.exists():
        local = ctx.site_file("manuscript/figures/fig_scale.png")
        if local:
            preview = local
        else:
            try:
                from PIL import Image
                im = Image.open(fs)
                im.thumbnail((2000, 2000))
                dst = DOCS / "repo/manuscript/figures/fig_scale.preview.png"
                dst.parent.mkdir(parents=True, exist_ok=True)
                im.save(dst, optimize=True)
                preview = "repo/manuscript/figures/fig_scale.preview.png"
            except Exception:                   # noqa: BLE001 (no Pillow: link only)
                preview = None
    panels = [("a", "tahoe95M_umap_all_cat", "every cell by cell line, point size 1, opacity 0.2"),
              ("b", "tahoe95M_umap_cmax30_all_gene", "every cell by FN1, colour capped at 30"),
              ("c (full box)", "tahoe95M_umap_default_all_zoom", "zoom box at point size 5, opacity 1"),
              ("d", "tahoe95M_umap_default_sub_cat", "default subset, part 1 of 957")]
    for lab, stem, cap in panels:
        p = f"figures/scale/{stem}.png"
        loc = ctx.site_file(p)
        v = views[stem]
        if loc:
            figs.append(f'<figure><a href="{ctx.rel(page, loc)}"><img src="{ctx.rel(page, loc)}" loading="lazy" alt="{stem}"></a>'
                        f'<figcaption><b>Fig. 7{lab}</b>: {cap}. Ready {v["ready_s"]} s after navigation; {v["browser"]}. '
                        f'{prov(p)}</figcaption></figure>')
    shot_rows = []
    for k, v in views.items():
        pc = v["view"]["layout"]["panelConfigs"]["cell-plot-A"]
        col = pc["color"]["key"]
        shot_rows.append(f'| [`{k}`]({ctx.GITHUB}/blob/{ctx.HEAD}/figures/scale/{k}.png) | {fmt_n(v["n_cells_store"])} | '
                         f'{"every cell" if ("subset" in v["view"] and v["view"]["subset"] is None) else "default subset"} | {col} | '
                         f'{pc.get("pointSize", "default")} / {pc.get("pointOpacity", "default")} | {v["ready_s"]} | '
                         f'{html.escape(v.get("notice") or "")} |')

    ins = [("notes and method", f"{D}/NOTES.md"), ("browser events (clean flag per row)", f"{R}/browser_rerun_events.csv"),
           ("browser summary (clean rows only)", f"{R}/browser_rerun_summary.csv"), ("server per click, summary", f"{R}/http_rerun_summary.csv"),
           ("server per click, raw", f"{R}/http_rerun.csv"), ("server environment", f"{R}/http_rerun_environment.json"),
           ("ceiling outcomes", f"{R}/ceiling_rerun.csv"), ("heap limit, default flags", f"{R}/heapcap_rerun.jsonl"),
           ("heap limit, --max-old-space-size", f"{R}/heapcap_rerun_maxold16384.jsonl"),
           ("raw browser events", f"{R}/browser_rerun.jsonl"), ("raw ceiling events", f"{R}/browser_rerun_ceiling.jsonl"),
           ("raw probes", f"{R}/browser_rerun_probe.jsonl"), ("confirm95 raw", f"{R}/browser_rerun_confirm95.jsonl"),
           ("probe crash stderr", f"{R}/probe200_crash_stderr.txt"), ("Chrome trace summary", f"{R}/traces/SUMMARY.txt"),
           ("CPU-profile summary", f"{R}/profiles/regular_summary.txt"), ("cell-name index (50M)", f"{D}/ceiling/results/prewarm50M_chunked.jsonl"),
           ("progress log", f"{D}/ceiling/results/PROGRESS_rerun.md"),
           ("baseline summary", f"{R}/summary.csv"), ("baseline environments", f"{R}/http_laptop_environment.json"),
           ("", f"{R}/browser_laptop_environment.json"), ("", f"{R}/browser_laptop_nolimit_environment.json"),
           ("store builds", f"{R}/builds_laptop.csv"), ("summariser (clean rule)", f"{D}/summarize_rerun.py"),
           ("browser harness", f"{D}/ceiling/ceiling.py"), ("crash probe", f"{D}/ceiling/probe.py"), ("heap probe", f"{D}/ceiling/heapcap.py"),
           ("server harness", f"{D}/bench_http.py"), ("prefix stores", f"{D}/ceiling/cut_prefix.py"), ("synthetic stores", f"{D}/ceiling/build_stores.py"),
           ("clean rerun order", f"{D}/ceiling/queue_rerun6.sh"), ("figure shots", f"{D}/ceiling/figures_tahoe.py"),
           ("figure shots README", "figures/scale/README.md"), ("figure shot commands", "figures/scale/commands.txt"),
           ("figure", "figures/fig_scale.py"), ("figure image", "manuscript/figures/fig_scale.png")]
    in_rows = "\n".join(f"| {a} | {prov(p)} |" for a, p in ins)
    queue6 = (REPO / f"{D}/ceiling/queue_rerun6.sh").read_text()
    sub_env_rows = "\n".join(
        f'| `{p.name}` | {json.loads(p.read_text())["date"]} | `{json.loads(p.read_text())["annzarro_commit"][:7]}` '
        f'({json.loads(p.read_text())["packages"]["annzarro"]}) | {prov(p.relative_to(REPO).as_posix())} |' for p in sub_envs)
    windows = "\n".join(f"| {a}Z | {b}Z |" for a, b in sr.OVERLAP)

    body = f"""---
hide: [navigation]
---

# Scale: Tahoe-100M on a laptop

How long AnnZarro takes to open, recolour and step through 1M to 95.6M real cells of
Tahoe-100M, how long one plot of every cell takes, where drawing every cell stops, and what
memory the browser and the server use.

!!! warning "Interim: re-run on the v0.3.0 tag pending"
    Measured on AnnZarro `{env_http["annzarro_commit"][:7]}` (branch `dominik/release-0.3`), not on a
    tagged release. Every headline number is to be re-run on the v0.3.0 tag and replaced if it moves
    by more than 5% (`notes/PAPER_TODO.md` E6; the manuscript marks these paragraphs “Interim until E6”).
    The HPC arm of this benchmark has not been delivered ([below](#hpc-pending)).

## The paper's numbers against the rows {{#claims}}

Every sentence of `manuscript/body.tex` and `manuscript/sections/*.tex` that quotes this
benchmark, next to the value recomputed from the result files at build time. Line numbers are
found by searching the sentence, so they follow edits. {csum}

{ctab}

## Inputs to this page

| file | provenance |
|---|---|
{in_rows}

## Environment {{#environment}}

{env_table}

**Browser runs of the release-0.3 rerun** (`browser_rerun*.jsonl`) record the browser and flags
per row but have no environment file: """ + "; ".join(f"`{b}` with `{f}` ({n} events)" for (b, f), n in browsers.items()) + f""".
WebGL: {", ".join(f"`{g}`" for g in sorted(gl))}. The AnnZarro commit of those runs
(`d5be664`) is recorded only in `NOTES.md` and `ceiling/results/PROGRESS_rerun.md`, not per row.

!!! note "Missing or inconsistent environment records"
    - No `environment.json` for the browser rerun, the ceiling runs, the heap probe or the
      cell-name index runs; their commit comes from the notes alone.
    - `http_rerun_environment.json` records the bench venv's `annzarro` as
      {env_http["packages"]["annzarro"]}, while the server under test reports version
      {env_http["packages"]["server"].split()[0]} for commit `{env_http["annzarro_commit"][:7]}` on the release-0.3 branch.
    - `prewarm50M_chunked.jsonl` (the 6.3-6.8 s first search) records no commit; its siblings
      point at the `plot-ceiling` worktree, so it predates `d5be664`.

Subset correctness tests (`results/subset_tests/`):

| environment | date | AnnZarro | provenance |
|---|---|---|---|
{sub_env_rows}

## Which rows count: the clean rule {{#clean}}

The laptop was shared. In five windows (UTC) someone live-tested AnnZarro on the same machine,
or functional browser tests ran without the bench lock:

| from | to |
|---|---|
{windows}

`summarize_rerun.clean_at(end, seconds)` marks a row `clean=False` when its interval
`[end − seconds − 30 s, end]` (30 s for the server start) meets a window; HTTP rows use
`[timestamp − latency, timestamp]`. **Times come only from clean rows**: the summaries
(`browser_rerun_summary.csv`, `http_rerun_summary.csv`) are computed from clean rows alone.
**Outcomes count from every row**: crash or ok, the heap limit and the bytes per point are
deterministic per V8 isolate (coordinator ruling, 2026-10-04), so `ceiling_rerun.csv` carries
`clean_outcome=True` on every row and `clean` for its times. Every overlapped timing was
re-run after 21:24:58Z with one bench-lock acquisition per run
({link(page, f"{D}/ceiling/queue_rerun6.sh", "queue_rerun6.sh")}).

| tag | events | clean | overlapped (times not used) |
|---|---:|---:|---:|
{clean_rows}

HTTP rows: {http_clean} of {len(http_raw)} clean.

## Results: default 100,000-cell subset {{#subset}}

Clean rows of tag `sub_cold`; each rep is a cold store clone, a fresh server and a fresh browser.
Hover a cell for the number of events.

{time_table("sub_cold", sub_rows)}

{mem_table("sub_cold")}

## Results: every cell in one plot {{#every-cell}}

Clean rows of tag `all_cold`. Path: {large_line}.

{time_table("all_cold", all_rows)}

{mem_table("all_cold")}

**95.6M at the figure's point size 1 and opacity 0.2** (`confirm95_*`, first plot, s per rep):

| store | category | gene |
|---|---|---|
{conf_rows}

**Cell-name prewarm on or off at 95.6M** (first plot):

| tag | colour | s, median (min–max) | server RSS max (GB) |
|---|---|---|---:|
{pw_rows}

**First cell-name search at 50M** (`prewarm50M_chunked.jsonl`):

| prewarm | plot drawn (s) | search at (s) | search took (s) | server RSS peak (GB) |
|---|---:|---:|---:|---:|
{name_rows}

### Where the 95.6M first plot goes (from the notes)

{where95}

## Results: server per click {{#server}}

`http_rerun_summary.csv`, clean rows, medians of 3 cold sessions (warm: 6).

{http_table}

## Results: the ceiling for drawing every cell {{#ceiling}}

Timings: clean rows of tag `ceil_rerun` on synthetic stores (95.6M is the synthetic
`syn_95624334`, not Tahoe).

{time_table("ceil_rerun", ceil_rows, ceil_n)}

{mem_table("ceil_rerun", ceil_n)}

Outcomes, from every row of `ceiling_rerun.csv` (largest N drawn: **{fmt_n(largest_ok)}**;
first crash: **{fmt_n(first_fail)}**):

| N | source | tag | colour | outcomes | clean rows | renderer RSS (GB) |
|---|---|---|---|---|---:|---|
{chr(10).join(r for r in out_rows if r)}

The tab's limits (`heapcap.py`):

| file | Chromium | flags | V8 heap filled | used at crash (GB) | `jsHeapSizeLimit` (GB) | ArrayBuffers allocated (GB) | then |
|---|---|---|---|---:|---:|---:|---|
{chr(10).join(r for r in heap_rows if r)}

{ceil_sec}

## Results: baseline before large-plot mode {{#baseline}}

AnnZarro `2858fc5`, before settylab/annzarro#62 and #63; superseded, not cited by the
manuscript. From `results/summary.csv`.

{base_table}

Store builds (`builds_laptop.csv`):

| step | N | nnz (10⁹) | minutes | peak RSS (GB) | CSC on disk (GB) | note |
|---|---|---:|---:|---:|---|---|
{build_rows}

## Plots {{#plots}}

"""
    if preview:
        body += (f'<figure><a href="{ctx.rel(page, preview)}"><img src="{ctx.rel(page, preview)}" alt="Fig. 7"></a>'
                 f'<figcaption><b>Fig. 7 as in the manuscript</b> ({"downscaled preview; " if "preview" in preview else ""}'
                 f'full size: {ctx.link_repo(page, "manuscript/figures/fig_scale.pdf", "PDF")}, '
                 f'{ctx.link_repo(page, "manuscript/figures/fig_scale.png", "PNG")}). {prov("manuscript/figures/fig_scale.png")}; '
                 f'drawn by {ctx.link_repo(page, "figures/fig_scale.py")}.</figcaption></figure>\n\n')
    body += '<div class="ev-proofs" markdown>\n' + "\n".join(figs) + "\n</div>\n\n"
    body += f"""Every app screenshot in `figures/scale/` with the readiness time from its `.view.json`:

| shot | N | cells | colour | point size / opacity | ready (s) | notice shown |
|---|---|---|---|---|---:|---|
{chr(10).join(shot_rows)}

## Method {{#method}}

### Data (from `NOTES.md`)

{data_sec}

### Stores (from `NOTES.md`)

{stores_sec}

### Conditions of the release-0.3 rerun (from `NOTES.md`)

{cond_sec}

### Files and columns (from `NOTES.md`)

{files_sec}

### Browser ceiling harness (from `ceiling/README.md`)

{rw(ceil_readme, f"{D}/ceiling/README.md")}

### Figure screenshots (from `figures/scale/README.md`)

{rw(fig_readme, "figures/scale/README.md")}

### Conditions of the baseline (from `NOTES.md`)

{base_cond}

## Interpretation (from `NOTES.md`)

<details class="ev-detail" markdown><summary>Release-0.3 interpretation, verbatim</summary>

{interp}

</details>

<details class="ev-detail" markdown><summary>Baseline interpretation, verbatim</summary>

{strip_tables(base_interp, "see the baseline table above")}

</details>

## Reproduce {{#reproduce}}

The release-0.3 rerun ran from {link(page, f"{D}/ceiling/queue_rerun.sh", "queue_rerun.sh")} (items 1-3),
{link(page, f"{D}/ceiling/queue_rerun2.sh", "queue_rerun2.sh")} (95.6M check, heap probe) and, for every
clean timing, {link(page, f"{D}/ceiling/queue_rerun6.sh", "queue_rerun6.sh")}. Then the tables:

```bash
python benchmark/scale/summarize_rerun.py   # browser_rerun_events/summary.csv, http_rerun_summary.csv, ceiling_rerun.csv
python figures/fig_scale.py                 # manuscript/figures/fig_scale.{{pdf,png}}
```

<details class="ev-detail" markdown><summary>queue_rerun6.sh, the clean rerun (paths generalised)</summary>

```bash
{queue6}
```

</details>

The screenshots of Fig. 7a-d (`figures/scale/commands.txt`, paths generalised):

```bash
{commands}
```

The baseline (from `NOTES.md`):

{repro}

## HPC arm: pending {{#hpc-pending}}

{hpc_pending}

## Generalised for publication

"""
    body = san(body)
    body += san.report() + (f"\nLinked copies of {n_pre} repository files under this benchmark's directories were "
                             "generalised the same way.\n" if n_pre else "")
    (DOCS / page).parent.mkdir(parents=True, exist_ok=True)
    (DOCS / page).write_text(body)
    san.fix_copies([D, "figures/scale", "benchmark/tool_ceiling/logs/windows.log"])  # 20_tool_ceiling links the log

