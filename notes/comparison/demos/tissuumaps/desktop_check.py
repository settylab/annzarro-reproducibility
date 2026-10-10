"""TissUUmaps 3.2.1.11 desktop build (pip `tissuumaps` GUI entry point, PySide6 6.4.3 / QtWebEngine), observed
over CDP; then the desktop's "Export to static webpage" code path, and the exported folder served statically.

Steps:
 1. Launch `tissuumaps -p 8909 <h5ad>` with QTWEBENGINE_REMOTE_DEBUGGING=127.0.0.1:8910 (the GUI env).
 2. Attach Playwright over CDP to the embedded Chromium; screenshot the page (the Qt menu bar is NOT in it);
    pick a categorical column so markers draw; read the project state with projectUtils.getActiveProject().
 3. Quit the app. Call tissuumaps.views.exportToStatic(state, folder, previouspath): the function the desktop
    menu item calls after its folder dialog (gui.py MainWindow.exportToStatic), run in the same env.
 4. List the exported folder; serve it with a static file server (no Python backend) and load index.html.
Output: argv[1] (shots, state.json, listing.txt, log.txt).
"""
import json, os, signal, subprocess, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
GUI = Path.home() / "annzarro_compare/_mamba/envs/tissuumaps_gui/bin"
DATA = Path.home() / "annzarro_compare/tissuumaps/data"
H5 = DATA / sys.argv[2] if len(sys.argv) > 2 else DATA / "spatial_demo.h5ad"
EXPORT = OUT / "static_export"
log = open(OUT / "log.txt", "w")
env = dict(os.environ, QTWEBENGINE_REMOTE_DEBUGGING="127.0.0.1:8910")
app = subprocess.Popen([str(GUI / "tissuumaps"), "-p", "8909", str(H5)], env=env, stdout=log, stderr=log)
try:
    for _ in range(120):
        try:
            urllib.request.urlopen("http://127.0.0.1:8910/json/version", timeout=2); break
        except Exception:
            time.sleep(1)
    # Playwright's connect_over_cdp needs Browser.setDownloadBehavior, which QtWebEngine's DevTools does not
    # support; so talk raw CDP to the page target (Runtime.evaluate, Input, Page.captureScreenshot).
    import base64, websocket
    targets = json.load(urllib.request.urlopen("http://127.0.0.1:8910/json"))
    print("targets:", [(t.get("type"), t.get("url")) for t in targets], file=log, flush=True)
    tgt = next(t for t in targets if t.get("type") == "page" and "8909" in t.get("url", ""))
    ws = websocket.create_connection(tgt["webSocketDebuggerUrl"], timeout=120)
    n = [0]
    def cdp(method, **params):
        n[0] += 1; ws.send(json.dumps({"id": n[0], "method": method, "params": params}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == n[0]: return m.get("result", m)
    def ev(expr):
        r = cdp("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        return r.get("result", {}).get("value")
    def shot(name):
        data = cdp("Page.captureScreenshot", format="png")["data"]
        (OUT / name).write_bytes(base64.b64decode(data))
    time.sleep(12)
    shot("d01_desktop_loaded.png")
    print("standalone:", ev("typeof flask !== 'undefined' && !!flask.standalone && typeof flask.standalone.exportToStatic"), file=log, flush=True)
    print("url:", ev("location.href"), "ua:", ev("navigator.userAgent"), file=log, flush=True)
    # pick a categorical column via select2's own API on the underlying <select>
    picked = ev("""(() => { const lab=[...document.querySelectorAll('*')].find(e=>e.textContent.trim()==='Categorical observations' && e.children.length===0);
        if(!lab) return 'no label'; let s=lab.parentElement.querySelector('select') || lab.nextElementSibling && lab.nextElementSibling.querySelector && lab.nextElementSibling.querySelector('select');
        if(!s){ const all=[...document.querySelectorAll('select')]; s=all.find(x=>[...x.options].some(o=>o.text==='leiden')); }
        if(!s) return 'no select'; const o=[...s.options].find(o=>o.text==='leiden'); if(!o) return 'no option';
        $(s).val(o.value).trigger('change'); $(s).trigger({type:'select2:select', params:{data:{id:o.value,text:o.text}}}); return 'ok '+o.value; })()""")
    print("pick:", picked, file=log, flush=True)
    time.sleep(10)
    shot("d02_desktop_markers.png")
    state = ev("projectUtils.getActiveProject().then(s => JSON.stringify(s))")
    (OUT / "state.json").write_text(state or "{}")
    ws.close()
finally:
    app.send_signal(signal.SIGTERM)
    try:
        app.wait(15)
    except Exception:
        app.kill()
# 3. the export code path, in the GUI env
code = ("import json,sys; from tissuumaps import views; "
        "r=views.exportToStatic(open(sys.argv[1]).read(), sys.argv[2], sys.argv[3]); print(json.dumps(r)[:400])")
r = subprocess.run([str(GUI / "python"), "-c", code, str(OUT / "state.json"), str(EXPORT), str(DATA)],
                   capture_output=True, text=True, timeout=600)
print("export:", r.stdout[-400:], r.stderr[-800:], file=log, flush=True)
listing = subprocess.run(["find", str(EXPORT), "-maxdepth", "3"], capture_output=True, text=True).stdout
(OUT / "listing.txt").write_text(listing)
# 4. serve statically, open
srv = subprocess.Popen([str(Path.home() / "annzarro_compare/ucsc-cell-browser/.venv/bin/python"),
                        str(Path.home() / "annzarro_compare/_bin/serve.py"), str(EXPORT), "8911"])
try:
    time.sleep(2)
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, channel="chromium")
        p = b.new_context(viewport={"width": 1400, "height": 900}).new_page()
        p.goto("http://127.0.0.1:8911/index.html", timeout=60000); p.wait_for_timeout(12000)
        p.screenshot(path=str(OUT / "d03_static_export_served.png"))
        print("static page text:", p.inner_text("body")[:300].replace("\n", " | "), file=log, flush=True)
        b.close()
finally:
    srv.terminate()
log.close()
