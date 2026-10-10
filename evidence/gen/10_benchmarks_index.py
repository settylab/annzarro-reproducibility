"""Benchmarks > Overview: every benchmark, the question it answers, where and on what it ran.

Also holds the helpers the other benchmark pages (30_scale.py, 40_hpc.py) load from this
file: Sanitizer (publication-safe rendering) and fnum.
"""
import csv
import html
import json
import re
from collections import Counter
from pathlib import Path

NAV = [("Benchmarks", "Overview", "benchmarks/index.md")]

# --------------------------------------------------------------------------- publication safety
# (label shown on the page, regex, replacement). Order matters: specific paths before generic ones.
# Labels never quote what they replace.
RULES = []   # the exported sources are already generalised: nothing is left to replace at build time


class Sanitizer:
    """sanitize(text) -> text with internal names generalised; .hits counts what it replaced."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.nodes = ctx.__dict__.setdefault("_bench_node_labels", {})
        if not self.nodes:                       # seed: every node in the HPC rows, numeric order
            names = set()
            for p in sorted((ctx.REPO / "benchmark/hpc/results").glob("*.csv")):
                for r in csv.DictReader(open(p)):
                    if r.get("node"):
                        names.add(r["node"])
            for n in sorted(names, key=lambda s: (re.sub(r"\d+", "", s), int(re.sub(r"\D", "", s) or 0))):
                self.nodes[n] = f"hpc-node-{len(self.nodes) + 1:02d}"
        self.rules = [(lab, re.compile(rx), rep) for lab, rx, rep in RULES]
        self.hits = Counter()

    def _node(self, m):
        return self.nodes.setdefault(m.group(0), f"hpc-node-{len(self.nodes) + 1:02d}")

    def __call__(self, text):
        text = str(text)
        for lab, rx, rep in self.rules:
            text, n = rx.subn(self._node if rep is None else rep, text)
            if n:
                self.hits[lab] += n
        return text

    def report(self):
        seen = set()
        rows = [(lab, "`hpc-node-NN` (one label per node, the same on every page)" if rep is None
                 else "`remote HPC orchestrator`" if callable(rep)
                 else (f"`{rep}`" if rep else "a repository-relative path"), self.hits[lab])
                for lab, _, rep in RULES if self.hits[lab] and not (lab in seen or seen.add(lab))]
        body = ("The source files keep their original names and paths; only this page generalises them. "
                "The table counts the replacements on this page; it never quotes what was replaced.\n\n")
        if not rows:
            return body + "Nothing was replaced on this page.\n"
        return body + "| what | rendered as | replacements |\n|---|---|---|\n" + "\n".join(
            f"| {a} | {b} | {c} |" for a, b, c in rows) + "\n"

    def presanitize(self, prefixes):
        """Copy every tracked text file under prefixes that holds internal names into the site, generalised,
        before any other page module links it; a later site_file() then finds it already copied."""
        files = self.ctx.git("ls-files", "--", *prefixes).splitlines()
        n = 0
        for rp in files:
            src = self.ctx.REPO / rp
            if rp in self.ctx.copied or not src.is_file() or src.stat().st_size > self.ctx.MAX_COPY:
                continue
            try:
                text = src.read_text()
            except UnicodeDecodeError:
                continue
            new = self(text)
            if new != text:
                dst = self.ctx.DOCS / "repo" / rp
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(new)
                self.ctx.copied.add(rp)
                n += 1
        return n

    def fix_copies(self, prefixes):
        """Rewrite the site's copies of text files under prefixes, so a linked file is as safe as the page."""
        for rp in sorted(self.ctx.copied):
            if not rp.startswith(tuple(prefixes)):
                continue
            dst = self.ctx.DOCS / "repo" / rp
            try:
                text = dst.read_text()
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            new = self(text)
            if new != text:
                dst.write_text(new)


def fnum(x, nd=None):
    """Seconds / GB the way the notes print them: 2 decimals below 10, 3 significant digits above."""
    if x in ("", None):
        return "–"
    x = float(x)
    if nd is not None:
        return f"{x:.{nd}f}"
    if abs(x) >= 100:
        return f"{x:.0f}"
    if abs(x) >= 10:
        return f"{x:.1f}"
    return f"{x:.2f}"


# --------------------------------------------------------------------------- the overview page
def build(ctx):
    REPO, DOCS = ctx.REPO, ctx.DOCS
    page = "benchmarks/index.md"
    san = Sanitizer(ctx)
    env = lambda p: json.loads((REPO / p).read_text())
    import yaml
    run0 = lambda p: env(p)["runs"][0]
    rel = yaml.safe_load((REPO / "evidence/superseded.yaml").read_text())["release"]["annzarro"]
    rtag = "v" + "".join(re.findall(r"\d", rel["version"]))                    # v0.4.1 -> v041

    def newest(pattern):
        """The release's environment file, else the newest earlier one (a series not yet rerun)."""
        fs = sorted(REPO.glob(pattern), key=lambda p: [int(x) for x in re.findall(r"_v(\d)(\d)(\d)_", p.name)[0]])
        mine = [p for p in fs if f"_{rtag}_" in p.name]
        return (mine or fs)[-1].relative_to(REPO).as_posix()
    scale_envf = newest("benchmark/scale/results/browser_v[0-9][0-9][0-9]_environment.json")
    lap_envf = newest("benchmark/results/scale_v[0-9][0-9][0-9]_environment.json")
    scale_env, lap_env = run0(scale_envf), run0(lap_envf)
    ceil = list(csv.DictReader(open(REPO / "benchmark/tool_ceiling/ceilings.csv")))
    tc_tools = sorted({r["tool"] for r in ceil})
    ram = lambda b: f"{int(b) / 2**30:.0f} GB"

    def soft(r):
        a = r["annzarro"]
        same = "v" + a["packages"]["annzarro"] == rel["version"]
        return (f'{a["packages"]["annzarro"]} (`{a["commit"][:7]}`'
                + (")" if same else f"; not yet rerun on the current release, {rel['version']})"))

    def mach(r):
        m = r["machine"]
        return f'{m["cpu"]} laptop, {ram(m["ram_bytes"])} RAM' + (f'; headless Chromium {r["browser"]["version"]}' if r.get("browser") else "")

    def link(path, label=None):
        return ctx.link_repo(page, path, label or path)

    bench = [
        ("AnnZarro scale", "../measurements/scale.md",
         "How long does AnnZarro take to open, recolor and draw every cell of 1M to 150M cells, where does the memory guard stop it, and how far does a subset reach?",
         mach(scale_env), soft(scale_env)),
        ("Tool ceiling: cells drawn within a client memory budget", "../measurements/tool-ceiling.md",
         f"How many cells does each of {len(tc_tools)} tools draw within 8, 16 and 32 GB of client memory?",
         "the same laptop; headless Chromium", rel["version"].lstrip("v")),
        ("Server at atlas scale: the HPC runs and the 1B run", "hpc.md",
         "What does one click cost the server for dense pairwise matrices, chunk shapes of a dense layer and the Tahoe-100M ladder on HPC nodes, and what does the 1B-cell server do over time?",
         "whole HPC compute nodes (Xeon Gold 6254, 36 CPUs); NFSv4.1 scratch",
         json.loads((REPO / "benchmark/scale/results/hpc/full/j5_v041/results_j5/http_hpc_filerwarm_environment.json")
                                  .read_text())["packages"]["annzarro"]),
        ("Laptop per-click benchmark", None,
         "Latency and server memory per click (gene column, cell row) on synthetic stores of 10k to 1M cells, and how chunk shape changes a cell-row read.",
         mach(lap_env), soft(lap_env)),
    ]
    lines = []
    for name, target, q, mach_, sw in bench:
        title = f"[{name}]({target})" if target else name
        src = "" if target else f" Sources: {link('benchmark/README.md')} and {link('benchmark/FINDINGS.md')}."
        lines.append(f"- {title}. {q} Machine: {mach_}. AnnZarro version: {sw}.{src}")

    body = f"""# Benchmarks

These benchmarks measure what AnnZarro and the tools it is compared with do at scale: how long a plot takes,
how much memory it needs, and how many cells fit. Each page states its method, the machine and the software, shows
every run, and links the files the numbers come from. All pages report AnnZarro {rel["version"]}.

{chr(10).join(lines)}
"""
    body = san(body)
    (DOCS / page).parent.mkdir(parents=True, exist_ok=True)
    (DOCS / page).write_text(body)
