"""Comparison > Not comparable: tools the paper names but does not score, and the evidence why.

Page module (see 20_tool_ceiling.py). Today one tool, scSVA (operator decision 2026-10-08: no Fig. 1c row, no
Supplementary Note 1 entry; the paper says it is not comparable because it draws binned densities, not cells).
Sources: notes/comparison/scsva/evidence/ (the pack: README.md, scsva_render.txt, the offline replication
snap_bm_aging_grid512*.json, the backend probes probe/probe_*.json, screenshots/) and notes/sources/scsva_2019.txt.
Claims whose sources lie there point at this page (evidence/tools/claim_targets.py).
"""
import json

NAV = [("Comparison", "Not comparable: scSVA", "comparison/not-comparable.md")]
PAGE = "comparison/not-comparable.md"
PACK = "notes/comparison/scsva/evidence"

SHOTS = [
    ("bm_aging_8090cells_density_grid512_bin_centres.png",
     "8,090 cells, the default 2-D density view at grid 512: each mark is a non-empty bin, drawn at the bin's center."),
    ("bm_aging_8090cells_gene_Malat1_zoomed_rebinned_grid512.png",
     "The same cells zoomed in and re-binned: 145 marks for 145 cells, each still a bin, not a cell row."),
    ("bm_aging_8090cells_hover_no_tooltip.png",
     "Hovering a mark: no tooltip; the plot declares no hover input (timings.json: hover_input_exists = [])."),
    ("tahoe_95624334cells_gene_MALAT1_zoomed_rebinned_grid512.png",
     "95,624,334 cells, colored by MALAT1, zoomed and re-binned."),
    ("tahoe_95624334cells_groups_category_grid512.png",
     "95,624,334 cells, the group (category) view: bins colored by group."),
]


def build(ctx):
    DOCS, REPO, link_repo, site_file, rel = ctx.DOCS, ctx.REPO, ctx.link_repo, ctx.site_file, ctx.rel
    page = PAGE
    snap = json.loads((REPO / PACK / "snap_bm_aging_grid512.json").read_text())
    zoom = json.loads((REPO / PACK / "snap_bm_aging_grid512_zoomwindow.json").read_text())
    probes = []
    for p in sorted((REPO / PACK / "probe").glob("probe_*.json"), key=lambda q: int(q.stem.split("_")[1])):
        d = json.loads(p.read_text())
        n = int(p.stem.split("_")[1])
        probes.append((n, d["bins_nonempty_density"], d["frac_bins_with_one_cell"], d["bins_nonempty_groups"],
                       d["max_cells_in_one_bin"], f"{PACK}/probe/{p.name}"))

    def L(path, label=None):
        return link_repo(page, path, label or path.rsplit("/", 1)[-1])

    rows = [f"| 8,090 (bone marrow demo, offline replication) | {snap['nonempty_bins_drawn']:,} | "
            f"{snap['single_cell_marks']:,} | {snap['max_cells_in_one_bin']} | {L(PACK + '/snap_bm_aging_grid512.json')} |",
            f"| 8,090, zoomed window of screenshot 2 | {zoom['nonempty_bins_drawn']:,} | {zoom['single_cell_marks']:,} | "
            f"{zoom['max_cells_in_one_bin']} | {L(PACK + '/snap_bm_aging_grid512_zoomwindow.json')} |"]
    for n, bins, frac, groups, mx, path in probes:
        rows.append(f"| {n:,} (Tahoe-100M, scSVA's own vaex binning) | {bins:,} | about {round(bins * frac):,} "
                    f"({frac:.1%}) | {mx:,} | {L(path)} |")
    shots = []
    for name, cap in SHOTS:
        sp = site_file(f"{PACK}/screenshots/{name}")
        if sp:
            shots.append(f"![{cap}]({rel(page, sp)})\n\n*{cap}*\n")
    body = f"""# Not comparable: scSVA

The paper names tools it does not score in [[fig:overview]]c when they answer a different question. This
page holds the evidence for each such statement.

## scSVA {{#scsva}}

scSVA (Tabaka, Gould and Regev, bioRxiv 2019; last commit c9e8fd6, 2019-03-26) reports that it shows "hundreds
of millions of cells on a laptop" ({L('notes/sources/scsva_2019.txt')}). It is **not comparable** to the viewers in
[[fig:overview]]c: every plot it draws marks grid bins at their centers, so no mark carries a cell's identity,
a cell cannot be hovered or picked, and a selection's cells cannot be listed or exported. Its demonstration
upsampled 274,000 bone marrow cells to 100 million.

**What is and is not claimed.** A bin that holds one cell is a mark for that cell, snapped to the bin's center and
anonymous; at small N or deep zoom most marks are such bins. So the claim is not that every mark aggregates several
cells, only that no mark is a cell the user can identify, hover, pick or export.

| cells | marks drawn (non-empty bins) | marks holding one cell | most cells in one bin | source |
|---|---|---|---|---|
""" + "\n".join(rows) + f"""

The code evidence, one verdict per question with a permalink and a verbatim excerpt for every rendering path at
c9e8fd6: {L(PACK + '/scsva_render.txt')}. The pack's summary, what was not verified (the 3-D plotly default
tooltip, the Analysis and cloud panels in a browser) and how to reproduce it: {L(PACK + '/README.md')}.
The install that ran: {L(PACK + '/recipe/README.md', 'recipe/README.md')}. The screenshots' provenance:
{L(PACK + '/screenshots.txt')}.

""" + "\n".join(shots) + "\n"
    (DOCS / page).parent.mkdir(parents=True, exist_ok=True)
    (DOCS / page).write_text(body)
