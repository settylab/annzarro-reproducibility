#!/usr/bin/env python
"""Check a built site's internal links: every href/src that stays inside the site must resolve.

Also flags root-absolute links ("/x"), which break when the site is served from a sub-path,
and lists files nothing links to (--orphans; --prune deletes those under the given prefixes).

Usage: linkcheck.py SITE_DIR [--orphans] [--prune repo/ annotated/]
Exit 1 on any broken or root-absolute link.
"""
from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("href", "src") and v:
                self.links.append(v)
            if k in ("id", "name") and v:
                self.ids.add(v)


def parse(f):
    p = Links()
    p.feed(f.read_text(errors="replace"))
    return p


def check(site: Path):
    pages = {f: parse(f) for f in site.rglob("*.html")}
    referenced, broken, absolute = set(), [], []
    for f, p in pages.items():
        for link in p.links:
            u = urlsplit(link)
            if u.scheme or link.startswith(("//", "mailto:", "data:", "javascript:")):
                continue
            if link.startswith("/"):
                absolute.append((f, link))
                continue
            if not u.path:                                  # same-page anchor
                if u.fragment and u.fragment not in p.ids:
                    broken.append((f, link, "missing anchor"))
                continue
            target = (f.parent / unquote(u.path)).resolve()
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                broken.append((f, link, "missing file"))
                continue
            referenced.add(target)
            if u.fragment and target.suffix == ".html" and target in pages and u.fragment not in pages[target].ids:
                broken.append((f, link, "missing anchor"))
    # CSS url(...) references (fonts, icons)
    for css in site.rglob("*.css"):
        for m in re.finditer(r"url\(['\"]?([^)'\"]+)", css.read_text(errors="replace")):
            if not urlsplit(m.group(1)).scheme and not m.group(1).startswith("data:"):
                referenced.add((css.parent / m.group(1).split("#")[0].split("?")[0]).resolve())
    return pages, referenced, broken, absolute


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site", type=Path)
    ap.add_argument("--orphans", action="store_true")
    ap.add_argument("--prune", nargs="*", default=None, help="delete unreferenced files under these prefixes")
    a = ap.parse_args()
    site = a.site.resolve()
    pages, referenced, broken, absolute = check(site)
    if a.prune is not None:
        gone = 0
        for f in list(site.rglob("*")):
            rel = f.relative_to(site).as_posix()
            if f.is_file() and rel.startswith(tuple(a.prune)) and f.resolve() not in referenced:
                f.unlink()
                gone += 1
        for d in sorted((d for d in site.rglob("*") if d.is_dir()), key=lambda d: -len(d.parts)):
            if not any(d.iterdir()):
                d.rmdir()
        print(f"pruned {gone} unreferenced files")
        pages, referenced, broken, absolute = check(site)
    files = [f for f in site.rglob("*") if f.is_file()]
    print(f"{len(pages)} pages, {len(files)} files, {sum(f.stat().st_size for f in files) / 2**20:.1f} MB; "
          f"{len(broken)} broken links, {len(absolute)} root-absolute links")
    for f, link, why in broken[:50]:
        print(f"BROKEN {f.relative_to(site)} -> {link} ({why})")
    for f, link in absolute[:20]:
        print(f"ABSOLUTE {f.relative_to(site)} -> {link}")
    if a.orphans:
        for f in files:
            if f.resolve() not in referenced and f.suffix != ".html":
                print("ORPHAN", f.relative_to(site))
    return 1 if broken or absolute else 0


if __name__ == "__main__":
    sys.exit(main())
