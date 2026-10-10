"""Print Fig. 1c as drawn, as JSON: run in the repository's .venv (it imports figures/fig_comparison.py).

The figure's own draw() is run on a figure that is never saved, with mark() and draw_strip()
wrapped so every mark, footnote and strip glyph is recorded with the arguments the figure used,
and every text the figure writes (headers, column labels, legend) is read back from the axes.
evidence/tools/figmarks.figure_model() calls this; the evidence site's matrix is rendered from
its output and build.py --check compares the site against it, so the two cannot drift.

Usage: .venv/bin/python evidence/tools/figmodel_dump.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import matplotlib  # noqa: E402

matplotlib.use("pdf")       # vector backend: no GUI, and it lays out every glyph the figure uses
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.text import Annotation  # noqa: E402

import figures.fig_comparison as f  # noqa: E402

marks, strips = [], []
_mark, _strip = f.mark, f.draw_strip


def mark(ax, x, y, v):
    marks.append((round(x, 4), round(y, 4), v))
    return _mark(ax, x, y, v)


def draw_strip(ax, x0, w, y, pts, measured_any, footnote, hosted=False, reach=None, **kw):
    """Records the arguments and the row's note as drawn (e.g. "not measured", "hosted", a reason),
    and passes everything on (new keywords included) unchanged."""
    before = len(ax.texts)
    out = _strip(ax, x0, w, y, pts, measured_any, footnote, hosted=hosted, reach=reach, **kw)
    notes = [t.get_text() for t in ax.texts[before:] if t.get_style() == "italic" and t.get_text()]
    strips.append({"y": round(y, 4), "pts": [[k, float(n), bool(lo), lab] for k, n, lo, lab in pts],
                   "measured_any": bool(measured_any), "footnote": footnote, "hosted": bool(hosted),
                   "reach": float(reach) if reach else None, "note": notes[-1] if notes else "",
                   **{k: v for k, v in kw.items() if isinstance(v, (str, int, float, bool))}})
    return out


f.mark, f.draw_strip = mark, draw_strip
fig = plt.figure(figsize=(f.W, f.H))
ax = fig.add_axes([0, 0, 1, 1])
f.draw(ax)

rows = []
for (name, raw, doc), y in zip(f.TOOLS, f.row_y):
    drawn = [v for (x, yy, v) in marks if abs(yy - y) < 1e-3 and x >= min(f.col_x) - 1e-3]
    s = next((s for s in strips if abs(s["y"] - y) < 1e-3), None)
    rows.append({"name": name, "marks": "".join(drawn), "documented": doc,
                 "dagger": bool(f.STRIP and f.server_rendered(name)),
                 "notes": {str(k): v for (n, k), v in f.MARK_NOTES.items() if n == name},
                 "strip": s})

legend_y = f.LEGEND_H
texts = [t for t in ax.texts if t.get_text()]
legend = []
for t in sorted((t for t in texts if t.get_position()[1] < legend_y), key=lambda t: (-round(t.get_position()[1], 3), t.get_position()[0])):
    tx, ty = t.get_position()
    glyph = None
    near = []
    for ln in ax.lines:
        xs, ys = ln.get_xdata(), ln.get_ydata()
        if len(xs) and ln.get_marker() not in (None, "None", "") and abs(ys[-1] - ty) < 0.01 and tx - 0.3 < xs[-1] < tx:
            near.append((xs[-1], ln))
    arrows = [a for a in ax.texts if isinstance(a, Annotation) and not a.get_text()
              and abs(a.xy[1] - ty) < 0.01 and tx - 0.3 < a.xy[0] <= tx]
    leg_marks = [v for (x, yy, v) in marks if abs(yy - ty) < 0.01 and tx - 0.3 < x < tx]
    if leg_marks:
        glyph = "mark:" + leg_marks[-1]
    elif near:
        ln = max(near, key=lambda p: p[0])[1]
        m, fc = ln.get_marker(), matplotlib.colors.to_hex(ln.get_markerfacecolor())
        ec = matplotlib.colors.to_hex(ln.get_markeredgecolor())
        accent = matplotlib.colors.to_hex(getattr(f, "STRIP_COLOR", f.ACCENT))   # the strip's own color since the 2026-10-08 review
        if m == "o" and fc == "#ffffff" and ec != accent:
            raise SystemExit(f"figmodel_dump: open circle in the legend ({t.get_text()!r}): the figure has no hollow glyph (873c846)")
        glyph = {"o": "ring" if fc == "#ffffff" else "client",
                 "s": "server", "^": "input", "D": "documented"}.get(m, m)
    elif arrows:
        glyph = "arrow"
    legend.append({"glyph": glyph, "text": t.get_text()})

head = {"groups": [[g, cols] for g, cols in f.GROUPS],
        "scale_header": next((t.get_text() for t in texts if "budget" in t.get_text() and t.get_position()[1] > f.grid_top), ""),
        "axis": [t.get_text() for t in texts if t.get_position()[1] > f.grid_top
                 and __import__("re").fullmatch(r"\d+(?:\.\d+)?[kMB]", t.get_text())],
        "strip_range": [f.STRIP_LO, f.STRIP_HI] if f.STRIP else None,
        # the strip's colour as the figure draws it (fig_comparison.STRIP_COLOR, else the accent)
        "strip_color": matplotlib.colors.to_hex(getattr(f, "STRIP_COLOR", f.ACCENT))}
print(json.dumps({"rows": rows, "legend": legend, "head": head,
                  "texts": [t.get_text() for t in texts]}, ensure_ascii=False))
