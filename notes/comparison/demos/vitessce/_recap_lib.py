"""Shared bits of the Vitessce re-capture drivers (recap_a.py, recap_b.py)."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import sys, time
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from recap import snap as _snap, pv
SW = "Vitessce (hosted app at vitessce.io, 2026-10-04)"
DATA = "bm_demo.zarr (8,090 cells), served on 127.0.0.1:8904"
APP = "https://vitessce.io/#?url=http://127.0.0.1:8904/"
LYMPH = "https://vitessce.io/#?dataset=human-lymph-node-10x-visium"
T0 = time.time()
def snap(page, name, proves, callouts, driver, data=DATA):
    try: _snap(page, "vitessce", name, proves, callouts, software=SW, driver=driver, data=data)
    except Exception as e: print("SNAP FAIL", name, str(e)[:200])
    print(f"  [{time.time()-T0:.0f}s]", flush=True)
def step(name, f):
    try: f()
    except Exception as e: print("FAIL", name, str(e)[:250])
TAG_JS = """([txt, tag, minh, exact]) => {
  const all = [...document.querySelectorAll('body *')].filter(e => e.offsetParent !== null || e.tagName==='svg');
  let c = all.filter(e => { const t = (e.innerText || e.textContent || '').trim(); return exact ? t === txt : t.startsWith(txt); });
  if (!c.length) return null;
  c.sort((a, b) => a.getBoundingClientRect().width * a.getBoundingClientRect().height - b.getBoundingClientRect().width * b.getBoundingClientRect().height);
  let e = c[0];
  while (e.parentElement && e.getBoundingClientRect().height < minh) e = e.parentElement;
  e.setAttribute('data-recap', tag); const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height].map(Math.round);
}"""
def tag(page, txt, name, minh=0, exact=True):
    try: r = page.evaluate(TAG_JS, [txt, name, minh, exact])
    except Exception as e: r = None
    print("  tag", name, r)
    return f"[data-recap='{name}']"
def gene(page, g):
    s = page.locator("input[placeholder*='Search']").first; s.click(); s.fill(g); page.wait_for_timeout(2500)
    page.locator(f"text=/^{g}$/").first.click(); page.wait_for_timeout(5000)
def lasso(page, pts):
    page.locator("[title='Select lasso']").first.click(); page.wait_for_timeout(600)
    page.mouse.move(*pts[0]); page.mouse.down()
    for p in pts[1:]: page.mouse.move(*p, steps=25); page.wait_for_timeout(50)
    page.mouse.up(); page.wait_for_timeout(4000)
