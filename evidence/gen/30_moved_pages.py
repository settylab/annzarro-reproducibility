"""Redirect pages for URLs that were public and have moved (out of the navigation).

benchmarks/tool-ceiling.md  -> measurements/tool-ceiling.md  (the two Tool ceiling pages became one, 2026-10-09)
benchmarks/scale.md         -> measurements/scale.md         (the scale page moved under Measurements, 2026-10-05)
"""
NAV = []

MOVED = [
    ("benchmarks/tool-ceiling.md", "Tool ceiling", "measurements/tool-ceiling"),
    ("benchmarks/scale.md", "AnnZarro scale: every run", "measurements/scale"),
]


def build(ctx):
    for page, title, target in MOVED:
        body = f"""# This page has moved

<meta http-equiv="refresh" content="0; url=../{target}.html">

**{title}** is now at [{target}.md](../{target}.md). If you are not taken there, follow the link.
"""
        (ctx.DOCS / page).parent.mkdir(parents=True, exist_ok=True)
        (ctx.DOCS / page).write_text(body)
