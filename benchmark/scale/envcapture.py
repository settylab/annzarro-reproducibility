"""Environment capture for every benchmark runner in benchmark/scale (stdlib only).

Each runner calls ``require_clean_bench()`` before it starts, and ``record()``
once it knows what it is measuring. ``record`` appends one entry per runner
invocation to ``<results stem>_environment.json`` next to the results:

  bench     commit and dirty flag of this repository's benchmark scripts
  annzarro  the checkout under test: commit, dirty flag, path, the version its
            interpreter's package metadata and ``annzarro.__version__`` report,
            and its Python and package versions
  server    the version the running server reports (/api/v1/status)
  browser   Chromium version and flags (when a browser is used)
  machine   host, CPU, cores, RAM, OS, and this harness's Python and packages
  run       argv, start time (UTC), and runner-specific fields

A run refuses to start when a tracked benchmark script under benchmark/scale
differs from the commit, or when an untracked script lies there, so every
result names the exact scripts that produced it.
"""
from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SCALE = Path(__file__).resolve().parent
REPO = SCALE.parents[1]
SCRIPT_EXT = (".py", ".sh", ".html", ".js")
PACKAGES = ["annzarro", "zarr", "numcodecs", "anndata", "numpy", "scipy", "flask", "werkzeug", "pandas", "h5py"]
HARNESS_PACKAGES = ["playwright", "psutil", "requests", "zarr", "numcodecs", "numpy"]


def _sh(cmd: list[str], cwd=None) -> str:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:   # recorded, never fatal
        return f"n/a ({type(e).__name__}: {e})"


def bench_state() -> dict:
    """Commit of this repository and the benchmark scripts that differ from it."""
    # not _sh: its strip() would eat the leading space of the first porcelain line
    status = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=all", "--",
                             str(SCALE.relative_to(REPO))], capture_output=True, text=True).stdout
    dirty = []
    for line in status.splitlines():
        path = line[3:].split(" -> ")[-1]
        if path.endswith(SCRIPT_EXT):
            dirty.append(line)
    return {"repo": str(REPO), "commit": _sh(["git", "-C", str(REPO), "rev-parse", "HEAD"]),
            "dirty": bool(dirty), "dirty_scripts": dirty}


def require_clean_bench():
    st = bench_state()
    if st["dirty"]:
        sys.exit("refusing to run: benchmark scripts differ from commit "
                 f"{st['commit'][:12]}; commit them first:\n  " + "\n  ".join(st["dirty_scripts"]))


_PROBE = r"""
import json, sys, importlib.metadata as md
out = {"python": sys.version, "executable": sys.executable, "packages": {}}
for p in PACKAGES:
    try: out["packages"][p] = md.version(p)
    except Exception: out["packages"][p] = None
try:
    import annzarro
    out["file"] = annzarro.__file__
    out["version_attr"] = getattr(annzarro, "__version__", None)
except Exception as e:
    out["import_error"] = repr(e)
print(json.dumps(out))
"""


def annzarro_state(exe: str | None = None, python: str | None = None) -> dict:
    """The AnnZarro under test, from the interpreter that runs it: ``exe`` is the
    ``annzarro`` console script (its sibling ``python`` is used) or ``python`` directly."""
    py = python or (str(Path(exe).with_name("python")) if exe else sys.executable)
    raw = _sh([py, "-c", f"PACKAGES = {PACKAGES!r}\n" + _PROBE])
    try:
        info = json.loads(raw.splitlines()[-1])
    except Exception:
        return {"python_exe": py, "error": raw[:500]}
    out = {"exe": exe, "python_exe": py, "python": info["python"], "packages": info["packages"],
           "version_metadata": info["packages"].get("annzarro"), "version_attr": info.get("version_attr")}
    if "file" in info:
        root = Path(info["file"]).resolve().parents[1]
        out["path"] = str(root)
        out["commit"] = _sh(["git", "-C", str(root), "rev-parse", "HEAD"])
        out["branch"] = _sh(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"])
        out["tag"] = _sh(["git", "-C", str(root), "describe", "--tags", "--exact-match", "HEAD"]) or None
        out["tree"] = _sh(["git", "-C", str(root), "rev-parse", "HEAD^{tree}"])   # the release's tree (tag check)
        tracked = _sh(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"])
        out["dirty"] = bool(tracked)
        out["dirty_files"] = tracked.splitlines()[:50]
    else:
        out["error"] = info.get("import_error")
    return out


def server_state(root: str) -> dict:
    """What the running server reports about itself."""
    out = {"root": root}
    try:
        with urllib.request.urlopen(root.rstrip("/") + "/api/v1/status", timeout=10) as r:
            st = json.loads(r.read())
        out["status"] = st
        srv = st.get("server", {}) if isinstance(st, dict) else {}
        out["version"] = srv.get("version", st.get("version") if isinstance(st, dict) else None)
        out["pid"], out["python"] = srv.get("pid"), srv.get("python_version")
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def machine_state() -> dict:
    def pkg(p):
        try:
            import importlib.metadata as md
            return md.version(p)
        except Exception:
            return None
    mac = sys.platform == "darwin"
    ram = _sh(["sysctl", "-n", "hw.memsize"]) if mac else _sh(["awk", "/MemTotal/ {print $2*1024}", "/proc/meminfo"])
    return {"hostname": socket.gethostname(), "platform": platform.platform(),
            "os": _sh(["sw_vers"]).replace("\n", "; ") if mac else _sh(["uname", "-a"]),
            "cpu": _sh(["sysctl", "-n", "machdep.cpu.brand_string"]) if mac else _sh(["sh", "-c", "lscpu | head -20"]),
            "n_cpu": os.cpu_count(), "ram_bytes": int(ram) if ram.isdigit() else ram,
            "harness_python": sys.version, "harness_executable": sys.executable,
            "harness_packages": {p: pkg(p) for p in HARNESS_PACKAGES}}


def env_path(results: str | Path) -> Path:
    p = Path(results)
    return p.with_name(p.stem + "_environment.json")


def record(results: str | Path, *, exe: str | None = None, python: str | None = None,
           server_root: str | None = None, browser: dict | None = None, **run) -> Path:
    """Append this invocation's environment to <results stem>_environment.json."""
    path = env_path(results)
    entry = {"bench": bench_state(), "annzarro": annzarro_state(exe, python) if (exe or python) else None,
             "server": server_state(server_root) if server_root else None, "browser": browser,
             "machine": machine_state(),
             "run": {"argv": [sys.executable, *sys.argv], "cwd": os.getcwd(),
                     "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **run}}
    doc = {"runs": []}
    if path.exists():
        try:
            doc = json.loads(path.read_text())
            if "runs" not in doc:          # an older single-run file: keep it as the first entry
                doc = {"runs": [doc]}
        except Exception:
            doc = {"runs": []}
    doc["runs"].append(entry)
    path.write_text(json.dumps(doc, indent=1))
    return path
