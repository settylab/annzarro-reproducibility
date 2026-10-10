"""Lookup data for evidence references: archive snapshots and paper sections.

Reads two files that live next to the tool YAML:

  matrix/archive.yaml  URL -> {checked, status, final_url, archive, archive_timestamp, ...}
                       (read-only Wayback lookups; no snapshot was ever requested)
  matrix/papers.yaml   per tool: papers (doi, title, year, venue, archive) and, per paper,
                       `sections`: column id -> [{where, quote, indicates, note?}]

build.py and the re-seed (tools/import_notes.py) call:

  archive_for(url)            -> the archive.yaml entry for url, or None
  paper_refs(tool, column)    -> evidence items {kind: paper, ...} in the tool-file schema
  enrich(item)                -> fills a docs/paper item's missing checked/archive from the cache
  papers_for(tool)            -> the tool's paper list (empty list plus `none` reason for Loupe)

Nothing here touches the network.
"""
from __future__ import annotations

import functools
import pathlib
import urllib.parse

import yaml

HERE = pathlib.Path(__file__).resolve().parent.parent      # evidence/
ARCHIVE = HERE / "matrix/archive.yaml"
PAPERS = HERE / "matrix/papers.yaml"


@functools.lru_cache(maxsize=None)
def _archive() -> dict:
    if not ARCHIVE.exists():
        return {}
    return (yaml.safe_load(ARCHIVE.read_text()) or {}).get("urls") or {}


@functools.lru_cache(maxsize=None)
def _papers() -> dict:
    if not PAPERS.exists():
        return {}
    return (yaml.safe_load(PAPERS.read_text()) or {}).get("tools") or {}


def _variants(url: str):
    """The URL as cited, then without fragment, then with/without trailing slash, http/https."""
    yield url
    base = url.split("#", 1)[0] if "#?" not in url else url
    yield base
    yield base.rstrip("/")
    yield base.rstrip("/") + "/"
    p = urllib.parse.urlsplit(base)
    other = "http" if p.scheme == "https" else "https"
    yield urllib.parse.urlunsplit((other,) + tuple(p)[1:])


def archive_for(url: str) -> dict | None:
    """The cache entry for url (keys: checked, status, final_url, archive, archive_timestamp,
    dead, blocked, skipped). `archive` is a web.archive.org URL or None. Returns None when
    the URL was never looked up; rerun the lookup to add it."""
    db = _archive()
    saved_path = ARCHIVE.parent / "archive_saved.yaml"     # Save Page Now results (archive_save.py) win
    saved = (yaml.safe_load(saved_path.read_text()) or {}) if saved_path.exists() else {}
    for v in _variants(url):
        if (saved.get(v) or {}).get("archive"):
            entry = dict(db.get(v) or {})
            entry.update(archive=saved[v]["archive"], checked=entry.get("checked") or saved[v]["saved"])
            return entry
    for v in _variants(url):
        if v in db:
            return db[v]
    # a paper cited by its landing page rather than its DOI
    for u, e in db.items():
        if e.get("final_url") and e["final_url"].split("#")[0].rstrip("/") == url.split("#")[0].rstrip("/"):
            return e
    return None


def papers_for(tool: str) -> list[dict]:
    return (_papers().get(tool) or {}).get("papers") or []


def no_paper_reason(tool: str) -> str | None:
    """For a tool with no paper (Loupe), the reason, for the cell's `na: {paper: ...}`."""
    return (_papers().get(tool) or {}).get("none")


def _label(p: dict) -> str:
    return f'{p.get("cite") or p["key"]}, {p.get("venue", "")}'.rstrip(", ")


def paper_refs(tool: str, column: str, indicates: str | None = None) -> list[dict]:
    """Evidence items for one matrix cell from the tool's papers, in the tool-file schema:
    {kind: paper, url, label, where, quote, indicates, checked, archive}. `where` is the
    section or figure; `quote` is verbatim (<= 25 words). Pass indicates='Y' (or a tuple
    like ('P', 'N')) to keep only passages pointing one way. Empty list: the papers are
    silent on this column."""
    want = (indicates,) if isinstance(indicates, str) else indicates
    out = []
    for p in papers_for(tool):
        for s in (p.get("sections") or {}).get(column) or []:
            if want and s.get("indicates") not in want:
                continue
            item = {
                "kind": "paper",
                "url": p.get("url") or f'https://doi.org/{p["doi"]}',
                "label": _label(p),
                "where": s["where"],
                "quote": s["quote"],
                "indicates": s.get("indicates"),
                "checked": p.get("checked"),
                "archive": p.get("archive"),
            }
            if s.get("note"):
                item["note"] = s["note"]
            out.append(item)
    return out


def enrich(item: dict) -> dict:
    """Fill a docs or paper evidence item's missing `checked` and `archive` from the cache.
    Never overwrites values already set; returns the item for chaining."""
    if item.get("kind") not in ("docs", "paper") or not item.get("url"):
        return item
    e = archive_for(item["url"])
    if not e:
        return item
    if not item.get("checked") and e.get("checked"):
        item["checked"] = str(e["checked"])
    if not item.get("archive") and str(e.get("archive") or "").startswith("http"):
        item["archive"] = e["archive"]
    return item


if __name__ == "__main__":       # quick self-check: python evidence/tools/refs.py isee cells
    import json
    import sys
    tool, col = (sys.argv[1:3] + ["isee", "cells"])[:2]
    print(json.dumps(paper_refs(tool, col), indent=1, ensure_ascii=False))
    print(json.dumps(archive_for("https://isee.github.io/iSEE/articles/basic.html"), indent=1, default=str))
