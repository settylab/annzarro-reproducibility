import yaml, glob, re, datetime
OUT = "evidence/matrix/papers.yaml"
ARCH = yaml.safe_load(open("evidence/matrix/archive.yaml"))["urls"]
ORDER = ["cellxgene", "vitessce", "cirrocumulus", "isee", "ucsc-cell-browser", "shinycell", "scanpy-seurat",
         "single-cell-portal", "scope", "kana", "napari-spatialdata", "loupe"]
CITE = {"megill2021": "Megill et al. 2021", "czi2025": "CZI Cell Science Program et al. 2025", "keller2025": "Keller et al. 2025",
        "li2020": "Li et al. 2020 (Cumulus)", "ruealbrecht2018": "Rue-Albrecht et al. 2018", "benedetti2025": "Benedetti et al. 2025",
        "speir2021": "Speir et al. 2021", "ouyang2021": "Ouyang et al. 2021", "ouyang2020": "Ouyang et al. 2020 (preprint)",
        "chen2025": "Chen et al. 2025 (preprint)", "moore2025": "Moore et al. 2025", "wolf2018": "Wolf et al. 2018",
        "virshup2024": "Virshup et al. 2024", "virshup2021": "Virshup et al. 2021 (preprint)", "hao2024": "Hao et al. 2024",
        "tarhan2023": "Tarhan et al. 2023 (preprint)", "davie2018": "Davie et al. 2018", "li2022": "Li et al. 2022 (Fly Cell Atlas)",
        "lun2023": "Lun & Kancherla 2023", "lun2022": "Lun & Kancherla 2022 (preprint)", "marconato2025": "Marconato et al. 2025",
        "sofroniew_napari": "napari contributors (Zenodo)"}
FIX = {"lun2022": {"title": "Powering single-cell analyses in the browser with WebAssembly",
                   "version": "v1, posted 2022-03-04, then titled 'Single-cell data analysis in the browser'; v2 (2023-05-15) carries the current title. Quotes and sections are from v1."}}
COLS = [c["id"] for c in yaml.safe_load(open("evidence/matrix/columns.yaml"))["columns"]]
tools = {}
for f in sorted(glob.glob("frag_*.yaml")):
    tools.update(yaml.safe_load(open(f)))
out = {}
for t in ORDER:
    v = tools[t]
    papers = []
    for p in v.get("papers") or []:
        p = dict(p); p.update(FIX.get(p["key"], {}))
        url = f'https://doi.org/{p["doi"]}'
        a = ARCH.get(url) or {}
        q = {"key": p["key"], "cite": CITE[p["key"]], "role": p["role"], "doi": p["doi"], "url": url,
             "title": p["title"], "year": p["year"], "venue": p["venue"]}
        for k in ("version", "program", "note"):
            if p.get(k): q[k] = p[k]
        q["landing_page"] = a.get("final_url") or url
        q["checked"] = "2026-10-04"
        q["archive"] = a.get("archive") if str(a.get("archive") or "").startswith("http") else None
        q["archive_timestamp"] = a.get("archive_timestamp") if q["archive"] else None
        q["fulltext"] = p.get("fulltext")
        secs = p.get("sections") or {}
        bad = set(secs) - set(COLS)
        assert not bad, (p["key"], bad)
        q["sections"] = {c: secs[c] for c in COLS if secs.get(c)}
        papers.append(q)
    e = {"papers": papers}
    if v.get("none"): e["none"] = v["none"]
    cons = []
    for c in v.get("contradictions") or []:
        c = dict(c)
        if "comment" in c: c["note"] = c.pop("comment")
        if c.get("key") == "lun2022" and "title" in c.get("where", "").lower():
            continue   # not a contradiction: the notes give the current (v2, Crossref) title; v1 had another

        cons.append(c)
    if cons or "contradictions" in v: e["contradictions"] = cons
    out[t] = e
hdr = """# Papers behind the Fig. 1c marks, per tool, with the section or figure that speaks to each
# matrix column (ids from columns.yaml). Loaded by evidence/tools/refs.py (paper_refs, papers_for).
#
# sections.<column>: [{where, quote, indicates, note?}]
#   where      section heading as printed and/or figure panel or legend
#   quote      verbatim, at most 25 words ("..." marks an elision); every quote was checked
#              by script against the full text named in `fulltext` (2026-10-04)
#   indicates  what this passage alone indicates under the column definition: Y, P or N
# A column absent under a paper means the paper says nothing about it. Nothing is inferred.
# archive: closest Wayback snapshot of the landing page (read-only lookup, from archive.yaml).
# contradictions: places where a paper's text disagrees with notes/comparison/<tool>.md or a mark.
"""
with open(OUT, "w") as f:
    f.write(hdr)
    yaml.safe_dump({"checked": "2026-10-04", "tools": out}, f, sort_keys=False, width=200, allow_unicode=True)
for t, e in out.items():
    print(t, [(p["key"], len(p["sections"]), p["archive_timestamp"]) for p in e["papers"]])
