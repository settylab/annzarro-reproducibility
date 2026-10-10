#!/usr/bin/env python
"""Print the FINDINGS.md tables as markdown, straight from results/*_summary.csv (basis rows:
post-#386, not $DATA_ROOT). Nothing in FINDINGS is transcribed by hand; rerun this after collect.py.

Usage: tables.py RESULTS_DIR
"""
import os
import sys

import pandas as pd

R = sys.argv[1]


def load(name):
    p = os.path.join(R, name)
    return pd.read_csv(p) if os.path.exists(p) else None


def cell(s, case, phase, col="median", nd=3):
    r = s[(s.case_id == case) & (s.phase == phase)]
    if r.empty:
        return "n/a"
    v = r[col].iloc[0]
    return f"{v:.{nd}g}" if col != "median" else (f"{v:.2f}" if v >= 1 else f"{v:.3f}")


def iqr(s, case, phase):
    r = s[(s.case_id == case) & (s.phase == phase)]
    if r.empty:
        return ""
    return f" ({r.q25.iloc[0]:.3g}–{r.q75.iloc[0]:.3g})"


def rss(s, case):
    r = s[s.case_id == case]
    return "n/a" if r.empty or "peak_rss_mb_max" not in r else f"{r.peak_rss_mb_max.max():.0f}"


def layer_table(http, raw, rows):
    print("| dataset | chunks | role | cell row cold / warm (HTTP) | gene col cold / warm (HTTP) "
          "| row / col cold (raw zarr) | server peak RSS, MB |")
    print("|---|---|---|---|---|---|---|")
    for ds, shape, role, prefix, layer in rows:
        rc, gc = f"{prefix}:dense_layer_cell_row:{layer}", f"{prefix}:dense_layer_gene_col:{layer}"
        print(f"| {ds} | {shape} | {role} | {cell(http, rc, 'cold')}{iqr(http, rc, 'cold')} / {cell(http, rc, 'warm')} "
              f"| {cell(http, gc, 'cold')}{iqr(http, gc, 'cold')} / {cell(http, gc, 'warm')} "
              f"| {cell(raw, rc, 'cold') if raw is not None else 'n/a'} / {cell(raw, gc, 'cold') if raw is not None else 'n/a'} "
              f"| {max(rss(http, rc), rss(http, gc), key=lambda x: float(x) if x != 'n/a' else -1)} |")


def main():
    sw, swr = load("chunksweep_http_summary.csv"), load("chunksweep_raw_summary.csv")
    at, atr = load("atlas_http_summary.csv"), load("atlas_raw_summary.csv")
    X, K = "kompot_de_Xenium_smoothed", "kompot_smooth_all_smoothed"
    print("## Chunk rule check ($SCRATCH)\n")
    if sw is not None:
        layer_table(sw, swr, [
            ("spatial-A 75k×18k", s, role, f"sweep_{s.replace(',', 'x').replace('(', '').replace(')', '').replace(' ', '')}", X)
            for s, role in [("allx64", "served"), ("1024x512", "RULE"), ("1024x1024", ""), ("512x512", ""),
                            ("4096x256", ""), ("256x4096", ""), ("2048x2048", "")]])
    if at is not None:
        print()
        layer_table(at, atr, [(f"{ds}", s, role, f"{tag}@{s}", K)
                              for ds, tag in [("scPLM 460k×34k", "scPLM"), ("atlas 1.17M×12.7k", "atlas-1.17M-scvi")]
                              for s, role in [("allx4", "served"),
                                              ("2048x256" if tag == "scPLM" else "8192x64", "RULE"),
                                              ("1024x1024", ""), ("2048x128", ""), ("4096x256", ""),
                                              ("4096x64", ""), ("8192x128", ""), ("16384x64", "")]
                              if not at[at.case_id.str.startswith(f"{tag}@{s}:")].empty])
    pw, pwr = load("pairwise_http_summary.csv"), load("pairwise_raw_summary.csv")
    if pw is not None:
        print("\n## Dense pairwise rows ($SCRATCH)\n")
        print("| matrix | row chunk | values/chunk | HTTP cold / warm | raw cold / warm | payload MB | server peak RSS, MB |")
        print("|---|---|---|---|---|---|---|")
        for case in sorted(pw.case_id.unique()):
            tag = case.split(":")[0]
            r = pw[pw.case_id == case].iloc[0]
            n = int(r["n_values"]) if "n_values" in r else 0
            rows = int(tag.split("_r")[1]) if "_r" in tag else (64 if tag.startswith("corr_") else 16)
            print(f"| {tag.split('_r')[0]} | {rows} | {rows * n:.2g} | {cell(pw, case, 'cold')} / {cell(pw, case, 'warm')} "
                  f"| {cell(pwr, case, 'cold') if pwr is not None else 'n/a'} / {cell(pwr, case, 'warm') if pwr is not None else 'n/a'} "
                  f"| {r.payload_bytes_median / 1e6:.2f} | {rss(pw, case)} |")
    rl = load("real_http_summary.csv")
    if rl is not None:
        print("\n## Real data (HTTP), $SCRATCH vs node tmpfs\n")
        print("| request | $SCRATCH cold / warm | tmpfs cold / warm | payload MB |")
        print("|---|---|---|---|")
        for case in sorted(rl.case_id.unique()):
            h = rl[(rl.case_id == case) & (rl.fs == "hpctemp")]
            t = rl[(rl.case_id == case) & (rl.fs == "tmpfs")]
            f = lambda d, ph: (lambda x: "n/a" if x.empty else (f"{x.iloc[0]:.2f}" if x.iloc[0] >= 1 else f"{x.iloc[0]:.3f}"))(d[d.phase == ph]["median"])
            pb = rl[rl.case_id == case].payload_bytes_median.max() / 1e6
            print(f"| {case} | {f(h, 'cold')} / {f(h, 'warm')} | {f(t, 'cold')} / {f(t, 'warm')} | {pb:.1f} |")
    fa = load("fsarm_http_summary.csv")
    if fa is not None:
        print("\n## Filesystem arm, spatial-A (HTTP cold / warm)\n")
        print("| request | $SCRATCH | node tmpfs |")
        print("|---|---|---|")
        for k in sorted({c.split(":", 1)[1] for c in fa.case_id}):
            h, t = f"fsarm_hpctemp:{k}", f"fsarm_tmpfs:{k}"
            print(f"| {k} | {cell(fa, h, 'cold')} / {cell(fa, h, 'warm')} | {cell(fa, t, 'cold')} / {cell(fa, t, 'warm')} |")
    cc = load("concurrency_summary.csv")
    if cc is not None:
        print("\n## Concurrency, 3 workers (slowest request, median over repeats, s)\n")
        piv = cc.pivot(index="store_label", columns="concurrency", values="slowest_request_median_s")
        print("| store | " + " | ".join(f"N={c}" for c in piv.columns) + " |")
        print("|---|" + "---|" * len(piv.columns))
        for s, row in piv.iterrows():
            print(f"| {s} | " + " | ".join(f"{v:.3g}" for v in row) + " |")
    ca = load("canary.csv")
    if ca is not None:
        ca = ca[~ca["when"].astype(str).str.startswith("probe")]
        # 12:25-12:29 PDT 10-02: readings from the 12 accidentally concurrent jobs (runs/quarantine_*)
        t = pd.to_datetime(ca.ts, utc=True)
        ca = ca[~((t >= pd.Timestamp("2026-10-02T12:25:00-07:00")) & (t <= pd.Timestamp("2026-10-02T12:29:00-07:00")))]
        print(f"\n## $SCRATCH canary over the measurement jobs (n={len(ca)})\n")
        print(f"read p50 {ca.read_p50_s.median() * 1e3:.1f} ms (range {ca.read_p50_s.min() * 1e3:.1f}–{ca.read_p50_s.max() * 1e3:.1f}); "
              f"p95 {ca.read_p95_s.median() * 1e3:.0f} ms (max {ca.read_p95_s.max() * 1e3:.0f}); "
              f"max single read {ca.read_max_s.max() * 1e3:.0f} ms; {ca.ts.min()} → {ca.ts.max()}")


if __name__ == "__main__":
    main()
