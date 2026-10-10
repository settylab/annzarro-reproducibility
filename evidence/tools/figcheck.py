#!/usr/bin/env python
"""Is each manuscript figure older than what it is made from?

Reads evidence/figures.yaml. For every figure it dates the outputs, the script, the code the
script imports and every input: the last commit touching the file (git log -1 --format='%h %cI'),
or the file's mtime when the file has uncommitted changes, is untracked or is gitignored.

  STALE  an input, the script or its code is newer than the newest output (the last
         render), and changed in
         substance. A Python file whose change since the output's commit touches only
         docstrings and comments (same AST once docstrings are dropped) is reported as
         doc-only and does not set STALE on its own
  DIRTY  an output, input or script has uncommitted changes (or is untracked)

An input may declare `reads: {where: {col: value, ...}, columns: [...]}`: a CSV of which the script reads only
those rows and columns (fig_scale.py reads the annzarro v041 row of ceilings.csv). It is dated by the last
commit that changed that slice, not by the last commit to the file, so another tool's row, or a guard-off
row the figure does not draw, does not make the figure STALE; a change to what the script reads does.

An input marked `external: true` (gitignored or outside the repository) is dated by mtime and
reported, but never makes a figure STALE: its mtime says when it was last written, not when its
content changed. When it is not on the host running the check, it is reported as "not on this host,
not checked here" (not as missing): nothing is claimed about it. Its `identity:` in figures.yaml says
what it should be.

Usage:
  python evidence/tools/figcheck.py                 # table for every figure; exit 1 if any STALE
  python evidence/tools/figcheck.py --json          # machine-readable
  python evidence/tools/figcheck.py --render scale  # re-run one figure's script into a scratch dir
                                                    # and compare image dimensions with the committed PNG

--render never writes manuscript/figures or figures/numbers: the script runs with
figures.style.save and figures._load.write_numbers redirected to the scratch dir, and the
check fails if either directory changed during the run. Only scripts listed in RENDERABLE
(fast, no app server, no browser) may be rendered.
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import struct
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "evidence" / "figures.yaml"
RENDERABLE = {"figures/fig5_app.py", "figures/fig_scale.py", "figures/fig6_performance.py",
              "figures/fig1_overview.py", "figures/fig_comparison.py",
              # these three only read the demo store (read-only) and draw: no server, no browser
              "figures/fig2_cell_by_cell.py", "figures/fig3_gene_by_gene.py", "figures/fig4_cells_by_genes.py"}
STORE_ENV = "ANNZARRO_DEMO_STORE"      # path of the demo store on this host (default: data/bm_aging_annzarro.zarr)
GUARDED = [REPO / "manuscript" / "figures", REPO / "figures" / "numbers"]
MAX_WALK = 50_000            # files walked to date a directory by mtime


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True).stdout.strip()


def _status_map():
    """path -> porcelain status code, for every modified or untracked path (one git call)."""
    out = {}
    for ln in git("status", "--porcelain", "-uall").splitlines():
        code, path = ln[:2], ln[3:]
        if " -> " in path:
            path = path.split(" -> ")[1]
        out[path.strip('"')] = code
    return out


STATUS = None


def _mtime(p: Path):
    if p.is_file():
        return p.stat().st_mtime
    if p.is_dir():
        best, n = p.stat().st_mtime, 0
        for root, _dirs, files in os.walk(p):
            for f in files:
                try:
                    best = max(best, os.stat(os.path.join(root, f)).st_mtime)
                except OSError:
                    pass
                n += 1
                if n > MAX_WALK:
                    return best
        return best
    return None


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).astimezone().isoformat(timespec="seconds")


def date_file(path: str, external=False):
    """Provenance of one path (repo-relative or absolute)."""
    global STATUS
    if STATUS is None:
        STATUS = _status_map()
    absolute = Path(path).is_absolute()
    p = Path(path) if absolute else REPO / path
    rec = {"path": path, "exists": p.exists(), "external": bool(external or absolute),
           "sha": None, "commit_time": None, "mtime": None, "state": "missing", "time": None, "basis": None}
    if not p.exists():
        return rec
    rec["mtime"] = _mtime(p)
    if absolute:
        rec.update(state="outside repo", time=rec["mtime"], basis="mtime")
        return rec
    log = git("log", "-1", "--format=%h %cI %ct", "--", path)
    if log:
        sha, ci, ct = log.split()
        rec.update(sha=sha, commit_time=ci, time=float(ct), basis="commit")
    dirty_codes = [c for k, c in STATUS.items() if k == path or k.startswith(path.rstrip("/") + "/")]
    ignored = not log and (external or bool(git("check-ignore", path)))   # external inputs are not tracked by definition
    if ignored:
        rec.update(state="ignored", time=rec["mtime"], basis="mtime")
    elif not log:
        rec.update(state="untracked", time=rec["mtime"], basis="mtime")
    elif dirty_codes:
        rec.update(state="dirty", time=max(rec["time"], rec["mtime"]), basis="mtime")
    else:
        rec["state"] = "clean"
    return rec


def _code_ast(src):
    """AST dump of Python source without docstrings; None if it does not parse."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(getattr(body[0], "value", None), ast.Constant) \
                and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree)


def doc_only(path, since_sha):
    """True if a .py file differs from its state at since_sha only in docstrings and comments."""
    if not path.endswith(".py") or not since_sha:
        return False
    old = subprocess.run(["git", "-C", str(REPO), "show", f"{since_sha}:{path}"],
                         capture_output=True, text=True)
    if old.returncode:
        return False
    a, b = _code_ast(old.stdout), _code_ast((REPO / path).read_text())
    return a is not None and a == b


def _csv_slice(text, reads):
    """The rows of a CSV text that match reads['where'], restricted to reads['columns'] (a tuple, for comparing)."""
    import csv
    import io
    where, cols = reads.get("where", {}), reads.get("columns")
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        if all(row.get(k) == str(v) for k, v in where.items()):
            out.append(tuple(row.get(c) for c in (cols or sorted(row))))
    return tuple(out)


def slice_date(path, reads):
    """(sha, commit time) of the newest commit that changed the rows and columns the script reads, or the
    file's oldest commit when no commit changed them (the slice has been the same since it was added)."""
    log = git("log", "--format=%h %ct", "--", path).splitlines()
    if not log:
        return None
    for ln in log:
        sha, ct = ln.split()
        cur = subprocess.run(["git", "-C", str(REPO), "show", f"{sha}:{path}"], capture_output=True, text=True)
        par = subprocess.run(["git", "-C", str(REPO), "show", f"{sha}^:{path}"], capture_output=True, text=True)
        if cur.returncode or par.returncode or _csv_slice(cur.stdout, reads) != _csv_slice(par.stdout, reads):
            return sha, float(ct)
    sha, ct = log[-1].split()
    return sha, float(ct)


def expand(path):
    """A path or glob -> list of repo-relative (or absolute) paths; a non-matching glob stays as is."""
    if any(c in path for c in "*?["):
        base = "" if Path(path).is_absolute() else str(REPO) + "/"
        hits = sorted(glob.glob(base + path))
        return [h[len(base):] for h in hits] or [path]
    return [path]


def check_figure(fig):
    outs = [date_file(o) for o in fig.get("outputs", [])]
    others = [date_file(o) for o in fig.get("other_outputs", [])]
    deps = []
    if fig.get("script"):
        deps.append(("script", date_file(fig["script"])))
    for c in fig.get("code", []) or []:
        if c != fig.get("script"):
            deps.append(("code", date_file(c)))
    for inp in fig.get("inputs", []) or []:
        for p in expand(inp["path"]):
            if inp.get("store"):         # the demo store: located (env var or data/), then verified by its md5
                sp = store_path(p)
                d = date_file(str(sp) if sp else p, True)
                d["path"] = p
                d["store"] = dict(inp["store"], here=check_store(inp["store"], sp))
                deps.append(("input", d))
                continue
            d = date_file(p, inp.get("external", False))
            if inp.get("reads") and d["state"] == "clean" and d["basis"] == "commit":
                sd = slice_date(p, inp["reads"])
                if sd:
                    d.update(sha=sd[0], time=sd[1], basis="commit (rows read)")
            deps.append(("input", d))
    present = [o for o in outs if o["time"] is not None]
    # One run of the script writes every output (figures.style.save writes .png and .pdf), and git
    # records no commit for an output a re-render left byte-identical, so the newest output dates
    # the last render.
    newest = max(present, key=lambda o: o["time"]) if present else None
    out_time = newest["time"] if newest else None
    out_sha = newest["sha"] if newest else None
    # A recorded reproduction (`reproduced: {commit, date, host, result}` in figures.yaml) is a render at that commit
    # whose output was byte-identical: git has no output commit for it, so it dates the last verified render.
    repro = fig.get("reproduced")
    ref_time = out_time                 # what inputs are compared with: the last render, or the last verified reproduction
    if repro and out_time is not None:
        ct = git("log", "-1", "--format=%ct", repro["commit"])
        if ct:
            ref_time = max(out_time, float(ct))
    stale, dirty = [], []
    for o in outs:
        if o["state"] in ("dirty", "untracked"):
            dirty.append({"role": "output", "path": o["path"], "state": o["state"]})
    for role, d in deps:
        d["role"] = role
        d["stale"] = False
        if d["state"] in ("dirty", "untracked"):
            dirty.append({"role": role, "path": d["path"], "state": d["state"]})
        if ref_time is not None and d["time"] is not None and not d["external"] and d["time"] > ref_time:
            d["stale"] = True
            since = git("log", "--format=%h %cd %s", "--date=short", f"--since={int(ref_time) + 1}", "--", d["path"]) \
                if d["basis"] == "commit" else ""
            d["doc_only"] = doc_only(d["path"], out_sha)
            stale.append({"role": role, "path": d["path"], "by": d["time"] - ref_time,
                          "doc_only": d["doc_only"], "commits_since": since.splitlines()[:5]})
    related = [dict(date_file(p), what=r.get("what", "")) for r in fig.get("related", []) or []
               for p in expand(r["path"])]
    import fignum
    return {"id": fig["id"], "number": fignum.fig(fig["label"]), "label": fig["label"], "outputs": outs,
            "other_outputs": others, "deps": [d for _, d in deps], "related": related,
            "out_time": out_time, "out_sha": out_sha,
            "stale": stale, "is_stale": any(not x["doc_only"] for x in stale), "dirty": dirty, "reproduced": repro,
            "store_differs": [d["path"] for _, d in deps if (d.get("store") or {}).get("here", {}) and
                              d["store"]["here"]["state"] == "DIFFERS"],
            # an external input that is not on this host cannot be checked here: reported as such, never as missing
            "not_on_host": [d["path"] for _, d in deps if not d["exists"] and d["external"]],
            "missing": [d["path"] for _, d in deps if not d["exists"] and not d["external"]]
            + [o["path"] for o in outs if not o["exists"]]}


def load_spec():
    return yaml.safe_load(SPEC.read_text())["figures"]


def check_all():
    return [check_figure(f) for f in load_spec()]


# --------------------------------------------------------------------------- the demo store
def _fetch_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("fetch_demo_store", REPO / "data_prep" / "fetch_demo_store.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def store_path(default="data/bm_aging_annzarro.zarr"):
    """The demo store on this host: $ANNZARRO_DEMO_STORE, else data/<name>; None when this host does not have it."""
    p = Path(os.environ[STORE_ENV]) if os.environ.get(STORE_ENV) else REPO / default
    return p if p.is_dir() else None


_STORE_CHECKS = {}


def check_store(spec, path):
    """Verify the demo store on this host against the identity in figures.yaml: its md5 (the docs' rule, see
    data_prep/fetch_demo_store.py) and file count. None if the store is not here; hashing is skipped, and said so,
    when FIGCHECK_SKIP_STORE_MD5 is set (a 5.7 GB read)."""
    if path is None:
        return None
    key = (str(path), spec.get("md5"))
    if key not in _STORE_CHECKS:
        if os.environ.get("FIGCHECK_SKIP_STORE_MD5"):
            _STORE_CHECKS[key] = {"path": str(path), "state": "skipped"}
        else:
            md5, n = _fetch_module().store_md5(path)
            ok = md5 == spec["md5"] and n == spec.get("files", n)
            _STORE_CHECKS[key] = {"path": str(path), "state": "verified" if ok else "DIFFERS", "md5": md5, "files": n}
    return _STORE_CHECKS[key]


# --------------------------------------------------------------------------- render
def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def _snapshot():
    snap = {}
    for d in GUARDED:
        for p in d.rglob("*"):
            if p.is_file():
                st = p.stat()
                snap[str(p)] = (st.st_mtime_ns, st.st_size)
    return snap


RUNNER = r"""
import runpy, sys
from pathlib import Path
repo, script, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
sys.path.insert(0, repo)
import figures.style as style
style.save.__defaults__ = (out,)
try:
    import figures._load as load
    load.NUMBERS_DIR = out / "numbers"
    (out / "numbers").mkdir(exist_ok=True)
except Exception:
    pass
sys.argv = [script]
runpy.run_path(str(Path(repo) / script), run_name="__main__")
"""


def render(fig, python, scratch=None):
    script = fig.get("script")
    if script not in RENDERABLE:
        sys.exit(f"--render: {fig['id']} ({script}) is not in RENDERABLE (slow, needs a server or a browser)")
    out = Path(tempfile.mkdtemp(prefix=f"figcheck_{fig['id']}_", dir=scratch))
    before = _snapshot()
    r = subprocess.run([python, "-c", RUNNER, str(REPO), script, str(out)], cwd=REPO,
                       capture_output=True, text=True)
    after = _snapshot()
    if before != after:
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        sys.exit("--render: GUARDED directories changed during the run (this must not happen): "
                 + ", ".join(changed))
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-4000:], sep="\n")
        sys.exit(f"--render: {script} failed (exit {r.returncode}); scratch dir {out}")
    rows = []
    for o in fig["outputs"]:
        if not o.endswith(".png"):
            continue
        new = out / Path(o).name
        a = png_size(REPO / o) if (REPO / o).exists() else None
        b = png_size(new) if new.exists() else None
        same_bytes = a is not None and b is not None and (REPO / o).read_bytes() == new.read_bytes()
        detail = "identical bytes" if same_bytes else "bytes differ"
        if not same_bytes and a is not None and a == b:
            try:                                           # same size, different bytes: how many pixels differ?
                from PIL import Image, ImageChops
                Image.MAX_IMAGE_PIXELS = None
                diff = ImageChops.difference(Image.open(REPO / o).convert("RGBA"), Image.open(new).convert("RGBA"))
                n = sum(1 for px in diff.getdata() if any(px))
                detail = f"bytes differ, {n} pixels differ" if n else "bytes differ, every pixel identical (encoder metadata)"
            except ImportError:
                detail = "bytes differ (Pillow not available for a pixel diff)"
        rows.append((o, a, b, "same size" if a == b else "DIFFERENT", detail))
    print(f"rendered into {out}")
    for o, a, b, verdict, by in rows:
        print(f"  {o}: committed {a}  rendered {b}  {verdict}, {by}")
    for o in fig.get("other_outputs", []) or []:           # numbers a caption quotes: compare the JSON values
        new = out / "numbers" / Path(o).name
        if o.endswith(".json") and new.exists() and (REPO / o).exists():
            same = json.loads((REPO / o).read_text()) == json.loads(new.read_text())
            print(f"  {o}: {'identical values' if same else 'VALUES DIFFER'}")
            rows.append((o, None, None, "same size" if same else "DIFFERENT", "identical values" if same else "values differ"))
    return rows


# --------------------------------------------------------------------------- report
def fmt_age(seconds):
    d = seconds / 86400
    return f"{d:.1f} d" if d >= 1 else f"{seconds / 3600:.1f} h"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--render", metavar="FIG_ID", help="re-run this figure's script into a scratch dir")
    ap.add_argument("--python", default=str(REPO / ".venv" / "bin" / "python"),
                    help="interpreter for --render (default: the repo's .venv)")
    ap.add_argument("--scratch", default=None, help="parent of the --render output dir (default: $TMPDIR)")
    a = ap.parse_args()
    if a.render:
        figs = {f["id"]: f for f in load_spec()}
        if a.render not in figs:
            sys.exit(f"unknown figure id {a.render}; known: {', '.join(figs)}")
        rows = render(figs[a.render], a.python, a.scratch)
        return 1 if any(r[3] != "same size" for r in rows) else 0
    res = check_all()
    if a.json:
        print(json.dumps(res, indent=1, default=str))
        return 1 if any(r["is_stale"] for r in res) else 0
    for r in res:
        flags = (["STALE"] if r["is_stale"] else ["doc-only"] if r["stale"] else []) \
            + (["DIRTY"] if r["dirty"] else [])
        when = _iso(r["out_time"]) if r["out_time"] else "-"
        print(f"{r['number']:<24} {r['label']:<16} {' '.join(flags) or 'ok':<12} "
              f"last render {r['out_sha'] or '-'} {when}")
        for s in r["stale"]:
            kind = "doc-only" if s["doc_only"] else "STALE"
            print(f"    {kind:<8} {s['role']:<6} {s['path']}  newer by {fmt_age(s['by'])}")
            for c in s["commits_since"]:
                print(f"             {c}")
        for d in r["dirty"]:
            print(f"    DIRTY  {d['role']:<6} {d['path']} ({d['state']})")
        for m in r["missing"]:
            print(f"    MISSING {m}")
        for m in r["not_on_host"]:
            print(f"    NOT ON THIS HOST (external input, not checked here) {m}")
        for d in r["deps"]:
            st = d.get("store")
            if st and st.get("here"):
                h = st["here"]
                print(f"    STORE {h['state']}: {h['path']}" + (f" md5 {h['md5']} ({h['files']} files)" if h.get("md5") else ""))
        for m in r["store_differs"]:
            print(f"    STORE DIFFERS from the recorded identity: {m}")
        if r.get("reproduced"):
            q = r["reproduced"]
            print(f"    reproduced at {q['commit']} on {q['date']} ({q['host']}): {q['result']}")
    return 1 if any(r["is_stale"] or r["store_differs"] for r in res) else 0


if __name__ == "__main__":
    sys.exit(main())
