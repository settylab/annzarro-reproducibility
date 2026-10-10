"""Benchmarks > Scale: retired (2026-10-05). The page showed the pre-tag scale runs
(branch dominik/release-0.3) as current; the current release's runs are on measurements/scale.md.

This module keeps benchmarks/scale.md as a stub that sends old links there, out of the
navigation. The old generator is kept as gen/_retired_30_scale.py (not run: build.py only
runs gen/[0-9]*.py).
"""
NAV = []


def build(ctx):
    page = "benchmarks/scale.md"
    body = f"""# Scale: retired page

<meta http-equiv="refresh" content="0; url=../measurements/scale.html">

!!! warning "Superseded"
    This page showed scale runs made on a branch commit before the v0.3.0 tag. The paper
    reports the current release, so those runs are superseded and no page shows them.

**Go to [AnnZarro scale: every run](../measurements/scale.md)**: every rep of first
plot and recolour, the memory-guard edge, the subset reach to 1B and the 1B server.

The superseded files stay in git only.
"""
    (ctx.DOCS / page).parent.mkdir(parents=True, exist_ok=True)
    (ctx.DOCS / page).write_text(body)
