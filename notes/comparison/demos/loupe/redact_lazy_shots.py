"""Loupe Part D shots (lazy-read test): the desktop session saved six full-screen captures that also show the
operator's desktop (Finder window, Dock, file names). Keep only the Loupe window, save as JPEG next to a manual
sidecar pinned by sha256. Raw PNGs (benchmark/tool_ceiling/lazy_loupe/partD/*_gene.png on the operator's disk,
$DEMO_ROOT/loupe/lazy/partD/) are not published. Window rectangles and callout boxes were read off each capture.
Usage: python redact_lazy_shots.py [RAW_DIR]"""
import hashlib, os, sys
from pathlib import Path
from PIL import Image
import yaml

_REPO = Path(__file__).resolve().parents[4]
S = _REPO / "notes/comparison/screens/loupe"
RAW = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "annzarro_compare/loupe/lazy/partD")
SW = "Loupe Browser 9.1.0 (macOS; About box: Version 9.1.0 (9.1.0))"
WIN = (131, 30, 1243, 735)        # the Loupe window in five captures; g200 r1 sits 45 px left and 18 px lower
WIN_G200_R1 = (86, 48, 1198, 753)
# (set, rep) -> (capture time, window rect); the Finder window and the Dock are outside the rectangle
SHOTS = {("g200", 1): ("22:06", WIN_G200_R1), ("g200", 2): ("22:10", WIN), ("g200", 3): ("22:14", WIN),
         ("g2000", 1): ("22:08", WIN), ("g2000", 2): ("22:12", WIN), ("g2000", 3): ("22:16", WIN)}
GENES = {"g200": (200, "feature_200", "0.366 GiB"), "g2000": (2000, "feature_1964", "2.201 GiB")}
# callouts in the coordinates of the usual window position (WIN); the layout inside the window is the same in every capture
CALL = [((535, 33, 305, 18), "title: the file that is open"), ((218, 195, 215, 50), "MALAT1, active feature"),
        ((668, 108, 360, 372), "UMAP colored by MALAT1"), ((1040, 185, 190, 55), "color legend: Log2 Exp - MALAT1"),
        ((1050, 370, 170, 22), "999966 barcodes found")]
OPENED = {}
for line in (_REPO / "benchmark/tool_ceiling/lazy_loupe/lazy_results.csv").read_text().splitlines()[1:]:
    c = line.split(","); OPENED[(c[0], int(c[1]))] = c[4]
for (s, k), (when, win) in SHOTS.items():
    g, feat, size = GENES[s]
    stem = f"m05_lazy_APP_{s}_r{k}_malat1"
    im = Image.open(RAW / f"{s}_r{k}_gene.png").convert("RGB")
    assert im.size == (1372, 891), im.size
    out = im.crop(win)
    jpg = S / (stem + ".jpg"); out.save(jpg, "JPEG", quality=88)
    side = {"version": 1, "image": stem + ".jpg", "tool": "loupe", "software": SW,
            "data": f"tahoe_first1000000_{s}.cloupe: the same 1,000,000 Tahoe-100M cells with {g:,} genes ({size}), LoupeR create_loupe() via benchmark/tool_ceiling/loupe_build.R",
            "url": "desktop app", "captured": "2026-10-08",
            "by": "comparison-auditor (scored) / desktop session operator (shots)",
            "driver": ("Loupe Part D, lazy-read test (computer-use desktop session; protocol benchmark/tool_ceiling/lazy_loupe/PROTOCOL.md, "
                       f"memory record benchmark/tool_ceiling/lazy_loupe/partD/{s}_r{k}.mem.json; redacted by notes/comparison/demos/loupe/redact_lazy_shots.py)"),
            "source": "manual", "image_sha256": hashlib.sha256(jpg.read_bytes()).hexdigest(),
            "proves": [{"column": "lazy", "mark": "Y",
                        "caption": (f"Loupe Browser 9.1.0 with the {g:,}-gene file ({size}), repetition {k}, colored by MALAT1: 999966 barcodes found. "
                                    f"The app's memory after opening was {OPENED[(s, k)]} GiB; the 200-gene and the 2,000-gene file gave the same median "
                                    "(1.273 and 1.272 GiB), see benchmark/tool_ceiling/lazy_loupe/partD/readout.txt")}],
            "callouts": [{"n": i + 1, "box": [b[0] - WIN[0], b[1] - WIN[1], b[2], b[3]], "label": l} for i, (b, l) in enumerate(CALL)]}
    (S / (stem + ".annot.yaml")).write_text(yaml.safe_dump(side, sort_keys=False, allow_unicode=True, width=110))
    print(stem, out.size)
