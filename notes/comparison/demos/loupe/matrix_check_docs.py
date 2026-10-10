# Loupe Browser: the app cannot be run (no 10x account may be created). This script screenshots the
# 10x DOCS pages that document each matrix mark. Every image gets a banner "10x DOCS PAGE, not the app".
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
import time, sys
sys.path.insert(0, f"{_REPO}/notes/comparison/demos/_bin")
from record_json import record
from playwright.sync_api import sync_playwright
OUT=f"{_REPO}/notes/comparison/screens/loupe/"
LB="https://www.10xgenomics.com/support/software/loupe-browser/latest/"
JOBS=[
 ("m01_plots_render_DOCS_view_panel.jpg", LB+"tutorials/introduction/lb-sc-interface-and-navigation", "View Panel"),
 ("m06_remote_DOCS_open_local_cloupe.jpg", "https://www.10xgenomics.com/support/software/loupe-browser/downloads", "double-clicking"),
 ("m07_spatial_DOCS_spatial_view_panel.jpg", LB+"tutorials/introduction/lb-navigation-for-spatial", "View Panel"),
 ("m08_filters_DOCS_barcode_highlighted.jpg", LB+"tutorials/assay-analysis/lb-sc-identify-cell-subtypes", "a barcode is highlighted"),
 ("m09_annotation_DOCS_custom_groups.jpg", LB+"tutorials/introduction/lb-sc-interface-and-navigation", "Custom groups can also be created"),
 ("m10_de_DOCS_run_differential_expression.jpg", LB+"tutorials/introduction/lb-sc-interface-and-navigation", "Run Differential Expression"),
 ("m11_image_DOCS_he_brightfield.jpg", LB+"tutorials/introduction/lb-navigation-for-spatial", "H&E brightfield image"),
 ("m12_share_DOCS_send_cloupe_file.jpg", LB+"tutorials/assay-analysis/lb-sc-sharing", "self-contained"),
 ("m13_export_DOCS_svg_png.jpg", LB+"tutorials/introduction/lb-sc-interface-and-navigation", "SVG (high resolution)"),
 ("m14_desktop_DOCS_download_center.jpg", "https://www.10xgenomics.com/support/software/loupe-browser/downloads", "Download for"),
 ("m05_lazy_DOCS_system_requirements.jpg", "https://www.10xgenomics.com/support/software/loupe-browser/downloads", "16GB"),
]
T0=time.time()
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True, channel="chromium")
    p=b.new_page(viewport={"width":1400,"height":900})
    cur=None
    for name,url,phrase in JOBS:
        try:
            if url!=cur:
                r=p.goto(url, timeout=60000, wait_until="domcontentloaded"); cur=url; time.sleep(5)
                print("GET",url,r.status if r else None, flush=True)
                for t in ["Reject All","Reject all","Accept All","Accept all","Accept"]:
                    try:
                        bt=p.get_by_role("button", name=t, exact=True)
                        if bt.count(): bt.first.click(timeout=2000); time.sleep(1); break
                    except Exception: pass
            loc=p.get_by_text(phrase, exact=False)
            n=loc.count(); print(" ",phrase,"matches",n)
            if not n: continue
            el=loc.first; el.scroll_into_view_if_needed(); time.sleep(1)
            p.evaluate("""(args)=>{let d=document.getElementById('docsbanner'); if(!d){d=document.createElement('div');d.id='docsbanner';document.body.appendChild(d);}
              d.style.cssText='position:fixed;top:0;left:0;right:0;z-index:2147483647;background:#b00;color:#fff;font:bold 16px sans-serif;padding:6px 10px';
              d.textContent='10x DOCS PAGE, not the app (Loupe Browser was not run). '+args[0]+'  |  phrase: "'+args[1]+'"';}""", [url, phrase])
            el.evaluate("e=>{e.style.outline='3px solid #f0a';e.style.background='#ffef8a'}")
            p.evaluate("window.scrollBy(0,-120)"); time.sleep(1)
            p.screenshot(path=OUT+name, type="jpeg", quality=70)
            col={"m01":"every_cell","m05":"lazy","m06":"remote","m07":"spatial","m08":"filters","m09":"annot","m10":"de","m11":"image","m12":"share","m13":"export","m14":"desktop"}[name[:3]]
            mark={"m01":"?","m05":"?","m06":"N","m07":"Y","m08":"P","m09":"Y","m10":"Y","m11":"Y","m12":"P","m13":"Y","m14":"Y"}[name[:3]]
            el.evaluate("e=>e.setAttribute('data-docs-phrase','1')")
            record(p, OUT+name, tool="loupe", software="Loupe Browser 9.1.0 DOCS PAGE (10x website), not the app", by="comparison-auditor", driver=__file__,
                   data="10x documentation page", url=url, proves=[{"column":col,"mark":mark,"caption":"10x docs (not the app): page states '"+phrase+"'"}],
                   callouts=[(1,"[data-docs-phrase='1']","docs phrase: "+phrase),(2,"#docsbanner","DOCS PAGE banner")])
            el.evaluate("e=>e.removeAttribute('data-docs-phrase')")
            print("  shot",name, flush=True)
        except Exception as e: print("ERR",name,str(e)[:200])
    b.close()
print(f"elapsed {time.time()-T0:.0f}")
