#!/usr/bin/env python
"""Smoke check of a built evidence site, offline: run after `python evidence/build.py --site`.

1. Page count: every Markdown page of the build has its HTML page; fewer HTML pages than --expect
   fails, more only prints a note (a newly linked note becomes a page; HOSTING.md records the count).
2. Every HTML page holds a page body and no unrendered template.
3. The matrix page carries the Fig. 1c model hash, and `build.py --check` passes: the YAML marks
   are the figure's, and the built matrix is the figure's (model, legend, header, strip, sizes).
4. No local link is broken (evidence/tools/linkcheck.py, local files only, no network).
5. Claims: every claim id is its own section of the search index (claims.html#<id>, title = the id),
   and every claim row says where the site shows it: a "shown in" link whose page and anchor exist,
   or "not drawn: <reason>". A target the current release does not draw yet is listed, not failed.
   With --browser (needs Playwright): types five claim ids of different kinds into the site's search
   box and checks that the first section hit is that claim's row.

Exit status 0 when all pass. Usage: python evidence/tools/site_smoke.py [--expect N]
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EV = HERE.parent
REPO = EV.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", type=int, help="expected number of HTML pages")
    ap.add_argument("--browser", metavar="URL", help="also run the search test in headless Chromium against URL")
    a = ap.parse_args()
    site, docs = EV / "_build/site", EV / "_build/docs"
    fails = []
    html = sorted(p for p in site.rglob("*.html"))
    md = sorted(p for p in docs.rglob("*.md"))
    def built(m):                       # MkDocs turns README.md into index.html
        r = m.relative_to(docs)
        return site / (r.with_name("index.html") if r.name == "README.md" else r.with_suffix(".html"))
    missing = [m for m in md if not built(m).exists()]
    print(f"pages: {len(html)} HTML, {len(md)} Markdown")
    if missing:
        fails.append(f"{len(missing)} Markdown pages without HTML, e.g. {missing[0].relative_to(docs)}")
    if a.expect is not None and len(html) < a.expect:      # fewer pages: something was not built
        fails.append(f"expected at least {a.expect} HTML pages, found {len(html)}")
    elif a.expect is not None and len(html) > a.expect:    # more: a page was added; every page is still checked
        print(f"note: {len(html)} HTML pages, more than the {a.expect} expected (update HOSTING.md)")
    for p in html:
        t = p.read_text(errors="replace")
        if "md-content" not in t or "{{" in t and "}}" in t and "{{ " in t:
            fails.append(f"{p.relative_to(site)}: no page body or an unrendered template")
    m = re.search(r"fig1c-model ([0-9a-f]{16})", (site / "matrix.html").read_text())
    print("matrix model:", m.group(1) if m else "MISSING")
    if not m:
        fails.append("matrix.html has no Fig. 1c model hash")
    r = subprocess.run([sys.executable, str(EV / "build.py"), "--check"], cwd=REPO, capture_output=True, text=True)
    if "SERVED" in r.stderr:            # right after a build the built matrix must be the figure's
        fails.append("the built matrix differs from the figure:\n" + "\n".join(
            l for l in r.stderr.splitlines() if l.startswith("SERVED")))
    print("build.py --check:", "pass" if r.returncode == 0 else "FAIL")
    if r.returncode:
        fails.append("build.py --check failed:\n" + r.stderr[-3000:])
    r = subprocess.run([sys.executable, str(HERE / "linkcheck.py"), str(site)], cwd=REPO, capture_output=True, text=True)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    print("linkcheck:", last)
    if r.returncode or " 0 broken" not in last:
        fails.append("linkcheck: " + last)
    off, globs = OFF_SITE(), SUPERSEDED_FILES()
    import fnmatch
    rel_md = lambda f: re.sub(r"\.html$", ".md", f.relative_to(site / "repo").as_posix())
    leaked = [rel_md(f) for f in (site / "repo").rglob("*")
              if f.is_file() and (off.search(rel_md(f)) or any(fnmatch.fnmatch(rel_md(f), g) for g in globs))]
    print(f"off-site records (HISTORY, out of scope, superseded): {len(leaked)} on the site")
    if leaked:
        fails.append(f"{len(leaked)} superseded or out-of-scope records on the site, e.g. {leaked[0]}")
    todo = [p.relative_to(site).as_posix() for p in list(html) + [site / "search/search_index.json"]
            if "PAPER_TODO" in p.read_text(errors="replace")]
    print(f"internal to-do list mentioned on {len(todo)} pages")
    if todo:
        fails.append(f"PAPER_TODO (the authors' internal list) appears in built pages, e.g. {todo[:3]}")
    fails += image_checks(site, html, a.browser)
    fails += claims_checks(site, a.browser)
    for f in fails:
        print("FAIL", f, file=sys.stderr)
    return 1 if fails else 0


MAGIC = {".png": b"\x89PNG", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".gif": b"GIF8", ".webp": b"RIFF"}


def image_checks(site, pages, browser_url=None):
    """Every <img> of every page: the file exists, is not empty, starts with its format's magic bytes, and a
    `?v=<hash>` (cache-busting, build.version_images) is the hash of that file's content. With --browser: each
    image of every page also loads in headless Chromium (HTTP 200, naturalWidth > 0, lazy images forced)."""
    import hashlib
    from urllib.parse import unquote
    fails, n, seen = [], 0, {}
    for pg in pages:
        for m in re.finditer(r'<img\b[^>]*?\bsrc="([^"]+)"', pg.read_text(errors="replace")):
            src = m.group(1)
            if re.match(r"(https?:|data:|//)", src):
                continue
            n += 1
            path, _, query = unquote(src).partition("?")
            f = (pg.parent / path).resolve()
            if not f.is_file() or f.stat().st_size == 0:
                fails.append(f"{pg.relative_to(site)}: image {src} is missing or empty")
                continue
            magic = MAGIC.get(f.suffix.lower())
            if magic and not f.read_bytes()[:8].startswith(magic):
                fails.append(f"{pg.relative_to(site)}: image {src} is not a valid {f.suffix} file")
            if query.startswith("v="):
                h = seen.get(f) or seen.setdefault(f, hashlib.sha1(f.read_bytes()).hexdigest()[:10])
                if query[2:] != h:
                    fails.append(f"{pg.relative_to(site)}: image {src} carries a stale cache-busting hash")
    print(f"images: {n} <img> on {len(pages)} pages, {len(fails)} bad")
    if browser_url:
        fails += image_browser_test(browser_url, [p.relative_to(site).as_posix() for p in pages
                                                      if 'http-equiv="refresh"' not in p.read_text(errors="replace")])   # redirect pages leave at once
    return fails


def image_browser_test(base, pages):
    from playwright.sync_api import sync_playwright
    fails, total = [], 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        for u in pages:
            pg.goto(base.rstrip("/") + "/" + u, timeout=120000)
            pg.evaluate("document.querySelectorAll('img').forEach(i => { i.loading = 'eager'; "
                        "if (!i.complete) { const s = i.src; i.src = ''; i.src = s } })")
            for _ in range(100):
                if pg.evaluate("[...document.images].every(i => i.complete)"):
                    break
                pg.wait_for_timeout(300)
            for src, ok, w in pg.evaluate("[...document.images].map(i => [i.currentSrc || i.src, i.complete, i.naturalWidth])"):
                total += 1
                if not ok or w == 0:
                    fails.append(f"{u}: image does not load in the browser: {src}")
        b.close()
    print(f"images in the browser: {total} loaded, {len(fails)} broken")
    return fails


def OFF_SITE():
    """build.py's rule for files the site never shows, read from its source (importing build.py runs git)."""
    src = (EV / "build.py").read_text()
    return re.compile(re.search(r'^OFF_SITE = re\.compile\((r".*")\)$', src, re.M).group(1)[2:-1])


def SUPERSEDED_FILES():
    """Whole-file globs evidence/superseded.yaml marks superseded (as build.py's off_site reads them)."""
    import yaml
    reg = yaml.safe_load((EV / "superseded.yaml").read_text())
    return [e["file"] for e in reg.get("superseded") or [] if "file" in e and "where" not in e]


def claims_checks(site, browser_url=None):
    import html as H
    import json
    fails = []
    page = (site / "claims.html").read_text()
    ids = re.findall(r'<h6 class="cl-h" id="([^"]+)">', page)
    index = {d["location"]: d for d in json.loads((site / "search/search_index.json").read_text())["docs"]}
    missing = [i for i in ids if index.get(f"claims.html#{i}", {}).get("title", "").strip() != i]
    print(f"claims: {len(ids)} rows; search sections for {len(ids) - len(missing)}")
    if missing:
        fails.append(f"{len(missing)} claim ids without their own search section, e.g. {missing[:3]}")
    rows = re.split(r'<h6 class="cl-h" id="', page)[1:]
    bad, pending, novis = [], [], 0
    for chunk in rows:
        cid = chunk.split('"', 1)[0]
        cell = chunk.split("</td>", 3)[:3]
        cell = "".join(cell)
        links = re.findall(r'class="cl-shown-link" href="([^"]+)"', cell)
        if "cl-novis" in cell:
            novis += 1
        elif "cl-pending" in cell and not links:
            pending.append(cid)
        elif not links:
            bad.append(f"{cid}: no 'shown in' link")
        for href in links:
            path, _, anchor = H.unescape(href).partition("#")
            f = site / path
            if not f.exists():
                bad.append(f"{cid}: {path} does not exist")
            elif anchor and f'id="{anchor}"' not in f.read_text(errors="replace"):
                bad.append(f"{cid}: {path} has no #{anchor}")
    import claim_targets
    bad += [f"{cid}: row says neither where it is shown nor why not" for cid in claim_targets.rows_without_target(page)
            if not any(b.startswith(cid + ":") for b in bad)]
    print(f"claims: {len(rows) - len(bad) - len(pending) - novis} shown, {novis} not drawn (with a reason), "
          f"{len(pending)} waiting for the release's data" + (f": {', '.join(pending[:8])}{' ...' if len(pending) > 8 else ''}" if pending else ""))
    fails += bad
    if browser_url:
        fails += search_test(browser_url)
    return fails


def search_ids():
    """Five claim ids of different kinds from the current ledger: a number, a comparison with a matrix
    source, a qualitative claim, a comparison without one, an interim claim."""
    import yaml
    claims = yaml.safe_load((EV / "claims.yaml").read_text())["claims"]

    def has_matrix(c):
        src = c.get("source")
        return any(isinstance(x, dict) and "matrix" in x for x in (src if isinstance(src, list) else [src]))
    picks = [lambda c: c.get("kind") == "number" and c.get("status", "ok") == "ok",
             lambda c: c.get("kind") == "comparison" and has_matrix(c),
             lambda c: c.get("kind") == "qualitative" and c.get("status", "ok") == "ok",
             lambda c: c.get("kind") == "comparison" and not has_matrix(c),
             lambda c: c.get("status") == "interim"]
    return [next(k for k, c in sorted(claims.items()) if isinstance(c, dict) and f(c)) for f in picks]


def search_test(base):
    """Type ids of five kinds (number, matrix comparison, qualitative, comparison, interim) into the search box."""
    import time
    from playwright.sync_api import sync_playwright
    fails = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page()
        pg.goto(f"{base.rstrip('/')}/index.html")
        for q in search_ids():
            pg.evaluate("document.querySelector('input.md-search__input').focus()")
            pg.fill("input.md-search__input", "")
            pg.type("input.md-search__input", q)
            time.sleep(1.5)
            hrefs = pg.evaluate("[...document.querySelectorAll('li.md-search-result__item a')].map(a=>a.getAttribute('href'))")
            first = next((h for h in hrefs if "#" in h), None)
            ok = bool(first) and first.split("#", 1)[1] == q and "claims.html" in first
            print(f"search {q!r}: first section hit {first}")
            if not ok:
                fails.append(f"search {q!r}: first section hit is {first}, not claims.html#{q}")
        b.close()
    return fails


if __name__ == "__main__":
    sys.exit(main())
