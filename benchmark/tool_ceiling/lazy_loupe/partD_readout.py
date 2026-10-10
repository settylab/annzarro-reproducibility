"""Loupe Part D readout: footprints at the checkpoints of each repetition, medians, and the verdict.

Reads <dir>/<set>_r<k>.mem.json (memmon, --started-file <set>_r<k>.go) and the checkpoint files
<set>_r<k>.opened / .cellline / .gene (each holds a Unix time written with `date +%s`).
The footprint at a checkpoint is memmon's last sample at or before it (phys_footprint of Loupe's whole process tree).

Verdict (the operator's rule: memory after open scales with gene count -> N; flat while the file grows -> Y; partial -> P):
  D_file = size(g2000.cloupe) - size(g200.cloupe);  delta = median opened(g2000) - median opened(g200)
  Y if delta < 0.10 * D_file (the spread between repetitions is printed alongside)
  N if delta >= 0.50 * D_file
  P otherwise (report the numbers)
Usage: python partD_readout.py [DIR]   (default: the folder of this script / partD)

Repo copy of the operator-side script (the only changes: the repetition start time is read from the saved .go
file times, saved in partD/go_mtimes.json (os.stat of each .go on 2026-10-08; the .go text holds the same time to the second), because a git checkout does not keep them; the two .cloupe sizes are
constants, measured with ls -l, since the files are not in the repo; and lazy_results.csv, with the gene-coloring rise, is written beside the
table). Run on partD/ it reproduces partD/readout.txt byte for byte.
"""
import csv, json, statistics, sys
from pathlib import Path

D = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "partD"
SIZES = {"g200": 393358341, "g2000": 2363578797}  # bytes of tahoe_first1000000_<set>.cloupe (ls -l)
GIB = 2 ** 30
GO = json.loads((D / "go_mtimes.json").read_text())  # mtime of each .go file as written by memmon (a git checkout does not keep them)
rows = []
for s in ("g200", "g2000"):
    for k in (1, 2, 3):
        b = D / f"{s}_r{k}"
        mem = Path(str(b) + ".mem.json")
        if not mem.exists():
            continue
        m = json.loads(mem.read_text())
        t0 = GO[f"{s}_r{k}"]
        tr = m.get("trace") or []
        r = {"set": s, "rep": k, "status": m.get("status"), "peak_gib": round(m["peaks"]["app"]["fp_peak"] / GIB, 3)}
        for c in ("opened", "cellline", "gene"):
            f = Path(str(b) + "." + c)
            if not f.exists():
                r[c] = None; continue
            t = float(f.read_text().strip() or f.stat().st_mtime) - t0
            upto = [fp for ts, fp in tr if ts <= t]
            r[c] = round(upto[-1] / GIB, 3) if upto else None
        rows.append(r)
print(f"{'set':6} {'rep':>3} {'opened':>8} {'cellline':>9} {'gene':>8} {'peak':>8}  status   (GiB, phys_footprint of Loupe's process tree)")
for r in rows:
    f = lambda v: f"{v:8.3f}" if v is not None else "       -"
    print(f"{r['set']:6} {r['rep']:>3} {f(r['opened'])} {f(r['cellline']):>9} {f(r['gene'])} {f(r['peak_gib'])}  {r['status']}")
med = {}
for s in ("g200", "g2000"):
    v = [r["opened"] for r in rows if r["set"] == s and r["opened"] is not None]
    if len(v) >= 3:
        med[s] = (statistics.median(v), max(v) - min(v))
if len(med) == 2:
    sz = SIZES
    dfile = (sz["g2000"] - sz["g200"]) / GIB
    delta = med["g2000"][0] - med["g200"][0]
    spread = max(med["g200"][1], med["g2000"][1])
    verdict = "Y (flat)" if delta < 0.10 * dfile else "N (scales)" if delta >= 0.50 * dfile else "P (partial)"
    print(f"\nmedian opened: g200 {med['g200'][0]:.3f} GiB, g2000 {med['g2000'][0]:.3f} GiB; delta {delta:+.3f} GiB")
    print(f"file sizes: g200 {sz['g200'] / GIB:.3f} GiB, g2000 {sz['g2000'] / GIB:.3f} GiB; D_file {dfile:.3f} GiB")
    print(f"largest spread of three opened values in one set: {spread:.3f} GiB")
    print(f"verdict: {verdict}   (Y if delta < {0.10 * dfile:.3f}; N if delta >= {0.50 * dfile:.3f})")
else:
    print("\nverdict: needs three repetitions with an 'opened' value for both sets")

with open(D.parent / "lazy_results.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["set", "rep", "file_bytes", "status", "opened_gib", "cellline_gib", "gene_gib", "gene_minus_opened_gib", "peak_gib"])
    for r in rows:
        w.writerow([r["set"], r["rep"], SIZES[r["set"]], r["status"], r["opened"], r["cellline"], r["gene"], round(r["gene"] - r["opened"], 3), r["peak_gib"]])
