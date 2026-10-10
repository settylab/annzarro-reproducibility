#!/usr/bin/env python
"""Summary tables of the scale benchmark (markdown) and results/summary.csv.

    python benchmark/scale/summarize.py [results dir]

Medians over repetitions; cold = first request on a fresh process and a cold
store, warm_new = another gene/cell on the same, now warm, process.
Interactive (per site, per N): server dataset open with the default subset
< 10 s, browser time to first plot (default subset) < 10 s, and recolour
by a new gene < 2 s both on the server (gene column, subset, cold) and in the
browser (subset).
"""

import sys
from pathlib import Path

import pandas as pd

RES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "results"


def fmt_n(n):
    return f"{n / 1e6:g}M"


def main():
    rows = []
    for site in ("laptop", "hpc"):
        hp, bp = RES / f"http_{site}.csv", RES / f"browser_{site}.csv"
        if not hp.exists():
            continue
        h = pd.read_csv(hp, dtype={"status": str})
        b = pd.read_csv(bp, dtype={"status": str}) if bp.exists() else pd.DataFrame()
        ok = h[h.status == "200"]
        lat = ok.pivot_table(index="interaction", columns=["n_cells", "condition"], values="latency_s",
                             aggfunc="median")
        byt = ok[ok.condition == "cold"].pivot_table(index="interaction", columns="n_cells", values="bytes",
                                                     aggfunc="median")
        print(f"\n## {site}: server latency (s), cold median\n")
        cold = lat.xs("cold", axis=1, level=1)
        cold.columns = [fmt_n(c) for c in cold.columns]
        print(cold.round(3).to_markdown())
        if "warm_new" in lat.columns.get_level_values(1):
            wn = lat.xs("warm_new", axis=1, level=1).dropna(how="all")
            wn.columns = [fmt_n(c) for c in wn.columns]
            print(f"\n## {site}: server latency (s), warm_new median\n")
            print(wn.round(3).to_markdown())
        print(f"\n## {site}: bytes per click (MB)\n")
        bb = (byt / 1e6).round(3)
        bb.columns = [fmt_n(c) for c in bb.columns]
        print(bb.to_markdown())
        bad = h[~h.status.isin(["200", "skipped"])]
        if len(bad):
            print(f"\n## {site}: failed requests\n")
            print(bad[["n_cells", "interaction", "condition", "status", "latency_s"]].to_markdown(index=False))
        mem = pd.DataFrame({
            "idle_GB": h[h.interaction.str.startswith("startup")].groupby("n_cells").rss_before.median() / 1e9,
            "after_open_sub_GB": h[h.interaction == "open_names_cells_sub"].groupby("n_cells").rss_peak.median() / 1e9,
            "peak_sub_GB": ok[ok.interaction.str.endswith("_sub")].groupby("n_cells").rss_peak.max() / 1e9,
            "peak_all_GB": ok.groupby("n_cells").rss_peak.max() / 1e9,
        })
        mem.index = [fmt_n(c) for c in mem.index]
        print(f"\n## {site}: server RSS\n")
        print(mem.round(2).to_markdown())
        if len(b):
            fp = b[b.event == "first_plot"]
            t = fp.groupby(["n_cells", "mode"]).agg(
                status=("status", lambda s: ",".join(sorted(set(s)))), first_plot_s=("seconds", "median"),
                js_heap_GB=("js_heap", lambda x: pd.to_numeric(x, errors="coerce").max() / 1e9),
                renderer_GB=("renderer_rss", lambda x: pd.to_numeric(x, errors="coerce").max() / 1e9))
            rc = b[(b.event == "recolour") & (b.status == "ok")].groupby(["n_cells", "mode"]).seconds.median()
            t["recolour_s"] = rc
            print(f"\n## {site}: browser\n")
            print(t.round(2).to_markdown())
        for n in sorted(h.n_cells.unique()):
            def med(inter, cond="cold"):
                x = ok[(ok.n_cells == n) & (ok.interaction == inter) & (ok.condition == cond)].latency_s
                return x.median() if len(x) else float("nan")
            r = {"site": site, "n_cells": n,
                 "open_sub_s": med("open_total_sub"), "open_all_s": med("open_total_all"),
                 "gene_sub_cold_s": med("gene_high_sub"), "gene_all_cold_s": med("gene_high_all"),
                 "gene_all_warm_new_s": med("gene_high_all", "warm_new"),
                 "cell_row_csr_s": med("cell_row_csr_all"), "cell_row_csc_scan_s": med("cell_row_cscscan_all"),
                 "obs_cat_all_s": med("obs_cat_all"), "emb_all_s": med("emb_all"),
                 "peak_rss_GB": ok[ok.n_cells == n].rss_peak.max() / 1e9}
            if len(b):
                for mode in ("subset", "all"):
                    d = b[(b.n_cells == n) & (b["mode"] == mode)]
                    f = d[d.event == "first_plot"]
                    r[f"browser_{mode}_status"] = ",".join(sorted(set(f.status))) if len(f) else ""
                    r[f"browser_{mode}_first_plot_s"] = f[f.status == "ok"].seconds.median()
                    r[f"browser_{mode}_recolour_s"] = d[(d.event == "recolour") & (d.status == "ok")].seconds.median()
            r["interactive"] = bool(r["open_sub_s"] < 10 and r["gene_sub_cold_s"] < 2 and
                                    r.get("browser_subset_first_plot_s", 0) < 10 and
                                    r.get("browser_subset_recolour_s", 0) < 2)
            rows.append(r)
    s = pd.DataFrame(rows)
    s.to_csv(RES / "summary.csv", index=False)
    print("\n## summary\n")
    print(s.round(3).to_markdown(index=False))


if __name__ == "__main__":
    main()
