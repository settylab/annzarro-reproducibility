"""Tests for fetch_demo_store.store_md5 (the docs' store md5). Run: python -m pytest data_prep/test_fetch_demo_store.py

The two store tests need the stores on this host and are skipped without them:
  the showcase store: $ANNZARRO_DEMO_STORE or data/bm_aging_annzarro.zarr  -> a372502012ded8cd238e5eb83e408b89
  the source store:   data/bm_aging.zarr                                    -> b0d150cf4161887febefafe460b0a4b4
"""
import hashlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_demo_store as f  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_sort_is_by_path_parts_not_strings(tmp_path):
    # as strings "a-x/c" < "a/b" ('-' sorts before '/'); as Path objects a/b comes first
    for rel in ("a/b", "a-x/c"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(rel.encode())
    h = hashlib.md5()
    for rel in ("a/b", "a-x/c"):
        h.update(rel.encode() + rel.encode())
    assert f.store_md5(tmp_path) == (h.hexdigest(), 2)


def test_showcase_store_md5():
    p = Path(os.environ.get("ANNZARRO_DEMO_STORE") or ROOT / "data" / "bm_aging_annzarro.zarr")
    if not p.is_dir():
        pytest.skip("the showcase store is not on this host")
    assert f.store_md5(p) == (f.STORE_MD5, f.STORE_FILES)


def test_source_store_md5():
    p = ROOT / "data" / "bm_aging.zarr"
    if not p.is_dir():
        pytest.skip("data/bm_aging.zarr is not on this host")
    assert f.store_md5(p) == ("b0d150cf4161887febefafe460b0a4b4", 3301)
