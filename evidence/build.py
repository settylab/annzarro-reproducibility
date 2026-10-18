#!/usr/bin/env python
"""Build the evidence site's Markdown from the repository's data and notes.

Sources (never edited here):
  evidence/matrix/columns.yaml, evidence/matrix/tools/*.yaml   the matrix and its evidence
  evidence/pages/                                               hand-written pages
  notes/comparison/<tool>.md                                    audit notes, included per tool
  benchmark/tool_ceiling/{README.md,ceilings.csv,results.csv,overlaps.csv,ceiling_curve.png}

Output: evidence/_build/docs (Markdown for MkDocs) and, with --site, evidence/_build/site.
Every repository file a page links to is copied next to the pages, so the built
site works offline and from file://.

Usage:
  python evidence/build.py            # Markdown only
  python evidence/build.py --site     # plus mkdocs build (evidence/requirements.txt; see evidence/HOSTING.md)
  python evidence/build.py --check    # fail if the figure, the YAML and the built matrix disagree
"""
from __future__ import annotations

import argparse
import ast
import csv
import fcntl
import html
import importlib.util
import re
import shutil
import tempfile
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import refs  # noqa: E402
import claim_targets  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
BUILD = HERE / "_build"
DOCS = BUILD / "docs"
GITHUB = "https://github.com/settylab/annzarro-reproducibility"
INTERNAL_NAME = re.compile(r"gizmo[a-z]?\d+|fhcrc|fredhutch", re.I)   # never copied into the site
# Superseded or out-of-scope records: kept in git, never copied, rendered or linked by the site
# (operator 2026-10-06: the site shows only what the paper uses, on the cited release).
OFF_SITE = re.compile(r"(^|/)([A-Z_]*HISTORY|OUT_OF_SCOPE)\.md$|_(history|superseded|out_of_scope)\.csv$|^benchmark/hpc/results/|^notes/APPROVALS\.md$")


def superseded_files():
    """File globs evidence/superseded.yaml marks superseded as whole files (table-row entries excluded)."""
    reg = yaml.safe_load((HERE / "superseded.yaml").read_text())
    return [e["file"] for e in reg.get("superseded") or [] if "file" in e and "where" not in e]


def off_site(repo_path):
    """A superseded or out-of-scope record: kept in git, never copied, rendered or linked by the site."""
    import fnmatch
    return bool(OFF_SITE.search(repo_path)) or any(fnmatch.fnmatch(repo_path, g) for g in superseded_files())
MAX_COPY = 5 * 2**20            # larger linked files are linked on GitHub only

MARK_TEXT = {"Y": "documented", "P": "partial, or only by writing code", "N": "searched, not found",
             "?": "not verified"}
CEILING_TOOL = {"annzarro": [("annzarro", "default")], "cellxgene": [("cellxgene", "default"), ("cellxgene", "backed")],
                "vitessce": [("vitessce", "default")], "cirrocumulus": [("cirrocumulus", "default"), ("cirrocumulus", "prepared")],
                "isee": [("isee", "default")], "ucsc-cell-browser": [("ucsc", "default")],
                "shinycell": [("shinycell", "default")],
                "scanpy-seurat": [("scanpy", "default"), ("scanpy", "lazy_h5ad"), ("seurat", "default")],
                "manivault": [("manivault", "default")], "loupe": [("loupe", "default")]}


# --------------------------------------------------------------------------- provenance
def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True).stdout.strip()


HEAD = git("rev-parse", "--short", "HEAD")
HOSTED = False                  # --hosted: no repo/ mirror, WebP images, GitHub links at the full HEAD sha
RAW_SHOT_DIRS = ("notes/comparison/screens/", "evidence/screens/")   # hosted: linked, the annotated copy is shown
IMAGE_EXT = (".png", ".jpg", ".jpeg")
_clean_cache = {}


def on_github(repo_path):
    """True when GitHub serves this path at HEAD exactly as it is here (tracked, no local changes)."""
    if repo_path not in _clean_cache:
        tracked = bool(git("ls-files", "--", repo_path))
        dirty = bool(git("status", "--porcelain", "--", repo_path))
        _clean_cache[repo_path] = tracked and not dirty
    return _clean_cache[repo_path]


def provenance(path):
    """Last commit touching path, and whether the working tree differs from it."""
    rel = Path(path).as_posix()
    sha = git("log", "-1", "--format=%h %cd", "--date=short", "--", rel)
    dirty = bool(git("status", "--porcelain", "--", rel))
    return sha or "untracked", dirty


def prov_badge(path):
    sha, dirty = provenance(path)
    flag = ' <span class="ev-dirty" title="the working tree differs from this commit">uncommitted changes</span>' if dirty else ""
    return f"`{path}` at `{sha}`{flag}"


# --------------------------------------------------------------------------- files and links
copied: set[str] = set()


_tracked: set[str] = set()


def tracked(repo_path):
    """True when git tracks the file: the site shows committed files only, so a clean clone
    builds the same site as a working tree with local, ignored or untracked files."""
    if not _tracked:
        _tracked.update(git("ls-files", "-z").split("\0"))
    return repo_path in _tracked


# Files whose full text carries earlier AnnZarro builds' numbers: not mirrored (the page links them on GitHub).
NO_MIRROR = {"benchmark/tool_ceiling/summarize.py"}
# Tables mirrored without the rows of AnnZarro builds other than the cited release (rule: no earlier AnnZarro
# data on the site): path -> (how a row names its AnnZarro variant). The files stay whole in git.
CURRENT_ROWS_ONLY = {"benchmark/tool_ceiling/results.csv", "benchmark/tool_ceiling/overlaps.csv"}


def current_annzarro_variants():
    """AnnZarro variants of results.csv that evidence/superseded.yaml lists as current (the cited release)."""
    reg = yaml.safe_load((HERE / "superseded.yaml").read_text())
    out = set()
    for e in reg.get("current") or []:
        w = e.get("where") or {}
        if e.get("csv") == "benchmark/tool_ceiling/results.csv" and w.get("variant"):
            out |= set(w["variant"] if isinstance(w["variant"], list) else [w["variant"]])
    return out


def write_current_rows(src, dst):
    """Copy a results/overlaps table, leaving out the rows of AnnZarro builds other than the current release."""
    import csv as _csv
    keep = current_annzarro_variants()
    with open(src, newline="") as f:
        rows = list(_csv.reader(f))
    def current(row):
        m = re.match(r"annzarro_(.+?)_(?:run|syn|convert|prep)", row[0]) if row else None
        if not m:
            return True
        return m.group(1) in keep
    with open(dst, "w", newline="") as f:
        _csv.writer(f).writerows([rows[0]] + [r for r in rows[1:] if current(r)])


def site_file(repo_path):
    """Copy a repository file into the site; return its site path, or None if missing or too big.

    An image over MAX_COPY is copied downscaled (the page says so where it matters; the
    full file stays one click away on GitHub)."""
    src = REPO / repo_path
    if not src.is_file() or INTERNAL_NAME.search(repo_path) or off_site(repo_path) or not tracked(repo_path) \
            or repo_path in NO_MIRROR:
        return None
    if HOSTED:
        image = src.suffix.lower() in IMAGE_EXT
        if image and repo_path.startswith(RAW_SHOT_DIRS):
            return None             # raw screenshots: the page shows the annotated copy and links the raw one
        if not image and on_github(repo_path):
            return None             # text and data: one click away on GitHub at the build's commit
    big = src.stat().st_size > MAX_COPY
    if big and src.suffix.lower() not in (".png", ".jpg", ".jpeg"):
        return None
    dst = DOCS / "repo" / repo_path
    if repo_path not in copied:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if big:
            from PIL import Image
            im = Image.open(src)
            im.thumbnail((2400, 2400))
            im.save(dst, optimize=True)
        elif repo_path in CURRENT_ROWS_ONLY:
            write_current_rows(src, dst)
        else:
            shutil.copy2(src, dst)
        copied.add(repo_path)
    return "repo/" + repo_path


def rel(from_page, to_path):
    """Relative link from one site page (e.g. tools/isee.md) to a site path."""
    depth = from_page.count("/")
    return "../" * depth + to_path


def link_repo(page, repo_path, label=None, anchor=""):
    label = label or repo_path
    if INTERNAL_NAME.search(repo_path):
        return f'{html.escape(label)} <small>(internal file, not published)</small>'
    if off_site(repo_path):
        return f'{html.escape(label)} <small>(superseded or out of scope; in git, not on this site)</small>'
    local = site_file(repo_path)
    gh = f"{GITHUB}/blob/{HEAD}/{repo_path}"
    if local:
        return f'<a href="{rel(page, local)}{anchor}">{html.escape(label)}</a>'
    if (REPO / repo_path).is_dir():
        gh = f"{GITHUB}/tree/{HEAD}/{repo_path}"
    return f'<a href="{gh}{anchor}">{html.escape(label)}</a>'


def rewrite_note_links(text, note_path, page, tool_pages):
    """Relative links inside an included note: tool notes -> tool pages, files -> copied files."""
    base = (REPO / note_path).parent

    def sub(m):
        label, url = m.group(1), m.group(2)
        if re.match(r"[a-z]+:", url) or url.startswith("#"):
            return m.group(0)
        target, _, anchor = url.partition("#")
        rp = (base / target).resolve()
        try:
            rp = rp.relative_to(REPO).as_posix()
        except ValueError:
            return m.group(0)
        if rp in tool_pages:
            return f"[{label}]({rel(page, tool_pages[rp])}{'#' + anchor if anchor else ''})"
        if off_site(rp):
            return f"{label} (in git, not on this site)"
        local = site_file(rp)
        if local:
            return f"[{label}]({rel(page, local)}{'#' + anchor if anchor else ''})"
        kind = "tree" if (REPO / rp).is_dir() else "blob"
        return f"[{label}]({GITHUB}/{kind}/{HEAD}/{rp})"

    return re.sub(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)", sub, text)


# --------------------------------------------------------------------------- data
def load():
    cols = yaml.safe_load((HERE / "matrix/columns.yaml").read_text())["columns"]
    tools = [yaml.safe_load(p.read_text()) for p in sorted((HERE / "matrix/tools").glob("*.yaml"))]
    tools = [t for t in tools if not t.get("out_of_scope")]     # removed from the paper: kept in git, not on the site
    for t in tools:                     # fill docs/paper `checked` and `archive` from evidence/matrix/archive.yaml
        for cell in list(t["cells"].values()) + list((t.get("proposed_columns") or {}).values()):
            for e in cell.get("evidence") or []:
                refs.enrich(e)
    tools.sort(key=lambda t: (t["figure"] is None, (t["figure"] or {}).get("row", 0), t["name"]))
    return cols, tools


def figure_tools():
    """Fig. 1c rows as drawn (scale reading applied): evidence/tools/figmarks.py."""
    import figmarks
    return figmarks.figure_tools()


def check_drift(cols, tools):
    """The marks in the YAML must be the marks the figure draws."""
    ids = [c["id"] for c in cols]
    import figmarks
    fig = {r["name"]: r["marks"] for r in figmarks.figure_model()["rows"]}      # as drawn
    errors = []
    for t in tools:
        if not t["figure"]:
            continue
        want = fig.get(t["figure"]["label"])
        have = "".join(t["cells"].get(c, {}).get("mark", "?") for c in ids)
        if want is None:
            errors.append(f"{t['name']}: no row '{t['figure']['label']}' in fig_comparison.py")
        elif len(want) != len(ids):
            errors.append(f"{t['name']}: the figure has {len(want)} columns, columns.yaml {len(ids)}")
        elif want != have:
            diff = [f"{c} fig={w} yaml={h}" for c, w, h in zip(ids, want, have) if w != h]
            errors.append(f"{t['name']}: " + ", ".join(diff))
    for name in fig:
        if name not in {t["figure"]["label"] for t in tools if t["figure"]}:
            errors.append(f"{name}: in fig_comparison.py, no YAML")
    return errors


def ceilings():
    p = REPO / "benchmark/tool_ceiling/ceilings.csv"
    return {(r["tool"], r["variant"]): r for r in csv.DictReader(open(p))} if p.exists() else {}


def fmt_n(n):
    n = float(n)
    if n >= 1e9:
        return f"{n / 1e9:.3g}B"
    if n >= 1e6:
        return f"{n / 1e6:.3g}M"
    if n >= 1e3:
        return f"{n / 1e3:.3g}k"
    return f"{n:.0f}"



# --------------------------------------------------------------------------- visual proof and coverage
sys.path.insert(0, str(REPO))
from evidence.tools import annotate  # noqa: E402

SIDECAR_DIRS = [HERE / "screens", REPO / "notes/comparison/screens"]   # evidence/annotations retired: sidecars sit next to their shots
REF_KINDS = ("docs", "paper", "code")


def sidecars():
    """Every sidecar, grouped by the raw image it annotates: {repo path of image: [sidecar paths]}."""
    by_image = {}
    for d in SIDECAR_DIRS:
        for side in sorted(d.rglob("*.annot.yaml")):
            meta = yaml.safe_load(side.read_text())
            raw = (side.parent / meta["image"]).resolve().relative_to(REPO).as_posix()
            by_image.setdefault(raw, []).append(side)
    return by_image


def duplicate_sidecars():
    """One image, one sidecar. Two sidecars on one image would count a proof twice, and a manual one
    beside a DOM one carries boxes from before the re-shoot: delete the manual one."""
    errs = []
    for raw, sides in sidecars().items():
        if len(sides) > 1:
            srcs = [f"{s.relative_to(REPO)} ({yaml.safe_load(s.read_text()).get('source')})" for s in sides]
            errs.append(f"{raw}: {len(sides)} sidecars: " + ", ".join(srcs))
    return errs


def load_annotations():
    """Render every sidecar into the site; return {(tool, column): [proof, ...]}.

    Where an image has several sidecars (an error, see duplicate_sidecars), only a DOM one is used."""
    out, errors = {}, list(duplicate_sidecars())
    gone = {y["id"] for y in (yaml.safe_load(p.read_text()) for p in (HERE / "matrix/tools").glob("*.yaml")) if y.get("out_of_scope")}
    for raw, sides in sidecars().items():
        metas = [(s, yaml.safe_load(s.read_text())) for s in sides]
        if all(m.get("tool") in gone for _, m in metas):
            continue                    # a tool removed from the paper: its proofs stay in git, not on the site
        dom = [x for x in metas if x[1].get("source") == "dom"]
        for side, meta in (dom[:1] or metas[:1]):
            err = annotate.check(side)
            if err:
                errors += [f"{side.relative_to(REPO)}: {e}" for e in err]
                continue
            png = annotate.render(side, DOCS / "annotated")
            for p in meta["proves"]:
                # a proof may target one figure row of a split tool (proves[].row, e.g. cellxgene-annotate)
                out.setdefault((p.get("row") or meta["tool"], p["column"]), []).append({
                    "png": png.relative_to(DOCS).as_posix(), "raw": raw, "mark": p["mark"],
                    "caption": p["caption"], "sidecar": side.relative_to(REPO).as_posix(),
                    "source": meta["source"], "captured": meta["captured"], "software": meta["software"]})
    return out, errors


def coverage(tid, cid, cell, ann):
    """Per evidence kind: 'ok', 'raw' (visual: unannotated screenshot only), 'na: reason', or ''."""
    ev = cell.get("evidence") or []
    na = cell.get("na") or {}
    cov = {}
    proofs = ann.get((tid, cid), [])
    if proofs:
        cov["visual"] = "ok"
    elif "visual" in na:
        cov["visual"] = "na: " + na["visual"]
    elif any(e["kind"] == "screenshot" for e in ev):
        cov["visual"] = "raw"
    else:
        cov["visual"] = ""
    for k in REF_KINDS:
        n = sum(1 for e in ev if e["kind"] == k)
        cov[k] = "ok" if n else ("na: " + na[k] if k in na else "")
    return cov


def complete(cov):
    """A mark is complete with visual proof (or a stated reason why none can exist) and at least one reference."""
    return cov["visual"].startswith(("ok", "na")) and any(cov[k] == "ok" for k in REF_KINDS)


def ref_warnings(cell):
    w = []
    mark = cell.get("proposed") or cell.get("mark")
    for e in cell.get("evidence") or []:
        ind = e.get("indicates")
        if ind and mark and mark not in (ind if isinstance(ind, (list, tuple)) else [ind]):
            w.append(f'{e["kind"]} supports {ind}, mark is {mark}: {e.get("label") or e.get("url")}')
    for e in cell.get("evidence") or []:
        if e["kind"] == "docs" and not e.get("archive"):
            w.append(f'docs without archive snapshot: {e["url"]}')
        if e["kind"] == "docs" and not e.get("checked"):
            w.append(f'docs without date checked: {e["url"]}')
        if e["kind"] == "paper" and not e.get("where"):
            w.append(f'paper without section/figure: {e["url"]}')
        if e["kind"] == "code" and not e.get("lines"):
            w.append(f'code without line range: {e.get("url")}')
    return w


def cov_chips(cov):
    letters = {"visual": "V", "docs": "D", "paper": "P", "code": "C"}
    out = []
    for k, L in letters.items():
        st = cov[k]
        cls = "ok" if st == "ok" else "na" if st.startswith("na") else "raw" if st == "raw" else "miss"
        tip = {"ok": f"{k}: present", "raw": "visual: screenshot not annotated", "miss": f"{k}: missing"}.get(cls, f"{k}: {st}")
        out.append(f'<span class="ev-chip ev-chip-{cls}" title="{html.escape(tip)}">{L}</span>')
    return '<span class="ev-chips">' + "".join(out) + "</span>"


def proof_block(page, proofs):
    out = ['<div class="ev-proofs">']
    for p in proofs:
        out.append(f'<figure><a href="{rel(page, p["png"])}"><img src="{rel(page, p["png"])}" loading="lazy" alt="{html.escape(p["caption"])}"></a>'
                   f'<figcaption><b>{html.escape(p["caption"])}</b> ({html.escape(p["software"])}, captured {p["captured"]}; '
                   f'{link_repo(page, p["raw"], "raw")}, {link_repo(page, p["sidecar"], "annotation data")})</figcaption></figure>')
    out.append("</div>\n")
    return "\n".join(out)


def coverage_page(cols, tools, ann, sidecar_errors):
    page = "coverage.md"
    rows, gaps, warns = [], [], []
    total = done = 0
    kinds = Counter()
    for t in tools:
        cells = []
        for c in cols:
            cell = t["cells"].get(c["id"])
            if not cell:
                cells.append("")
                continue
            cov = coverage(t["id"], c["id"], cell, ann)
            total += 1
            ok = complete(cov)
            done += ok
            for k, v in cov.items():
                kinds[k, "ok" if v == "ok" else "na" if v.startswith("na") else "raw" if v == "raw" else "miss"] += 1
            if not ok:
                gaps.append((t["name"], c["id"], cell.get("mark", cell.get("proposed")), cov))
            warns += [(t["name"], c["id"], w) for w in ref_warnings(cell)]
            cells.append(f'<a href="tools/{t["id"]}.md#col-{c["id"]}">{cov_chips(cov)}</a>')
        rows.append(f'<tr><th class="ev-tool"><a href="tools/{t["id"]}.md">{html.escape(t["name"])}</a></th>'
                    + "".join(f'<td class="ev-cov">{x}</td>' for x in cells) + "</tr>")
    head = ('<tr><th class="ev-tool">Tool</th>' + "".join(
        f'<th class="ev-col"><span>{html.escape(c["label"].replace(chr(10), " "))}</span></th>' for c in cols) + "</tr>")
    kind_rows = [(k, kinds[k, "ok"], kinds[k, "raw"], kinds[k, "na"], kinds[k, "miss"]) for k in ("visual",) + REF_KINDS]
    gap_lines = "\n".join(f"| {n} | {c} | {m} | " + ", ".join(k for k, v in cov.items() if not (v == "ok" or v.startswith("na"))) + " |"
                          for n, c, m, cov in gaps)
    warn_lines = "\n".join(f"| {n} | {c} | {html.escape(w)} |" for n, c, w in warns[:400])
    side_err = "\n".join(f"- `{e}`" for e in sidecar_errors) or "none"
    body = f"""---
hide: [toc]
---
{WIDE_PAGE_STYLE}
# Evidence coverage

Every mark needs **visual proof** (an annotated screenshot for this tool and
column; for an N, the menu or list where the feature would be, shown without it) **and at
least one reference** (documentation, paper or code). Where one kind cannot exist, the
mark's record says why it is not applicable (for example, no paper for a product without one).

**{done} of {total}** marks are complete.

Chips: <span class="ev-chip ev-chip-ok">V</span> visual proof, annotated;
<span class="ev-chip ev-chip-raw">V</span> screenshot exists but is not annotated;
<span class="ev-chip ev-chip-na">D</span> not applicable, reason given;
<span class="ev-chip ev-chip-miss">C</span> missing. D documentation, P paper, C code.

| kind | present | raw shot only | not applicable | missing |
|---|---|---|---|---|
""" + "\n".join(f"| {k} | {a} | {b if k == 'visual' else '–'} | {c} | {d} |" for k, a, b, c, d in kind_rows) + f"""

<div class="ev-matrix-wrap"><table class="ev-matrix ev-covtable"><thead>{head}</thead><tbody>
{chr(10).join(rows)}
</tbody></table></div>

## Incomplete marks ({len(gaps)})

| tool | column | mark | lacking |
|---|---|---|---|
{gap_lines}

## Reference quality warnings ({len(warns)})

Documentation links need the date checked and an archive.org snapshot; papers need the
section or figure; code needs a line range.

| tool | column | warning |
|---|---|---|
{warn_lines}

## Sidecar errors

{side_err}
"""
    (DOCS / page).write_text(body)
    return done, total


# --------------------------------------------------------------------------- matrix page
def glyph(v, proposed=None):
    cls = {"Y": "y", "P": "p", "N": "n", "?": "q"}.get(v, "q")
    out = f'<span class="ev-mark ev-{cls}" aria-label="{MARK_TEXT.get(v, v)}">{v}</span>'
    if proposed:
        pc = {"Y": "y", "P": "p", "N": "n", "?": "q"}[proposed]
        out += f'<span class="ev-prop" title="proposed: {proposed}">&rarr;<span class="ev-mark ev-{pc}">{proposed}</span></span>'
    return out


STRIP_GLYPH = {"client": "circle", "server": "square", "input": "triangle", "documented": "diamond"}


def _strip_glyph(kind, X, Y, r=4.2):
    """One strip glyph as SVG, the shapes fig_comparison.draw_strip() has used (filled; documented is open).
    Since 8377c36 the figure draws every measured point as the circle; strip_svg picks the glyph from
    the figure's legend, so the other shapes are drawn only if the legend shows them again."""
    fill = "ev-sg-fill"
    if kind == "client":
        return f'<circle class="{fill}" cx="{X:.1f}" cy="{Y:.1f}" r="{r}"/>'
    if kind == "server":
        return f'<rect class="{fill}" x="{X - r:.1f}" y="{Y - r:.1f}" width="{2 * r:.1f}" height="{2 * r:.1f}"/>'
    if kind == "input":
        return f'<polygon class="{fill}" points="{X:.1f},{Y - r - 1:.1f} {X + r + 1:.1f},{Y + r:.1f} {X - r - 1:.1f},{Y + r:.1f}"/>'
    if kind == "documented":
        return (f'<polygon class="ev-sg-open" points="{X:.1f},{Y - r:.1f} {X + r:.1f},{Y:.1f} '
                f'{X:.1f},{Y + r:.1f} {X - r:.1f},{Y:.1f}"/>')
    if kind == "ring":
        return f'<circle class="ev-sg-ring" cx="{X:.1f}" cy="{Y:.1f}" r="{r * 0.8:.1f}"/>'
    if kind == "arrow":
        return (f'<line class="ev-sg-line" x1="{X - 6:.1f}" x2="{X + 4:.1f}" y1="{Y:.1f}" y2="{Y:.1f}"/>'
                f'<polygon class="ev-sg-ink" points="{X + 8:.1f},{Y:.1f} {X + 3:.1f},{Y - 3:.1f} {X + 3:.1f},{Y + 3:.1f}"/>')
    return ""


def strip_svg(strip, lo, hi, legend, w=210, h=30):
    """A row's cells strip as fig_comparison draws it: measured glyphs above, documented below."""
    import math
    import figmarks
    if strip is None:
        return ""
    shown = {l["glyph"] for l in legend}
    as_drawn = next((g for g in ("client", "server", "input") if g in shown), "client")   # the legend's measured glyph
    pad = 10
    X = lambda n: pad + (math.log10(n) - lo) / (hi - lo) * (w - 2 * pad)          # noqa: E731
    out = [f'<svg class="ev-strip" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
           f'aria-label="{html.escape(figmarks.strip_text(strip, legend) or "documented only")}">'
           f'<title>{html.escape(figmarks.strip_text(strip, legend) or "documented only")}</title>']
    for e in range(lo, hi + 1):
        out.append(f'<line class="ev-sg-grid" x1="{X(10 ** e):.1f}" x2="{X(10 ** e):.1f}" y1="0" y2="{h}"/>')
    top, bot = h * 0.36, h * 0.74
    measured = [p for p in strip["pts"] if p[0] != "documented"]
    if strip.get("reach"):
        start = max((n for _, n, _, _ in measured), default=None)
        if start is not None:
            out.append(f'<line class="ev-sg-acc" x1="{X(start):.1f}" x2="{X(strip["reach"]):.1f}" y1="{top:.1f}" y2="{top:.1f}"/>')
        out.append(_strip_glyph("ring", X(strip["reach"]), top))
    for k, n, lower, lab in strip["pts"]:
        y = bot if k == "documented" else top
        # a kind keeps its own glyph only while the figure's legend shows it; otherwise it is drawn as the
        # legend's measured glyph (since the 2026-10-08 review one circle for all; what stopped the tool
        # stays in the kind and in the hover text, figmarks.strip_text)
        out.append(_strip_glyph(k if k == "documented" or k in shown else as_drawn, X(n), y))
        if lower:
            out.append(_strip_glyph("arrow", X(n) + 9, y))
        if lab:
            out.append(f'<text class="ev-sg-lab" x="{X(n):.1f}" y="{y - 6:.1f}" text-anchor="middle">{html.escape(lab)}</text>')
        if k == "documented" and strip.get("footnote"):
            out.append(f'<text class="ev-sg-lab" x="{X(n) + 6:.1f}" y="{y - 3:.1f}">{html.escape(strip["footnote"])}</text>')
    if not strip["measured_any"]:
        out.append(f'<text class="ev-sg-nm" x="{w - 2}" y="{top + 3:.1f}" text-anchor="end">'
                   f'{html.escape(strip.get("note") or ("hosted only" if strip["hosted"] else "n.m."))}</text>')
    out.append("</svg>")
    return "".join(out)


def legend_glyph(g):
    if g and g.startswith("mark:"):
        return glyph(g[5:])
    if not g:
        return ""
    return (f'<svg class="ev-strip" width="22" height="14" viewBox="0 0 22 14">'
            + (f'<line class="ev-sg-acc" x1="1" x2="9" y1="7" y2="7"/>' if g == "ring" else "")
            + _strip_glyph(g, 12 if g != "arrow" else 8, 7, 4) + "</svg>")


def check_matrix(cols, tools, model):
    """Every element of Fig. 1c that the site's matrix shows must be the figure's own:
    column groups and labels, row names, documented sizes (the YAML's copies), mark footnotes."""
    errs = []
    fig_cols = [(g, c) for g, cs in model["head"]["groups"] for c in cs]
    if len(fig_cols) != len(cols):
        errs.append(f"columns: figure {len(fig_cols)}, columns.yaml {len(cols)}")
    for (g, lab), c in zip(fig_cols, cols):
        if c["label"].strip() != lab.strip():
            errs.append(f"column {c['id']}: label {c['label']!r} != figure {lab!r}")
        if c["group"] != g:
            errs.append(f"column {c['id']}: group {c['group']!r} != figure {g!r}")
    rows = {r["name"]: r for r in model["rows"]}
    ytools = {t["figure"]["label"]: t for t in tools if t["figure"]}
    order = [t["figure"]["label"] for t in tools if t["figure"]]
    if order != [r["name"] for r in model["rows"]]:
        errs.append(f"row order: YAML {order} != figure {[r['name'] for r in model['rows']]}")
    for name, r in rows.items():
        t = ytools.get(name)
        if t is None:
            errs.append(f"{name}: in the figure, no YAML")
            continue
        if (t["figure"].get("largest_documented") or "").strip() != r["documented"].strip():
            errs.append(f"{name}: largest_documented {t['figure'].get('largest_documented')!r} != figure {r['documented']!r}")
    return errs


def matrix_body(cols, tools, model):
    """The matrix page, rendered from the figure model (marks: YAML, checked equal to the figure)."""
    import figmarks
    rows = {r["name"]: r for r in model["rows"]}
    lo, hi = model["head"]["strip_range"] or (5, 9)
    groups = []
    for g, cs in model["head"]["groups"]:
        groups.append([g, len(cs)])
    head_scale = model["head"]["scale_header"]
    strip_color = html.escape(model["head"].get("strip_color") or "#eb6834")   # fig_comparison.STRIP_COLOR
    h = ['<div class="ev-controls">',
         '<label><input type="checkbox" id="ev-show-proposed" checked> show proposed changes</label>',
         '<label><input type="checkbox" id="ev-only-figure"> [[fig:overview]]c rows only</label>',
         "</div>",
         '<div class="ev-legend-fig" style="--ev-strip: {sc}">'.format(sc=strip_color) + "".join(
             f'<span class="ev-key">{legend_glyph(l["glyph"])}{html.escape(l["text"])}</span>' for l in model["legend"]) + "</div>",
         '<div class="ev-matrix-wrap" style="--ev-strip: {sc}"><table class="ev-matrix"><thead>'.format(sc=strip_color),
         '<tr><th></th>' + "".join(f'<th colspan="{n}" class="ev-group">{html.escape(g)}</th>' for g, n in groups)
         + '<th colspan="2" class="ev-group">Cells</th></tr>',
         '<tr><th class="ev-tool">Tool</th>'
         + "".join(f'<th class="ev-col" data-col="{c["id"]}"><a href="columns.md#{c["id"]}" title="{html.escape(c["definition"])}">'
                   f'<span>{html.escape(c["label"].replace(chr(10), " "))}</span></a>'
                   + ('<sup title="definition under decision">*</sup>' if c.get("status") == "proposed" else "") + "</th>"
                   for c in cols)
         + f'<th class="ev-col ev-scalehead"><span>{html.escape(head_scale.replace(chr(10), " "))}</span>'
         + '<div class="ev-axis">' + "".join(f"<span>{html.escape(a)}</span>" for a in model["head"]["axis"]) + "</div></th>"
         + '<th class="ev-col"><span>Largest dataset documented or observed (cells; not a limit)</span></th></tr>',
         "</thead><tbody>"]
    for t in tools:
        fig = t["figure"]
        r = rows.get(fig["label"]) if fig else None
        tr_cls = "ev-fig" if fig else "ev-extra"
        name = html.escape(fig["label"] if fig else t["name"])
        row = [f'<tr class="{tr_cls}"><th class="ev-tool"><a href="tools/{t["id"]}.md">{name}</a>'
               + ('<span class="ev-dagger" title="server-rendered">†</span>' if r and r["dagger"] else "")
               + ("" if fig else ' <small title="not a row of [[fig:overview]]c">(text only)</small>') + "</th>"]
        for k, c in enumerate(cols):
            cell = t["cells"].get(c["id"])
            if not cell:
                row.append('<td class="ev-empty"></td>')
                continue
            mark = cell.get("mark", cell.get("proposed"))
            prop = cell.get("proposed") if "mark" in cell else None
            note = (r or {}).get("notes", {}).get(str(k), "")
            tip = html.escape(f'{c["label"].replace(chr(10), " ")}: {mark}'
                              + (f" (proposed {prop})" if prop else "") + " — " + cell.get("reason", "no reason recorded"))
            cls = "ev-cell" + (" ev-changed" if prop else "")
            row.append(f'<td class="{cls}" data-col="{c["id"]}"><a href="tools/{t["id"]}.md#col-{c["id"]}" title="{tip}">'
                       f'{glyph(mark, prop)}</a>' + (f'<sup class="ev-fn">{html.escape(note)}</sup>' if note else "") + "</td>")
        if r:
            row.append(f'<td class="ev-num ev-stripcell"><a href="measurements/tool-ceiling.md">{strip_svg(r["strip"], lo, hi, model["legend"])}</a>'
                       f'<div class="ev-striptxt">{html.escape(figmarks.strip_text(r["strip"], model["legend"]))}</div></td>')
            row.append(f'<td class="ev-num">{html.escape(r["documented"]).replace(chr(10), " ")}'
                       + (f'<sup class="ev-fn">{html.escape(r["strip"]["footnote"])}</sup>' if r["strip"] and r["strip"].get("footnote") else "")
                       + "</td>")
        else:
            row += ['<td class="ev-num"></td>', '<td class="ev-num"></td>']
        h.append("".join(row) + "</tr>")
    h.append("</tbody></table></div>")
    n_cells = sum(len(t["cells"]) for t in tools)
    n_prop = sum(1 for t in tools for c in t["cells"].values() if "mark" in c and c.get("proposed"))
    prop_text = (f"**{n_prop}** carry an audit proposal that differs from the figure (arrow), awaiting a "
                 "decision." if n_prop else
                 "Every mark is the figure's; no audit proposal is waiting for a decision.")
    n_open = sum(1 for c in cols if c.get("status") == "proposed")
    star_text = (" Columns marked * have a definition under decision; see [Columns](columns.md)." if n_open else "")
    return f"""---
hide: [toc]
---
{WIDE_PAGE_STYLE}
# Feature matrix

<!-- fig1c-model {figmarks.model_hash(model)} -->

The marks of [[fig:overview]]c, with every cell linked to its evidence. Hover a mark for the
one-line reason; click it for the sources, the screenshots and how to repeat the check.
The column headers, the cells strip, the documented sizes, the footnotes and the legend are
drawn from `figures/fig_comparison.py` itself (`evidence/tools/figmodel_dump.py`), and
this page and the figure are checked to be identical.

!!! info "State of this page"
    {n_cells} marked cells. {prop_text}
    Checked against the figure at commit `{HEAD}` on {date.today().isoformat()}.

{chr(10).join(h)}

The cells strip is [[fig:overview]]c's, on the same log axis (100k to 10B): above the line, the largest
number of cells drawn within the 16 GiB client budget, shaped by what stopped the tool; below
it, the largest dataset documented or observed. Hover a strip for it in words; click it for every
run behind it ([Tool ceiling](measurements/tool-ceiling.md)).{star_text}
"""


def matrix_expect(model):
    """Strings the built matrix page must contain, straight from the figure."""
    import figmarks
    out = [model["head"]["scale_header"].replace("\n", " ")] + [l["text"] for l in model["legend"]]
    out += [g for g, _ in model["head"]["groups"]]
    for r in model["rows"]:
        out.append(r["name"])
        out.append(r["documented"].replace("\n", " "))
        if r["strip"]:
            out.append(figmarks.strip_text(r["strip"], model["legend"]))
    return [html.escape(x) for x in out if x]


def matrix_page(cols, tools, ceil, model):
    (DOCS / "matrix.md").write_text(matrix_body(cols, tools, model))


def check_served(model, site=None):
    """The served site's matrix must be the figure's current one (same model, same strings)."""
    import figmarks
    f = (site or BUILD / "site") / "matrix.html"
    if not f.exists():
        return [f"{f}: no built site (run build.py --site)"]
    text = f.read_text()
    m = re.search(r"fig1c-model ([0-9a-f]{16})", text)
    errs = []
    if not m or m.group(1) != figmarks.model_hash(model):
        errs.append(f"served matrix is stale: built from figure model {m.group(1) if m else 'none'}, "
                    f"the figure is now {figmarks.model_hash(model)} (rebuild: build.py --site)")
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
    plain = " ".join(plain.split())
    for s in matrix_expect(model):
        if " ".join(html.unescape(s).split()) not in plain:
            errs.append(f"served matrix lacks {html.unescape(s)[:90]!r}")
    return errs


# --------------------------------------------------------------------------- tool pages
def evidence_item(page, e):
    kind = e["kind"]
    if kind == "code":
        lab = f'{e["repo"]}@{e["commit"][:7]} {e["path"]}' + (f' L{e["lines"]}' if e.get("lines") else "")
        return f'<span class="ev-kind">code</span> <a href="{e["url"]}">{html.escape(lab)}</a>'
    if kind in ("docs", "paper"):
        extra = []
        if e.get("where"):
            extra.append(html.escape(e["where"]))
        if e.get("checked"):
            extra.append(f'checked {e["checked"]}')
        if e.get("archive"):
            extra.append(f'<a href="{e["archive"]}">archived copy</a>')
        tail = f' <small>({"; ".join(extra)})</small>' if extra else ""
        if e.get("quote"):
            tail += f'<br><q class="ev-quote">{html.escape(e["quote"])}</q>'
        if e.get("indicates"):
            tail += f' <span class="ev-indicates" title="what this passage supports">supports {html.escape(str(e["indicates"]))}</span>'
        return f'<span class="ev-kind">{kind}</span> <a href="{e["url"]}">{html.escape(e.get("label") or e["url"])}</a>{tail}'
    path, _, anchor = e["path"].partition("#")
    lab = e.get("label") or Path(path).name
    return f'<span class="ev-kind">{kind}</span> ' + link_repo(page, path, lab, "#" + anchor if anchor else "")


def tool_page(t, cols, tool_pages, ceil, ann):
    page = f"tools/{t['id']}.md"
    out = [f"# {t['name']}", ""]
    fig = t["figure"]
    out.append(f"[[fig:overview]]c row {fig['row']}." if fig else "Not a row of [[fig:overview]]c; named in the manuscript's comparison text.")
    out.append(f" Audit notes: {link_repo(page, t['notes'].split('#')[0])} ({prov_badge(t['notes'].split('#')[0])}).")
    yml = f"evidence/matrix/tools/{t['id']}.yaml"
    out.append(f" Marks: {link_repo(page, yml)}.\n")
    out.append(claim_targets.backs_html(page, "", rel) + "\n")
    meas = [(k, ceil[k]) for k in CEILING_TOOL.get(t["id"], []) if k in ceil]
    if meas:
        out.append("**Measured ceiling** (largest N drawn, client within 8 / 16 / 32 GB; "
                   "[method](../measurements/tool-ceiling.md)): "
                   + "; ".join(f'{k[0]} {k[1]}: {fmt_n(r["max_n_8gb"])} / {fmt_n(r["max_n_16gb"])} / {fmt_n(r["max_n_32gb"])}'
                               for k, r in meas if r["max_n_8gb"]) + ".\n")
    if t["id"] == "ucsc-cell-browser":
        out.append(prep_block(page) + "\n")
    out.append("## Matrix cells\n")
    for c in cols:
        cell = t["cells"].get(c["id"])
        if not cell:
            continue
        mark = cell.get("mark")
        prop = cell.get("proposed")
        cov = coverage(t["id"], c["id"], cell, ann)
        head = (f'<span class="ev-colname">{html.escape(c["label"].replace(chr(10), " "))}</span> '
                + glyph(mark or prop, prop if mark else None) + cov_chips(cov))
        out.append(f'<div class="ev-card" id="col-{c["id"]}" markdown>')
        out.append(claim_targets.backs_html(page, f'col-{c["id"]}', rel))
        out.append(f'<div class="ev-card-head">{head}<a class="ev-anchor" href="#col-{c["id"]}">¶</a></div>\n')
        if prop and mark:
            out.append(f"Figure shows **{mark}**; the audit proposes **{prop}**"
                       + (f" (decision: {c['decision']})" if c.get("decision") else "") + ".\n")
        elif prop:
            out.append(f"Audit mark **{prop}** (tool not in the figure).\n")
        if cell.get("by_reading"):
            out.append("**Depends on the column's reading** (see [Columns](../columns.md)): "
                       + "; ".join(f"reading {k}: **{v}**" for k, v in cell["by_reading"].items()) + ".\n")
        out.append(f"**Reason.** {cell.get('reason', '_none recorded_')}\n")
        if ann.get((t["id"], c["id"])):
            out.append(proof_block(page, ann[(t["id"], c["id"])]))
        elif not complete(cov):
            out.append('<p class="ev-dirty">No annotated visual proof yet.</p>\n')
        if cell.get("detail"):
            out.append('<details class="ev-detail"><summary>Full evidence text</summary>\n')
            out.append(rewrite_note_links(cell["detail"], t["notes"].split("#")[0], page, tool_pages) + "\n")
            out.append("</details>\n")
        ev = cell.get("evidence") or []
        shots = [e for e in ev if e["kind"] == "screenshot"]
        rest = [e for e in ev if e["kind"] != "screenshot"]
        if rest:
            out.append('<ul class="ev-list">' + "".join(f"<li>{evidence_item(page, e)}</li>" for e in rest) + "</ul>\n")
        if shots:
            out.append('<div class="ev-shots">')
            for e in shots:
                local = site_file(e["path"])
                if local:
                    out.append(f'<a href="{rel(page, local)}"><img src="{rel(page, local)}" loading="lazy" '
                               f'alt="{html.escape(Path(e["path"]).stem)}"><span>{html.escape(Path(e["path"]).stem)}</span></a>')
                else:
                    out.append(f'<span class="ev-shot-link">raw screenshot: {link_repo(page, e["path"], Path(e["path"]).name)}</span>')
            out.append("</div>\n")
        if cell.get("reproduce"):
            out.append("**Repeat it.** " + ", ".join(link_repo(page, p, Path(p).name) for p in cell["reproduce"]) + "\n")
        ch = cell.get("checked") or {}
        out.append(f'<p class="ev-meta">Checked {ch.get("date", "?")} by {ch.get("by", "?")} ({ch.get("how", "?")}).</p>')
        out.append("</div>\n")
    if t.get("proposed_columns"):
        out.append("## Proposed columns\n")
        for cid, cell in t["proposed_columns"].items():
            out.append(f'<div class="ev-card" id="col-{cid}" markdown>')
            out.append(f'<div class="ev-card-head"><span class="ev-colname">selection or filter restricts linked views</span> {glyph(cell["proposed"][0])} <small>{html.escape(cell["proposed"])}</small></div>\n')
            out.append(f"**Observed.** {cell['reason']}\n")
            if ann.get((t["id"], cid)):
                out.append(proof_block(page, ann[(t["id"], cid)]))
            for e in cell.get("evidence", []):
                local = site_file(e["path"]) if "path" in e else None
                if local:
                    out.append(f'<div class="ev-shots"><a href="{rel(page, local)}"><img src="{rel(page, local)}" loading="lazy"><span>{html.escape(Path(e["path"]).stem)}</span></a></div>\n')
            out.append("</div>\n")
    note = t["notes"].split("#")[0]
    if note.endswith(".md") and (REPO / note).is_file():
        text = (REPO / note).read_text()
        text = re.sub(r"^## .*\n", "", text, count=1)        # the page has its own title
        text = re.sub(r"^(#+) ", lambda m: "#" + m.group(1) + " ", text, flags=re.M)
        out.append(f"## Audit notes\n\nIncluded verbatim from {link_repo(page, note)}.\n")
        out.append(rewrite_note_links(text, note, page, tool_pages))
    (DOCS / page).parent.mkdir(parents=True, exist_ok=True)
    (DOCS / page).write_text("\n".join(out))


def columns_page(cols):
    out = ["# Columns\n", "What each column of [[fig:overview]]c scores. Mark scale for every column: "
           + "; ".join(f"**{k}** {v}" for k, v in MARK_TEXT.items()) + ".\n"]
    rules = yaml.safe_load((HERE / "matrix/columns.yaml").read_text()).get("visual_proof_rules") or []
    if rules:
        out.append("## What counts as visual proof\n")
        out.append("Every mark, N included, needs an annotated image. See [Evidence coverage](coverage.md).\n")
        out += [f"- {r}" for r in rules] + [""]
    group = None
    for c in cols:
        if c["group"] != group:
            group = c["group"]
            out.append(f"## {group}\n")
        out.append(f'### {c["label"].replace(chr(10), " ")} {{#{c["id"]}}}\n')
        out.append(c["definition"] + "\n")
        if c.get("status") == "proposed":
            out.append(f'!!! warning "Definition under decision"\n    The authors have not settled it.\n')
    (DOCS / "columns.md").write_text("\n".join(out))


# --------------------------------------------------------------------------- shared helpers for evidence/gen/*
def prep_block(page):
    """The preparation caveat of UCSC Cell Browser, computed from ucsc_prep_cost.csv and ucsc_prep_disk.csv
    (measured values only): shown on UCSC's tool page."""
    d = "benchmark/tool_ceiling"
    cost = [r for r in csv.DictReader(open(REPO / d / "ucsc_prep_cost.csv")) if r["origin"] == "HPC"]
    disk = {r["n_cells"]: r for r in csv.DictReader(open(REPO / d / "ucsc_prep_disk.csv"))}
    rows, last = [], None
    for n in sorted({int(r["n_cells"]) for r in cost}):
        st = {r["step"]: r for r in cost if int(r["n_cells"]) == n}
        if "cbBuild" not in st or "cbImportScanpy" not in st:
            continue
        hours = (float(st["cbImportScanpy"]["wall_s"]) + float(st["cbBuild"]["wall_s"])) / 3600
        rows.append((fmt_n(n), f'{float(st["cbImportScanpy"]["peak_gib"]):.0f}', f'**{float(st["cbBuild"]["peak_gib"]):.0f}**',
                     f"{hours:.1f}", st["cbBuild"]["machine"], f'{float(disk[str(n)]["site_gb"]):.0f}'))
        last = (n, st["cbBuild"], disk[str(n)])
    n, bld, dk = last
    copies = float(dk["input_h5ad_gb"]) + float(dk["in_dir_matrix_mtx_gz_gb"])
    table = "\n".join("    " + ln for ln in md_table(rows, ["cells", "cbImportScanpy peak GiB", "cbBuild peak GiB",
                                                         "prep hours (both steps)", "machine that ran cbBuild", "site GB"]).split("\n"))
    big = "large-memory" in bld["machine"]
    return f"""!!! danger "UCSC Cell Browser needs very large memory to prepare a dataset"
    UCSC cannot open a store or an h5ad directly. A dataset must first be converted into UCSC's own
    format (`cbImportScanpy`, then `cbBuild`), and that conversion holds the whole matrix in memory.
    Every ceiling reported here for UCSC (the client's memory while drawing) **assumes this preparation was
    possible**. The table gives the preparation, measured on the HPC step by step; it is not part of any client number:

{table}

    At {fmt_n(n)} cells the build peaks at {float(bld["peak_gib"]):.0f} GiB of RAM{", more than a standard compute node holds, so it runs only on a large-memory node (1.5 TB)" if big else ""}.
    No ordinary workstation can prepare a dataset of that size for UCSC.
    The site is large too: {float(dk["site_gb"]):.0f} GB at {fmt_n(n)} cells, of which {copies:.0f} GB are download copies
    (the h5ad and the matrix) that the viewer never requests. Every value and the
    laptop runs (1M to 10M cells; the 20M run reaches the 48 GiB machine cap) are in
    {link_repo(page, d + "/ucsc_prep_cost.csv", "ucsc_prep_cost.csv")} and
    {link_repo(page, d + "/ucsc_prep_disk.csv", "ucsc_prep_disk.csv")}; a value that was not recorded reads MISSING.
    The client ceiling is a property of the viewer; this preparation is a property of the format.
"""


def md_table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)




def write_config(tools, nav_extra):
    """_build/mkdocs.yml: inherits ../mkdocs.yml, adds the navigation (core pages, tools, page modules)."""
    nav = [{"Overview": "index.md"},
           {"Feature matrix": [{"Matrix": "matrix.md"}, {"Columns": "columns.md"}, {"Evidence coverage": "coverage.md"},
                               {"Tools": [{t["name"]: f"tools/{t['id']}.md"} for t in tools]}]}]
    sections = {}
    for section, title, page in nav_extra:
        sections.setdefault(section, []).append({title: page})
    nav += [{k: v} for k, v in sections.items()]
    run = DOCS.parent
    for where, inherit in ((run, "../../mkdocs.yml"), (BUILD, "../mkdocs.yml")):
        cfg = {"INHERIT": inherit, "docs_dir": "docs", "site_dir": "site", "nav": nav}
        (where / "mkdocs.yml").write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))


def sanitize_site(san):
    """Last pass over everything in DOCS: generalise internal names in text and in file names.

    Pages and copied text files may quote hostnames, cluster and home paths; the public site
    must not. Copies of repository files therefore differ from their source where this pass
    replaced something (the benchmark pages list what kinds of names were generalised)."""
    renames = []
    for f in sorted(DOCS.rglob("*")):
        if not f.is_file() or f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".pdf", ".gz", ".ico", ".woff2"):
            continue
        try:
            text = f.read_text()
        except UnicodeDecodeError:
            continue
        new = san(text)
        if new != text:
            f.write_text(new)
    for f in sorted(DOCS.rglob("*"), key=lambda x: -len(x.parts)):
        name = san(f.name)
        if name != f.name:
            renames.append((f.name, name))
            f.rename(f.with_name(name))
    if renames:                          # links to renamed files
        for f in DOCS.rglob("*.md"):
            text = f.read_text()
            new = text
            for a, b in renames:
                new = new.replace(a, b)
            if new != text:
                f.write_text(new)


def hosted_images(max_w=2400, quality=85):
    """--hosted: every PNG/JPEG in the site becomes a WebP at most max_w pixels wide, and every
    reference to it is rewritten. The repository keeps the originals; sidecars, image_sha256 and
    the 'raw' links all point at those."""
    from PIL import Image
    renames = []
    for f in sorted(DOCS.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in IMAGE_EXT:
            continue
        im = Image.open(f)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        dst = f.with_suffix(".webp")
        im.save(dst, "WEBP", quality=quality, method=6)
        f.unlink()
        renames.append((f.relative_to(DOCS).as_posix(), dst.relative_to(DOCS).as_posix()))
    for f in DOCS.rglob("*.md"):
        text = new = f.read_text()
        for a, b in renames:
            new = new.replace(a, b)
        if new != text:
            f.write_text(new)
    return len(renames)


def hosted_config(run, out):
    """mkdocs config for the hosted build: built-in search only (no offline plugin), site into `out`."""
    cfg = yaml.safe_load((run / "mkdocs.yml").read_text())
    cfg.update({"site_dir": str(out), "plugins": ["search"], "site_url": "https://settylab.github.io/annzarro-reproducibility/"})
    (run / "mkdocs.hosted.yml").write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    return run / "mkdocs.hosted.yml"


def hosted_prune(out):
    """Drop what a hosted English site never loads: the lunr language packs, the offline search index."""
    for d in [out / "assets/javascripts/lunr/min"]:
        shutil.rmtree(d, ignore_errors=True)
    for f in ["assets/javascripts/lunr/tinyseg.js", "assets/javascripts/lunr/wordcut.js", "search/search_index.js"]:
        (out / f).unlink(missing_ok=True)
    for f in ["sitemap.xml", "sitemap.xml.gz"] + [p.relative_to(out).as_posix() for p in out.rglob("*.map")]:
        (out / f).unlink(missing_ok=True)


# Pages whose tables need more than the default column: they widen the page grid themselves (one <style> block
# in the page), so no other page is affected.
WIDE_PAGE_STYLE = '<style>.md-grid { max-width: 90rem; }</style>\n'
WIDE_TABLE_STYLE = '<style>.md-typeset table:not([class]) th, .md-typeset table:not([class]) td { padding: 0.5em 0.4em; }</style>\n'


def version_images(site):
    """Cache-busting: every local image an HTML page embeds gets `?v=<content hash>`, so a browser that
    cached an earlier version of a figure or screenshot (the server sends only Last-Modified) loads
    the new one as soon as the file changes, and keeps the cached copy while it does not."""
    import hashlib
    seen: dict[Path, str] = {}
    src = re.compile(r'(src)="([^"#:?]+\.(?:png|jpe?g|webp|gif))"')
    for f in site.rglob("*.html"):
        text = f.read_text()

        def sub(m):
            target = (f.parent / m.group(2)).resolve()
            if not target.is_file():
                return m.group(0)
            v = seen.get(target)
            if v is None:
                v = seen[target] = hashlib.sha1(target.read_bytes()).hexdigest()[:10]
            return f'src="{m.group(2)}?v={v}"'
        new = src.sub(sub, text)
        if new != text:
            f.write_text(new)


def fix_site_links(site):
    """After mkdocs: links written as raw HTML keep their `.md` targets (MkDocs rewrites only
    Markdown links), so point them at the built `.html`; a relative link to a repository
    directory that the site does not hold goes to GitHub; 404.html (root-absolute asset
    paths, breaks under a sub-path) is dropped."""
    (site / "404.html").unlink(missing_ok=True)
    for f in site.rglob("*.html"):            # footer link (mkdocs.yml copyright): __ROOT__ -> relative root
        text = f.read_text()
        if "__ROOT__/" in text:
            depth = len(f.relative_to(site).parts) - 1
            f.write_text(text.replace("__ROOT__/", "../" * depth if depth else "./"))
    href = re.compile(r'(href|src)="([^"#:?]+)((?:#[^"]*)?)"')
    for f in site.rglob("*.html"):
        text = f.read_text()

        def sub(m):
            attr, path, frag = m.groups()
            if path.startswith("/"):
                return m.group(0)
            target = (f.parent / path)
            if path.endswith(".md"):
                html_path = path[:-3] + ".html"
                if (f.parent / html_path).exists():
                    return f'{attr}="{html_path}{frag}"'
            if not target.exists() or (target.is_dir() and not (target / "index.html").exists()):
                try:
                    rp = target.resolve().relative_to((site / "repo").resolve()).as_posix()
                except ValueError:
                    return m.group(0)
                kind = "tree" if (REPO / rp).is_dir() else "blob"
                if off_site(rp) and attr == "href":
                    return f'{attr}="#not-in-repository" title="{html.escape(rp)}: in git, not on this site"'
                if (REPO / rp).is_dir() or tracked(rp):
                    return f'{attr}="{GITHUB}/{kind}/{HEAD}/{rp}{frag}"'
                if attr == "href":           # a local or ignored file a note links: not in the repository
                    return f'{attr}="#not-in-repository" title="{html.escape(rp)}: not in the repository"'
            return m.group(0)

        new = href.sub(sub, text)
        new = re.sub(r'<a [^>]*href="#not-in-repository" title="([^"]*)"[^>]*>(.*?)</a>',
                     r'<span class="ev-missing" title="\1">\2</span>', new, flags=re.S)
        if new != text:
            f.write_text(new)

def registry_paths():
    """Every repository path the site's registries name: (registry, path or glob, must_exist)."""
    out = []
    figs = yaml.safe_load((HERE / "figures.yaml").read_text())["figures"]
    for f in figs:
        reg = f"evidence/figures.yaml {f['id']}"
        for k in ("outputs", "other_outputs", "not_in_paper", "code"):
            out += [(reg, x) for x in f.get(k) or []]
        out.append((reg, f["script"]))
        out += [(reg, i["path"]) for i in f.get("inputs") or [] if not i.get("external")]
        out += [(reg, r["path"]) for r in f.get("related") or [] if not r.get("external")]
        out += [(reg, u["script"]) for u in f.get("upstream") or [] if u.get("script") and not u.get("external")]
    for t in sorted((HERE / "matrix/tools").glob("*.yaml")):
        tool = yaml.safe_load(t.read_text())
        reg = f"evidence/matrix/tools/{t.name}"
        for cell in list(tool["cells"].values()) + list((tool.get("proposed_columns") or {}).values()):
            for e in cell.get("evidence") or []:
                if e.get("path") and e.get("kind") != "code":
                    out.append((reg, e["path"]))
            out += [(reg, x) for x in cell.get("reproduce") or [] if isinstance(x, str)]
    claims = yaml.safe_load((HERE / "claims.yaml").read_text())["claims"]
    for cid, c in claims.items():
        src = c.get("source") if isinstance(c, dict) else None
        for x in (src if isinstance(src, list) else [src]):
            if isinstance(x, dict):
                pth = x.get("csv") or x.get("jsonl") or x.get("json") or x.get("file")
                if pth:
                    out.append((f"evidence/claims.yaml {cid}", pth))
    return out


def check_tracked():
    """Every path a registry names is a file git tracks at HEAD (a directory: one tracked file under it;
    a glob: at least one tracked match). An untracked or ignored working-tree file does not count."""
    import fnmatch
    files = set(git("ls-files", "-z").split("\0"))
    head = set(git("ls-tree", "-r", "--name-only", "-z", "HEAD").split("\0"))
    tracked_head = files & head
    dirs = {str(Path(p).parent) for p in tracked_head}
    errs = []
    for reg, pth in registry_paths():
        if not isinstance(pth, str) or not pth:
            continue
        p = pth.split("#", 1)[0].rstrip("/")
        if " " in p or p.startswith(("~", "/", "http")):     # free text or a place outside the repository
            if p.startswith(("~", "/")):
                errs.append(f"{reg}: {pth} names a path outside the repository (not reproducible from a clone)")
            continue
        if any(ch in p for ch in "*?["):
            ok = any(fnmatch.fnmatch(f, p) for f in tracked_head)
        else:
            ok = p in tracked_head or p in dirs or any(f.startswith(p + "/") for f in tracked_head)
        if not ok:
            errs.append(f"{reg}: {pth} is not tracked by git at HEAD")
    return errs


def check_claims_page():
    """Render the claims ledger into a scratch directory and check every row says where it is shown
    or why not (the same rule site_smoke.py applies to the built site, here before any build)."""
    global DOCS
    keep = DOCS
    BUILD.mkdir(exist_ok=True)              # a fresh clone has no _build yet
    tmp = Path(tempfile.mkdtemp(prefix="check-", dir=BUILD))
    try:
        DOCS = tmp
        spec = importlib.util.spec_from_file_location("check_claims", HERE / "gen/60_claims.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.build(sys.modules[__name__])
        missing = claim_targets.rows_without_target((tmp / "claims.md").read_text())
    finally:
        DOCS = keep
        shutil.rmtree(tmp, ignore_errors=True)
    return [f"{cid}: its claims-page row says neither where it is shown nor why not" for cid in missing]


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", action="store_true", help="also run mkdocs build")
    ap.add_argument("--check", action="store_true",
                    help="only check: figure vs YAML marks and the matrix, claim sources and targets, figure numbers, sidecars")
    ap.add_argument("--no-served", action="store_true", help=argparse.SUPPRESS)   # no-op: the served copy is a warning
    ap.add_argument("--hosted", type=Path, metavar="OUT",
                    help="build a hosted copy into OUT: no repo/ mirror (GitHub links at the full HEAD sha), "
                         "WebP images, built-in search; _build/ is left untouched")
    args = ap.parse_args()
    global HOSTED, HEAD
    if args.hosted:
        HOSTED, HEAD = True, git("rev-parse", "HEAD")
    cols, tools = load()
    drift = check_drift(cols, tools)
    for e in drift:
        print("DRIFT", e, file=sys.stderr)
    import fignum                           # figure numbers from the manuscript's own labels
    if not args.check and fignum.refresh():
        print("figure numbers refreshed from manuscript/main.aux: evidence/figure_numbers.json")
    numerr = fignum.check()
    for e in numerr:
        print("FIGNUM", e, file=sys.stderr)
    import figmarks
    model = figmarks.figure_model()
    mx = check_matrix(cols, tools, model)
    for e in mx:
        print("MATRIX", e, file=sys.stderr)
    if args.check:
        # figure vs YAML drift and the site's matrix vs the figure, plus sidecars: one per image,
        # valid, boxes drawn on the current image. The local built site (_build/site, not in git)
        # is only compared as a warning here: it lags every figure commit until the next site
        # build. site_smoke.py, which runs right after a build, fails on it.
        for e in check_served(model):
            print("SERVED (warning: rebuild the local site)", e, file=sys.stderr)
        served = []
        import superseded                      # no green claim on a superseded or non-current source
        stale = superseded.check() + claim_targets.check()     # and every claim shown on a page, or a reason
        stale += check_claims_page()                           # the rendered ledger says so on every row
        stale += check_tracked()                               # every registry path is committed
        import py_compile                      # every evidence script compiles (site_smoke.py runs only on deploys)
        for f in sorted(list((HERE / "tools").glob("*.py")) + list((HERE / "gen").glob("*.py")) + [HERE / "build.py"]):
            try:
                py_compile.compile(str(f), doraise=True, cfile=str(Path(tempfile.gettempdir()) / "evidence_pycheck.pyc"))
            except py_compile.PyCompileError as e:
                stale.append(f"{f.relative_to(REPO)} does not compile: {e.msg.strip().splitlines()[-1]}")
        import py311check                      # the host builds with Python 3.11: no 3.12-only syntax (PEP 701 f-strings)
        stale += py311check.check(sorted(list((HERE / "tools").glob("*.py")) + list((HERE / "gen").glob("*.py"))
                                         + [HERE / "build.py", REPO / "benchmark/tool_ceiling/summarize.py"]
                                         + list((REPO / "figures").glob("*.py"))))
        for e in stale:
            print("SOURCE", e, file=sys.stderr)
        bad = duplicate_sidecars()
        for raw, sides in sidecars().items():
            for side in sides:
                bad += [f"{side.relative_to(REPO)}: {e}" for e in annotate.check(side)]
        for e in bad:
            print("SIDECAR", e, file=sys.stderr)
        return 1 if drift or bad or mx or served or stale or numerr else 0
    # Each run builds into its own directory and swaps the result in at the end, so
    # concurrent builds never delete each other's files (they used to share _build/docs).
    global DOCS
    BUILD.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=BUILD))
    DOCS = run / "docs"
    shutil.copytree(HERE / "pages", DOCS)
    ceil = ceilings()
    ann, sidecar_errors = load_annotations()
    for t in tools:          # split rows (CELLxGENE Explorer/Annotate) also get the shared tool's untargeted proofs
        et = t.get("evidence_tool")
        if et and et != t["id"]:
            for (tid, cid), proofs in list(ann.items()):
                if tid == et:
                    ann.setdefault((t["id"], cid), [])
                    ann[(t["id"], cid)] = ann[(t["id"], cid)] + proofs
    for e in sidecar_errors:
        print("SIDECAR", e, file=sys.stderr)
    tool_pages = {t["notes"].split("#")[0]: f"tools/{t['id']}.md" for t in tools}
    matrix_page(cols, tools, ceil, model)
    columns_page(cols)
    for t in tools:
        tool_page(t, cols, tool_pages, ceil, ann)
    done, total = coverage_page(cols, tools, ann, sidecar_errors)
    print(f"coverage: {done}/{total} marks complete; {sum(len(v) for v in ann.values())} annotated proofs")
    nav_extra, mods = [], {}
    for p in sorted((HERE / "gen").glob("[0-9]*.py")):
        spec = importlib.util.spec_from_file_location(p.stem, p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.build(sys.modules[__name__])
        nav_extra += mod.NAV
        mods[p.stem] = mod
    fignum.expand_docs(DOCS)                # [[fig:<label>]] -> "Fig. N" in every page
    sanitize_site(mods["10_benchmarks_index"].Sanitizer(sys.modules[__name__]))
    write_config(tools, nav_extra)
    if HOSTED:
        n = hosted_images()
        out = args.hosted.resolve()
        if out.exists():
            shutil.rmtree(out)
        rc = subprocess.run([sys.executable, "-m", "mkdocs", "build", "-q", "-f", str(hosted_config(run, out))]).returncode
        hosted_prune(out)
        fix_site_links(out)
        import linkcheck                      # evidence/tools: drop copies no page links (e.g. sanitised mirrors)
        _, referenced, _, _ = linkcheck.check(out)
        for f in [f for f in out.rglob("*") if f.is_file()]:
            if f.relative_to(out).as_posix().startswith(("repo/", "annotated/")) and f.resolve() not in referenced:
                f.unlink()
        for d in sorted((d for d in out.rglob("*") if d.is_dir()), key=lambda d: -len(d.parts)):
            if not any(d.iterdir()):
                d.rmdir()
        fix_site_links(out)                   # links into folders the prune just emptied go to GitHub
        shutil.rmtree(run, ignore_errors=True)
        files = [f for f in out.rglob("*") if f.is_file()]
        print(f"hosted: {out}: {len(files)} files, {sum(f.stat().st_size for f in files) / 2**20:.1f} MB, {n} images as WebP")
        return rc
    print(f"evidence/_build/docs: {sum(1 for _ in DOCS.rglob('*.md'))} pages, {len(copied)} files copied")
    rc = 0
    if args.site:
        rc = subprocess.run([sys.executable, "-m", "mkdocs", "build", "-q", "-f", str(run / "mkdocs.yml")]).returncode
        if (run / "site").exists():
            fix_site_links(run / "site")
            version_images(run / "site")
    with open(BUILD / ".lock", "w") as lock:   # swap in: the last finished build wins, never a half-built one
        fcntl.flock(lock, fcntl.LOCK_EX)
        for name in ("docs", "site"):
            if (run / name).exists():
                old = BUILD / name
                if old.is_dir():
                    # sync in place: a server running inside _build/site (python -m http.server
                    # started there) keeps its directory, so it serves the new build at once
                    subprocess.run(["rsync", "-a", "--delete", f"{run / name}/", f"{old}/"], check=True)
                else:
                    (run / name).rename(old)
    shutil.rmtree(run, ignore_errors=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
