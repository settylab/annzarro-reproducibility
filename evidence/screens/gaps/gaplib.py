"""Shared helpers for the evidence-curator drivers (evidence/screens/gaps/capture_<tool>.py).

Run the drivers with the Playwright venv (benchmark/scale/ceiling/.venv/bin/python), always under
notes/comparison/demos/scale_probe/gap_run.sh. That venv lacks PyYAML and Pillow, so sidecars are written as
JSON (valid YAML) by notes/comparison/demos/_bin/record_json.py, with boxes from the DOM (source: dom).

Three kinds of shot:
  docs_shot()   a documentation page with the establishing sentence highlighted and boxed
  table_shot()  a request log or a folder listing rendered as an HTML page (caption: "request log" / "terminal")
  app shots     written by the drivers themselves with snap()
"""
import html
import os
import sys
import time

sys.path.insert(0, "notes/comparison/demos/_bin")
from record_json import record  # noqa: E402

SCREENS = "notes/comparison/screens/"
SCRATCH = "$TMPDIR/evidence/gap-capture/"
BY = "evidence-curator"
TODAY = time.strftime("%Y-%m-%d")
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:5.0f}s]", *a, flush=True)


def pv(col, mark, cap):
    return {"column": col, "mark": mark, "caption": cap}


def snap(page, tool, name, proves, callouts, *, software, driver, data=None, url=None, min_callouts=1):
    """Viewport screenshot to screens/<tool>/<name> plus a DOM sidecar. Callouts whose selector is not
    visible are dropped (and reported); fewer than min_callouts left -> no sidecar, image removed."""
    path = SCREENS + tool + "/" + name
    page.screenshot(path=path, type="jpeg", quality=80)
    vp = page.viewport_size
    ok = []
    for c in callouts:
        try:
            bb = page.locator(c[1]).first.bounding_box(timeout=2000)
        except Exception:
            bb = None
        if bb is None or bb["width"] <= 0 or bb["height"] <= 0:
            log("  callout not visible:", c[1][:90])
        elif bb["x"] >= vp["width"] or bb["y"] >= vp["height"] or bb["x"] + bb["width"] <= 0 or bb["y"] + bb["height"] <= 0:
            log("  callout outside viewport:", c[1][:90])
        else:
            ok.append(c)
    if len(ok) < min_callouts:
        os.remove(path)
        log("SKIP", tool, name, f"only {len(ok)} callouts")
        return None
    side = record(page, path, tool=tool, software=software, by=BY, driver=driver, data=data, url=url,
                  proves=proves, callouts=ok)
    log("shot", tool, name, "callouts", len(ok), "/", len(callouts))
    return side


def dismiss_cookies(page):
    for t in ["Reject All", "Reject all", "Decline", "I decline", "Accept All", "Accept all", "Accept", "Got it", "OK"]:
        try:
            bt = page.get_by_role("button", name=t, exact=True)
            if bt.count() and bt.first.is_visible():
                bt.first.click(timeout=2000)
                time.sleep(1)
                return t
        except Exception:
            pass


def banner(page, text, color="#7a1f1f"):
    page.evaluate("""([t,c])=>{let d=document.getElementById('gapbanner'); if(!d){d=document.createElement('div');d.id='gapbanner';document.body.appendChild(d);}
      d.style.cssText='position:fixed;top:0;left:0;right:0;z-index:2147483647;background:'+c+';color:#fff;font:bold 15px/1.35 Helvetica,Arial,sans-serif;padding:7px 12px';
      d.textContent=t;}""", [text, color])


def find_phrase(page, phrases):
    """First phrase found on the page -> (phrase, locator of the smallest element holding it)."""
    for ph in phrases:
        loc = page.get_by_text(ph, exact=False)
        try:
            n = loc.count()
        except Exception:
            n = 0
        if n:
            for i in range(min(n, 6)):
                el = loc.nth(i)
                try:
                    if el.is_visible():
                        return ph, el
                except Exception:
                    pass
    return None, None


def docs_shot(page, *, tool, name, url, phrases, column, mark, software, caption, driver, kind="docs page",
              banner_text=None, goto=True, extra=None, wait=4):
    """Open `url`, highlight the first matching phrase, add a banner naming the kind of shot, screenshot,
    write the sidecar. caption gets the matched phrase appended. Returns the matched phrase or None."""
    if goto:
        r = page.goto(url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(wait)
        log("GET", url, r.status if r else None)
        dismiss_cookies(page)
    ph, el = find_phrase(page, phrases)
    if el is None:
        log("NO PHRASE on", url, phrases)
        return None
    el.evaluate("e=>e.scrollIntoView({block:'center'})")
    time.sleep(1)
    el.evaluate("e=>{e.style.background='#ffef8a';e.style.outline='2px solid #d62728';e.setAttribute('data-gap-phrase','1')}")
    banner(page, banner_text or f"{kind.upper()} (documentation, not the running app): {url}")
    time.sleep(0.5)
    callouts = [(1, "[data-gap-phrase='1']", f'{kind}: "{ph}"'), (2, "#gapbanner", f"{kind}, with its URL")]
    if extra:
        callouts += extra
    side = snap(page, tool, name, [pv(column, mark, f"{kind}, {caption}")], callouts,
                software=software, driver=driver, data=f"{kind}: {url}", url=url)
    el.evaluate("e=>e.removeAttribute('data-gap-phrase')")
    return ph if side else None


TABLE_CSS = """body{font:14px/1.4 Menlo,Monaco,monospace;margin:0;background:#fff;color:#1d2733}
h1{font:bold 18px Helvetica,Arial,sans-serif;margin:0;padding:12px 16px;background:#1d2733;color:#fff}
.sub{font:13px Helvetica,Arial,sans-serif;padding:8px 16px;color:#333;background:#eef1f5;border-bottom:1px solid #ccd}
table{border-collapse:collapse;margin:10px 16px;width:calc(100% - 32px)}
th,td{border:1px solid #ccd;padding:3px 7px;text-align:left;vertical-align:top;word-break:break-all}
th{background:#f3f4f6;font-family:Helvetica,Arial,sans-serif}
tr.hl td{background:#fff3b0}
pre{margin:10px 16px;padding:10px;background:#111;color:#e6e6e6;border-radius:4px;white-space:pre-wrap;word-break:break-all}
.note{font:13px Helvetica,Arial,sans-serif;margin:6px 16px;color:#333}"""


def table_shot(page, *, tool, name, title, sub, header, rows, hl, proves, callouts, software, driver, data=None,
               url=None, pre=None, note=None, height=None):
    """Render rows as an HTML table page (rows with index in `hl` get class hl and id r<i>), screenshot it.
    callouts may name '#r<i>', '#pre', '#note', 'h1', '.sub'. `pre` adds a terminal-style block (id pre)."""
    body = f"<h1>{html.escape(title)}</h1><div class='sub'>{sub}</div>"
    if pre is not None:
        body += f"<pre id='pre'>{html.escape(pre)}</pre>"
    if rows:
        body += "<table><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in header) + "</tr>"
        for i, r in enumerate(rows):
            body += f"<tr id='r{i}' class='{'hl' if i in hl else ''}'>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>"
        body += "</table>"
    if note:
        body += f"<div class='note' id='note'>{note}</div>"
    page.set_content(f"<!doctype html><html><head><meta charset='utf-8'><style>{TABLE_CSS}</style></head><body>{body}</body></html>")
    if height is None:
        h = page.evaluate("document.body.scrollHeight") + 10
        page.set_viewport_size({"width": page.viewport_size["width"], "height": max(400, min(int(h), 1600))})
    time.sleep(0.3)
    return snap(page, tool, name, proves, callouts, software=software, driver=driver, data=data, url=url)
