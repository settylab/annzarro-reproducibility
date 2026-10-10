#!/usr/bin/env python
"""Annotated screenshots from YAML sidecars: boxes, arrows, numbered callouts, caption.

A sidecar sits next to its raw screenshot, same stem, suffix .annot.yaml:
    notes/comparison/screens/isee/01_gene_Mpo_recolours_two_panels.jpg
    notes/comparison/screens/isee/01_gene_Mpo_recolours_two_panels.annot.yaml

Sidecar format (version 1). Coordinates are pixels of the raw image, origin top
left; `source` says where they came from (dom = element bounding boxes recorded
by the driver script at capture time, see record(); manual = read off the
image, allowed only for shots taken before sidecars existed).

    version: 1
    image: 01_gene_Mpo_recolours_two_panels.jpg
    tool: isee                       # evidence/matrix/tools/<tool>.yaml
    software: iSEE 2.18.0 (Bioc 3.20)
    data: bm_demo_sce.rds (8,090 cells)
    url: http://127.0.0.1:8902       # what the browser showed
    captured: 2026-10-03             # date of the screenshot
    by: comparison-auditor
    driver: notes/comparison/demos/isee/focus_check.py
    source: dom | manual
    note: optional; where the capture differs from the audited setup (another variant, platform or data)
    image_sha256: <hex>              # manual sidecars: the image the boxes were read off; check fails if it changes
    proves:                          # the matrix cells this shot is evidence for
      - column: cells                # column id from evidence/matrix/columns.yaml
        row: cellxgene-annotate      # optional: one figure row of a split tool (default: every row of `tool`)
        mark: N
        caption: >-
          One line saying what the shot proves, e.g. "Color by offers no
          pairwise (colPairs) option".
    callouts:
      - n: 1                         # number drawn in a disc at the box corner
        box: [x, y, w, h]
        label: short text listed under the image
      - n: 2
        arrow: [[x0, y0], [x1, y1]]  # optional, alone or with a box
        label: ...

Rendering: every callout gets a box (and/or arrow) and a numbered disc; under
the image a strip carries the caption(s) and the numbered labels, then a
provenance line (software, data, captured, driver). The raw image is never
modified.

Usage:
  annotate.py render <sidecar.annot.yaml>... [--out DIR]   # default: evidence/_build/annotated
  annotate.py check  <sidecar.annot.yaml>...              # schema and bounds, exit 1 on error

From a Playwright driver (coordinates from the DOM, never by hand):
  from evidence.tools.annotate import record
  page.screenshot(path=shot)
  record(page, shot, tool="isee", proves=[...], callouts=[(1, "#colour-by-radio", "Color by options")])
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "evidence/_build/annotated"
MARKS = {"Y", "P", "N", "?"}
REQUIRED = ["version", "image", "tool", "software", "captured", "by", "source", "proves", "callouts"]
COLOR = (214, 39, 40)          # callout red: boxes, arrows, discs
INK = (29, 39, 51)
MUTED = (95, 105, 117)


def columns():
    doc = yaml.safe_load((REPO / "evidence/matrix/columns.yaml").read_text())
    return {c["id"] for c in doc["columns"]} | set(doc.get("retired_columns") or {})


def font(size, bold=False):
    names = (["Arial Bold.ttf", "DejaVuSans-Bold.ttf"] if bold else ["Arial.ttf", "DejaVuSans.ttf"])
    for d in ["/System/Library/Fonts/Supplemental", "/Library/Fonts", "/usr/share/fonts/truetype/dejavu"]:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def load(sidecar):
    sidecar = Path(sidecar)
    meta = yaml.safe_load(sidecar.read_text())
    return sidecar, meta, sidecar.parent / meta["image"]


def check(sidecar):
    sidecar, m, img = load(sidecar)
    err = [f"missing field '{k}'" for k in REQUIRED if k not in m]
    if not img.exists():
        return err + [f"image not found: {img}"]
    W, H = Image.open(img).size
    if m.get("image_sha256") and m["image_sha256"] != hashlib.sha256(img.read_bytes()).hexdigest():
        err.append("image changed since the boxes were drawn (image_sha256 mismatch): re-annotate")
    cols = columns()
    for p in m.get("proves") or []:
        if p.get("column") not in cols:
            err.append(f"unknown column {p.get('column')!r}")
        if p.get("mark") not in MARKS:
            err.append(f"bad mark {p.get('mark')!r}")
        if p.get("row") and not (REPO / "evidence/matrix/tools" / f'{p["row"]}.yaml').exists():
            err.append(f"unknown row {p['row']!r}")
        if not p.get("caption"):
            err.append(f"no caption for {p.get('column')}")
    if m.get("source") not in ("dom", "manual"):
        err.append("source must be dom or manual")
    seen = set()
    for c in m.get("callouts") or []:
        if c.get("n") in seen:
            err.append(f"callout {c.get('n')} twice")
        seen.add(c.get("n"))
        if "box" not in c and "arrow" not in c:
            err.append(f"callout {c.get('n')}: needs box or arrow")
        if "box" in c:
            x, y, w, h = c["box"]
            if not (0 <= x and 0 <= y and w > 0 and h > 0 and x + w <= W and y + h <= H):
                err.append(f"callout {c.get('n')}: box {c['box']} outside {W}x{H}")
        for pt in c.get("arrow") or []:
            if not (0 <= pt[0] <= W and 0 <= pt[1] <= H):
                err.append(f"callout {c.get('n')}: arrow point {pt} outside {W}x{H}")
        if not c.get("label"):
            err.append(f"callout {c.get('n')}: no label")
    return err


SOURCES = REPO / "notes/comparison/screens/SOURCES.yaml"
_sources = None


def credit_line(img):
    """Per-image credit for third-party screenshots (user decision P8, 2026-10-04): software,
    its licence, and the dataset shown with its licence, from notes/comparison/screens/SOURCES.yaml."""
    global _sources
    if _sources is None:
        _sources = {}
        if SOURCES.exists():
            try:
                doc = yaml.safe_load(SOURCES.read_text()) or {}
            except yaml.YAMLError as err:
                print(f"warning: {SOURCES.relative_to(REPO)} is not valid YAML, no credit lines: {err}", file=sys.stderr)
                doc = {}
            for e in doc.get("images") or []:
                _sources[e["image"]] = e
    try:
        key = Path(img).resolve().relative_to(SOURCES.parent.resolve()).as_posix()
    except ValueError:
        return None
    e = _sources.get(key)
    if not e:
        return None
    return (f'Credit: screenshot of {e.get("software")} ({e.get("software_licence")}), shown as scholarly comparison; '
            f'data: {e.get("dataset")} ({e.get("dataset_licence")}).')


def disc(d, x, y, n, f):
    r = 15
    d.ellipse([x - r, y - r, x + r, y + r], fill=COLOR, outline="white", width=2)
    d.text((x, y), str(n), fill="white", font=f, anchor="mm")


def arrow(d, p0, p1, width=4):
    import math
    d.line([tuple(p0), tuple(p1)], fill=COLOR, width=width)
    a = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    L = 18
    left = (p1[0] - L * math.cos(a - 0.45), p1[1] - L * math.sin(a - 0.45))
    right = (p1[0] - L * math.cos(a + 0.45), p1[1] - L * math.sin(a + 0.45))
    d.polygon([tuple(p1), left, right], fill=COLOR)


def render(sidecar, out=OUT):
    sidecar, m, img = load(sidecar)
    im = Image.open(img).convert("RGB")
    W, H = im.size
    scale = max(1.0, W / 1400)
    f_n, f_cap, f_lab, f_meta = font(int(17 * scale), True), font(int(19 * scale), True), font(int(16 * scale)), font(int(13 * scale))
    d = ImageDraw.Draw(im)
    for c in m["callouts"]:
        if "box" in c:
            x, y, w, h = c["box"]
            d.rectangle([x, y, x + w, y + h], outline=COLOR, width=int(4 * scale))
            disc(d, min(x + w, W - 18), max(y, 18), c["n"], f_n)
        if "arrow" in c:
            arrow(d, *c["arrow"], width=int(4 * scale))
            if "box" not in c:
                disc(d, *c["arrow"][0], c["n"], f_n)

    # caption strip: wrapped by measured width, so bold text cannot run off the right edge
    maxw = W - 32 * scale

    def fit(text, f):
        out, cur = [], ""
        for word in text.split():
            nxt = f"{cur} {word}" if cur else word
            if cur and f.getlength(nxt) > maxw:
                out.append(cur)
                cur = word
            else:
                cur = nxt
        return out + ([cur] if cur else [])

    lines = []
    for p in m["proves"]:
        lines += [("cap", t) for t in fit(f'{p["column"]} = {p["mark"]}: {p["caption"]}', f_cap)]
    for c in m["callouts"]:
        lines += [("lab", t) for t in fit(f'({c["n"]}) {c["label"]}', f_lab)]
    prov = (f'{m["software"]}' + (f' · {m["data"]}' if m.get("data") else "") + f' · captured {m["captured"]} by {m["by"]}'
            + (f' · {m["driver"]}' if m.get("driver") else "") + f' · coordinates: {m["source"]}'
            + (f' · NOTE: {m["note"]}' if m.get("note") else ""))
    lines += [("meta", t) for t in fit(prov, f_meta)]
    credit = credit_line(img)
    if credit:
        lines += [("meta", t) for t in fit(credit, f_meta)]
    lh = {"cap": 28 * scale, "lab": 24 * scale, "meta": 20 * scale}
    strip = int(sum(lh[k] for k, _ in lines) + 30 * scale)
    canvas = Image.new("RGB", (W, H + strip), "white")
    canvas.paste(im, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.line([(0, H), (W, H)], fill=COLOR, width=int(3 * scale))
    y = H + 14 * scale
    for kind, t in lines:
        d.text((16 * scale, y), t, fill={"cap": INK, "lab": INK, "meta": MUTED}[kind],
               font={"cap": f_cap, "lab": f_lab, "meta": f_meta}[kind])
        y += lh[kind]
    rel = img.resolve().relative_to(REPO)
    dst = out / rel.parent / (img.stem + ".annotated.png")
    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst, optimize=True)
    return dst


def record(page, shot, *, tool, proves, callouts, software, by, driver, data=None, url=None, pad=4):
    """Write the sidecar for a screenshot just taken by a Playwright `page`.

    callouts: [(n, css_selector, label)] -> boxes from element.bounding_box(),
    scaled by devicePixelRatio, padded by `pad` px, clipped to the image.
    """
    shot = Path(shot)
    dpr = page.evaluate("window.devicePixelRatio") or 1
    W, H = Image.open(shot).size
    out = []
    for n, sel, label in callouts:
        bb = page.locator(sel).first.bounding_box()
        if bb is None:
            raise RuntimeError(f"callout {n}: selector {sel!r} not visible")
        x, y = max(0, (bb["x"] - pad) * dpr), max(0, (bb["y"] - pad) * dpr)
        w, h = min(W - x, (bb["width"] + 2 * pad) * dpr), min(H - y, (bb["height"] + 2 * pad) * dpr)
        out.append({"n": n, "box": [round(x), round(y), round(w), round(h)], "label": label, "selector": sel})
    meta = {"version": 1, "image": shot.name, "tool": tool, "software": software, "data": data,
            "url": url or page.url, "captured": date.today().isoformat(), "by": by, "driver": driver,
            "source": "dom", "proves": proves, "callouts": out}
    side = shot.with_name(shot.stem + ".annot.yaml")
    side.write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=100))
    return side


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["render", "check"])
    ap.add_argument("sidecars", nargs="+")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    bad = 0
    for s in a.sidecars:
        err = check(s)
        for e in err:
            print(f"{s}: {e}", file=sys.stderr)
        bad += bool(err)
        if a.cmd == "render" and not err:
            out = render(s, a.out)
            print(out.relative_to(REPO) if out.is_relative_to(REPO) else out)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
