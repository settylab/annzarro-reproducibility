"""ShinyCell 2.1.0 local app (evidence-curator, 2026-10-04): h02 subset Y, the per-plot subset form. steps(page) for
_focus_run.py, which starts and stops the app ($DEMO_ROOT/shinycell/start.sh, 127.0.0.1:8907):
  notes/comparison/demos/scale_probe/gap_run.sh $DEMO_ROOT/_browser/.venv/bin/python \
      notes/comparison/demos/_focus_run.py shinycell 8907 evidence/screens/gaps/capture2_shinycell.py
Steps of notes/comparison/demos/shinycell/recap_focus.py (shot 04): "Toggle to subset cells", subset by Age, untick one value.
"""
import sys

sys.path.insert(0, "evidence/screens/gaps")
from capture2lib import TODAY, log, pv, shot, step  # noqa: E402

DRV = "evidence/screens/gaps/capture2_shinycell.py"
SW = "ShinyCell 2.1.0 (local Shiny app built by build.R)"
DATA = "bm_demo_sce.rds (8,090 cells)"


def sel(p, id_, text):
    p.evaluate("([i,v])=>{const s=$('#'+i)[0].selectize; if(!s.options[v]) s.addOption({value:v,label:v}); s.setValue(v);}", [id_, text])
    p.wait_for_timeout(300)


def steps(p, S):
    p.set_default_timeout(20000)
    p.goto("http://127.0.0.1:8907", timeout=60000)
    p.wait_for_timeout(8000)
    sel(p, "sc1a1inp1", "highres_celltype")
    p.wait_for_timeout(4000)
    p.click("#sc1a1togL")
    p.wait_for_timeout(1500)
    sel(p, "sc1a1sub1", "Age")
    p.wait_for_timeout(2500)
    boxes = p.locator("#sc1a1sub1\\.ui input[type=checkbox]")
    labels = p.eval_on_selector_all("#sc1a1sub1\\.ui label", "els=>els.map(e=>e.innerText.trim())")
    log("subset boxes", boxes.count(), labels)
    if boxes.count() > 1:
        boxes.nth(0).uncheck()
        p.wait_for_timeout(7000)
    h = p.evaluate("()=>document.documentElement.scrollHeight")
    p.set_viewport_size({"width": 1400, "height": max(900, min(h, 1600))})
    p.wait_for_timeout(1000)
    shown = [lab for i, lab in enumerate(labels) if i > 0]
    shot(p, "shinycell", "h02_subset_per_plot_form.jpg",
         [pv("subset", "Y", f"ShinyCell 2.1.0 ({TODAY}): 'Toggle to subset cells' opens a per-plot form; choosing a metadata field and unticking values ({labels[0] if labels else 'one value'} off) restricts both plots of the tab to the rest")],
         [(1, "#sc1a1togL", "Toggle to subset cells"), (2, "#sc1a1sub1 + .selectize-control", "Cell information to subset: Age"),
          (3, "#sc1a1sub1\\.ui", "Select which cells to show: " + ", ".join(shown)[:60]), (4, "#sc1a1oup1 img", "plot drawn from the subset"), (5, "#sc1a1oup2 img", "second plot, same subset")],
         software=SW, driver=DRV, data=DATA, url="http://127.0.0.1:8907", min_callouts=3)
    log("done")
