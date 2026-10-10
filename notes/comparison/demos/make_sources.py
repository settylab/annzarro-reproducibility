"""Write notes/comparison/screens/SOURCES.yaml: attribution for every screenshot.

One entry per image: tool, software and version, URL shown, dataset and its licence, software
licence. Rules go from tool defaults to filename patterns (first match wins). "to check" means the
licence was not established; resolve those before the evidence site is published.
Run: python3 notes/comparison/demos/make_sources.py
"""
import re
from pathlib import Path

SCREENS = Path(__file__).resolve().parent.parent / "screens"

BM = ("Murine bone marrow ageing, 8,090 cells (the AnnZarro paper's demo store, bm_aging_showcase.zarr, "
      "converted by demos/_data/make_demo.py)", "CC BY 4.0 (Zenodo 10.5281/zenodo.15587768, Fred Hutch)")
VISIUM_BRAIN = ("10x Genomics Visium Mouse Brain Serial Section 1 (Sagittal-Anterior), Space Ranger 1.1.0", "CC BY 4.0")
DISCOVER = "CC BY 4.0 (CELLxGENE Discover requires CC BY 4.0 for hosted datasets)"

TOOLS = {
    "cellxgene": dict(software="CELLxGENE Annotate 1.3.0 (local) / CELLxGENE Explorer (hosted, single-cell-explorer dbbcef3)",
                      software_licence="MIT", url="http://127.0.0.1:8903", data=BM),
    "cirrocumulus": dict(software="Cirrocumulus 1.1.61", software_licence="BSD-3-Clause",
                         url="http://127.0.0.1:8901", data=BM),
    "isee": dict(software="iSEE 2.18.0 (Bioconductor 3.20, R 4.4.3)", software_licence="MIT",
                 url="http://127.0.0.1:8902", data=BM),
    "ucsc-cell-browser": dict(software="UCSC Cell Browser 1.2.20 (local build) / cells.ucsc.edu",
                              software_licence="GPL-3.0", url="http://127.0.0.1:8906/?ds=bm_demo", data=BM),
    "shinycell": dict(software="ShinyCell 2.1.0 (5c61db7)", software_licence="GPL-3.0",
                      url="http://127.0.0.1:8907", data=BM),
    "vitessce": dict(software="Vitessce (hosted app at vitessce.io, @vitessce 4.x) with local data",
                     software_licence="MIT", url="https://vitessce.io/?url=http://127.0.0.1:8904/config.json", data=BM),
    "kana": dict(software="Kana (kanaverse.org, gh-pages build)", software_licence="MIT",
                 url="https://www.kanaverse.org/kana/", data=BM),
    "scope": dict(software="SCope (scope.aertslab.org)", software_licence="GPL-3.0",
                  url="https://scope.aertslab.org", data=("public SCope session shown in the shot (see scope.md)", "to check")),
    "single-cell-portal": dict(software="Single Cell Portal (singlecell.broadinstitute.org)", software_licence="BSD-3-Clause",
                               url="https://singlecell.broadinstitute.org/single_cell",
                               data=("public SCP study named in the file name (see single-cell-portal.md)", "to check (per study)")),
    "napari-spatialdata": dict(software="napari 0.9.2 + napari-spatialdata 0.7.2 (spatialdata 0.8.0)",
                               software_licence="BSD-3-Clause", url="desktop window", data=VISIUM_BRAIN),
    "loupe": dict(software="Loupe Browser 9 (docs pages, not the app)",
                  software_licence="proprietary (10x Genomics), free download",
                  url="https://www.10xgenomics.com/support/software/loupe-browser/latest",
                  data=("as shown in the 10x documentation page", "10x Genomics documentation (screenshot shown as scholarly comparison)")),
    "manivault": dict(software="ManiVault Studio 1.5.0 (macOS desktop app)", software_licence="LGPL-3.0",
                      url="desktop app", data=BM),
    "scanpy-seurat": dict(software="scanpy (paper .venv) + matplotlib; code output, no GUI", software_licence="BSD-3-Clause",
                          url="script output", data=BM),
}

# (tool, filename regex) -> overrides
RULES = [
    ("cellxgene", r"explorer.*visium|m07|m11", dict(url="https://cellxgene.cziscience.com (Visium dataset, see cellxgene.md)",
                                                   data=("Visium dataset hosted on CELLxGENE Discover (see cellxgene.md)", DISCOVER))),
    ("cellxgene", r"^s0", dict(url="https://cellxgene.cziscience.com/e/dcfd4feb-18a3-4b30-81d7-1b0c544a8ab3.cxg/",
                               data=("Qiu et al. 2024 mouse embryonic development timelapse, 11,441,407 cells", DISCOVER))),
    ("cellxgene", r"explorer", dict(url="https://cellxgene.cziscience.com/e/53d208b0-2cfd-4366-9866-c3c6114081bc.cxg/",
                                    data=("Tabula Sapiens, all cells (or the Discover dataset named in cellxgene.md)", DISCOVER))),
    ("ucsc-cell-browser", r"^s0", dict(url="https://cells.ucsc.edu/?ds=mouse-pansci+all",
                                       data=("PanSci Organismal Aging, All (Zhang et al. 2025), 21,786,931 cells", "to check (cells.ucsc.edu dataset terms)"))),
    ("ucsc-cell-browser", r"portal|spatial", dict(url="https://cells.ucsc.edu (dataset in ucsc-cell-browser.md)",
                                                  data=("cells.ucsc.edu dataset named in ucsc-cell-browser.md", "to check"))),
    ("vitessce", r"lymph|m07|m11", dict(url="https://vitessce.io/#?dataset=human-lymph-node-10x-visium",
                                        data=("10x Genomics Visium human lymph node", "CC BY 4.0 (10x Genomics datasets)"))),
    ("shinycell", r"shinycell2|m07|m15", dict(software="ShinyCell2 showcase (shinycell.ouyanglab.com)",
                                              url="https://shinycell.ouyanglab.com/",
                                              data=("ShinyCell2 showcase dataset", "to check"))),
    ("napari-spatialdata", r"HE|m11", dict(data=("SpatialData Visium example with H&E (see napari-spatialdata.md)", "to check"))),
    ("kana", r"remote", dict(data=("no dataset (load dialog)", "n/a"))),
]


def main():
    import yaml  # run with a Python that has PyYAML (the paper .venv)
    images = []
    for img in sorted(SCREENS.glob("*/*.jpg")):
        tool = img.parent.name
        e = dict(TOOLS.get(tool, dict(software="unknown", software_licence="to check", url="unknown", data=("unknown", "to check"))))
        for t, pat, ov in RULES:
            if t == tool and re.search(pat, img.name):
                e.update(ov)
                break
        side = img.with_name(img.stem + ".annot.yaml")
        if side.exists():  # the sidecar knows what the shot shows; it wins over the defaults
            d = yaml.safe_load(side.read_text()) or {}
            for k in ("software", "url"):
                if d.get(k) and str(d[k]) != "?":
                    e[k] = str(d[k])
            if d.get("data") and str(d["data"]) != "?":
                e["data"] = (str(d["data"]), e["data"][1])
        dl = e["data"][0].lower()
        if "lymph" in dl:
            e["data"] = (e["data"][0], "CC BY 4.0 (10x Genomics datasets)")
        elif "spatial_demo" in dl and "visium" not in dl and "2,693" in dl:
            e["data"] = (e["data"][0], "CC BY 4.0 (10x Genomics Visium Mouse Brain Serial Section 1)")
        elif "spatial_demo" in dl or "mouse brain serial" in dl:
            e["data"] = (e["data"][0], "CC BY 4.0 (10x Genomics Visium Mouse Brain Serial Section 1)")
        elif "bm_spatial_test" in dl:
            e["data"] = (e["data"][0], "CC BY 4.0 (derived from Zenodo 10.5281/zenodo.15587768; synthetic coordinates)")
        elif "allen" in dl:
            e["data"] = (e["data"][0], "to check (Allen Institute terms of use)")
        if "tahoe" in dl:
            e["data"] = (e["data"][0], "CC0-1.0 (Tahoe-100M, Hugging Face tahoebio/Tahoe-100M)")
        if "_DOCS_" in img.name:
            e["data"] = ("none (documentation page)", "n/a")
        images.append({"image": f"{tool}/{img.name}", "tool": tool, "software": e["software"],
                       "software_licence": e["software_licence"], "url": e["url"],
                       "dataset": e["data"][0], "dataset_licence": e["data"][1]})
    head = ("# Attribution for every screenshot under notes/comparison/screens/ (generated by demos/make_sources.py).\n"
            "# 'to check' = licence not yet established; resolve before publishing the evidence site.\n")
    (SCREENS / "SOURCES.yaml").write_text(head + yaml.safe_dump({"images": images}, sort_keys=False, allow_unicode=True, width=120))
    print(len(images), "images;", sum("to check" in str(x) for x in images), "with 'to check'")


if __name__ == "__main__":
    main()
