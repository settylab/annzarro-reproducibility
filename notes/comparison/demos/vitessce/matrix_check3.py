"""Vitessce matrix check, part 3: which X chunks are fetched with only a scatterplot and a gene list
(config_lazy.json), before and after choosing one gene. Local store on 8904 through https://vitessce.io.
Run: gap_run.sh <venv python> /abs/demos/_focus_run.py vitessce 8904 /abs/demos/vitessce/matrix_check3.py"""
import os as _os, tempfile as _tempfile
from pathlib import Path as _Path
_REPO = str(_Path(__file__).resolve().parents[4])  # repository root
D = f"{_REPO}/notes/comparison/screens/vitessce/"
def steps(page, S):
    page.context.grant_permissions(["local-network-access"], origin="https://vitessce.io")
    reqs = []
    page.on("request", lambda r: reqs.append(r.url.split("8904/")[-1]) if "127.0.0.1:8904" in r.url else None)
    page.goto("https://vitessce.io/#?url=http://127.0.0.1:8904/config_lazy.json", timeout=90000); page.wait_for_timeout(15000)
    xs = [u for u in reqs if "/X/" in u]
    print("X requests at load:", len(xs), xs[:4])
    n0 = len(reqs)
    s = page.locator("input[placeholder*='Search']").first; s.click(); s.fill("Mpo"); page.wait_for_timeout(2500)
    page.locator("text=/^Mpo$/").first.click(); page.wait_for_timeout(6000)
    print("after Mpo: X requests", [u for u in reqs[n0:] if "/X/" in u][:8], "| all new", len(reqs) - n0)
    page.screenshot(path=D + "m05_lazy_scatter_genelist_mpo.jpg", type="jpeg", quality=70); print("shot m05")
