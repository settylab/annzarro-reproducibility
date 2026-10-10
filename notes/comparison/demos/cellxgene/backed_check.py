"""CELLxGENE Annotate 1.3.0 --backed: does a gene request read one column or materialise X?
For a CSR-encoded and a CSC-encoded copy of the same 8,090 x 16,285 matrix, launch `cellxgene launch --backed`,
then request genes through the REST API and record the server's RSS after load and after each request."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_DEMO_ROOT = _os.environ.get("DEMO_ROOT", str(_Path.home() / "annzarro_compare"))  # local demos, apps and data
_TMP = _tempfile.gettempdir()
import json, os, subprocess, sys, time, urllib.request
import psutil
CX = os.path.expanduser(f"{_DEMO_ROOT}/cellxgene/.venv/bin/cellxgene")
FILES = {"csr": os.path.expanduser(f"{_DEMO_ROOT}/_data/bm_demo.h5ad"),
         "csc": os.path.expanduser(f"{_DEMO_ROOT}/tissuumaps/data/bm_demo_csc.h5ad")}
def rss(pid):
    try:
        p = psutil.Process(pid); return round(sum(x.memory_info().rss for x in [p] + p.children(recursive=True)) / 2**20)
    except psutil.Error: return None
def port_free():
    # cellxgene's own check binds without SO_REUSEADDR, so wait out TIME_WAIT from earlier requests too
    import socket
    for _ in range(240):
        with socket.socket() as so:
            try: so.bind(("127.0.0.1", 8903)); return True
            except OSError: time.sleep(1)
    return False
out = {}
for enc, f in FILES.items():
    assert port_free(), "port 8903 already in use; stop the stale server first"
    pr = subprocess.Popen([CX, "launch", f, "--backed", "--X-approximate-distribution", "normal", "--host", "127.0.0.1", "--port", "8903",
                           "--disable-annotations"], stdout=open(f"{_TMP}/cx_{enc}.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    try:
        for _ in range(180):
            assert pr.poll() is None, f"cellxgene exited rc={pr.returncode}"
            try: schema = json.load(urllib.request.urlopen("http://127.0.0.1:8903/api/v0.2/schema", timeout=2)); break
            except Exception: time.sleep(1)
        key = schema["schema"]["annotations"]["var"]["index"]
        time.sleep(3); r = {"var_index": key, "after_load_MiB": rss(pr.pid)}
        for g in ["Mpo", "Elane", "Cd74"]:
            t = time.time()
            # Content-Length is set once the column is computed; this cellxgene 1.3.0 + werkzeug 3.1.9 install then fails
            # writing the body ("applications must write bytes"), which happens after the X read being measured.
            hdr = subprocess.run(["curl", "-s", "-D", "-", "-H", "Accept: application/octet-stream", "-o", "/dev/null",
                                  f"http://127.0.0.1:8903/api/v0.2/data/var?var:{key}={g}"], capture_output=True, text=True, timeout=300).stdout
            cl = [l.split(":")[1].strip() for l in hdr.splitlines() if l.lower().startswith("content-length")]
            r[g] = {"status": hdr.split()[1] if hdr else None, "content_length": cl[0] if cl else None,
                    "s": round(time.time() - t, 2), "rss_MiB": rss(pr.pid)}
        out[enc] = r
    finally:
        try: os.killpg(pr.pid, 15); pr.wait(20)
        except Exception: pass
    time.sleep(2)
print(json.dumps(out, indent=1))
