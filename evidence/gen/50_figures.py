"""Figures: for every manuscript figure, the script, its inputs, their commits, and whether it is stale.

Page module (see 20_tool_ceiling.py). Sources: evidence/figures.yaml (what each figure is made
from), evidence/tools/figcheck.py (dates and STALE/DIRTY flags), 
"""
import html
import importlib.util
import re

NAV = [("Figures", "Provenance", "figures/index.md")]
PAGE = "figures/index.md"

STYLE = """<style>
.fg-sum td, .fg-sum th { vertical-align: middle; }
.fg-card { border: 1px solid var(--md-default-fg-color--lightest); border-radius: 6px; padding: 0.6rem 0.9rem 0.5rem; margin: 0.6rem 0 1.6rem; }
.fg-top { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: 0.6rem 1.2rem; align-items: start; }
.fg-thumb img { width: 100%; max-height: 460px; object-fit: contain; object-position: top left; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 4px; background: #fff; }
.fg-thumb .fg-none { display: flex; align-items: center; justify-content: center; height: 120px; border: 1px dashed var(--md-default-fg-color--lighter); border-radius: 4px; font-size: 0.65rem; color: var(--md-default-fg-color--light); text-align: center; padding: 0.5rem; }
.fg-meta { font-size: 0.7rem; }
.fg-meta dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 0.25rem 0.8rem; margin: 0; }
.fg-meta dt { color: var(--md-default-fg-color--light); font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.04em; padding-top: 0.1rem; }
.fg-meta dd { margin: 0; overflow-wrap: anywhere; }
.fg-meta code, .fg-card td code { font-size: 0.92em; overflow-wrap: anywhere; }
.md-typeset .fg-card h4 { margin: 0.9rem 0 0.3rem; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--md-default-fg-color--light); }
.md-typeset table.fg-tab { display: table; width: 100%; font-size: 0.66rem; border-collapse: collapse; table-layout: auto; }
.md-typeset table.fg-tab th, .md-typeset table.fg-tab td { padding: 0.25rem 0.45rem; vertical-align: top; text-align: left; }
.md-typeset table.fg-tab th { white-space: nowrap; }
.md-typeset table.fg-tab td.fg-file { min-width: 13em; overflow-wrap: anywhere; }
.md-typeset table.fg-tab td.fg-nw { white-space: nowrap; }
.md-typeset table.fg-tab td.fg-id { width: 3em; white-space: nowrap; }
.fg-cmd { margin: 0.5rem 0 0; font-size: 0.66rem; }
.fg-cmd code { display: block; padding: 0.3rem 0.5rem; white-space: pre-wrap; overflow-wrap: anywhere; }
.fg-chip { display: inline-block; padding: 0 0.35em; border-radius: 3px; font-size: 0.58rem; font-weight: 700; letter-spacing: 0.03em; line-height: 1.6; white-space: nowrap; border: 1px solid transparent; }
.fg-ok { color: var(--ev-accent); border-color: var(--ev-accent); }
.fg-stale { background: #b5532f; color: #fff; }
.fg-doc { color: #9a6a00; border-color: #c99a2e; }
.fg-dirty { color: #b5532f; border-color: #b5532f; }
.fg-ext { color: var(--ev-muted); border: 1px dashed var(--ev-muted); }
.fg-miss { color: #fff; background: var(--ev-muted); }
.fg-small { font-size: 0.62rem; color: var(--md-default-fg-color--light); }
.md-typeset ul.fg-chain { list-style: none; margin: 0; padding: 0; font-size: 0.68rem; }
.md-typeset ul.fg-chain li { margin: 0.2rem 0; }
.fg-gaps { font-size: 0.68rem; }
.fg-scroll { overflow-x: auto; max-width: 100%; }
.fg-card { min-width: 0; overflow-wrap: anywhere; }
@media (max-width: 760px) { .fg-top { grid-template-columns: minmax(0, 1fr); } .fg-thumb img { max-height: 260px; }
  .fg-card { padding: 0.5rem 0.6rem; } .fg-meta dl { grid-template-columns: minmax(0, 1fr); gap: 0 0; } .fg-meta dd { margin-bottom: 0.35rem; } }
</style>
"""


def _figcheck(ctx):
    spec = importlib.util.spec_from_file_location("figcheck", ctx.HERE / "tools" / "figcheck.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _short(text, n):
    text = re.sub(r"`([^`]*)`", r"\1", text)
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def chip(kind, text=None, title=""):
    cls = {"ok": "fg-ok", "STALE": "fg-stale", "doc-only": "fg-doc", "DIRTY": "fg-dirty",
           "external": "fg-ext", "missing": "fg-miss", "reproduced": "fg-ok", "differs": "fg-dirty"}[kind]
    t = f' title="{html.escape(title)}"' if title else ""
    return f'<span class="fg-chip {cls}"{t}>{html.escape(text or kind)}</span>'


def build(ctx):
    import sys
    sys.path.insert(0, str(ctx.REPO / "evidence/tools"))
    import fignum
    import claim_targets as CT
    DOCS, REPO = ctx.DOCS, ctx.REPO
    fc = _figcheck(ctx)
    spec = {f["id"]: f for f in fc.load_spec()}
    results = fc.check_all()

    def a(path, label=None):
        if path.startswith("/"):
            return f"<code>{html.escape(path)}</code>"
        if any(c in path for c in "*?["):
            return f"<code>{html.escape(path)}</code>"
        if not (REPO / path).exists():
            return f"<code>{html.escape(path)}</code>"
        return ctx.link_repo(PAGE, path.rstrip("/"), label or path)

    def dep_status(d):
        out = []
        st = (d.get("store") or {}).get("here")
        if st:
            if st["state"] == "verified":
                return chip("reproduced", "store verified", title=f"the store on this host has the recorded md5 {st['md5']}")
            if st["state"] == "skipped":
                return chip("external", "store present, md5 not checked")
            return chip("differs", "STORE DIFFERS", title=f"md5 {st['md5']} is not the recorded one")
        if not d["exists"]:
            if d["external"]:
                return chip("external", "not on this build host", title="an external input this host does not have: not checked here")
            return chip("missing")
        if d.get("stale"):
            out.append(chip("doc-only", title="changed since the last render, docstrings and comments only")
                       if d.get("doc_only") else chip("STALE", title="newer than the figure's last render"))
        if d["state"] in ("dirty", "untracked"):
            out.append(chip("DIRTY", d["state"] if d["state"] == "untracked" else "DIRTY",
                            title="the working tree differs from the last commit"))
        if d["external"] or d["state"] == "ignored":
            out.append(chip("external", "outside git", title="gitignored or outside the repository: dated by mtime"))
        return " ".join(out) or chip("ok")

    def when(d):
        if not d["exists"]:
            return '<span class="fg-small">not on this build host</span>' if d["external"] else "missing"
        if d["sha"]:
            s = f'<code>{d["sha"]}</code> {d["commit_time"][:16].replace("T", " ")}'
            if d["state"] == "dirty":
                s += f'<br><span class="fg-small">edited {fc._iso(d["mtime"])[:16].replace("T", " ")}</span>'
            return s
        return f'<span class="fg-small">mtime {fc._iso(d["mtime"])[:16].replace("T", " ")}</span>'

    def fig_flags(r):
        f = []
        if r["is_stale"]:
            f.append(chip("STALE"))
        elif r["stale"]:
            f.append(chip("doc-only", title="only docstrings/comments changed since the last render"))
        if r["dirty"]:
            f.append(chip("DIRTY"))
        if r["missing"]:
            f.append(chip("missing", f"{len(r['missing'])} missing"))
        if r["store_differs"]:
            f.append(chip("differs", "STORE DIFFERS"))
        verified = [d for d in r["deps"] if ((d.get("store") or {}).get("here") or {}).get("state") == "verified"]
        if verified:
            f.append(chip("reproduced", "store verified on this host"))
        if r.get("reproduced"):
            q = r["reproduced"]
            f.append(chip("reproduced", f"reproduced {q['date']}", title=f"at {q['commit'][:7]} on {q['host']}: {q['result']}"))
        if r["not_on_host"]:
            f.append(chip("external", "an external input is not on this build host",
                          title="; ".join(r["not_on_host"])))
        elif any(d["external"] or d["state"] == "ignored" for d in r["deps"]):
            f.append(chip("external", "external input"))
        return " ".join(f) or chip("ok")

    # ------------------------------------------------------------------ summary
    n_stale = sum(r["is_stale"] for r in results)
    n_doc = sum(bool(r["stale"]) and not r["is_stale"] for r in results)
    n_dirty = sum(bool(r["dirty"]) for r in results)
    out = ["---\nhide:\n  - toc\n---\n", "# Figure provenance\n", STYLE, f"""
For every figure in the manuscript: the script that draws it, the data it reads, the commit
each file was last changed in, and whether the figure is older than what it is made from.
Listed in {a("evidence/figures.yaml")} and checked by
{a("evidence/tools/figcheck.py")}; run `python evidence/tools/figcheck.py` for the same report
in a terminal, or `--render <id>` to redraw a figure into a scratch directory and compare it
with the committed PNG.

**How to read the chips.** {chip("STALE")} an input, the script or a module it imports was
committed (or edited) after the figure's last render, the newest commit of its outputs.
{chip("doc-only")} the only change since then is in docstrings or comments (same Python AST), so
the drawing cannot differ. {chip("DIRTY")} the file has uncommitted changes.
{chip("external", "outside git")} the input is gitignored or outside the repository: git cannot
date it, the build shows its mtime, and it never sets STALE. {chip("external", "not on this build host")}
the build host does not have that input (the demo store is large and not in git): nothing is claimed
about it here; the input's expected identity is listed, and the figure's last render says when it was
drawn from it. {chip("reproduced", "reproduced")} the figure was re-drawn from the published store and the
result compared with the committed figure (the record gives commit, date, machine and result);
{chip("reproduced", "store verified")} the store on the host that built this page has the recorded md5. An input
of which the script reads only some rows is dated by the last commit that changed those rows.

**Now:** {n_stale} stale, {n_doc} doc-only, {n_dirty} with uncommitted inputs, of {len(results)} figures.
""", '<div class="fg-scroll"><table class="fg-tab fg-sum"><thead><tr><th>figure</th><th>label</th><th>status</th>'
         '<th>last render</th><th>script</th></tr></thead><tbody>']
    for r in results:
        f = spec[r["id"]]
        lr = (f'<code>{r["out_sha"]}</code> {fc._iso(r["out_time"])[:10]}' if r["out_time"] else "-")
        out.append(f'<tr><td><a href="#{r["id"]}">{html.escape(fignum.fig(f["label"]))}</a><br>'
                   f'<span class="fg-small">{html.escape(_short(f["title"], 70))}</span></td>'
                   f'<td class="fg-nw"><code>{html.escape(f["label"])}</code></td><td>{fig_flags(r)}</td>'
                   f'<td class="fg-nw">{lr}</td>'
                   f'<td class="fg-nw">{a(f["script"], Path_name(f["script"])) if f.get("script") else "TikZ in the manuscript"}</td></tr>')
    out.append("</tbody></table></div>\n")

    # ------------------------------------------------------------------ one card per figure
    for r in results:
        f = spec[r["id"]]
        pngs = [o for o in f["outputs"] if o.endswith(".png")]
        thumb = None
        if pngs:
            local = ctx.site_file(pngs[0])
            if not local:
                local = _thumbnail(REPO / pngs[0], DOCS / "figures" / "thumbs" / (r["id"] + ".png"))
                local = local and f"figures/thumbs/{r['id']}.png"
            if local:
                thumb = (f'<a href="{ctx.rel(PAGE, local)}"><img src="{ctx.rel(PAGE, local)}" '
                         f'alt="{html.escape(fignum.fig(f["label"]))}" loading="lazy"></a>')
        if not thumb:
            thumb = (f'<div class="fg-none">no image: {html.escape(", ".join(Path_name(o) for o in f["outputs"]))}'
                     f'<br>{"TikZ, compiled with the manuscript" if not f.get("script") else ""}</div>')
        outs = "<br>".join(f'{a(o["path"])} {when(o)} '
                           f'{chip("DIRTY") if o["state"] in ("dirty", "untracked") else ""}'
                           f'{chip("missing") if not o["exists"] else ""}' for o in r["outputs"])
        others = "<br>".join(f'{a(o["path"])}' + ("" if o["exists"] else " " + chip("missing"))
                             for o in r["other_outputs"])
        script_dep = next((d for d in r["deps"] if d["role"] == "script"), None)
        code = [d for d in r["deps"] if d["role"] == "code"]
        meta = [("label", f'<code>{html.escape(f["label"])}</code> &middot; placed at '
                          f'<code>{html.escape(fignum.placement(f["label"]) or "?")}</code>'),
                ("outputs", outs)]
        if others:
            meta.append(("also writes", others))
        if f.get("not_in_paper"):
            meta.append(("also writes, not in the paper", "<br>".join(a(x) for x in f["not_in_paper"])))
        if script_dep:
            meta.append(("script", f'{a(script_dep["path"])} {when(script_dep)} {dep_status(script_dep)}'))
        if code:
            meta.append(("imports", "<br>".join(f'{a(d["path"])} {when(d)} {dep_status(d)}' for d in code)))
        meta.append(("status", fig_flags(r)))
        out.append(f'\n## {fignum.fig(f["label"])}: {f["title"]} {{#{r["id"]}}}\n')
        out.append(CT.backs_html(PAGE, r["id"], ctx.rel))
        out.append('<div class="fg-card"><div class="fg-top">')
        out.append(f'<div class="fg-thumb">{thumb}</div>')
        out.append('<div class="fg-meta"><dl>' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in meta)
                   + "</dl></div></div>")
        out.append(f'<div class="fg-cmd"><code>{html.escape(f["command"])}</code></div>')

        # inputs
        inputs = [d for d in r["deps"] if d["role"] == "input"]
        out.append("<h4>Inputs</h4>")
        if inputs:
            by_path = {}
            for i in f.get("inputs", []):
                for p in fc.expand(i["path"]):
                    by_path[p] = i
            out.append('<div class="fg-scroll"><table class="fg-tab"><thead><tr><th>file</th><th>panels</th><th>what</th>'
                       '<th>last commit</th><th>status</th></tr></thead><tbody>')
            for d in inputs:
                i = by_path.get(d["path"], {})
                what = html.escape(i.get("what", ""))
                if i.get("identity"):
                    what += f'<br><span class="fg-small"><b>Expected:</b> {html.escape(i["identity"])}</span>'
                sp = i.get("store")
                if sp:
                    what += (f'<br><span class="fg-small"><b>Source:</b> <code>bm_aging_annzarro.zarr</code> from Zenodo '
                             f'<a href="https://doi.org/{sp["doi"]}">{sp["doi"]}</a> (concept DOI of the record; the files are pinned to '
                             f'version 1.0). Store md5 <code>{sp["md5"]}</code>, {sp["files"]:,} files; '
                             f'<code>{html.escape(sp["fetch"])}</code> downloads it, checks the zip sha256 and this md5.</span>')
                    h = (d.get("store") or {}).get("here")
                    if h and h["state"] == "verified":
                        what += '<br><span class="fg-small"><b>Verified on this host:</b> the store here has that md5.</span>'
                    elif not d["exists"]:
                        what += '<br><span class="fg-small"><b>Not on this build host,</b> so not checked here.</span>'
                    if r.get("reproduced"):
                        q = r["reproduced"]
                        what += (f'<br><span class="fg-small"><b>Reproduced</b> at <code>{q["commit"][:7]}</code> on {q["date"]} on '
                                 f'{html.escape(q["host"])}: {html.escape(q["result"])}.</span>')
                elif i.get("identity") and not d["exists"] and r["out_sha"]:
                    what += (f'<br><span class="fg-small"><b>Not checked on this host.</b> The figure was last drawn from it at '
                             f'<code>{r["out_sha"]}</code> on {fc._iso(r["out_time"])[:10]}, on a machine that has it.</span>')
                if i.get("reads"):
                    rd = i["reads"]
                    what += ('<br><span class="fg-small">Only ' + html.escape(", ".join(f"{k} = {v}" for k, v in rd.get("where", {}).items()))
                             + ' rows' + (', columns ' + html.escape(", ".join(rd["columns"])) if rd.get("columns") else "")
                             + ' are read: dated by the last commit that changed them.</span>')
                out.append(f'<tr><td class="fg-file">{a(d["path"])}</td><td class="fg-nw">{", ".join(i.get("panels", [])) or "-"}</td>'
                           f'<td>{what}</td><td class="fg-nw">{when(d)}</td><td>{dep_status(d)}</td></tr>')
            out.append("</tbody></table></div>")
        else:
            out.append('<p class="fg-small">No data files: the figure is drawn from code alone.</p>')

        stale_notes = [s for s in r["stale"] if s["commits_since"]]
        if stale_notes:
            out.append('<p class="fg-small">Commits since the last render: '
                       + "; ".join(f'<code>{html.escape(s["path"])}</code>: '
                                   + ", ".join(html.escape(c) for c in s["commits_since"]) for s in stale_notes)
                       + "</p>")

        # panels
        if f.get("panels"):
            out.append("<h4>Panels</h4>")
            out.append('<div class="fg-scroll"><table class="fg-tab"><thead><tr><th>panel</th><th>shows</th><th>from</th></tr></thead><tbody>')
            for letter, p in f["panels"].items():
                src = "<br>".join(a(x, x.split("/")[-1]) if "*" not in x else f"<code>{html.escape(x)}</code>"
                                  for x in p.get("inputs", [])) or '<span class="fg-small">code only</span>'
                out.append(f'<tr><td class="fg-id"><b>{html.escape(str(letter))}</b></td><td>{html.escape(p["shows"])}</td>'
                           f'<td>{src}</td></tr>')
            out.append("</tbody></table></div>")

        # upstream
        if f.get("upstream"):
            out.append("<h4>Upstream: what makes the inputs</h4><ul class=\"fg-chain\">")
            for u in f["upstream"]:
                cmd = f' <code>{html.escape(u["command"])}</code>' if u.get("command") else ""
                note = f' <span class="fg-small">{html.escape(u["note"])}</span>' if u.get("note") else ""
                out.append(f'<li>{a(u["script"])} makes {html.escape(str(u["makes"]))}.{cmd}{note}</li>')
            out.append("</ul>")

        if r.get("related"):
            out.append("<h4>Related, not read by the script</h4><ul class=\"fg-chain\">")
            seen = set()
            for d in r["related"]:
                key = d["what"]
                if key in seen:
                    continue
                seen.add(key)
                grp = [x for x in r["related"] if x["what"] == key]
                files = grp[0]["path"] if len(grp) == 1 else f"{len(grp)} files: " + ", ".join(
                    x["path"].split("/")[-1] for x in grp)
                out.append(f'<li>{a(grp[0]["path"]) if len(grp) == 1 else html.escape(files)}: {html.escape(key)}</li>')
            out.append("</ul>")

        if f.get("gaps"):
            out.append('<h4>Reproducibility gaps</h4><ul class="fg-gaps">'
                       + "".join(f"<li>{html.escape(g)}</li>" for g in f["gaps"]) + "</ul>")

        out.append("</div>\n")

    (DOCS / PAGE).parent.mkdir(parents=True, exist_ok=True)
    (DOCS / PAGE).write_text("\n".join(out))


def Path_name(p):
    return p.rsplit("/", 1)[-1]


def _thumbnail(src, dst, width=1200):
    """Downscaled copy for PNGs too large to copy into the site; None without Pillow."""
    try:
        from PIL import Image
    except ImportError:
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(src)
    im.thumbnail((width, width * 4))
    im.save(dst, optimize=True)
    return dst
