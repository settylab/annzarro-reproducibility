#!/usr/bin/env python
"""End-to-end check of the AnnZarro v0.3.1 "edit the store in Jupyter, refresh the viewer" workflow.

Candidate claim tested: "analysis can run in parallel, even in a Jupyter session on the displayed
store, and a single refresh discards AnnZarro's cache and reloads every view."

What it does (everything on COPIES of the paper's bm_aging store; the original is never opened for
writing):

  setup  clone data/bm_aging.zarr (APFS copy-on-write), a copy without .zmetadata, and slim h5ad and
         zarr-format-3 copies (X, obs, var, obsm, layers/MAGIC_imputed_data, obsp/connectivities).
  (a)    in-place modification while plots are open: obs column used for colour, a gene column of a
         layer used for colour, an obsm coordinate used for x. Written from a SEPARATE python process
         (the stand-in for a Jupyter kernel) in two styles: zarr/h5py slice assignment (only chunk
         data changes) and anndata.io.write_elem replacing the array. Each refresh mechanism is then
         applied and the values DRAWN by plotly (per cell name) are compared with the values on disk.
  (b)    adding elements with anndata.io.write_elem (obs column via an obs rewrite, layer, obsp,
         varp), with and without zarr.consolidate_metadata, on a consolidated and an unconsolidated
         store; what the source menus list after refresh, whether .zmetadata is touched, and what an
         unconsolidated in-place dtype change does.
  (c)    the same for the h5ad copy (plus file-lock behaviour) and the zarr-format-3 copy.
  (d)    what a refresh keeps: layout, focused cell/gene, a locked panel, and whether the page reloads.
  (e)    hosted mode (gunicorn, 2 workers, login on): who may POST /cache/reset, what Refresh does for
         a non-admin, and whether an admin's reset reaches every worker.

Run (one command, given a venv with annzarro 0.3.1 installed from the v0.3.1 tag with its vendor
assets, plus anndata, playwright (chromium) and gunicorn):

    <venv>/bin/python annzarro_v0.3.1_refresh.py --work <scratch dir> --out annzarro_v0.3.1_refresh.txt

The script is also its own "Jupyter" writer: `--write <json>` runs one write in a fresh process.
`--only abcde` picks cases; `--reuse`, `--skip-modify`, `--c-formats` are for development only.

What the v0.3.1 run (annzarro_v0.3.1_refresh.txt) shows, and why (code at tag v0.3.1):
  1. Refresh dataset / Ctrl+R does not clear the browser-side cache: refreshCacheForDataset
     (static/js/data-manager.js:244) clears keys containing `dataset_path=<raw path>`, but the keys
     are built with URLSearchParams and hold `dataset_path=%2F...`. Every panel is redrawn from the
     in-memory copy until it expires (60 s, CacheManager.set default ttl, static/js/cache-manager.js).
  2. The ETag (server/http_cache.py) is a stat() of the store's top-level members, so slice
     assignment into existing chunks keeps it; every revalidation is a 304 and the browser keeps
     the old body through cache reset, server restart and reload. Touching metadata
     (zarr.consolidate_metadata) changes the tag.
  3. The ETag is computed from the store, the body from the server's result cache: a request
     after a group-level write but before a reset caches the OLD body under the NEW tag in the
     browser, and later refreshes revalidate it (304) indefinitely.
  4. POST /cache/reset clears only the zarr reader (server/routes/zarr_routes.py:79); the h5ad
     reader keeps its own cache, so h5ad changes show only after a server restart.
  5. Hosted: non-admin Refresh never clears the server cache (by design, 403 admin_only), and an
     admin's reset reaches one gunicorn worker only.
The panel's Refresh button re-requests nothing within 60 s and gets the server's cached copy after.
"""

import argparse
import base64
import datetime
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

SRC_STORE = Path.home() / "gits/annzarro-reproducibility/data/bm_aging.zarr"
GENE = "Gata2"          # layer column used for colour (focused gene)
GENE2 = "Kit"           # second gene, for the lock test
OBS_COL = "doublet_score"
LAYER = "MAGIC_imputed_data"
EMB = "X_umap"
WAIT_OK = 20.0          # seconds a mechanism gets to show the new values
AGE_S = 65.0            # the browser-side cache (static/js/cache-manager.js) keeps a reply for 60 s

OUT_LINES = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    print(line, flush=True)
    OUT_LINES.append(line)


# --------------------------------------------------------------------------------------------
# the "Jupyter" writer: always runs in its own process (python this_script.py --write '<json>')
# --------------------------------------------------------------------------------------------

def _values(step, n, base=None):
    import numpy as np
    rng = np.random.default_rng(1000 + step)
    obs = step * 10.0 + rng.random(n)                            # float64, like doublet_score
    layer = (step * 10.0 + rng.random(n)).astype("float32")      # one gene column of the layer
    umap0 = (base + 100.0 * step).astype("float32") if base is not None else None
    return obs, layer, umap0


def _new_elements(n_obs, n_vars, seed):
    import numpy as np
    import scipy.sparse as sp
    rng = np.random.default_rng(seed)
    new_obs = rng.random(n_obs) + 5.0
    new_layer = sp.random(n_obs, n_vars, density=2e-3, format="csr", dtype="float32", random_state=seed)
    new_obsp = sp.random(n_obs, n_obs, density=2e-3, format="csr", dtype="float32", random_state=seed + 1)
    new_varp = sp.random(n_vars, n_vars, density=2e-4, format="csr", dtype="float32", random_state=seed + 2)
    return new_obs, new_layer, new_obsp, new_varp


def writer_main(spec):
    import numpy as np
    import anndata as ad
    path, fmt, op = spec["path"], spec["fmt"], spec["op"]
    out = {"op": op}
    if fmt in ("zarr2", "zarr3"):
        import zarr
        g = zarr.open_group(path, mode="r+", use_consolidated=False)
        n = g["obs/" + OBS_COL].shape[0]
        if op == "slice":
            obs, layer, umap0 = _values(spec["step"], n, np.asarray(spec["base_umap0"], dtype="float32"))
            g["obs/" + OBS_COL][:] = obs
            g["layers/" + LAYER][:, spec["gene_j"]] = layer
            g["obsm/" + EMB][:, 0] = umap0
        elif op == "write_elem":
            obs, _, umap0 = _values(spec["step"], n, np.asarray(spec["base_umap0"], dtype="float32"))
            ad.io.write_elem(g["obs"], OBS_COL, obs)
            emb = g["obsm/" + EMB][:]
            emb[:, 0] = umap0
            ad.io.write_elem(g["obsm"], EMB, emb)
        elif op == "add":
            n_vars = len(ad.io.read_elem(g["var"]).index)
            new_obs, new_layer, new_obsp, new_varp = _new_elements(n, n_vars, spec["seed"])
            df = ad.io.read_elem(g["obs"])
            df["refresh_new_obs"] = new_obs
            ad.io.write_elem(g, "obs", df)                     # the anndata way: rewrite obs
            ad.io.write_elem(g["obs"], "refresh_naive_col", new_obs)   # bare array, no column-order
            ad.io.write_elem(g["layers"], "refresh_new_layer", new_layer)
            ad.io.write_elem(g["obsp"], "refresh_new_obsp", new_obsp)
            ad.io.write_elem(g["varp"], "refresh_new_varp", new_varp)
        elif op == "dtype_change":
            ad.io.write_elem(g["obs"], OBS_COL, np.asarray(g["obs/" + OBS_COL][:], dtype="float32") + 1.0,
                             dataset_kwargs={"chunks": (1000,)})
        elif op == "consolidate":
            zarr.consolidate_metadata(path)
        else:
            raise SystemExit(f"unknown op {op}")
    elif fmt == "h5ad":
        import h5py
        if op == "rewrite":
            adata = ad.read_h5ad(path)
            obs, _, _ = _values(spec["step"], adata.n_obs)
            adata.obs[OBS_COL] = obs
            adata.write_h5ad(path)
        elif op == "hold_open":
            # a Jupyter user holding the file open for writing (h5py r+) until told to stop
            with h5py.File(path, "r+") as f:
                out["opened"] = True
                print(json.dumps(out), flush=True)
                stop = Path(spec["stop_file"])
                t0 = time.time()
                while not stop.exists() and time.time() - t0 < 120:
                    time.sleep(0.2)
            return
        else:
            with h5py.File(path, "r+") as f:
                n = f["obs/" + OBS_COL].shape[0]
                if op == "slice":
                    obs, layer, umap0 = _values(spec["step"], n, np.asarray(spec["base_umap0"], dtype="float32"))
                    f["obs/" + OBS_COL][:] = obs
                    f["layers/" + LAYER][:, spec["gene_j"]] = layer
                    f["obsm/" + EMB][:, 0] = umap0
                elif op == "write_elem":
                    obs, _, umap0 = _values(spec["step"], n, np.asarray(spec["base_umap0"], dtype="float32"))
                    ad.io.write_elem(f["obs"], OBS_COL, obs)
                    emb = f["obsm/" + EMB][:]
                    emb[:, 0] = umap0
                    ad.io.write_elem(f["obsm"], EMB, emb)
                elif op == "add":
                    n_vars = len(ad.io.read_elem(f["var"]).index)
                    new_obs, new_layer, new_obsp, new_varp = _new_elements(n, n_vars, spec["seed"])
                    df = ad.io.read_elem(f["obs"])
                    df["refresh_new_obs"] = new_obs
                    ad.io.write_elem(f, "obs", df)
                    ad.io.write_elem(f["layers"], "refresh_new_layer", new_layer)
                    ad.io.write_elem(f["obsp"], "refresh_new_obsp", new_obsp)
                    if "varp" not in f:
                        f.create_group("varp")
                    ad.io.write_elem(f["varp"], "refresh_new_varp", new_varp)
                else:
                    raise SystemExit(f"unknown op {op}")
    out["ok"] = True
    print(json.dumps(out), flush=True)


def jupyter_write(spec, timeout=600):
    """Run one write in a separate python process, as a Jupyter kernel would. Returns (ok, text)."""
    t0 = time.time()
    r = subprocess.run([sys.executable, __file__, "--write", json.dumps(spec)],
                       capture_output=True, text=True, timeout=timeout)
    text = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode != 0:
        err = (r.stderr.strip().splitlines() or ["?"])[-1]
        return False, f"exit {r.returncode}: {err}"
    return True, f"{text} ({time.time() - t0:.1f} s)"


# --------------------------------------------------------------------------------------------
# reading what is on disk (fresh handle each time, closed straight away)
# --------------------------------------------------------------------------------------------

def disk_read(path, fmt, what, j=None, row=None):
    import numpy as np
    if fmt == "h5ad":
        import h5py
        import anndata as ad
        with h5py.File(path, "r") as f:
            if what == "obs":
                return np.asarray(f["obs/" + OBS_COL][:], dtype="float64")
            if what == "layer":
                return np.asarray(f["layers/" + LAYER][:, j], dtype="float64")
            if what == "umap0":
                return np.asarray(f["obsm/" + EMB][:, 0], dtype="float64")
            if what == "obs_names":
                return list(ad.io.read_elem(f["obs"]).index)
            if what == "var_names":
                return list(ad.io.read_elem(f["var"]).index)
            return ad.io.read_elem(f[what])
    import zarr
    import anndata as ad
    g = zarr.open_group(str(path), mode="r", use_consolidated=False)
    if what == "obs":
        return np.asarray(g["obs/" + OBS_COL][:], dtype="float64")
    if what == "layer":
        return np.asarray(g["layers/" + LAYER][:, j], dtype="float64")
    if what == "umap0":
        return np.asarray(g["obsm/" + EMB][:, 0], dtype="float64")
    if what == "obs_names":
        return list(ad.io.read_elem(g["obs"]).index)
    if what == "var_names":
        return list(ad.io.read_elem(g["var"]).index)
    return ad.io.read_elem(g[what])


# --------------------------------------------------------------------------------------------
# servers
# --------------------------------------------------------------------------------------------

def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Server:
    def __init__(self, work, data_dir, name="local"):
        self.work, self.data_dir, self.name = Path(work), Path(data_dir), name
        self.proc = None
        self.port = None

    def start(self, hosted_cfg=None):
        import requests
        self.port = self.port or free_port()
        home = self.work / f"home_{self.name}"
        home.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, HOME=str(home), ANNZARRO_HOME=str(home / ".annzarro"))
        logf = open(self.work / f"server_{self.name}.log", "a")
        if hosted_cfg is None:
            cmd = [sys.executable, "-m", "annzarro.cli", "start", "--host", "127.0.0.1", "--port", str(self.port),
                   "--data-dir", str(self.data_dir), "--no-browser", "--auth-disabled"]
        else:
            cfg = hosted_cfg(self.port)
            env["ANNZARRO_CONFIG"] = str(cfg)
            gunicorn = str(Path(sys.executable).with_name("gunicorn"))
            cmd = [gunicorn, "-c", "python:annzarro.server.gunicorn_config", "annzarro.server.wsgi:create_wsgi_app()"]
        self.cmd = cmd
        self.proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, env=env, cwd=str(self.work),
                                     start_new_session=True)
        url = f"http://127.0.0.1:{self.port}/login" if hosted_cfg else f"http://127.0.0.1:{self.port}/api/v1/datasets"
        for _ in range(120):
            try:
                if requests.get(url, timeout=2).status_code in (200, 302, 401):
                    return self
            except Exception:
                pass
            if self.proc.poll() is not None:
                raise RuntimeError(f"server {self.name} exited; see {self.work}/server_{self.name}.log")
            time.sleep(0.5)
        raise RuntimeError("server did not come up")

    @property
    def root(self):
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
        self.proc = None

    def restart(self):
        self.stop()
        return self.start()


# --------------------------------------------------------------------------------------------
# the browser side
# --------------------------------------------------------------------------------------------

XY = ({"type": "obsm", "key": EMB, "column": "0"}, {"type": "obsm", "key": EMB, "column": "1"})


def view_link(root, ds, panels, constants=None, percentages=None):
    """A #view= deep link with the given panels side by side (controls open)."""
    ids = [p["id"] for p in panels]
    pct = percentages or [round(100 / len(ids), 3)] * len(ids)
    view = {"v": 1, "layout": {"v": 1, "hierarchy": [{
        "type": "split", "direction": "horizontal", "panes": [{"percentage": x} for x in pct],
        "children": [{"type": "tile", "id": i} for i in ids]}],
        "controlState": {i: True for i in ids}, "panelConfigs": {p["id"]: p for p in panels}}}
    if constants:
        view["constants"] = constants
    from urllib.parse import quote
    return (f"{root}/?dataset_path={quote(str(ds))}#view="
            + base64.urlsafe_b64encode(json.dumps(view).encode()).decode().rstrip("="))


def cell_panel(pid, color):
    return {"id": pid, "title": pid, "x": XY[0], "y": XY[1], "z": None, "color": color}


PANELS_A = [cell_panel("cell-plot-A", {"type": "obs", "key": OBS_COL}),
            cell_panel("cell-plot-B", {"type": "layer", "key": LAYER, "column": GENE})]

READ_JS = """(tid) => {
  const g = document.querySelector(`.tile[data-tile-id="${tid}"] .js-plotly-plot`);
  if (!g || !g._fullData) return null;
  const out = {names: [], x: [], y: [], c: [], ctitle: null};
  for (const t of g._fullData) {
    if (!t.customdata || !t.customdata.length || /^Focused/.test(t.name || '')) continue;
    const col = t.marker && t.marker.color;
    for (let i = 0; i < t.customdata.length; i++) {
      out.names.push(String(t.customdata[i])); out.x.push(Number(t.x[i])); out.y.push(Number(t.y[i]));
      out.c.push(col && col.length !== undefined && typeof col !== 'string' ? Number(col[i]) : null);
    }
  }
  try { out.ctitle = g._fullLayout && g._fullData[0].marker.colorbar && g._fullData[0].marker.colorbar.title.text; } catch (e) {}
  return out; }"""


def compare(drawn, key, names, expected, prev=None):
    """How many drawn values (by cell/gene name) equal the expected on-disk value."""
    import numpy as np
    if not drawn or not drawn["names"]:
        return {"n_drawn": 0, "n_match": 0, "ok": False, "n_prev": 0}
    pos = {n: i for i, n in enumerate(names)}
    idx = np.array([pos.get(n, -1) for n in drawn["names"]])
    vals = np.array(drawn[key], dtype="float64")
    good = idx >= 0
    exp = np.full(len(idx), np.nan)
    exp[good] = np.asarray(expected)[idx[good]]
    match = np.isclose(vals, exp, rtol=1e-5, atol=1e-6)
    res = {"n_drawn": int(len(vals)), "n_match": int(match.sum()),
           "max_err": float(np.nanmax(np.abs(vals - exp))) if good.any() else None}
    if prev is not None:
        pexp = np.full(len(idx), np.nan)
        pexp[good] = np.asarray(prev)[idx[good]]
        res["n_prev"] = int(np.isclose(vals, pexp, rtol=1e-5, atol=1e-6).sum())
    res["ok"] = res["n_match"] == len(names) == res["n_drawn"]
    return res


class Browser:
    def __init__(self, pw):
        self.b = pw.chromium.launch()
        self.ctx = None
        self.contexts = []
        self.p = None
        self.console = []
        self.responses = []

    def new_context(self, keep=False):
        if not keep:
            for c in self.contexts:
                c.close()
            self.contexts = []
        self.ctx = self.b.new_context(viewport={"width": 1600, "height": 950})
        self.contexts.append(self.ctx)
        self.p = self.ctx.new_page()
        self.p.on("console", lambda m: self.console.append(f"{m.type}: {m.text[:300]}"))
        self.p.on("response", lambda r: self.responses.append((r.status, r.url.split("?")[0].split("/api/v1/")[-1],
                                                                r.request.method)) if "/api/v1/" in r.url else None)
        return self.p

    def use(self, page):
        self.p = page

    def mark(self):
        self.console.clear()
        self.responses.clear()

    def drawn(self, tid):
        try:
            return self.p.evaluate(READ_JS, tid)
        except Exception:
            return None

    def close(self):
        for c in self.contexts:
            c.close()
        self.b.close()

    def data_status_summary(self):
        from collections import Counter
        c = Counter((s, path.split("/")[1] if "/" in path else path) for s, path, m in self.responses
                    if path.startswith("data/"))
        return ", ".join(f"{k[1]}:{k[0]}x{v}" for k, v in sorted(c.items())) or "no data requests"

    def notes(self):
        keep = [c for c in self.console if "Notification" in c or c.startswith("error")]
        return keep[-4:]


def wait_for(fn, timeout, interval=0.4):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        last = fn()
        if last and last[0]:
            return True, time.time() - t0, last
        time.sleep(interval)
    return False, time.time() - t0, last


# --------------------------------------------------------------------------------------------
# refresh mechanisms
# --------------------------------------------------------------------------------------------

def mech_none(ctx):
    pass


def mech_panel_refresh(ctx):
    for tid in ctx["tiles"]:
        ctx["br"].p.click(f"#refresh-plot-{tid}", timeout=5000)


def mech_ctrl_r(ctx):
    p = ctx["br"].p
    p.evaluate("() => { if (document.activeElement) document.activeElement.blur(); }")
    p.keyboard.press("Control+r")


def mech_dataset_button(ctx):
    ctx["br"].p.click("#refresh-dataset", timeout=5000)


def mech_reload(ctx):
    ctx["br"].p.reload(wait_until="load")


def _post_reset(ctx):
    import requests
    r = requests.post(f"{ctx['root']}/api/v1/cache/reset", timeout=30)
    ctx["reset_status"] = r.status_code


def mech_reset(ctx):
    _post_reset(ctx)


def mech_reset_panel(ctx):
    _post_reset(ctx)
    mech_panel_refresh(ctx)


def mech_reset_reload(ctx):
    _post_reset(ctx)
    mech_reload(ctx)


def mech_ctrl_r_reload(ctx):
    mech_ctrl_r(ctx)
    time.sleep(3)
    mech_reload(ctx)


def mech_restart_reload(ctx):
    ctx["srv"].restart()
    mech_reload(ctx)


def mech_cons_ctrlr_reload(ctx):
    ok, msg = jupyter_write({"path": str(ctx["ds"]), "fmt": ctx["fmt"], "op": "consolidate"})
    mech_ctrl_r_reload(ctx)


def mech_reload_then_ctrlr_reload(ctx):
    mech_reload(ctx)
    time.sleep(6)
    mech_ctrl_r_reload(ctx)


def mech_restart_panel(ctx):
    ctx["srv"].restart()
    mech_panel_refresh(ctx)


def mech_cons_ctrlr(ctx):
    ok, msg = jupyter_write({"path": str(ctx["ds"]), "fmt": ctx["fmt"], "op": "consolidate"})
    mech_ctrl_r(ctx)


def mech_aged_ctrlr(ctx):
    time.sleep(max(0.0, AGE_S - (time.time() - ctx.get("t_loaded", 0))))
    mech_ctrl_r(ctx)


def mech_reset_fresh_profile(ctx):
    _post_reset(ctx)
    p = ctx["br"].new_context()
    p.goto(ctx["link"])


MECHS = {
    "none": ("no action (control)", mech_none),
    "panel": ("each panel's Refresh button (#refresh-plot-<id>, label 'Refresh', title 'Redraw the plot')", mech_panel_refresh),
    "ctrlr": ("Ctrl+R (REFRESH_DATASETS; clicks the header Refresh-dataset button)", mech_ctrl_r),
    "dsbtn": ("header Refresh-dataset button (#refresh-dataset, sync icon next to Dataset)", mech_dataset_button),
    "reload": ("browser reload (page.reload, like F5)", mech_reload),
    "reset": ("POST /api/v1/cache/reset from the Jupyter process, nothing in the browser", mech_reset),
    "reset+panel": ("POST /api/v1/cache/reset, then each panel's Refresh", mech_reset_panel),
    "reset+reload": ("POST /api/v1/cache/reset, then browser reload", mech_reset_reload),
    "ctrlr+reload": ("Ctrl+R, then browser reload", mech_ctrl_r_reload),
    "restart+reload": ("server restart (same port), then browser reload", mech_restart_reload),
    "cons+ctrlr+reload": ("zarr.consolidate_metadata(path) from the Jupyter process, Ctrl+R, then browser reload", mech_cons_ctrlr_reload),
    "reload,ctrlr+reload": ("browser reload first, then Ctrl+R, then browser reload", mech_reload_then_ctrlr_reload),
    "restart+panel": ("server restart (same port), then each panel's Refresh", mech_restart_panel),
    "cons+ctrlr": ("zarr.consolidate_metadata(path) from the Jupyter process, then Ctrl+R", mech_cons_ctrlr),
    "aged-ctrlr": (f"Ctrl+R at least {AGE_S:.0f} s after the page loaded", mech_aged_ctrlr),
    "reset+fresh": ("POST /api/v1/cache/reset, then the link in a fresh browser profile (empty HTTP cache)", mech_reset_fresh_profile),
}


# --------------------------------------------------------------------------------------------
# case (a)/(c): modification of displayed values
# --------------------------------------------------------------------------------------------

def fresh_server(srv, fmt):
    """A starting point with no stale server state: a reset for zarr; a restart for h5ad (see (c))."""
    import requests
    if fmt == "h5ad":
        srv.restart()
    else:
        requests.post(f"{srv.root}/api/v1/cache/reset", timeout=30)


def run_modify(label, br, srv, ds, fmt, names, gene_j, base_umap0, mechs, styles, step0, aged=False):
    """quick: per (style, mechanism) a fresh page, write, apply within a few seconds of the plot's load.
    aged: per style one page per mechanism, all loaded, then AGE_S seconds pass, one write, then each
    mechanism on its own page (mechanisms without a server reset first)."""
    import requests
    results = []
    link = view_link(srv.root, ds, PANELS_A, constants={"focusedGene": GENE})
    step = step0
    tag = f"{label} aged" if aged else label
    for style in styles:
        groups = [mechs] if aged else [[mk] for mk in mechs]
        for group in groups:
            step += 1
            fresh_server(srv, fmt)
            link = view_link(srv.root, ds, PANELS_A, constants={"focusedGene": GENE})
            before = {"obs": disk_read(ds, fmt, "obs"), "layer": disk_read(ds, fmt, "layer", j=gene_j),
                      "umap0": disk_read(ds, fmt, "umap0")}

            def check(exp):
                a, b = br.drawn("cell-plot-A"), br.drawn("cell-plot-B")
                ra = compare(a, "c", names, exp["obs"])
                rb = compare(b, "c", names, exp["layer"])
                rx = compare(a, "x", names, exp["umap0"])
                return (ra["ok"] and rb["ok"] and rx["ok"]), ra, rb, rx
            pages, bad = {}, None
            for mk in group:
                page = br.new_context(keep=bool(pages))
                page.goto(link)
                ok0, _, last0 = wait_for(lambda: check(before), 90)
                if not ok0:
                    bad = f"baseline not drawn: {last0[1:] if last0 else None}"
                    break
                pages[mk] = page
            t_loaded = time.time()
            if bad:
                for mk in group:
                    results.append((style, mk, "ERROR", bad))
                    log(f"  [{tag}] {style:10s} {mk:13s} ERROR {bad}")
                continue
            etq = {"dataset_path": str(ds), "columns": OBS_COL}
            et0 = requests.get(f"{srv.root}/api/v1/data/obs", params=etq, timeout=30).headers.get("ETag")
            if aged:
                time.sleep(max(0.0, AGE_S - (time.time() - t_loaded)))
            ok, msg = jupyter_write({"path": str(ds), "fmt": fmt, "op": style, "step": step,
                                     "gene_j": gene_j, "base_umap0": base_umap0.tolist()})
            if not ok:
                for mk in group:
                    results.append((style, mk, "ERROR", f"write failed: {msg}"))
                    log(f"  [{tag}] {style:10s} {mk:13s} ERROR write failed: {msg}")
                continue
            if "none" in group and fmt != "h5ad":
                requests.post(f"{srv.root}/api/v1/cache/reset", timeout=30)
                r304 = requests.get(f"{srv.root}/api/v1/data/obs", params=etq, headers={"If-None-Match": et0}, timeout=30)
                requests.post(f"{srv.root}/api/v1/cache/reset", timeout=30)
                log(f"  [{tag}] {style}: ETag probe: GET obs with the pre-write ETag, after the write and a cache "
                    f"reset -> HTTP {r304.status_code} (304 = the browser keeps its old body); ETag "
                    f"{'unchanged' if r304.headers.get('ETag') == et0 else 'changed'}")
            after = {"obs": disk_read(ds, fmt, "obs"), "layer": disk_read(ds, fmt, "layer", j=gene_j),
                     "umap0": disk_read(ds, fmt, "umap0")}
            changed = {k: bool((after[k] != before[k]).any()) for k in after}
            time.sleep(1.0)
            for mk in group:
                desc, fn = MECHS[mk]
                br.use(pages[mk])
                ctx = {"br": br, "root": srv.root, "link": link, "tiles": ["cell-plot-A", "cell-plot-B"],
                       "srv": srv, "ds": ds, "fmt": fmt}
                age = time.time() - t_loaded
                br.mark()
                try:
                    fn(ctx)
                    err = None
                except Exception as e:
                    err = f"{type(e).__name__}: {e}"
                ok, dt, last = wait_for(lambda: check(after), WAIT_OK if mk != "none" else 6)
                _, ra, rb, rx = last if last else (None, {}, {}, {})
                parts = []
                for nm, r, k in (("obs colour", ra, "obs"), ("layer colour", rb, "layer"), ("obsm x", rx, "umap0")):
                    if not changed[k]:
                        parts.append(f"{nm}: not written")
                        continue
                    prev = compare(br.drawn("cell-plot-A" if k != "layer" else "cell-plot-B"),
                                   "x" if k == "umap0" else "c", names, before[k])
                    state = "NEW" if r.get("ok") else ("OLD" if prev["n_match"] == len(names) else
                                                         f"mixed {r.get('n_match')}/{len(names)} new")
                    parts.append(f"{nm}: {state}")
                verdict = "PASS" if ok else "FAIL"
                extra = f"reset HTTP {ctx['reset_status']}; " if "reset_status" in ctx else ""
                evidence = (f"{'; '.join(parts)}; {extra}plot loaded {age:.0f} s before the action; "
                            f"new values after {dt:.1f} s; requests: {br.data_status_summary()}"
                            + (f"; action error {err}" if err else ""))
                if not ok:
                    evidence = evidence.replace(f"new values after {dt:.1f} s", f"waited {dt:.0f} s")
                results.append((style, mk, verdict, evidence))
                log(f"  [{tag}] {style:10s} {mk:13s} {verdict}  {evidence}")
    return results, step


# --------------------------------------------------------------------------------------------
# case (b)/(c): additions and source menus
# --------------------------------------------------------------------------------------------

MENU_JS = """async ([tid, type]) => {
  const q = s => document.querySelector(`.tile[data-tile-id="${tid}"] ${s}`);
  const t = q('select.axis-type-select[data-axis="color"]');
  if (!t) return null;
  jQuery(t).val(type).trigger('change');
  await new Promise(r => setTimeout(r, 900));
  return [...document.querySelectorAll(`.tile[data-tile-id="${tid}"] select.axis-key-select[data-axis="color"] option`)].map(o => o.value);
}"""

SET_COLOR_JS = """async ([tid, type, key]) => {
  const q = s => document.querySelector(`.tile[data-tile-id="${tid}"] ${s}`);
  jQuery(q('select.axis-type-select[data-axis="color"]')).val(type).trigger('change');
  await new Promise(r => setTimeout(r, 900));
  const k = q('select.axis-key-select[data-axis="color"]');
  if (![...k.options].some(o => o.value === key)) return false;
  jQuery(k).val(key).trigger('change');
  return true;
}"""

NEW = {"obs": "refresh_new_obs", "naive": "refresh_naive_col", "layer": "refresh_new_layer",
       "obsp": "refresh_new_obsp", "varp": "refresh_new_varp"}


def menus(br):
    m = {}
    m["obs"] = br.p.evaluate(MENU_JS, ["cell-plot-C", "obs"]) or []
    m["layer"] = br.p.evaluate(MENU_JS, ["cell-plot-C", "layer"]) or []
    m["obsp"] = br.p.evaluate(MENU_JS, ["cell-plot-C", "obsp"]) or []
    m["varp"] = br.p.evaluate(MENU_JS, ["gene-plot-D", "varp"]) or []
    return {"obs": NEW["obs"] in m["obs"], "naive obs array": NEW["naive"] in m["obs"],
            "layer": NEW["layer"] in m["layer"], "obsp": NEW["obsp"] in m["obsp"], "varp": NEW["varp"] in m["varp"],
            "_n": {k: len(v) for k, v in m.items()}}


def probe_link(srv, ds, focused_cell):
    panels = [cell_panel("cell-plot-C", {"type": "obs", "key": OBS_COL}),
              {"id": "gene-plot-D", "title": "gene-plot-D", "z": None,
               "x": {"type": "var", "key": "dispersions"}, "y": {"type": "var", "key": "dispersions_norm"},
               "color": {"type": "var", "key": "dispersions"}}]
    return view_link(srv.root, ds, panels, constants={"focusedGene": GENE, "focusedCell": focused_cell})


def load_probe(br, link, keep=False):
    br.new_context(keep=keep).goto(link)
    ok, _, _ = wait_for(lambda: (bool(br.drawn("cell-plot-C")) and bool(br.drawn("gene-plot-D")), None), 90)
    time.sleep(1.5)
    return ok


def api_probe(srv, ds):
    """What the HTTP API says about the new elements (status, and the message on an error)."""
    import requests
    out = {}
    q = {"dataset_path": str(ds)}
    s = requests.get(f"{srv.root}/api/v1/data/dataset_structure", params=q, timeout=60)
    out["structure"] = s.status_code
    for nm, url, extra in (("obs", "data/obs", {"columns": NEW["obs"]}),
                           ("layer", f"data/layer/{NEW['layer']}", {"cols": "0"}),
                           ("obsp", f"data/obsp/{NEW['obsp']}", {"rows": "0"}),
                           ("varp", f"data/varp/{NEW['varp']}", {"rows": "0"})):
        r = requests.get(f"{srv.root}/api/v1/{url}", params={**q, **extra}, timeout=60)
        msg = ""
        if r.status_code != 200:
            try:
                j = r.json()
                msg = " " + str(j.get("reason") or j.get("error") or j.get("message"))[:80]
            except Exception:
                pass
        out[nm] = f"{r.status_code}{msg}"
    return out


def plot_new(br, ds, fmt, names, var_names, gene_j, cell_i, seed):
    """Colour by each new element through the menus and compare drawn vs written values."""
    import numpy as np
    new_obs, new_layer, new_obsp, new_varp = _new_elements(len(names), len(var_names), seed)
    res = {}
    for nm, tid, typ, key, exp, labels in (
            ("obs", "cell-plot-C", "obs", NEW["obs"], new_obs, names),
            ("layer", "cell-plot-C", "layer", NEW["layer"], np.asarray(new_layer[:, gene_j].todense()).ravel(), names),
            ("obsp", "cell-plot-C", "obsp", NEW["obsp"], np.asarray(new_obsp[cell_i, :].todense()).ravel(), names),
            ("varp", "gene-plot-D", "varp", NEW["varp"], np.asarray(new_varp[gene_j, :].todense()).ravel(), var_names)):
        if not br.p.evaluate(SET_COLOR_JS, [tid, typ, key]):
            res[nm] = "not in menu"
            continue
        ok, dt, last = wait_for(lambda: ((r := compare(br.drawn(tid), "c", labels, exp))["ok"], r), 30)
        r = last[1] if last else {}
        res[nm] = "drawn = written" if ok else f"MISMATCH {r.get('n_match')}/{len(labels)}"
    return res


def run_additions(label, br, srv, ds, fmt, names, var_names, gene_j, cell_i, seed, consolidated, refresh_via):
    """Pages open (one per mechanism), the four new elements are written, each page is refreshed its
    own way and its source menus are read; then optionally consolidate and repeat on new pages."""
    rows = []
    fresh_server(srv, fmt)
    link = probe_link(srv, ds, names[cell_i])

    def open_pages(hows):
        pages = {}
        for how in hows:
            load_probe(br, link, keep=bool(pages))
            pages[how] = (br.p, time.time())
        return pages

    def apply(pages, prefix):
        for how, (page, t_loaded) in pages.items():
            br.use(page)
            br.mark()
            MECHS[how][1]({"br": br, "root": srv.root, "link": link, "tiles": ["cell-plot-C", "gene-plot-D"],
                           "t_loaded": t_loaded, "srv": srv, "ds": ds, "fmt": fmt})
            time.sleep(4)
            wait_for(lambda: (bool(br.drawn("cell-plot-C")), None), 30)
            time.sleep(1)
            m = menus(br)
            rows.append((f"menus after {prefix}{how}", fmt_menus(m) + f"; API: {api_probe(srv, ds)}"))
    pages = open_pages([h for h in refresh_via if h != "restart"])
    ok, msg = jupyter_write({"path": str(ds), "fmt": fmt, "op": "add", "seed": seed})
    rows.append(("write", f"anndata.io.write_elem from a separate process: {'ok' if ok else 'FAILED ' + msg}"))
    if not ok:
        return rows
    zm = Path(ds) / ".zmetadata"
    if zm.exists():
        meta = json.loads(zm.read_text())["metadata"]
        rows.append((".zmetadata", "lists the new elements after write_elem: "
                     + str({k: any(x.startswith(f"{p}/{v}/") for x in meta)
                            for k, (p, v) in {"obs": ("obs", NEW["obs"]), "layer": ("layers", NEW["layer"]),
                                              "obsp": ("obsp", NEW["obsp"]), "varp": ("varp", NEW["varp"])}.items()})))
    zj = Path(ds) / "zarr.json"
    if fmt == "zarr3" and zj.exists():
        cm = (json.loads(zj.read_text()).get("consolidated_metadata") or {}).get("metadata", {})
        rows.append(("zarr.json", f"has consolidated metadata: {bool(cm)}; it lists the new layer: "
                                  f"{('layers/' + NEW['layer']) in cm}"))
    apply(pages, "")
    if "restart" in refresh_via:
        srv.restart()
        load_probe(br, link)
        m = menus(br)
        rows.append(("menus after server restart + reload", fmt_menus(m) + f"; API: {api_probe(srv, ds)}"))
    if consolidated:
        pages = open_pages(["ctrlr", "ctrlr+reload", "aged-ctrlr"])
        ok, msg = jupyter_write({"path": str(ds), "fmt": fmt, "op": "consolidate"})
        rows.append(("zarr.consolidate_metadata", "ok" if ok else msg))
        apply(pages, "consolidate + ")
    load_probe(br, link)
    rows.append(("plot new elements (fresh page)", str(plot_new(br, ds, fmt, names, var_names, gene_j, cell_i, seed))))
    return rows


def tile_text(br, tid):
    try:
        return br.p.evaluate("(t) => (document.querySelector(`.tile[data-tile-id=\"${t}\"]`) || {}).innerText", tid)[-220:].replace("\n", " ")
    except Exception:
        return None


def all4(res):
    return all(f"{k}=yes" in res for k in (" obs", "layer", "obsp", "varp"))


def add_summary(summary, label, rows):
    for step, res in rows:
        if step.startswith("menus after"):
            summary.append((f"{label}: new obs/layer/obsp/varp in the source menus, {step}",
                            "PASS" if all4(res) else "FAIL"))
        if step.startswith("plot new elements"):
            summary.append((f"{label}: new elements, once listed, drawn with the written values",
                            "PASS" if res.count("drawn = written") == 4 else "FAIL"))


def fmt_menus(m):
    return "listed: " + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in m.items() if not k.startswith("_"))


# --------------------------------------------------------------------------------------------
# case (d): what a refresh keeps
# --------------------------------------------------------------------------------------------

STATE_JS = """() => {
  const v = window.sessionManager && window.sessionManager.captureView ? window.sessionManager.captureView() : null;
  const lock = q => { const b = document.querySelector(`.tile[data-tile-id="${q}"] .axis-lock-btn`);
                      return b ? (b.innerHTML.includes('fa-lock-open') ? 'open' : 'closed') : null; };
  return {marker: window.__refreshMarker || null,
          focusedCell: (document.getElementById('focused-cell') || {}).value,
          focusedGene: (document.getElementById('focused-gene') || {}).value,
          tiles: [...document.querySelectorAll('.tile[data-tile-id]')].map(t => t.dataset.tileId),
          widths: [...document.querySelectorAll('.tile[data-tile-id]')].map(t => Math.round(t.getBoundingClientRect().width)),
          lockB: lock('cell-plot-B'),
          view: v ? JSON.stringify({layout: v.layout && v.layout.hierarchy, constants: v.constants,
                                    colorB: v.layout && v.layout.panelConfigs && v.layout.panelConfigs['cell-plot-B'] && v.layout.panelConfigs['cell-plot-B'].color}) : null};
}"""


def run_state(br, srv, ds, fmt, names, var_names):
    import numpy as np
    rows = []
    gj, gj2 = var_names.index(GENE), var_names.index(GENE2)
    lay1 = disk_read(ds, fmt, "layer", j=gj)
    lay2 = disk_read(ds, fmt, "layer", j=gj2)
    panels = [cell_panel("cell-plot-A", {"type": "obs", "key": OBS_COL}),
              cell_panel("cell-plot-B", {"type": "layer", "key": LAYER, "column": GENE})]
    link = view_link(srv.root, ds, panels, constants={"focusedGene": GENE, "focusedCell": names[100]},
                     percentages=[35, 65])
    for how in ("panel", "ctrlr", "reload"):
        p = br.new_context()
        p.goto(link)
        wait_for(lambda: (compare(br.drawn("cell-plot-B"), "c", names, lay1)["ok"], None), 90)
        time.sleep(1)
        # user actions after load: lock panel B to Gata2, then focus Kit and another cell
        p.click('.tile[data-tile-id="cell-plot-B"] .axis-lock-btn', timeout=5000)
        time.sleep(0.5)
        p.fill("#focused-gene", GENE2)
        time.sleep(1.2)
        p.keyboard.press("Enter")
        time.sleep(1.5)
        p.evaluate("() => document.activeElement && document.activeElement.blur()")
        p.evaluate("() => { window.__refreshMarker = 'same-page'; }")
        s0 = p.evaluate(STATE_JS)
        b0 = compare(br.drawn("cell-plot-B"), "c", names, lay1)["ok"]
        MECHS[how][1]({"br": br, "root": srv.root, "link": link, "tiles": ["cell-plot-A", "cell-plot-B"]})
        time.sleep(5)
        wait_for(lambda: (bool(br.drawn("cell-plot-B")), None), 60)
        time.sleep(2)
        s1 = p.evaluate(STATE_JS)
        dB = br.drawn("cell-plot-B")
        b1 = "Gata2 (locked)" if compare(dB, "c", names, lay1)["ok"] else (
            "Kit (focused)" if compare(dB, "c", names, lay2)["ok"] else "neither")
        diff = [k for k in ("focusedCell", "focusedGene", "tiles", "widths", "lockB", "view") if s0.get(k) != s1.get(k)]
        rows.append((how, s0, s1, b0, b1, diff))
    return rows


# --------------------------------------------------------------------------------------------
# case (e): hosted
# --------------------------------------------------------------------------------------------

def run_hosted(br, work, data_dir, ds, fmt, names, base_umap0, gene_j, step):
    import requests
    rows = []
    hdir = Path(work) / "hosted"
    hdir.mkdir(exist_ok=True)
    users = hdir / "users.json"
    if users.exists():
        users.unlink()

    def cfg(port):
        c = hdir / "site.yaml"
        c.write_text(f"server:\n  host: 127.0.0.1\n  port: {port}\n  data_dir: {data_dir}\n  workers: 2\n"
                     f"  log_file: {hdir}/server.log\nauth:\n  enabled: true\n  user_file: {users}\n")
        return c
    srv = Server(work, data_dir, name="hosted")
    srv.port = free_port()
    c = cfg(srv.port)
    env = dict(os.environ, HOME=str(Path(work) / "home_hosted"))
    for u, pw_, admin in (("admin", "admin-pass-123", True), ("bob", "bob-pass-123", False)):
        cmd = [sys.executable, "-m", "annzarro.cli", "user", "--config", str(c), "add", "--username", u,
               "--password", pw_] + (["--admin"] if admin else [])
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        rows.append(("user add", f"{u} admin={admin}: exit {r.returncode}"))
    srv.start(hosted_cfg=cfg)
    try:
        return _hosted_checks(br, srv, cfg, rows, ds, fmt, names, base_umap0, gene_j, step)
    finally:
        srv.stop()


def _hosted_checks(br, srv, cfg, rows, ds, fmt, names, base_umap0, gene_j, step):
    import requests
    root = srv.root

    def login(user, pw_):
        s = requests.Session()
        r = s.post(f"{root}/login", data={"username": user, "password": pw_}, allow_redirects=False, timeout=20)
        return s, r.status_code
    anon = requests.post(f"{root}/api/v1/cache/reset", timeout=20)
    rows.append(("POST /cache/reset anonymous", f"{anon.status_code} {anon.text[:90]}"))
    sb, st = login("bob", "bob-pass-123")
    rb = sb.post(f"{root}/api/v1/cache/reset", timeout=20)
    rows.append(("POST /cache/reset as bob (non-admin)", f"login {st}; {rb.status_code} {rb.text[:120]}"))
    sa, st = login("admin", "admin-pass-123")
    ra = sa.post(f"{root}/api/v1/cache/reset", timeout=20)
    rows.append(("POST /cache/reset as admin", f"login {st}; {ra.status_code} {ra.text[:80]}"))

    # the Refresh button for each user, and what it does to data changed on disk (write_elem style,
    # which also changes the ETag, so only the server's result cache can keep old values)
    link = view_link(root, ds, PANELS_A, constants={"focusedGene": GENE})
    for user, pw_ in (("bob", "bob-pass-123"), ("admin", "admin-pass-123")):
        step += 1
        srv.stop()                       # every user's test starts with empty caches in both workers
        srv.start(hosted_cfg=cfg)
        sa, _ = login("admin", "admin-pass-123")
        p = br.new_context()
        p.goto(f"{root}/login")
        p.fill('input[name="username"]', user)
        p.fill('input[name="password"]', pw_)
        p.click('button[type="submit"], input[type="submit"]')
        p.wait_for_load_state("load")
        p.goto(link)
        before = disk_read(ds, fmt, "obs")
        ok0, _, _ = wait_for(lambda: (compare(br.drawn("cell-plot-A"), "c", names, before)["ok"], None), 90)
        # warm both workers' caches with the current column
        q = {"dataset_path": str(ds), "columns": OBS_COL}
        for _ in range(12):
            sa.get(f"{root}/api/v1/data/obs", params=q, timeout=30)
        title = p.get_attribute("#refresh-dataset", "title")
        ok, msg = jupyter_write({"path": str(ds), "fmt": fmt, "op": "write_elem", "step": step,
                                 "gene_j": gene_j, "base_umap0": base_umap0.tolist()})
        after = disk_read(ds, fmt, "obs")
        br.mark()
        mech_ctrl_r({"br": br})
        ok1, dt, last = wait_for(lambda: ((r := compare(br.drawn("cell-plot-A"), "c", names, after))["ok"], r), WAIT_OK)
        resets = [r for r in br.responses if r[1] == "cache/reset"]
        prev = compare(br.drawn("cell-plot-A"), "c", names, before)
        state = "NEW" if ok1 else ("OLD" if prev["n_match"] == len(names) else "mixed")
        rows.append((f"Ctrl+R as {user}", f"{'PASS' if ok1 else 'FAIL'}: obs colour {state} after {dt:.1f} s; "
                     f"button title '{title}'; cache/reset calls {resets or 'none'}; baseline ok {ok0}; "
                     f"requests: {br.data_status_summary()}"))
        # which workers still hold the old column? fresh requests, no If-None-Match
        import numpy as np
        fresh, stale = 0, 0
        for _ in range(16):
            r = sa.get(f"{root}/api/v1/data/obs", params=q, headers={"Cache-Control": "no-cache"}, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"GET obs {r.status_code}: {r.text[:200]}")
            v = np.asarray(r.json()["data"][OBS_COL], dtype="float64")
            if np.allclose(v, after):
                fresh += 1
            elif np.allclose(v, before):
                stale += 1
        rows.append((f"16 direct GETs after {user}'s Ctrl+R", f"new values {fresh}, old values {stale}"))
        br.mark()
        mech_reload({"br": br})
        ok2, dt, _ = wait_for(lambda: (compare(br.drawn("cell-plot-A"), "c", names, after)["ok"], None), WAIT_OK)
        prev = compare(br.drawn("cell-plot-A"), "c", names, before)
        state = "NEW" if ok2 else ("OLD" if prev["n_match"] == len(names) else "mixed")
        rows.append((f"Ctrl+R then browser reload as {user}", f"{'PASS' if ok2 else 'FAIL'}: obs colour {state} after "
                     f"{dt:.1f} s; requests: {br.data_status_summary()}"))
    # an admin reset reaches only the worker that answers it
    step += 1
    for _ in range(12):
        sa.get(f"{root}/api/v1/data/obs", params=q, timeout=30)
    jupyter_write({"path": str(ds), "fmt": fmt, "op": "write_elem", "step": step, "gene_j": gene_j,
                   "base_umap0": base_umap0.tolist()})
    after2 = disk_read(ds, fmt, "obs")
    ra = sa.post(f"{root}/api/v1/cache/reset", timeout=20)
    fresh = stale = 0
    import numpy as np
    for _ in range(16):
        r = sa.get(f"{root}/api/v1/data/obs", params=q, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"GET obs {r.status_code}: {r.text[:200]}")
        v = np.asarray(r.json()["data"][OBS_COL], dtype="float64")
        fresh += bool(np.allclose(v, after2))
        stale += bool(not np.allclose(v, after2))
    rows.append(("admin POST /cache/reset once, then 16 GETs", f"reset {ra.status_code}; new {fresh}, old {stale} "
                 f"(2 gunicorn workers, one cache each)"))
    return rows, step


# --------------------------------------------------------------------------------------------
# setup
# --------------------------------------------------------------------------------------------

def tree_mtimes(path):
    out = {}
    for dp, dn, fn in os.walk(path):
        for f in fn:
            fp = os.path.join(dp, f)
            out[fp] = os.stat(fp).st_mtime_ns
    return out


def make_copies(work, reuse=False):
    import anndata as ad
    import zarr
    data = Path(work) / "data"
    h5, z3 = data / "bm_aging_slim.h5ad", data / "bm_aging_slim_v3.zarr"
    if reuse and h5.exists() and z3.exists():
        for d in ("bm_aging.zarr", "bm_aging_nocons.zarr", "bm_aging_d.zarr", "bm_aging_e.zarr"):
            shutil.rmtree(data / d, ignore_errors=True)
    else:
        if data.exists():
            shutil.rmtree(data)
        data.mkdir(parents=True)
    z2 = data / "bm_aging.zarr"
    subprocess.run(["cp", "-cR", str(SRC_STORE), str(z2)], check=True)     # APFS clone, copy-on-write
    nc = data / "bm_aging_nocons.zarr"
    subprocess.run(["cp", "-cR", str(SRC_STORE), str(nc)], check=True)
    (nc / ".zmetadata").unlink()
    for extra in ("bm_aging_d.zarr", "bm_aging_e.zarr"):
        shutil.rmtree(data / extra, ignore_errors=True)
        subprocess.run(["cp", "-cR", str(SRC_STORE), str(data / extra)], check=True)
    if reuse and h5.exists() and z3.exists():
        return data, z2, nc, h5, z3
    g = zarr.open_group(str(z2), mode="r", use_consolidated=False)
    adata = ad.AnnData(X=ad.io.read_elem(g["X"]), obs=ad.io.read_elem(g["obs"]), var=ad.io.read_elem(g["var"]),
                       obsm={k: ad.io.read_elem(g["obsm/" + k]) for k in g["obsm"].keys()},
                       layers={LAYER: ad.io.read_elem(g["layers/" + LAYER])},
                       obsp={"connectivities": ad.io.read_elem(g["obsp/connectivities"])})
    adata.write_h5ad(h5)
    ad.settings.zarr_write_format = 3
    adata.write_zarr(z3)
    ad.settings.zarr_write_format = 2
    return data, z2, nc, h5, z3


# --------------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------------

def table(rows, header):
    log("  " + " | ".join(header))
    for r in rows:
        log("  " + " | ".join(str(x) for x in r))


def main():
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(143))
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=False)
    ap.add_argument("--out", default=None)
    ap.add_argument("--write", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--only", default="abcde")
    ap.add_argument("--reuse", action="store_true", help="development: keep existing slim copies")
    ap.add_argument("--skip-modify", action="store_true", help="development: skip the (a)/(c) modification runs")
    ap.add_argument("--c-formats", default="h5ad,zarr3", help="development: formats for case (c)")
    args = ap.parse_args()
    if args.write:
        return writer_main(json.loads(args.write))
    import numpy as np
    import annzarro
    import anndata as ad
    import zarr
    import h5py
    import importlib.metadata as md
    from playwright.sync_api import sync_playwright
    work = Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    src = Path(annzarro.__file__).resolve().parent.parent
    try:
        commit = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        tags = subprocess.run(["git", "-C", str(src), "tag", "--points-at", "HEAD"], capture_output=True, text=True).stdout.split()
        dirty = subprocess.run(["git", "-C", str(src), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True).stdout.strip()
    except Exception:
        commit, tags, dirty = "?", [], "?"
    log("AnnZarro refresh workflow check (annzarro-reproducibility notes/sources/annzarro_v0.3.1_refresh.py)")
    log(f"date        {datetime.datetime.now().astimezone().isoformat(timespec='seconds')}")
    log(f"annzarro    {annzarro.__version__} from {src}; commit {commit} tags {tags} "
        f"tracked changes: {'none' if not dirty else dirty}")
    log(f"python      {platform.python_version()} on {platform.platform()}")
    log(f"libraries   zarr {zarr.__version__}, anndata {md.version('anndata')}, h5py {h5py.__version__}, "
        f"numpy {np.__version__}, playwright {md.version('playwright')}, gunicorn {md.version('gunicorn')}")
    log(f"source      {SRC_STORE} (never written; cloned with cp -c)")
    log(f"work dir    {work}")
    log("load        not run under the bench lock (~/.annzarro-bench.lock): one headless Chromium, one Flask or "
        "gunicorn server, an 8,090-cell store; nothing here is a timing measurement")
    log("")
    t_setup = time.time()
    data, z2, nc, h5, z3 = make_copies(work, args.reuse)
    log(f"setup: copies made in {time.time() - t_setup:.0f} s: {z2.name} (format 2, consolidated), {nc.name} "
        f"(format 2, .zmetadata removed), {h5.name} and {z3.name} (slim: X, obs, var, obsm, layers/{LAYER}, "
        f"obsp/connectivities; written with anndata {md.version('anndata')})")
    names = disk_read(z2, "zarr2", "obs_names")
    var_names = disk_read(z2, "zarr2", "var_names")
    gene_j = var_names.index(GENE)
    cell_i = 100
    base_umap0 = disk_read(z2, "zarr2", "umap0").astype("float32")
    summary = []
    srv = Server(work, data).start()
    log(f"server: {' '.join(srv.cmd)}  (HOME={work}/home_local)")
    step = 0
    with sync_playwright() as pw:
        br = Browser(pw)
        try:
            # ---------------- read-only check ----------------
            m0 = tree_mtimes(z2)
            br.new_context().goto(view_link(srv.root, z2, PANELS_A, constants={"focusedGene": GENE}))
            wait_for(lambda: (bool(br.drawn("cell-plot-B")), None), 90)
            time.sleep(2)
            mech_ctrl_r({"br": br})
            time.sleep(5)
            m1 = tree_mtimes(z2)
            touched = [k for k in m1 if m0.get(k) != m1[k]] + [k for k in m0 if k not in m1]
            log(f"read-only: files of {z2.name} created/changed/removed by the server while browsing and refreshing: "
                f"{len(touched)}")
            summary.append(("(e) server never writes the store (browse + Ctrl+R, file mtimes)",
                            "PASS" if not touched else "FAIL"))

            if "a" in args.only:
                log("")
                log("(a) in-place modification of displayed values, zarr format 2 with consolidated metadata")
                log(f"    panels: cell-plot-A colour = obs/{OBS_COL}, x = obsm/{EMB}[:,0]; cell-plot-B colour = "
                    f"layers/{LAYER}[:, {GENE}] (focused gene). Drawn plotly values are matched per cell name "
                    f"with the values on disk (rtol 1e-5), all {len(names)} cells.")
                log("    styles: slice = g['obs/..'][:] = v, g['layers/..'][:, j] = v, g['obsm/X_umap'][:, 0] = v "
                    "(zarr.open_group(mode='r+', use_consolidated=False)); write_elem = anndata.io.write_elem "
                    "replacing obs/doublet_score and obsm/X_umap (layer not written)")
                for k, (d, _) in MECHS.items():
                    log(f"    mechanism {k:13s} = {d}")
                res, step = run_modify("zarr2", br, srv, z2, "zarr2", names, gene_j, base_umap0,
                                       ["none", "panel", "ctrlr", "dsbtn", "reload", "reset", "reset+panel",
                                        "reset+reload", "ctrlr+reload", "reload,ctrlr+reload", "restart+reload",
                                        "cons+ctrlr+reload", "reset+fresh"],
                                       ["slice", "write_elem"], step)
                for style, mk, v, ev in res:
                    summary.append((f"(a) zarr2 {style} + {mk} (within 60 s of the plot's load)", v))
                log(f"  aged: the same, but the refresh comes {AGE_S:.0f} s after the plot loaded (past the 60 s "
                    "browser-side cache), one page per mechanism")
                res, step = run_modify("zarr2", br, srv, z2, "zarr2", names, gene_j, base_umap0,
                                       ["panel", "ctrlr", "reset+panel", "cons+ctrlr"], ["slice", "write_elem"], step,
                                       aged=True)
                for style, mk, v, ev in res:
                    summary.append((f"(a) zarr2 {style} + {mk} ({AGE_S:.0f} s after the plot's load)", v))

            if "b" in args.only:
                log("")
                log("(b) adding elements with anndata.io.write_elem from a separate process")
                log("    writes: obs rewritten with a new column (read_elem obs, add column, write_elem(g,'obs',df)); "
                    "a bare array written into obs (no column-order update); layers/obsp/varp new sparse matrices")
                log("  [b1] consolidated store, user skips zarr.consolidate_metadata, then consolidates")
                rows = run_additions("b1", br, srv, z2, "zarr2", names, var_names, gene_j, cell_i, 7, True,
                                     ["reload", "ctrlr", "ctrlr+reload", "aged-ctrlr"])
                table(rows, ["step", "result"])
                add_summary(summary, "(b) zarr2 consolidated", rows)
                log("  [b2] store without .zmetadata")
                rows = run_additions("b2", br, srv, nc, "zarr2", names, var_names, gene_j, cell_i, 8, False,
                                     ["reload", "ctrlr", "ctrlr+reload", "aged-ctrlr"])
                table(rows, ["step", "result"])
                add_summary(summary, "(b) zarr2 unconsolidated", rows)
                log("  [b3] consolidated store: obs/doublet_score replaced by a float32 array with other chunks, "
                    "not re-consolidated")
                import requests
                link = view_link(srv.root, z2, PANELS_A, constants={"focusedGene": GENE})
                fresh_server(srv, "zarr2")
                p_aged = br.new_context()
                p_aged.goto(link)
                t_aged = time.time()
                wait_for(lambda: (bool(br.drawn("cell-plot-A")), None), 90)
                p_quick = br.new_context(keep=True)
                p_quick.goto(link)
                wait_for(lambda: (bool(br.drawn("cell-plot-A")), None), 90)
                ok, msg = jupyter_write({"path": str(z2), "fmt": "zarr2", "op": "dtype_change"})
                exp = disk_read(z2, "zarr2", "obs")
                old = exp - 1.0
                b3 = {}
                for mk, page in (("ctrlr", p_quick), ("ctrlr+reload", p_quick), ("aged-ctrlr", p_aged)):
                    br.use(page)
                    br.mark()
                    MECHS[mk][1]({"br": br, "root": srv.root, "link": link, "t_loaded": t_aged})
                    okd, dt, last = wait_for(lambda: (compare(br.drawn("cell-plot-A"), "c", names, exp)["ok"], None), WAIT_OK)
                    stale = compare(br.drawn("cell-plot-A"), "c", names, old)["n_match"] == len(names)
                    b3[mk] = "new values" if okd else ("OLD values, no message" if stale else
                                                     f"no plot; panel text: {tile_text(br, 'cell-plot-A')!r}")
                    log(f"    after {mk}: panel A shows {b3[mk]}; UI notes {[n[:160] for n in br.notes()][:2]}")
                r = requests.get(f"{srv.root}/api/v1/data/obs", params={"dataset_path": str(z2), "columns": OBS_COL})
                body = r.text[:260].replace("\n", " ")
                log(f"    write: {msg}; GET obs -> {r.status_code} {body}")
                summary.append(("(b) unconsolidated dtype change: error shown, never wrong data (Ctrl+R)",
                                "PASS" if "OLD" not in b3["ctrlr"] and "new" not in b3["ctrlr"] else f"FAIL ({b3['ctrlr']})"))
                for mk in ("ctrlr+reload", "aged-ctrlr"):
                    summary.append((f"(b) unconsolidated dtype change: error shown, never wrong data ({mk})",
                                    "PASS" if "OLD" not in b3[mk] and "new" not in b3[mk] else f"FAIL ({b3[mk]})"))
                jupyter_write({"path": str(z2), "fmt": "zarr2", "op": "consolidate"})
                for mk in ("ctrlr", "ctrlr+reload"):
                    MECHS[mk][1]({"br": br, "root": srv.root, "link": link})
                    okd2, dt, _ = wait_for(lambda: (compare(br.drawn("cell-plot-A"), "c", names, exp)["ok"], None), WAIT_OK)
                    log(f"    after zarr.consolidate_metadata + {mk}: panel A shows the new float32 values: {okd2}")

            if "c" in args.only:
                for label, ds, fmt in [x for x in (("h5ad", h5, "h5ad"), ("zarr3", z3, "zarr3"))
                                       if x[0] in args.c_formats.split(",")]:
                    log("")
                    log(f"(c) {label}: {ds.name}")
                    if not args.skip_modify:
                        res, step = run_modify(label, br, srv, ds, fmt, names, gene_j, base_umap0,
                                               ["panel", "ctrlr", "reload", "reset+reload", "ctrlr+reload", "reload,ctrlr+reload", "restart+reload"]
                                               + (["cons+ctrlr+reload"] if fmt == "zarr3" else []) + ["reset+fresh"],
                                               ["slice", "write_elem"], step)
                        for style, mk, v, ev in res:
                            summary.append((f"(c) {label} {style} + {mk} (within 60 s)", v))
                        res, step = run_modify(label, br, srv, ds, fmt, names, gene_j, base_umap0,
                                               ["panel", "ctrlr", "reset+panel"]
                                               + (["restart+panel"] if fmt == "h5ad" else ["cons+ctrlr"]),
                                               ["slice", "write_elem"], step, aged=True)
                        for style, mk, v, ev in res:
                            summary.append((f"(c) {label} {style} + {mk} ({AGE_S:.0f} s after load)", v))
                    if fmt == "h5ad":
                        # full rewrite with anndata, then the strongest UI refresh
                        link = view_link(srv.root, ds, PANELS_A, constants={"focusedGene": GENE})
                        for mk in ("ctrlr", "reset+fresh"):
                            step += 1
                            br.new_context().goto(link)
                            before = disk_read(ds, fmt, "obs")
                            wait_for(lambda: (compare(br.drawn("cell-plot-A"), "c", names, before)["ok"], None), 90)
                            ok, msg = jupyter_write({"path": str(ds), "fmt": fmt, "op": "rewrite", "step": step})
                            after = disk_read(ds, fmt, "obs")
                            if np.allclose(after, before):
                                raise RuntimeError("rewrite did not change the values; test invalid")
                            br.mark()
                            MECHS[mk][1]({"br": br, "root": srv.root, "link": link})
                            okr, dt, _ = wait_for(lambda: (compare(br.drawn("cell-plot-A"), "c", names, after)["ok"], None), WAIT_OK)
                            log(f"  [h5ad] rewrite    {mk:13s} {'PASS' if okr else 'FAIL'}  adata.write_h5ad(path) over the "
                                f"served file: {msg}; obs colour new after {dt:.1f} s: {okr}; requests: {br.data_status_summary()}")
                            summary.append((f"(c) h5ad full rewrite (write_h5ad) + {mk}", "PASS" if okr else "FAIL"))
                        srv.restart()
                        link = view_link(srv.root, ds, PANELS_A, constants={"focusedGene": GENE})
                        br.new_context().goto(link)
                        okr, dt, _ = wait_for(lambda: (compare(br.drawn("cell-plot-A"), "c", names, disk_read(ds, fmt, "obs"))["ok"], None), 90)
                        log(f"  [h5ad] after server restart: obs colour = disk: {okr}")
                        # file locking
                        br.new_context().goto(link)
                        wait_for(lambda: (bool(br.drawn("cell-plot-A")), None), 90)
                        t0 = time.time()
                        ok, msg = jupyter_write({"path": str(ds), "fmt": fmt, "op": "slice", "step": step + 1,
                                                 "gene_j": gene_j, "base_umap0": base_umap0.tolist()})
                        step += 1
                        log(f"  [h5ad] lock: separate process opens h5py.File(path, 'r+') while the page shows the file: "
                            f"{'ok' if ok else 'REFUSED ' + msg}")
                        summary.append(("(c) h5ad writable by another process while displayed", "PASS" if ok else "FAIL"))
                        stop = work / "hold.stop"
                        if stop.exists():
                            stop.unlink()
                        exp_hold = disk_read(ds, fmt, "obs")
                        holder = subprocess.Popen([sys.executable, __file__, "--write", json.dumps(
                            {"path": str(ds), "fmt": "h5ad", "op": "hold_open", "stop_file": str(stop)})],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        first = holder.stdout.readline().strip()
                        srv.restart()
                        link = view_link(srv.root, ds, PANELS_A, constants={"focusedGene": GENE})
                        br.new_context().goto(link)
                        okh, dt, _ = wait_for(lambda: (compare(br.drawn("cell-plot-A"), "c", names, exp_hold)["ok"], None), 60)
                        import requests
                        r = requests.get(f"{srv.root}/api/v1/data/obs", params={"dataset_path": str(ds), "columns": OBS_COL})
                        try:
                            with h5py.File(ds, "r"):
                                locked_open = "a default (locking) h5py open from a third process succeeds"
                        except OSError as e:
                            locked_open = f"a default (locking) h5py open from a third process fails: {str(e)[:90]}"
                        stop.write_text("x")
                        holder.wait(timeout=30)
                        lock_lines = [l for l in (work / "server_local.log").read_text().splitlines()[-400:] if "lock" in l.lower()]
                        log(f"  [h5ad] lock: while another process holds h5py r+ ({first}), the server reads the file: "
                            f"plot drawn {okh}; GET obs {r.status_code}; meanwhile {locked_open} (the server's reader retries "
                            f"with locking=False, h5ad_reader._open); server log lock lines: {lock_lines[-2:]}")
                        summary.append(("(c) h5ad readable by the server while a writer holds it open", "PASS" if okh else "FAIL"))
                    log(f"  [{label}] additions")
                    rows = run_additions(label, br, srv, ds, fmt, names, var_names, gene_j, cell_i, 11 if fmt == "h5ad" else 12,
                                         fmt == "zarr3", ["reload", "ctrlr", "ctrlr+reload", "aged-ctrlr"]
                                         + (["restart"] if fmt == "h5ad" else []))
                    table(rows, ["step", "result"])
                    add_summary(summary, f"(c) {label}", rows)

            if "d" in args.only:
                log("")
                log("(d) what a refresh keeps (own copy bm_aging_d.zarr). Start: link with 2 panels at 35/65 %, focused gene Gata2; then the user "
                    "locks panel B's colour (lock button), focuses Kit in the Focused Gene picker (Enter).")
                rows = run_state(br, srv, data / "bm_aging_d.zarr", "zarr2", names, var_names)
                for how, s0, s1, b0, b1, diff in rows:
                    log(f"  {how}: before: focusedGene={s0['focusedGene']} focusedCell={s0['focusedCell'][:24]} "
                        f"tiles={s0['tiles']} widths={s0['widths']} lockB={s0['lockB']} marker={s0['marker']}")
                    log(f"  {how}: after:  focusedGene={s1['focusedGene']} focusedCell={(s1['focusedCell'] or '')[:24]} "
                        f"tiles={s1['tiles']} widths={s1['widths']} lockB={s1['lockB']} marker={s1['marker']}; "
                        f"panel B draws {b1}; changed: {diff or 'nothing'}")
                    if diff and "view" in diff:
                        log(f"      view before {s0['view']}")
                        log(f"      view after  {s1['view']}")
                    kept = not diff and s1["marker"] == "same-page" and b1.startswith("Gata2")
                    summary.append((f"(d) {how} keeps layout, focus, lock, same page",
                                    "PASS" if kept else f"FAIL ({', '.join(diff) or ''}{'; page reloaded' if s1['marker'] != 'same-page' else ''}"
                                    f"{'; lock lost' if not b1.startswith('Gata2') else ''})"))
        finally:
            srv.stop()
            if "e" in args.only:
                log("")
                log("(e) hosted: gunicorn 2 workers, login on, users admin (admin) and bob; own copy bm_aging_e.zarr")
                try:
                    rows, step = run_hosted(br, work, data, data / "bm_aging_e.zarr", "zarr2", names, base_umap0, gene_j, step)
                    table(rows, ["check", "result"])
                    d = dict(rows)
                    summary.append(("(e) anonymous reset refused", "PASS" if d["POST /cache/reset anonymous"].startswith("401") else "FAIL"))
                    summary.append(("(e) non-admin reset refused (403 admin_only)", "PASS" if "403" in d["POST /cache/reset as bob (non-admin)"] else "FAIL"))
                    summary.append(("(e) admin reset allowed", "PASS" if " 200" in d["POST /cache/reset as admin"] else "FAIL"))
                    summary.append(("(e) Ctrl+R as non-admin shows data changed on disk", d["Ctrl+R as bob"].split(":")[0]))
                    summary.append(("(e) Ctrl+R as admin shows data changed on disk", d["Ctrl+R as admin"].split(":")[0]))
                    summary.append(("(e) Ctrl+R + reload as non-admin shows data changed on disk", d["Ctrl+R then browser reload as bob"].split(":")[0]))
                    summary.append(("(e) Ctrl+R + reload as admin shows data changed on disk", d["Ctrl+R then browser reload as admin"].split(":")[0]))
                    rr = d["admin POST /cache/reset once, then 16 GETs"]
                    summary.append(("(e) one admin reset clears every worker", "PASS" if "old 0" in rr else "FAIL"))
                except Exception:
                    log("  hosted run failed: " + traceback.format_exc().replace("\n", " | "))
                    summary.append(("(e) hosted run", "ERROR"))
            br.close()
    log("")
    log("SUMMARY")
    for k, v in summary:
        log(f"  {v:5s}  {k}")
    if args.out:
        Path(args.out).write_text("\n".join(OUT_LINES) + "\n")


if __name__ == "__main__":
    main()
