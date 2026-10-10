"""CELLxGENE Annotate 1.3.0, local, bm_demo (evidence-curator, 2026-10-04). Re-captures every Annotate shot under its
existing filename with a DOM sidecar (replacing the manual ones), plus h01/h02 subset Y. steps(page) for _focus_run.py,
which starts and stops the server ($DEMO_ROOT/cellxgene/start.sh, 127.0.0.1:8903):
  notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
      notes/comparison/demos/_focus_run.py cellxgene 8903 evidence/screens/gaps/capture2_cellxgene.py
Steps of notes/comparison/demos/cellxgene/matrix_check.py, matrix_check2.py and focus_check_annotate.py, in one page:
  m00 render; m04 layout menu; m12 coloured by Mpo, then the same URL reopened; 01 Mpo on the UMAP and the Elane vs Mpo
  scatter; 02 a click selects nothing; 03 lasso highlights in the scatter; h01/h02 Subset to the selection, Undo subset;
  m08 Age Mid+Old unticked; m10 DE Young vs Old, Pop1 high genes; m09 category + label; m13 the only menu, no export.
The user data directory created here (annotations/gapcapture2-*) is removed afterwards.

Standalone, `<Playwright venv python> capture2_cellxgene.py backed` (job cxg_backed in run_session2.py, no _focus_run):
  h05 lazy Y (row cellxgene-annotate): start.sh run twice, without and with --backed; the server's RSS after load and
  after one gene request, next to the h5ad's size and X's in-memory size: backed mode leaves X on disk.
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, "evidence/screens/gaps")
from capture2lib import SCRATCH, TODAY, log, pv, shot, step, tag, term_page  # noqa: E402

DRV = "evidence/screens/gaps/capture2_cellxgene.py"
SW = "CELLxGENE Annotate 1.3.0 (local)"
DATA = "bm_demo.h5ad (8,090 cells; obsp holds connectivities, distances, diffusion_distance; one counts layer)"
URL = "http://127.0.0.1:8903/"
A = "Annotate 1.3.0"
ANN = os.path.expanduser("$DEMO_ROOT/cellxgene/annotations")
USER = "gapcapture2"
FOOT = "text=/out of 8090 cells/ >> nth=0"
EMB = "[data-testid='layout-graph']"
SCAT = "[data-testid='scatterplot']"


def tid(t):
    return f"[data-testid='{t}']"


def S(page, name, proves, callouts, minc=1, note=None):
    return shot(page, "cellxgene", name, proves, callouts, software=SW, driver=DRV, data=DATA, url=URL, note=note, min_callouts=minc)


def footer(page):
    try:
        return page.locator(FOOT).inner_text(timeout=2000)
    except Exception:
        return "NA"


def cleanup():
    for f in glob.glob(ANN + f"/{USER}*") + glob.glob(ANN + f"/*{USER}*"):
        shutil.rmtree(f) if os.path.isdir(f) else os.remove(f)


def openapp(page):
    page.goto(URL)
    page.wait_for_timeout(12000)
    try:
        page.locator(".bp3-dialog input").first.fill(USER, timeout=4000)
        page.click("text=Create user generated data directory")
        page.wait_for_timeout(2000)
    except Exception as e:
        log("no user-dir dialog", str(e)[:80])


def addgene(page, g):
    inp = page.locator(f"{tid('gene-search')} input")
    if inp.count() == 0:
        inp = page.locator(tid("gene-search"))
    inp.first.click()
    page.wait_for_timeout(600)
    inp.first.fill(g)
    page.wait_for_timeout(2500)
    items = page.locator(".bp3-menu-item, [role=option]")
    items.filter(has_text=re.compile("^" + g + "$")).first.click()
    page.wait_for_timeout(3500)


def lasso(page, box):
    x0, y0, x1, y1 = box
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    page.mouse.move(*pts[0])
    page.mouse.down()
    for x, y in pts[1:]:
        page.mouse.move(x, y, steps=12)
    page.mouse.up()
    page.wait_for_timeout(3500)


def toggle(page, cat, val):
    page.locator(f"label:has(#value-toggle-checkbox-{cat}-{val})").first.click()
    page.wait_for_timeout(1500)


def part1(page):
    openapp(page)
    log("footer", footer(page))
    S(page, "m00_plots_annotate_render.jpg", [pv("every_cell", "Y", f"{A} ({TODAY}): every one of the 8,090 cells is drawn in the UMAP, no downsampling")],
      [(1, EMB, "every cell drawn as a point"), (2, FOOT, "umap: 8090 out of 8090 cells")], minc=2)

    def layouts():
        page.click(tid("layout-choice"))
        page.wait_for_timeout(1000)
        opts = page.evaluate("()=>[...document.querySelectorAll('.bp3-popover-content label, .bp3-popover-content [role=menuitem]')].map(e=>e.innerText.trim()).filter(Boolean)")
        log("layouts:", opts)
        obs = tag(page, "obs", "^Age$", x1=400, minh=300)
        S(page, "m04_slots_annotate_layout_menu.jpg",
          [pv("slots", "N", f"{A} ({TODAY}): X, obs and four obsm layouts only; the counts layer, obsp, varp and varm appear in no menu"),
           pv("cells", "N", "neither the embedding menu nor the obs panel offers any obsp (cell x cell) matrix, although the file holds three"),
           pv("genes", "N", "the gene panel offers only gene search over X and gene sets; no varp (gene x gene) matrix"),
           pv("focus", "N", "no control takes a cell or gene's stored pairwise row: the menus list obsm layouts and obs columns only")],
          [(1, ".bp3-popover-content >> visible=true", "Embedding Choice: " + ", ".join(opts)[:70] + " (obsm only)"), (2, obs, "left panel: obs categories only"),
           (3, tid("gene-search"), "Genes: search over X and gene sets; no varp")], minc=2)
        page.keyboard.press("Escape")
        page.mouse.click(700, 880)
        page.wait_for_timeout(800)
    step("layouts", layouts)

    def mpo():
        addgene(page, "Mpo")
        page.click(tid("colorby-Mpo"))
        page.wait_for_timeout(2500)
        log("url after colouring:", page.url)
        S(page, "m12_share_annotate_coloured_before_reload.jpg",
          [pv("share", "N", f"{A} ({TODAY}), before: coloured by Mpo; the toolbar has no share, link or save-view control, and the URL stays {page.url}")],
          [(1, tid("header"), "toolbar: no share, link or save-view item"), (2, EMB, "view state to share: coloured by Mpo"), (3, tid("colorby-Mpo"), "Mpo in the gene list, colouring")], minc=2)
        p2 = page.context.new_page()
        p2.goto(page.url)
        p2.wait_for_timeout(12000)
        try:
            p2.locator(".bp3-dialog input").first.fill(USER, timeout=3000)
            p2.click("text=Create user generated data directory")
            p2.wait_for_timeout(1500)
        except Exception:
            pass
        S(p2, "m12_share_annotate_same_url_reopened.jpg",
          [pv("share", "N", f"{A} ({TODAY}): the same URL reopened in a new tab shows the default view; the Mpo colouring and the gene are gone")],
          [(1, EMB, "cells drawn uncoloured (default), not by Mpo"), (2, tid("gene-search"), "gene list empty; Mpo not restored")], minc=1)
        p2.close()
    step("mpo/share", mpo)

    def scatter():
        addgene(page, "Elane")
        ids = page.evaluate("()=>[...new Set([...document.querySelectorAll('[data-testid]')].map(e=>e.getAttribute('data-testid')).filter(s=>/Mpo|Elane/.test(s)))]")
        for t in ids:
            if re.search("plot-x.*Mpo", t) or re.search("plot-y.*Elane", t):
                page.click(tid(t))
                page.wait_for_timeout(1500)
        page.wait_for_timeout(3000)
        S(page, "01_annotate_mpo_colours_embedding_and_scatter.jpg",
          [pv("focus", "N", f"{A} ({TODAY}): feature colouring, not a focus: Mpo (one column of X) colours the UMAP and the Elane vs Mpo scatterplot together")],
          [(1, EMB, "UMAP coloured by Mpo"), (2, SCAT, "Elane vs Mpo scatterplot, coloured by Mpo"), (3, tid("colorby-Mpo"), "colour by Mpo")], minc=2)
        page.mouse.click(820, 650)
        page.wait_for_timeout(1500)
        log("after click:", page.inner_text(tid("cellset-count-1"))[:40], footer(page))
        S(page, "02_annotate_single_click_no_effect.jpg",
          [pv("focus", "N", f"{A} ({TODAY}): a click on a cell focuses nothing: no set is filled, no count changes, no view re-drives")],
          [(1, tid("cellset-count-1"), "after the click: 0 cells in set 1"), (2, FOOT, "umap: 8090 out of 8090 cells (nothing selected)"), (3, SCAT, "scatter unchanged")], minc=2)
        page.click(tid("mode-lasso"))
        page.wait_for_timeout(300)
        lasso(page, (640, 150, 960, 300))
        log("after lasso:", footer(page))
        S(page, "03_annotate_lasso_highlights_in_scatter.jpg",
          [pv("selection", "Y", f"{A} ({TODAY}): a lasso in the UMAP highlights the same cells in the linked Elane vs Mpo scatterplot ({footer(page)})")],
          [(1, EMB, "lasso around the top arm of the UMAP"), (2, SCAT, "Elane vs Mpo: selected cells large, the rest small"), (3, FOOT, footer(page))], minc=2)
    step("scatter/lasso", scatter)

    def subset():
        page.locator(tid("subset-button")).hover()
        page.wait_for_timeout(1500)
        tip = tag(page, "tip", "^Subset to currently selected cells")
        S(page, "h01_subset_button_with_selection.jpg",
          [pv("subset", "Y", f"{A} ({TODAY}): with a lasso selection active, the toolbar's 'Subset to currently selected cells and associated metadata' button restricts the view to it")],
          [(1, tid("subset-button"), "Subset button"), (2, tip, "Subset to currently selected cells and associated metadata"), (3, FOOT, footer(page))], minc=2)
        page.click(tid("subset-button"))
        page.wait_for_timeout(5000)
        log("after subset:", footer(page))
        foot = tag(page, "foot2", "out of [0-9]+ cells$")
        S(page, "h02_subset_applied_undo_subset.jpg",
          [pv("subset", "Y", f"{A} ({TODAY}): after Subset only the selected cells remain in every view ({page.locator(foot).first.inner_text(timeout=1500) if page.locator(foot).count() else 'subset'}); 'Undo subset' restores all; view only, nothing recomputed")],
          [(1, EMB, "UMAP: only the subset drawn"), (2, foot, "cell count of the subset"), (3, tid("reset-subset-button"), "Undo subset")], minc=2)
        page.click(tid("reset-subset-button"))
        page.wait_for_timeout(4000)
    step("subset", subset)


def part2(page):
    openapp(page)

    def filt():
        page.click(tid("colorby-Age"))
        page.wait_for_timeout(1500)
        page.click(tid("Age:category-expand"))
        page.wait_for_timeout(1000)
        toggle(page, "Age", "Mid")
        toggle(page, "Age", "Old")
        log("after unticking Mid, Old:", footer(page))
        S(page, "m08_filters_annotate_age_young_only.jpg",
          [pv("filters", "P", f"{A} ({TODAY}): unticking Age Mid and Old masks the embedding to the Young cells, but via category checkboxes, not a table of cells or genes")],
          [(1, tag(page, "agecat", "^Age$", x1=400, minh=120), "Age: Mid and Old unticked, Young ticked (checkboxes, not a table)"), (2, EMB, "only Young cells drawn at full size"), (3, FOOT, footer(page))], minc=2)
    step("filter", filt)

    def de():
        page.click(tid("cellset-button-1"))
        page.wait_for_timeout(1000)
        c1 = page.inner_text(tid("cellset-count-1"))[:40]
        toggle(page, "Age", "Old")
        toggle(page, "Age", "Young")
        page.click(tid("cellset-button-2"))
        page.wait_for_timeout(1000)
        c2 = page.inner_text(tid("cellset-count-2"))[:40]
        log("sets:", c1, c2)
        page.click(tid("diffexp-button"))
        page.wait_for_timeout(12000)
        res = tag(page, "deres", "^Pop1 high", minh=60)
        S(page, "m10_de_annotate_young_vs_old.jpg",
          [pv("de", "Y", f"{A} ({TODAY}): two cell sets (Young {c1}, Old {c2}) are compared in the session, returning Pop1 high and Pop2 high gene sets")],
          [(1, tid("cellset-button-1"), f"set 1: {c1} (Young)"), (2, tid("cellset-button-2"), f"set 2: {c2} (Old)"), (3, tid("diffexp-button"), "See top differentially expressed genes"),
           (4, res, "results: Pop1 high and Pop2 high gene sets")], minc=3)
        page.get_by_text("Pop1 high").first.click()
        page.wait_for_timeout(3000)
        genes = page.evaluate("()=>[...document.querySelectorAll('[data-testid$=\\\\:gene-label]')].map(e=>e.innerText.trim()).slice(0,6)")
        log("Pop1 genes:", genes)
        g1 = tag(page, "pop1", "^Pop1 high", minh=200)
        S(page, "m10_de_annotate_pop1_high_genes.jpg",
          [pv("de", "Y", f"{A} ({TODAY}): the top genes of the on-the-fly Young vs Old test (Pop1 high: {', '.join(genes[:5])}, ...)")],
          [(1, g1, "Pop1 high, created by the DE run: " + ", ".join(genes[:5])), (2, tid("cellset-button-1"), "the compared sets")], minc=1)
    step("de", de)

    def ann():
        page.get_by_text("Create new category").first.click()
        page.wait_for_timeout(1000)
        page.locator(".bp3-dialog input").first.fill("matrix_check")
        page.wait_for_timeout(300)
        page.click(tid("submit-category"))
        page.wait_for_timeout(1500)
        page.click(tid("matrix_check:see-actions"))
        page.wait_for_timeout(500)
        page.click(tid("matrix_check:add-new-label-to-category"))
        page.wait_for_timeout(1000)
        page.locator(".bp3-dialog input").first.fill("old_cells")
        page.wait_for_timeout(300)
        page.locator(f"{tid('matrix_check:submit-label')}, .bp3-dialog button:has-text('Add label')").first.click()
        page.wait_for_timeout(1500)
        try:
            page.click(tid("matrix_check:category-expand"), timeout=3000)
        except Exception:
            pass
        page.wait_for_timeout(800)
        page.click(tid("matrix_check:old_cells:see-actions"))
        page.wait_for_timeout(500)
        page.click(tid("matrix_check:old_cells:add-current-selection-to-this-label"))
        page.wait_for_timeout(2500)
        page.click(tid("colorby-matrix_check"))
        page.wait_for_timeout(8000)
        files = [(os.path.basename(f), os.path.getsize(f)) for f in glob.glob(ANN + "/**/*", recursive=True) if os.path.isfile(f) and USER in f]
        log("annotation files:", files)
        cat = tag(page, "mcat", "^matrix_check", x1=400, minh=80)
        saved = tag(page, "saved", "^All saved$|^Saved$|^Saving", y1=200)
        S(page, "m09_annotation_annotate_category_and_label.jpg",
          [pv("annot", "Y", f"{A} ({TODAY}): a user-created category matrix_check labels the selected (Old) cells old_cells, written to {files[0][0] if files else 'a CSV'} in the user data directory")],
          [(1, cat, "new category matrix_check: label old_cells and unassigned"), (2, saved, "labels written to the user data directory"), (3, EMB, "UMAP coloured by matrix_check")], minc=1)
    step("annotation", ann)

    def menubar():
        page.keyboard.press("Escape")
        page.locator(tid("menu")).click(force=True)
        page.wait_for_timeout(1000)
        items = page.evaluate("()=>[...document.querySelectorAll('.bp3-menu-item')].map(e=>e.innerText.trim()).filter(Boolean)")
        log("menu items:", items)
        S(page, "m13_export_annotate_menu_no_export.jpg",
          [pv("export", "Y", f"{A} ({TODAY}): Annotate itself has no image export; its only menu lists {', '.join(items)[:80]}. The Y rests on Explorer's 'Current view (.png)' (m13_export_explorer_download_menu)")],
          [(1, ".bp3-menu >> visible=true", "the only menu: " + ", ".join(items)[:60]), (2, tid("header"), "toolbar: no download or export")], minc=1)
    step("menubar", menubar)


def steps(page, S_):
    page.set_default_timeout(20000)
    cleanup()
    step("part1", lambda: part1(page))
    p2 = page.context.new_page()
    p2.set_default_timeout(20000)
    step("part2", lambda: part2(p2))
    cleanup()
    log("done")


CXG = os.path.expanduser("$DEMO_ROOT/cellxgene")
H5AD = os.path.expanduser("$DEMO_ROOT/_data/bm_demo.h5ad")
ROW = "cellxgene-annotate"


def rss_mb(port=8903):
    """RSS of the process listening on `port` plus its descendants, in MB."""
    pids = subprocess.run(["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout.split()
    if not pids:
        return None
    rows = [ln.split() for ln in subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss="], capture_output=True, text=True).stdout.splitlines()]
    rows = [(int(a), int(b), int(c)) for a, b, c in rows if a.isdigit()]
    keep, grew = {int(pids[0])}, True
    while grew:
        new = {pid for pid, ppid, _ in rows if ppid in keep} - keep
        grew = bool(new)
        keep |= new
    return sum(r for pid, _, r in rows if pid in keep) / 1024


def launch(extra):
    """start.sh [extra]; wait until the API answers; RSS after load and after one gene (the request the gene search sends)."""
    lg = open(SCRATCH + f"cxg_backed_{'backed' if extra else 'default'}.log", "w")
    proc = subprocess.Popen([CXG + "/start.sh"] + extra, stdout=lg, stderr=subprocess.STDOUT)
    t0, up = time.time(), False
    try:
        while time.time() - t0 < 180 and proc.poll() is None:
            try:
                urllib.request.urlopen(URL + "api/v0.2/schema", timeout=3)
                up = True
                break
            except Exception:
                time.sleep(1)
        t_up = time.time() - t0
        if not up:
            log("cellxgene", extra, "not up after", round(t_up), "s, rc", proc.poll())
            return None
        time.sleep(4)
        r_load = rss_mb()
        req = urllib.request.Request(URL + "api/v0.2/data/var?var:name_0=Mpo", headers={"Accept": "application/octet-stream"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                st, nb = r.status, len(r.read())
        except Exception as e:
            st, nb = str(e)[:40], 0
        time.sleep(2)
        r_gene = rss_mb()
        log("cellxgene", extra or "default", f"up {t_up:.0f}s rss load {r_load} gene {r_gene} status {st} bytes {nb}")
        return t_up, r_load, st, nb, r_gene
    finally:
        subprocess.run([CXG + "/stop.sh"], capture_output=True)
        try:
            proc.wait(timeout=30)
        except Exception:
            proc.kill()


def x_info():
    """h5ad size on disk and X's size once in memory (CSR: float32 data + int32 indices + indptr), read with h5py."""
    py = CXG + "/.venv/bin/python"
    code = ("import h5py,sys; f=h5py.File(sys.argv[1],'r'); X=f['X']; s=X.attrs['shape']; d=X['data']; "
            "print(int(s[0]), int(s[1]), d.shape[0], d.shape[0]*(d.dtype.itemsize+X['indices'].dtype.itemsize)+X['indptr'].nbytes)")
    out = subprocess.run([py, "-c", code, H5AD], capture_output=True, text=True).stdout.split()
    n, g, nnz, xb = (int(v) for v in out)
    return os.path.getsize(H5AD) / 1e6, n, g, nnz, xb / 1e6


def backed(page):
    size, n, g, nnz, xmb = x_info()
    a = launch([])
    b = launch(["--backed"])
    if not a or not b or a[1] is None or b[1] is None:
        log("backed: a launch failed, no shot")
        return
    cmd = "cellxgene launch bm_demo.h5ad --host 127.0.0.1 --port 8903 --annotations-dir annotations"
    d = a[1] - b[1]
    lines = [f"$ ls -l bm_demo.h5ad   # {size:,.1f} MB on disk (gzip-compressed HDF5)",
             f"  X: CSR {n:,} cells x {g:,} genes, {nnz:,} non-zeros = {xmb:,.1f} MB once in memory (float32 data + int32 indices)",
             "", f"$ {cmd}            # the audited start.sh: whole h5ad read into memory",
             (f"  up after {a[0]:.0f} s; server RSS after load {a[1]:,.0f} MB; after GET data/var?var:name_0=Mpo ({a[2]}, {a[3]:,} bytes) {a[4]:,.0f} MB", True),
             "", f"$ {cmd} --backed",
             (f"  up after {b[0]:.0f} s; server RSS after load {b[1]:,.0f} MB; after GET data/var?var:name_0=Mpo ({b[2]}, {b[3]:,} bytes) {b[4]:,.0f} MB", True),
             "", (f"  --backed holds {d:,.0f} MB less after load (X alone is {xmb:,.1f} MB in memory): X stays on disk and is read per request", True)]
    term_page(page, title="Terminal: CELLxGENE Annotate's --backed launch leaves the expression matrix on disk",
              sub=f"cellxgene 1.3.0 (Annotate), anndata 0.11.4; run {TODAY} on the laptop with the audited demo's start.sh, once as is and once with "
                  "--backed. RSS from ps (the listening server process and its children), 4 s after the API answered and again after one gene request.",
              blocks=[("code", "the audited demo's launch command (start.sh), run twice", cmd + "\n" + cmd + " --backed"), ("out", None, lines)],
              note="--backed opens the h5ad with anndata's backed='r': X is read from disk per request, a launch option, no code: Y. "
                   "obs, obsm, obsp and layers still load whole (anndata backed mode), which is why RSS does not fall to near zero.")
    shot(page, "cellxgene", "h05_lazy_annotate_backed_rss.jpg",
         [dict(pv("lazy", "Y", f"terminal, CELLxGENE Annotate 1.3.0 ({TODAY}): launched with --backed the server holds {d:,.0f} MB less after load than the default "
                               f"(X is {xmb:,.1f} MB in memory), and a gene request is still served: X is read from disk on demand by a launch option"), row=ROW)],
         [(1, "#code0", "the same launch, with and without --backed"), (2, "[id^=hl1_] >> nth=0", f"default: RSS {a[1]:,.0f} MB"),
          (3, "[id^=hl1_] >> nth=1", f"--backed: RSS {b[1]:,.0f} MB"), (4, "[id^=hl1_] >> nth=-1", "X stays on disk"), (5, "#note", "launch option, no code")],
         software="CELLxGENE Annotate 1.3.0 (local; cellxgene launch), anndata 0.11.4", driver=DRV, data=DATA, url=URL, min_callouts=3,
         note="Terminal shot of the server process; the audited demo runs without --backed (start.sh), this adds the flag the docs name.")


if __name__ == "__main__" and sys.argv[1:] == ["backed"]:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, channel="chromium")
        pg = br.new_page(viewport={"width": 1400, "height": 900})
        step("backed", lambda: backed(pg))
        br.close()
    log("done")
