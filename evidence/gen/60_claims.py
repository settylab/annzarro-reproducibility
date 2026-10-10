"""Claims: every number and comparison in the manuscript, recomputed from its source.

A page module (see 20_tool_ceiling.py): build(ctx) writes claims.md from evidence/claims.yaml,
checked by evidence/tools/claims.py, the same code the command line and CI run.
"""
import html
import importlib
from collections import Counter

NAV = [("Claims", "Claims ledger", "claims.md")]

STATUS = {   # chip label, css class, meaning
    "reproduced": ("reproduced", "ok", "recomputed from the source; matches the text"),
    "interim": ("interim", "interim", "matches the text; the number is still moving"),
    "mismatch": ("mismatch", "bad", "the source gives a different value, or the text or source is missing"),
    "unsourced": ("unsourced", "none", "no file in this repository holds it"),
    "unmarked": ("unmarked", "unmarked", "a number in the prose that no ledger entry covers"),
}
FILE_TITLE = {"manuscript/sections/abstract.tex": "Abstract", "manuscript/main.tex": "Key points, Supplementary Note 1, Supplementary Fig. S1",
              "manuscript/body.tex": "Body", "manuscript/sections/figs_results.tex": "Figure captions",
              "manuscript/sections/procedure_prep.tex": "Procedure, data preparation"}

CSS = """<style>
.cl-chip { display: inline-block; padding: 0 0.45em; border-radius: 3px; font-size: 0.62rem; font-weight: 700;
  line-height: 1.6; white-space: nowrap; border: 1px solid transparent; }
.cl-ok { background: var(--ev-accent); color: #fff; }
.cl-interim { color: var(--ev-accent); border-color: var(--ev-accent); }
.cl-bad { background: #b5532f; color: #fff; }
.cl-none { color: var(--ev-muted); border: 1px dashed var(--ev-muted); }
.cl-unmarked { color: var(--md-default-fg-color--light); border-color: var(--md-default-fg-color--lighter); }
.cl-nomark { color: var(--ev-muted); font-size: 0.55rem; font-weight: 400; margin-top: 0.15rem; display: block; }
.cl-counts { display: flex; flex-wrap: wrap; gap: 0.4rem 1.1rem; margin: 0.6rem 0 1rem; font-size: 0.75rem; align-items: center; }
.cl-counts b { font-variant-numeric: tabular-nums; }
.md-typeset table.cl-table { display: table; width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 0.66rem; }
.md-typeset .cl-table th, .md-typeset .cl-table td { padding: 0.35rem 0.4rem; vertical-align: top; border: 0;
  border-top: 1px solid var(--md-default-fg-color--lightest); overflow-wrap: anywhere; }
.md-typeset .cl-table thead th { font-weight: 700; text-align: left; border-top: 0; border-bottom: 2px solid var(--md-default-fg-color--lighter); }
.md-typeset ul.cl-src { list-style: none; margin: 0; padding: 0; }
.md-typeset ul.cl-src > li { margin: 0 0 0.3rem; padding: 0; }
.cl-diff { background: color-mix(in srgb, #b5532f 22%, transparent); color: inherit; border-radius: 2px; padding: 0 1px; font-weight: 700; }
.cl-mx { display: inline-flex; align-items: center; gap: 0.15rem; margin-right: 0.45rem; white-space: nowrap; }
.cl-mx a { color: inherit; }
.cl-mxcol { font-weight: 600; }
.cl-need { color: var(--md-default-fg-color--light); font-size: 0.58rem; margin-right: 0.25rem; }
.cl-table col.c-st { width: 6.5rem; } .cl-table col.c-claim { width: 34%; } .cl-table col.c-val { width: 17%; }
.cl-table col.c-src { width: 22%; }
.cl-text { font-weight: 600; }
.md-typeset h6.cl-h { margin: 0 0 0.15rem; font-size: 0.6rem; font-weight: 600; font-family: var(--md-code-font-family);
  color: var(--md-default-fg-color--light); text-transform: none; letter-spacing: 0; scroll-margin-top: 4rem; }
.md-typeset h6.cl-h:target { color: var(--ev-accent); }
.cl-shown { font-size: 0.62rem; margin-bottom: 0.3rem; }
.cl-shown a { font-weight: 600; }
.cl-pending { color: #b5532f; }
.cl-novis { color: var(--md-default-fg-color--light); font-style: italic; }
.cl-id, .cl-loc { display: block; color: var(--md-default-fg-color--light); font-size: 0.58rem; font-family: var(--md-code-font-family); }
.cl-val code, .cl-unm code { font-size: 0.62rem; word-break: break-word; }
.cl-src { margin: 0; padding-left: 0; list-style: none; }
.cl-detail { color: var(--md-default-fg-color--light); font-size: 0.58rem; display: block; }
.cl-problem { color: #b5532f; display: block; margin-top: 0.15rem; }
.cl-warn { color: var(--md-default-fg-color--light); display: block; margin-top: 0.15rem; font-style: italic; }
.cl-table tr.cl-row-bad { background: color-mix(in srgb, #b5532f 7%, transparent); }
.cl-filter { font-size: 0.72rem; margin: 0.4rem 0 0.2rem; display: flex; gap: 0.9rem; flex-wrap: wrap; }
.cl-hide-ok tr.cl-row-reproduced { display: none; }
@media (max-width: 52rem) {
  .md-typeset table.cl-table, .cl-table tbody, .cl-table tr, .cl-table td { display: block; width: 100%; }
  .cl-table thead, .cl-table colgroup { display: none; }
  .md-typeset .cl-table td { border-top: 0; padding: 0.15rem 0.3rem; }
  .md-typeset .cl-table tr { border-top: 1px solid var(--md-default-fg-color--lightest); padding: 0.3rem 0; }
}
</style>
<script>
document.addEventListener("change", function (e) {
  if (e.target && e.target.id === "cl-only-open") {
    document.querySelectorAll(".cl-table").forEach(function (t) { t.classList.toggle("cl-hide-ok", e.target.checked); });
  }
});
</script>
"""


def chip(status, extra=""):
    label, cls, tip = STATUS[status]
    return f'<span class="cl-chip cl-{cls}" title="{html.escape(tip)}">{label}</span>{extra}'


def fmt_value(v):
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, bool):
        return "found" if v else "missing"
    return str(v)


def diff_html(rendered, text):
    """The recomputed phrase with the tokens that differ from the text highlighted."""
    import re
    a = re.findall(r"\S+|\s+", rendered)
    b = re.findall(r"\S+|\s+", text)
    out = []
    for i, t in enumerate(a):
        same = i < len(b) and t == b[i]
        out.append(html.escape(t) if same or t.isspace() else f'<mark class="cl-diff">{html.escape(t)}</mark>')
    return "".join(out)


def matrix_group(ctx, srcs):
    """Matrix sources grouped by column: one line per column, a linked glyph per tool."""
    groups = {}
    for s in srcs:
        want = s["spec"].get("expect")
        key = (s.get("column", "?"), "/".join(want) if isinstance(want, list) else str(want))
        groups.setdefault(key, []).append(s)
    out = []
    for (col, wants), ss in groups.items():
        items = "".join(
            f'<span class="cl-mx"><a href="tools/{html.escape(x.get("tool", "?"))}.md#col-{html.escape(col)}" '
            f'title="{html.escape(x.get("tool", "?"))}: {html.escape(str(x.get("value")))}">{html.escape(x.get("tool", "?"))}</a>'
            f'{ctx.glyph(x.get("value")) if x.get("value") in ("Y", "P", "N", "?") else ""}</span>' for x in ss)
        out.append(f'<li><span class="cl-mxcol">{html.escape(col)}</span> <span class="cl-need">needs {html.escape(wants)}:</span> {items}</li>')
    return "".join(out)


def source_item(ctx, page, s):
    kind, spec = s["kind"], s["spec"]
    if kind == "matrix":
        tool, col = s.get("tool", "?"), s.get("column", "?")
        mark = s.get("value")
        want = spec.get("expect")
        wants = "/".join(want) if isinstance(want, list) else (want or "")
        g = ctx.glyph(mark) if mark in ("Y", "P", "N", "?") else html.escape(str(mark))
        return (f'<li><a href="tools/{html.escape(tool)}.md#col-{html.escape(col)}">{html.escape(tool)} · {html.escape(col)}</a> '
                f'{g}<span class="cl-detail">text needs {html.escape(wants)}</span></li>')
    paths = s.get("files") or [s["path"]]
    links = ", ".join(ctx.link_repo(page, p) for p in paths[:6]) + (f" and {len(paths) - 6} more" if len(paths) > 6 else "")
    line = f":{s['line']}" if s.get("line") else ""
    detail = s.get("detail") or ""
    if s.get("rows") is not None:
        detail += f" ({s['rows']} row{'s' if s['rows'] != 1 else ''})"
    if "value" in s:
        detail += f" → {fmt_value(s['value'])}"
    if s.get("error"):
        detail += f" — {s['error']}"
    return f'<li>{links}{line}<span class="cl-detail">{html.escape(detail)}</span></li>'


def row(ctx, page, r):
    e = r.entry
    bound = sorted({(f, b) for f, _, b in r.markers if b})           # every marked place, e.g. a claim marked twice
    loc = (", ".join(f"{f.replace('manuscript/', '')}:{b}" for f, b in bound) if bound
           else f"{e.get('file', '?').replace('manuscript/', '')}:{r.line or '?'}")
    nomark = "" if r.placed else '<span class="cl-nomark" title="no %claim marker in the manuscript yet">no marker yet</span>'
    # the id is its own heading: the search plugin indexes each heading as a section of its own, so
    # searching an id (or its prefix) lands on #id, the row
    claim = (f'<h6 class="cl-h" id="{html.escape(r.id)}"> {html.escape(r.id)} </h6>'
             f'<span class="cl-text">{html.escape(e.get("text", ""))}</span>'
             f'<span class="cl-id"> {e.get("kind", "")} · {html.escape(loc)} </span>')
    if r.rendered is not None:
        val = f"<code>{diff_html(r.rendered, e.get('text', '')) if r.status == 'mismatch' else html.escape(r.rendered)}</code>"
    elif r.status == "unsourced":
        val = "–"
    elif r.sources:
        val = "matches" if not r.problems else "–"
        if any(s["kind"] == "matrix" for s in r.sources):
            val = "marks agree" if not r.problems else "marks disagree"
        elif all(s["kind"] == "file" for s in r.sources):
            val = "anchor found" if not r.problems else "anchor missing"
    else:
        val = "–"
    import claim_targets as CT
    if CT.hpc_pending(e):               # its sources are the 0.1.1 series; the site shows none of its values
        val = "–"
    mx = [s for s in r.sources if s["kind"] == "matrix"]
    tg = CT.targets(r.id, e)

    def exists(pg, a):                  # the target page was written earlier in this build, with that anchor
        f = ctx.DOCS / pg
        if not f.exists():
            return False
        t = f.read_text(errors="replace")
        if not a or f'id="{a}"' in t or "{#" + a + "}" in t:
            return True
        import re
        slug = lambda h: re.sub(r"[\s]+", "-", re.sub(r"[^\w\s-]", "", h.strip().lower()))   # toc's default ids
        return any(slug(line.lstrip("#")) == a for line in t.splitlines() if line.startswith("#"))

    if tg:
        shown = ('<div class="cl-shown">shown in: ' + ", ".join(
            (f'<a class="cl-shown-link" href="{html.escape(pg)}{"#" + html.escape(a) if a else ""}">{html.escape(lab)}</a>'
             if exists(pg, a) else f'<span class="cl-pending" title="the page does not draw this source on the current release">'
                                    f'{html.escape(lab)} (not drawn yet)</span>')
            for pg, a, lab in tg) + "</div>")
    else:
        why = CT.no_visual(r.id, e)
        shown = f'<div class="cl-shown cl-novis">not drawn: {html.escape(why)}</div>' if why else ""
    if CT.hpc_pending(e):               # the paper states no 0.1.1 value: no link to that series
        srcs = shown + '<span class="cl-detail">source: the HPC re-measure (J3/T), pending</span>'
    else:
        srcs = shown + (('<ul class="cl-src">' + matrix_group(ctx, mx) + "".join(source_item(ctx, page, s) for s in r.sources if s["kind"] != "matrix")
                         + "</ul>") if r.sources else ("arithmetic" if e.get("compute") and r.status != "unsourced" else "–"))
    if e.get("compute") and not CT.hpc_pending(e):
        srcs += f'<span class="cl-detail">compute: <code>{html.escape(str(e["compute"]))}</code></span>'
    note = html.escape(e.get("note") or "")
    note += "".join(f'<span class="cl-problem">{html.escape(p)}</span>' for p in r.problems)
    note += "".join(f'<span class="cl-warn">{html.escape(w)}</span>' for w in r.warnings)
    cls = f"cl-row-{r.status}" + (" cl-row-bad" if r.status == "mismatch" else "")
    return (f'<tr class="{cls}"><td>{chip(r.status)}{nomark}</td><td>{claim}</td>'
            f'<td class="cl-val">{val}</td><td>{srcs}</td><td>{note}</td></tr>')


def table(rows_html):
    return ('<div class="cl-wrap"><table class="cl-table"><colgroup><col class="c-st"><col class="c-claim"><col class="c-val">'
            '<col class="c-src"><col class="c-note"></colgroup><thead><tr><th>status</th><th>claim</th>'
            '<th>recomputed</th><th>source</th><th>note</th></tr></thead><tbody>\n' + "\n".join(rows_html)
            + "\n</tbody></table></div>")


def build(ctx):
    REPO, DOCS = ctx.REPO, ctx.DOCS
    claims = importlib.import_module("evidence.tools.claims")   # build.py puts the repo on sys.path
    page = "claims.md"
    ev = claims.evaluate()
    c = claims.counts(ev)
    results = ev["results"]
    order = list(FILE_TITLE)
    by_file = {}
    for r in sorted(results, key=lambda r: (order.index(r.entry.get("file")) if r.entry.get("file") in order else 99,
                                             r.line or 10 ** 6, r.id)):
        by_file.setdefault(r.entry.get("file", "?"), []).append(r)
    kinds = Counter(r.entry.get("kind", "?") for r in results)

    sections = []
    for f, rs in by_file.items():
        st = Counter(r.status for r in rs)
        summary = ", ".join(f"{n} {s}" for s, n in st.most_common())
        sections.append(f"## {FILE_TITLE.get(f, f)} {{#{f.split('/')[-1].replace('.tex', '')}}}\n\n"
                        f"`{f}`: {len(rs)} claims ({summary}).\n\n" + table([row(ctx, page, r) for r in rs]) + "\n")

    mism = [r for r in results if r.status == "mismatch"]
    def recomputed(r):
        if r.rendered is not None and any(p.startswith("recomputed") for p in r.problems):
            return diff_html(r.rendered, r.entry.get("text", ""))
        return html.escape("; ".join(r.problems))
    mism_lines = "\n".join(
        f"| [{r.id}](#{r.id}) | `{r.entry.get('file', '').replace('manuscript/', '')}:{r.line or '?'}` | "
        + html.escape(r.entry.get("text", "")).replace("|", "\\|") + " | "
        + recomputed(r).replace("|", "\\|") + " | " + html.escape(r.entry.get("note") or "").replace("|", "\\|") + " |"
        for r in mism) or "| – | – | – | none | |"

    unm = ev["unmarked"]
    unm_rows = "\n".join(
        f'<tr><td>{chip("unmarked")}</td><td><code>{html.escape(u["file"].replace("manuscript/", ""))}:{u["line"]}</code></td>'
        f'<td><code>{html.escape(u["match"])}</code></td><td class="cl-unm">{html.escape(u["fragment"])}</td></tr>' for u in unm)
    unm_block = ('<table class="cl-table"><colgroup><col class="c-st"><col style="width:9rem"><col style="width:9rem"><col></colgroup>'
                 '<thead><tr><th>status</th><th>where</th><th>number</th><th>context</th></tr></thead><tbody>'
                 + unm_rows + "</tbody></table>") if unm else "None: every number with a unit or scale word in the prose is covered by an entry."
    errs = "\n".join(f"- `{html.escape(e)}`" for e in ev["errors"]) or "None."
    placed = c["claims"] - c["unplaced"]
    marker_note = (f"**{placed} of {c['claims']}** entries have their `%claim{{…}}` marker in the manuscript."
                   if ev["markers_exist"] else
                   f"The manuscript has no `%claim{{…}}` markers yet, so every entry is located by its text and shown "
                   f"with *no marker yet*. `claims.py --list` prints where each marker goes; once any marker exists, "
                   f"an entry without one is an error.")

    counts_html = '<div class="cl-counts">' + "".join(
        f'<span>{chip(s)} <b>{c[s]}</b></span>' for s in ("reproduced", "interim", "mismatch", "unsourced", "unmarked")) + \
        f'<span>of <b>{c["claims"]}</b> claims ({kinds["number"]} numbers, {kinds["comparison"]} comparisons, {kinds["qualitative"]} qualitative)</span></div>'

    body = f"""---
hide: [toc]
---

# Claims ledger
{CSS}
Every quantitative or comparative claim in the manuscript, with the file it comes from and
the value recomputed from that file. A claim is **reproduced** when the
recomputed value, formatted as the text formats it, is the text; **comparison** claims about
other tools must agree with their marks in the [feature matrix](matrix.md).

{counts_html}

!!! info "Where these claims come from"
    Ledger: {ctx.link_repo(page, "evidence/claims.yaml")} ({ctx.prov_badge("evidence/claims.yaml")}).
    Checker: {ctx.link_repo(page, "evidence/tools/claims.py")}, which you can also run yourself
    (`python evidence/tools/claims.py`; it reports any mismatch).
    Manuscript files scanned: {", ".join(f"`{t}`" for t in ev["texs"])}. {marker_note}
    **Interim** claims reproduce but rest on numbers that will be re-measured; **unsourced** claims have no file in this repository
    to check them against.

<div class="cl-filter"><label><input type="checkbox" id="cl-only-open"> hide reproduced claims</label></div>

## Mismatches ({len(mism)}) {{#mismatches}}

Highlighted: where the recomputed phrase differs from the text.

| claim | where | text | recomputed from the source | note |
|---|---|---|---|---|
{mism_lines}

{chr(10).join(sections)}

## Numbers in the prose without an entry ({len(unm)}) {{#unmarked}}

The checker looks for numbers with a unit or scale word (M, k, million, GB, s, ms, %, ×,
cells, genes, …) and "N of M", skipping citations, figure, step and version numbers and
dates. A number is covered when it lies inside an entry's text.

{unm_block}

## Ledger errors

{errs}
"""
    (DOCS / page).write_text(body)
