"""V8 heap ceiling in a Chromium tab: jsHeapSizeLimit and how much an array of
arrays can hold (on-heap) and how many 256 MB ArrayBuffers (off-heap) a tab
can allocate, for a given set of browser flags."""
import os, sys, json, time
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import envcapture  # noqa: E402
# environment goes next to the results: HEAPCAP_OUT names the results file (stdout is usually redirected there)
envcapture.require_clean_bench()
flags = sys.argv[2:]
channel = sys.argv[1]
JS = """async () => {
  const lim = performance.memory.jsHeapSizeLimit;
  const keep = []; let onheap = 0, err1 = '';
  try { for (let i = 0; i < 400; i++) { const a = new Array(16*1024*1024).fill(1.5); keep.push(a); onheap += 128*1024*1024; console.log('onheap ' + onheap + ' used ' + performance.memory.usedJSHeapSize + ' lim ' + lim); } }
  catch (e) { err1 = String(e); }
  const heapUsed = performance.memory.usedJSHeapSize;
  keep.length = 0;
  return {lim, onheap, err1, heapUsed};
}"""
JS2 = """async () => {
  const keep = []; let off = 0, err2 = '';
  try { for (let i = 0; i < 200; i++) { const b = new Float32Array(64*1024*1024); b.fill(1); keep.push(b); off += 256*1024*1024; } }
  catch (e) { err2 = String(e); }
  keep.length = 0;
  return {off, err2};
}"""
with sync_playwright() as pw:
    kw = dict(args=["--enable-precise-memory-info"] + flags)
    if channel != "bundled": kw["channel"] = channel
    b = pw.chromium.launch(**kw)
    out = {"version": b.version, "flags": flags}
    envcapture.record(os.environ.get("HEAPCAP_OUT", str(Path(__file__).resolve().parents[1] / "results" / "heapcap.jsonl")),
                      browser={"channel": channel, "version": b.version, "flags": kw["args"], "headless": True})
    for name, js in (("heap", JS), ("buffers", JS2)):
        p = b.new_page(); crashed = []
        p.on("crash", lambda *_: crashed.append(1))
        logs = []
        p.on("console", lambda m: logs.append(m.text))
        p.goto("about:blank")
        try:
            out[name] = p.evaluate(js)
        except Exception as e:
            out[name] = {"exception": str(e)[:200], "crashed": bool(crashed), "last": logs[-1:] }
        p.close()
    b.close()
print(json.dumps(out))
