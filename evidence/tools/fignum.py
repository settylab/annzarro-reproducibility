"""The manuscript's figure numbers, from LaTeX's own labels: never typed by hand.

Source: the \\newlabel{fig:...}{{N}...} entries of manuscript/main.aux, written when the manuscript is
built. main.aux is a build product (gitignored), so its figure labels are kept in
evidence/figure_numbers.json: build.py refreshes that file whenever main.aux is newer than every
manuscript .tex file, and a clean clone (no LaTeX run) reads the committed copy.

    fig("fig:cellcell")          -> "Fig. 3"
    fig("fig:cellcell", "b")     -> "Fig. 3b"
    fig("figS:binary")           -> "Supplementary Fig. S1"
    expand("the paper's [[fig:cellcell]]b")  -> "the paper's Fig. 3b"

check() lists what build.py --check must fail on: a figures.yaml label or a [[label]] in the
evidence sources that the manuscript does not define, and a figure_numbers.json older than a
fresh main.aux.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUX = REPO / "manuscript/main.aux"
JSON = REPO / "evidence/figure_numbers.json"
REF = re.compile(r"\[\[((?:fig|figS):[\w-]+)\]\]")
SOURCES = ["evidence/matrix/tools/*.yaml", "evidence/matrix/columns.yaml", "evidence/notes/*.md",
           "evidence/pages/*.md", "evidence/claims.yaml", "evidence/gen/[0-9]*.py", "evidence/build.py"]


LOG = REPO / "manuscript/main.log"


def from_aux():
    """{label: number} from main.aux, or None when there is no fresh, finished aux.

    Fresh: newer than every manuscript .tex. Finished: the LaTeX run that wrote it has ended, i.e.
    main.log is at least as new as main.aux and records "Output written" (several sessions run
    make in the shared tree; a mid-run aux holds only the labels reached so far)."""
    if not AUX.exists():
        return None
    tex = [p for p in (REPO / "manuscript").rglob("*.tex")]
    if tex and AUX.stat().st_mtime < max(p.stat().st_mtime for p in tex):
        return None
    if not LOG.exists() or LOG.stat().st_mtime < AUX.stat().st_mtime \
            or "Output written" not in LOG.read_text(errors="replace")[-4000:]:
        return None
    out = {}
    for m in re.finditer(r"\\newlabel\{((?:fig|figS):[^}]+)\}\{\{([^}]*)\}", AUX.read_text(errors="replace")):
        out[m.group(1)] = m.group(2)
    return out


def numbers():
    """{label: number as LaTeX prints it}: the fresh aux if there is one, else the committed copy."""
    aux = from_aux()
    if aux:
        return aux
    return json.loads(JSON.read_text()) if JSON.exists() else {}


def refresh():
    """Write evidence/figure_numbers.json from a fresh main.aux; True when it changed."""
    aux = from_aux()
    if not aux:
        return False
    text = json.dumps(dict(sorted(aux.items())), indent=1) + "\n"
    if JSON.exists() and JSON.read_text() == text:
        return False
    JSON.write_text(text)
    return True


def fig(label, panels=""):
    n = numbers().get(label)
    if n is None:
        raise KeyError(f"no figure label {label!r} in the manuscript (manuscript/main.aux, evidence/figure_numbers.json)")
    return (f"Supplementary Fig. {n}" if label.startswith("figS:") else f"Fig. {n}") + panels


def expand_docs(docs):
    """Expand [[fig:label]] in every Markdown page the build wrote (the last pass before MkDocs)."""
    n = 0
    for f in Path(docs).rglob("*.md"):
        t = f.read_text(errors="replace")
        if "[[fig" in t:
            f.write_text(expand(t))
            n += 1
    return n


def expand(text):
    """[[fig:label]] -> 'Fig. N' in any text; an unknown label raises (check() reports it first)."""
    return REF.sub(lambda m: fig(m.group(1)), text) if isinstance(text, str) and "[[" in text else text


def placement(label):
    """Where the manuscript places the figure with this label, found by the label, never typed:
    'manuscript/body.tex:157', or, for a figure defined as a macro in another file and placed by
    calling it, 'manuscript/body.tex:454 (\\figscale, defined in manuscript/sections/figs_results.tex)'.
    None when the label is in no .tex file."""
    tex = sorted((REPO / "manuscript").rglob("*.tex"))
    for f in tex:
        lines = f.read_text(errors="replace").splitlines()
        for i, line in enumerate(lines):
            if f"\\label{{{label}}}" not in line:
                continue
            macro = None                   # the \newcommand{\figX} this label sits in, if any
            for j in range(i, -1, -1):
                m = re.match(r"\\newcommand\{\\(\w+)\}", lines[j])
                if m:
                    macro = m.group(1)
                    break
                if j < i and re.match(r"\\end\{figure\}\}", lines[j]):
                    break
            rel = f.relative_to(REPO).as_posix()
            if not macro:
                env = next((j for j in range(i, -1, -1) if "\\begin{figure" in lines[j]), i)
                return f"{rel}:{env + 1}"
            for g in tex:                  # the line that calls the macro on its own
                for k, l2 in enumerate(g.read_text(errors="replace").splitlines()):
                    if l2.strip() == f"\\{macro}":
                        return f"{g.relative_to(REPO).as_posix()}:{k + 1} (\\{macro}, defined in {rel})"
            return f"{rel}:{i + 1} (\\{macro}, never called)"
    return None


def check():
    import yaml
    errs = []
    nums = numbers()
    if not nums:
        errs.append("no figure numbers: neither a fresh manuscript/main.aux nor evidence/figure_numbers.json")
    aux = from_aux()
    if aux and JSON.exists() and json.loads(JSON.read_text()) != aux:
        errs.append("evidence/figure_numbers.json is older than manuscript/main.aux: run build.py and commit it")
    entries = yaml.safe_load((REPO / "evidence/figures.yaml").read_text())["figures"]
    for f in entries:
        if f["label"] not in nums:
            errs.append(f"figures.yaml {f['id']}: label {f['label']} is not a figure of the manuscript")
        elif placement(f["label"]) is None:
            errs.append(f"figures.yaml {f['id']}: label {f['label']} is in no manuscript .tex file")
    listed = {f["label"] for f in entries}
    for lab in sorted(set(nums) - listed):
        errs.append(f"{lab} ({fig(lab)}) is a figure of the manuscript with no entry in evidence/figures.yaml")
    for pat in SOURCES:
        for p in sorted(REPO.glob(pat)):
            for m in REF.finditer(p.read_text(errors="replace")):
                if m.group(1) not in nums:
                    errs.append(f"{p.relative_to(REPO)}: [[{m.group(1)}]] is not a figure of the manuscript")
    return errs


if __name__ == "__main__":
    e = check()
    print("\n".join(e) or "\n".join(f"{k}: {fig(k)}" for k in sorted(numbers())))
    raise SystemExit(1 if e else 0)
