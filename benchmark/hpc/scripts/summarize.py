#!/usr/bin/env python
"""Tidy summary: median, IQR (q25, q75), n per (case_id, phase) from a bench CSV.

phase=cold uses all R repeats (repeat 0 is the true first touch, also reported
separately as cold_first_touch); phase=warm pools warm_repeats x R requests.
Usage: summarize.py in.csv [more.csv ...] --out summary.csv
"""
import argparse
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("csv", nargs="+")
ap.add_argument("--out", required=True)
a = ap.parse_args()
df = pd.concat([pd.read_csv(f) for f in a.csv], ignore_index=True)
src = "http" if "payload_bytes" in df.columns else "raw"
keys = ["experiment", "case_id", "kind", "fs", "phase"]
agg = {"latency_s": [("median", "median"), ("q25", lambda s: s.quantile(.25)),
                     ("q75", lambda s: s.quantile(.75)), ("n", "size"), ("min", "min"), ("max", "max")]}
g = df.groupby(keys)
out = g["latency_s"].agg(**{k: v for k, v in agg["latency_s"]}).reset_index()
out["iqr"] = out["q75"] - out["q25"]
hwm = "server_hwm_mb" if src == "http" else "proc_hwm_mb"
out["peak_rss_mb_max"] = g[hwm].max().values
if src == "http":
    out["payload_bytes_median"] = g["payload_bytes"].median().values
    out["n_values"] = g["n_values"].max().values
    out["non200"] = g["status"].apply(lambda s: int((s != 200).sum())).values
ft = df[(df.phase == "cold") & (df.first_touch == 1)].groupby(keys)["latency_s"].first()
out = out.merge(ft.rename("cold_first_touch_s").reset_index(), on=keys, how="left")
out["ts_first"] = g["ts"].min().values
out["ts_last"] = g["ts"].max().values
out["source"] = src
out.to_csv(a.out, index=False)
pd.set_option("display.width", 250, "display.max_rows", 500, "display.max_colwidth", 70)
print(out[["case_id", "fs", "phase", "median", "q25", "q75", "n", "peak_rss_mb_max"]].to_string(index=False))
