"""Shared bits of the Cirrocumulus re-capture drivers (recap_*.py): snap() writes the image under its final name plus a
dom sidecar (demos/_bin/recap.py); tag*() put a data-recap attribute on the element that carries the evidence, so the
sidecar box comes from that element's DOM bounding box."""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import sys
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
import recap
from recap import pv
SW = "Cirrocumulus 1.1.61 (local cirro launch)"
BM = "bm_demo.h5ad (8,090 cells)"
LYMPH = "V1_Human_Lymph_Node.h5ad (3,962 spots, Cirrocumulus repository example)"
def snap(page, name, proves, callouts, driver, data=BM):
    recap.snap(page, "cirrocumulus", name, proves, callouts, software=SW, driver=driver, data=data)
_TAGLEAF = """([re, x0, x1, y0, y1, up, key])=>{const r=new RegExp(re);
 for(const e of document.querySelectorAll('body *')){ if(e.children.length) continue; const t=(e.innerText||e.textContent||'').trim();
  if(!r.test(t)) continue; const b=e.getBoundingClientRect(); if(!b.width||b.x<x0||b.x>x1||b.y<y0||b.y>y1) continue;
  let a=e; for(let i=0;i<up;i++) a=a.parentElement; a.setAttribute('data-recap',key); return [Math.round(b.x),Math.round(b.y)];}
 return null}"""
def tagleaf(page, key, rx, x0=0, x1=1e5, y0=0, y1=1e5, up=0):
    r = page.evaluate(_TAGLEAF, [rx, x0, x1, y0, y1, up, key]); print("  tag", key, rx, r)
    return f"[data-recap='{key}']"
_TAGPLOTS = """()=>{const els=[...document.querySelectorAll('canvas, img, svg')].filter(e=>{const b=e.getBoundingClientRect();return b.width>150&&b.height>150});
 els.sort((a,b)=>{const p=a.getBoundingClientRect(),q=b.getBoundingClientRect();return (p.y-q.y)||(p.x-q.x)});
 return els.map((e,i)=>{e.setAttribute('data-recap','p'+i);const b=e.getBoundingClientRect();
  return {sel:"[data-recap='p"+i+"']",tag:e.tagName,x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.width),h:Math.round(b.height)}})}"""
def plots(page):
    """Tag every plot surface (canvas/img/svg > 150 px); returns them sorted top-left first."""
    r = page.evaluate(_TAGPLOTS); print("  plots", [(p["tag"], p["x"], p["y"], p["w"], p["h"]) for p in r])
    return r
def main_plot(page):
    ps = plots(page); return max(ps, key=lambda p: p["w"] * p["h"])["sel"] if ps else "canvas"
def gallery(page, ymin=850):
    return [p["sel"] for p in sorted(plots(page), key=lambda p: p["x"]) if p["y"] > ymin and p["w"] < 500]
def chip(page, key, label):
    """Tag the filter chip with this label (the chips under FILTERS, between FILTERS and ANALYZE)."""
    r = page.evaluate("""([label,key])=>{const y=t=>{for(const e of document.querySelectorAll('body *')){if(!e.children.length&&(e.innerText||'').trim()===t)return e.getBoundingClientRect().y}return null};
     const f=y('FILTERS'), a=y('ANALYZE')||1e5; for(const c of document.querySelectorAll('.MuiChip-root')){const b=c.getBoundingClientRect();
     if(c.innerText.trim()===label&&b.y>f&&b.y<a){c.setAttribute('data-recap',key);return [Math.round(b.x),Math.round(b.y)]}} return null}""", [label, key])
    print("  chip", label, r); return f"[data-recap='{key}']"
HEADER = "text=/\\/ 8,090 cells/ >> nth=0"
LISTBOX = "[role=listbox] >> visible=true"
MENU = "[role=menu] >> visible=true"
