#!/usr/bin/env python
"""Fetch the AnnZarro showcase store (murine bone-marrow ageing) from Zenodo and verify it.

The store is `bm_aging_annzarro.zarr` (Zenodo record 10.5281/zenodo.23277102, all versions; the files are pinned to
version 1.0, record 23277103). It holds everything `data/bm_aging.zarr` holds, unchanged, plus the fields the AnnZarro
documentation and the paper's figure pages use; the paper's figures 4 to 6 read only the unchanged
arrays. Steps:

  1. download `bm_aging_annzarro.zarr.zip` (5.7 GB) and the record's `SHA256SUMS`;
  2. check the zip's sha256 against SHA256SUMS and against the value pinned below;
  3. unzip into data/ (git ignores it): data/bm_aging_annzarro.zarr, 4,243 files;
  4. check the store md5: md5 over every file of the directory, in sorted relative-path order, each
     file contributing its relative path (UTF-8) followed by its bytes; the files are sorted as pathlib.Path
     objects (part by part), which differs from sorting the path strings where a name has `-` or `.`.

Usage (from the repository root):
  python data_prep/fetch_demo_store.py                 # download, verify, unzip into data/
  python data_prep/fetch_demo_store.py --check DIR     # only verify a store directory (no download)
  python data_prep/fetch_demo_store.py --zip FILE      # use an already downloaded zip

Exit status 0 when every check passes. If the files cannot be downloaded, the script says so and
stops (it never reports a download that did not happen).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

DOI = "10.5281/zenodo.23277102"   # concept DOI: cite this; it resolves to the latest version
RECORD = "https://zenodo.org/records/23277103/files"   # files stay pinned to version 1.0
ZIP_NAME = "bm_aging_annzarro.zarr.zip"
STORE_NAME = "bm_aging_annzarro.zarr"
ZIP_SHA256 = "ba42a5fd921871eac31de19ef6528d1e0d7a33a6cee5c2d2728d2801f40d1131"
STORE_MD5 = "a372502012ded8cd238e5eb83e408b89"
STORE_FILES = 4243
ROOT = Path(__file__).resolve().parent.parent


def store_md5(path) -> tuple[str, int]:
    """(md5, number of files): md5 over sorted relative path, then bytes, of every file of the directory."""
    root = Path(path)
    h = hashlib.md5()
    # Path objects sort part by part (obs/a/b before obs/a-x/c), not as strings: the docs' function, exactly
    files = sorted(f for f in root.rglob("*") if f.is_file())
    for f in files:
        h.update(f.relative_to(root).as_posix().encode())
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest(), len(files)


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, dest: Path):
    """Download url to dest (resumes a partial file). Exits with a plain message if the record is not public."""
    have = dest.stat().st_size if dest.exists() else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    try:
        with urllib.request.urlopen(req) as r, open(dest, "ab" if have else "wb") as out:
            total = int(r.headers.get("Content-Length", 0)) + have
            got = have
            while chunk := r.read(1 << 22):
                out.write(chunk)
                got += len(chunk)
                print(f"\r  {got / 2**30:.2f} of {total / 2**30:.2f} GiB", end="", file=sys.stderr)
            print(file=sys.stderr)
    except urllib.error.HTTPError as e:
        if e.code == 416:                      # the partial file is already the whole file
            return
        sys.exit(f"cannot download {url}: HTTP {e.code}. See the Zenodo record {DOI}.")
    except urllib.error.URLError as e:
        sys.exit(f"cannot download {url}: {e.reason}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "data"), help="directory that receives the store (default: data/)")
    ap.add_argument("--zip", help="an already downloaded zip (skips the download)")
    ap.add_argument("--check", metavar="DIR", help="only verify this store directory")
    a = ap.parse_args()
    if a.check:
        md5, n = store_md5(a.check)
        ok = md5 == STORE_MD5 and n == STORE_FILES
        print(f"{a.check}: {n} files, store md5 {md5}: {'OK' if ok else 'DIFFERS from ' + STORE_MD5}")
        return 0 if ok else 1
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    zpath = Path(a.zip) if a.zip else out / ZIP_NAME
    if not a.zip:
        print(f"downloading {RECORD}/{ZIP_NAME}")
        download(f"{RECORD}/{ZIP_NAME}", zpath)
        sums = out / "SHA256SUMS"
        download(f"{RECORD}/SHA256SUMS", sums)
        listed = {ln.split()[-1].lstrip("*"): ln.split()[0] for ln in sums.read_text().splitlines() if ln.strip()}
        if listed.get(ZIP_NAME) != ZIP_SHA256:
            sys.exit(f"SHA256SUMS lists {listed.get(ZIP_NAME)} for {ZIP_NAME}, this script expects {ZIP_SHA256}")
    got = file_sha256(zpath)
    if got != ZIP_SHA256:
        sys.exit(f"{zpath}: sha256 {got} differs from {ZIP_SHA256}")
    print(f"zip sha256 OK {got}")
    with zipfile.ZipFile(zpath) as z:
        z.extractall(out)
    md5, n = store_md5(out / STORE_NAME)
    if md5 != STORE_MD5 or n != STORE_FILES:
        sys.exit(f"{out / STORE_NAME}: {n} files, store md5 {md5}; expected {STORE_FILES} files, {STORE_MD5}")
    print(f"store md5 OK {md5} ({n} files): {out / STORE_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
