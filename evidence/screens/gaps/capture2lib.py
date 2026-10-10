"""Shared helpers for the final capture round (evidence/screens/gaps/capture2_<tool>.py, evidence-curator, 2026-10-04).

Builds on gaplib.py (docs_shot, table_shot, banner, find_phrase) and adds:
  shot()       viewport screenshot under notes/comparison/screens/<tool>/<name> plus a DOM sidecar, with an
               optional `note` (setup that differs from the audited one); the previous image is backed up to scratch;
               callouts whose element is not visible are dropped, and with fewer than `min_callouts` left the image
               and sidecar are not written (an existing image is restored).
  tag()        put data-cap="<key>" on the smallest visible element whose text matches, so a callout can box it.
  term_shot()  a terminal or code-output page (code block, then the output in a dark block), screenshotted with
               DOM boxes on the code, the output and highlighted output lines.
Run every driver under notes/comparison/demos/scale_probe/gap_run.sh (run_session2.py does that for a batch).
"""
import html
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gaplib  # noqa: E402
from gaplib import TABLE_CSS, banner, dismiss_cookies, find_phrase, log, pv  # noqa: E402,F401

sys.path.insert(0, "notes/comparison/demos/_bin")
from record_json import record  # noqa: E402

SCREENS = gaplib.SCREENS
SCRATCH = "$TMPDIR/evidence/gap-capture-2/"
BY = "evidence-curator"
TODAY = time.strftime("%Y-%m-%d")
gaplib.BY = BY


def add_note(side, note):
    if side and note:
        m = json.loads(open(side).read())
        m["note"] = note
        open(side, "w").write(json.dumps(m, indent=1, ensure_ascii=False))
    return side


def shot(page, tool, name, proves, callouts, *, software, driver, data=None, url=None, note=None, min_callouts=1, full_page=False):
    path = SCREENS + tool + "/" + name
    bk = None
    if os.path.exists(path):
        os.makedirs(SCRATCH + "prev/" + tool, exist_ok=True)
        bk = SCRATCH + "prev/" + tool + "/" + name
        if not os.path.exists(bk):
            shutil.copy2(path, bk)
    vp = page.viewport_size
    ok = []
    for c in callouts:
        try:
            bb = page.locator(c[1]).first.bounding_box(timeout=2000)
        except Exception:
            bb = None
        if bb is None or bb["width"] <= 0 or bb["height"] <= 0:
            log("  callout not visible:", c[1][:100])
        elif bb["x"] >= vp["width"] or bb["y"] >= vp["height"] or bb["x"] + bb["width"] <= 0 or bb["y"] + bb["height"] <= 0:
            log("  callout outside viewport:", c[1][:100])
        else:
            ok.append(c)
    if len(ok) < min_callouts:
        log("SKIP", tool, name, f"only {len(ok)} of {len(callouts)} callouts visible")
        page.screenshot(path=SCRATCH + f"fail_{tool}_{name}", type="jpeg", quality=60)
        return None
    page.screenshot(path=path, type="jpeg", quality=80)
    side = record(page, path, tool=tool, software=software, by=BY, driver=driver, data=data, url=url,
                  proves=proves, callouts=ok)
    add_note(side, note)
    log("shot", tool, name, "callouts", len(ok), "/", len(callouts))
    return side


TAG_JS = """([key, re, x0, x1, y0, y1, up, minh]) => {
  const ci = re.startsWith('(?i)'); const r = new RegExp(ci ? re.slice(4) : re, ci ? 'i' : '');   // Python-style (?i) prefix
  let c = [...document.querySelectorAll('body *')].filter(e => {
    const t = (e.innerText || e.textContent || '').trim(); if (!r.test(t)) return false;
    const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 && b.x >= x0 && b.x <= x1 && b.y >= y0 && b.y <= y1; });
  if (!c.length) return null;
  c.sort((a, b) => { const p = a.getBoundingClientRect(), q = b.getBoundingClientRect(); return p.width * p.height - q.width * q.height; });
  let e = c[0];
  for (let i = 0; i < up && e.parentElement; i++) e = e.parentElement;
  while (e.parentElement && e.getBoundingClientRect().height < minh) e = e.parentElement;
  e.setAttribute('data-cap', key); const b = e.getBoundingClientRect(); return [b.x, b.y, b.width, b.height].map(Math.round);
}"""


def tag(page, key, rx, x0=-1, x1=1e5, y0=-1, y1=1e5, up=0, minh=0):
    try:
        r = page.evaluate(TAG_JS, [key, rx, x0, x1, y0, y1, up, minh])
    except Exception as e:
        r = "ERR " + str(e)[:80]
    log("  tag", key, rx, r)
    return f"[data-cap='{key}']"


def step(name, f):
    try:
        return f()
    except Exception as e:
        log("FAIL", name, str(e)[:300])


TERM_CSS = TABLE_CSS + """
.cell{margin:10px 16px;border:1px solid #ccd;border-radius:4px;background:#f6f8fa}
.cell .lab{font:12px Menlo,monospace;color:#1f5fa8;padding:6px 10px 0}
.cell pre{background:#f6f8fa;color:#1d2733;margin:0;padding:6px 10px 10px}
.out pre{margin:0 16px 10px;padding:10px;background:#111;color:#e6e6e6;border-radius:4px;white-space:pre-wrap;word-break:break-all}
.out pre span.hl{background:#7a5c00;color:#fff}
"""


def term_page(page, *, title, sub, blocks, note=None, width=1400):
    """blocks: [("code", label, text) | ("out", None, [lines or (line, True=highlight)])]. Output block i gets id out<i>,
    code block i gets id code<i>, highlighted lines get id hl<i>_<j>. Viewport height fits the page (max 1600)."""
    body = f"<h1>{html.escape(title)}</h1><div class='sub' id='sub'>{sub}</div>"
    for i, (kind, lab, content) in enumerate(blocks):
        if kind == "code":
            body += f"<div class='cell' id='code{i}'><div class='lab'>{html.escape(lab or '')}</div><pre>{html.escape(content)}</pre></div>"
        elif kind == "img":  # content: path of a PNG, embedded; lab: its caption
            import base64
            b64 = base64.b64encode(open(content, "rb").read()).decode()
            body += (f"<div class='note'>{html.escape(lab or '')}</div>"
                     f"<img id='img{i}' style='margin:4px 16px 10px;max-height:330px;border:1px solid #ccd' src='data:image/png;base64,{b64}'>")
        else:
            lines = []
            for j, ln in enumerate(content):
                if isinstance(ln, tuple):
                    lines.append(f"<span class='hl' id='hl{i}_{j}'>{html.escape(ln[0])}</span>")
                else:
                    lines.append(html.escape(ln))
            body += f"<div class='out'><pre id='out{i}'>" + "\n".join(lines) + "</pre></div>"
    if note:
        body += f"<div class='note' id='note'>{note}</div>"
    page.set_viewport_size({"width": width, "height": 900})
    page.set_content(f"<!doctype html><html><head><meta charset='utf-8'><style>{TERM_CSS}</style></head><body>{body}</body></html>")
    h = page.evaluate("document.body.scrollHeight") + 12
    page.set_viewport_size({"width": width, "height": max(420, min(int(h), 1600))})
    time.sleep(0.3)


def docs(page, *, tool, name, url, phrases, proves, software, driver, kind="docs page", note=None, extra=None, wait=5,
         goto=True, banner_text=None):
    """Documentation shot: highlight and box the first phrase found, banner with the URL, DOM sidecar."""
    if goto:
        r = page.goto(url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(wait)
        log("GET", url, r.status if r else None)
        dismiss_cookies(page)
    ph, el = find_phrase(page, phrases)
    if el is None:
        log("NO PHRASE on", url, phrases)
        page.screenshot(path=SCRATCH + f"fail_{tool}_{name}", type="jpeg", quality=60)
        return None
    el.evaluate("e=>e.scrollIntoView({block:'center'})")
    time.sleep(1)
    el.evaluate("e=>{e.style.background='#ffef8a';e.style.outline='2px solid #d62728';e.setAttribute('data-cap','phrase')}")
    banner(page, banner_text or f"{kind.upper()} (documentation, not the running app): {url}")
    time.sleep(0.5)
    callouts = [(1, "[data-cap='phrase']", f'{kind}: "{ph}"'), (2, "#gapbanner", f"{kind}, with its URL")] + (extra or [])
    side = shot(page, tool, name, proves, callouts, software=software, driver=driver, data=f"{kind}: {url}", url=url, note=note, min_callouts=2)
    el.evaluate("e=>e.removeAttribute('data-cap')")
    return side
