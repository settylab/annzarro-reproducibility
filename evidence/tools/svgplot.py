"""Small inline-SVG charts for the measurement pages: computed at build time, no JavaScript.

Every mark carries a <title>, so hovering it shows the run id and its numbers (the browser's
own tooltip). Colours come from CSS variables in pages/assets/evidence.css (light and dark).
Shapes, not colour alone, carry the run status:

    ok          filled circle          fail, error, timeout   cross
    hang        hollow diamond         over a budget          filled square
    cap         up-arrow at the cap (the true peak is above it, unknown)
    excluded    grey hollow circle (harness wait, superseded build, overlapping session)
"""
from __future__ import annotations

import html
import math

STATUS_SHAPE = {"ok": "circle", "fail": "cross", "error": "cross", "timeout": "cross", "guard_refusal": "declined",
                "declined": "declined",
                "no_plot": "cross", "prep_stop": "cross", "hang": "diamond", "server_budget": "square",
                "cap": "arrow", "excluded": "ring"}
LEGEND = [("circle", "ok"), ("declined", "declined by design (the tool's memory guard)"),
          ("cross", "failed (error, timeout)"), ("diamond", "hang"),
          ("square", "over the server budget"), ("arrow", "stopped at the machine cap (peak above it)"),
          ("ring", "excluded (reason in the tooltip)")]


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def shape_of(status: str) -> str:
    return STATUS_SHAPE.get(status, "cross")


class Axis:
    def __init__(self, lo, hi, log=False, ticks=None, fmt=str, label=""):
        self.lo, self.hi, self.log, self.fmt, self.label = lo, hi, log, fmt, label
        self.ticks = ticks if ticks is not None else self._auto()

    def _auto(self):
        if self.log:
            a, b = math.floor(math.log10(self.lo)), math.ceil(math.log10(self.hi))
            return [10 ** k for k in range(a, b + 1) if self.lo <= 10 ** k <= self.hi]
        step = 10 ** math.floor(math.log10((self.hi - self.lo) / 4 or 1))
        for m in (1, 2, 5, 10):
            if (self.hi - self.lo) / (step * m) <= 6:
                step *= m
                break
        t = math.ceil(self.lo / step) * step
        out = []
        while t <= self.hi + 1e-9:
            out.append(round(t, 10))
            t += step
        return out

    def frac(self, v):
        if self.log:
            v = max(v, self.lo)
            return (math.log10(v) - math.log10(self.lo)) / (math.log10(self.hi) - math.log10(self.lo))
        return (v - self.lo) / (self.hi - self.lo)


class Chart:
    """One panel. Coordinates in data units; render() returns the <svg> element."""

    def __init__(self, x: Axis, y: Axis, title="", width=420, height=260, desc=""):
        self.x, self.y, self.title, self.w, self.h, self.desc = x, y, title, width, height, desc
        self.m = dict(l=50, r=12, t=26 if title else 10, b=40)
        self.items: list[str] = []
        self.under: list[str] = []
        self.used: set[str] = set()      # shapes drawn, for the chart's own legend

    # data -> pixels
    def px(self, v):
        return self.m["l"] + self.x.frac(v) * (self.w - self.m["l"] - self.m["r"])

    def py(self, v):
        return self.h - self.m["b"] - self.y.frac(v) * (self.h - self.m["t"] - self.m["b"])

    def clip_y(self, v):
        return min(max(v, self.y.lo), self.y.hi)

    def hline(self, y, label="", cls="ev-ref", left=False):
        if not self.y.lo <= y <= self.y.hi:
            return
        Y = self.py(y)
        self.under.append(f'<line class="{cls}" x1="{self.m["l"]}" x2="{self.w - self.m["r"]}" y1="{Y:.1f}" y2="{Y:.1f}"/>')
        if label:
            x, anchor = (self.m["l"] + 3, "start") if left else (self.w - self.m["r"] - 2, "end")
            self.under.append(f'<text class="ev-reflab" x="{x}" y="{Y - 3:.1f}" text-anchor="{anchor}">{esc(label)}</text>')

    def vband(self, x0, x1, label="", tip="", cls="ev-band"):
        a, b = self.px(x0), self.px(x1)
        t = f"<title>{esc(tip)}</title>" if tip else ""
        self.under.append(f'<rect class="{cls}" x="{min(a, b):.1f}" y="{self.m["t"]}" width="{abs(b - a):.1f}" '
                          f'height="{self.h - self.m["t"] - self.m["b"]}">{t}</rect>')

    def vline(self, x, label="", tip="", cls="ev-glyph"):
        X = self.px(x)
        t = f"<title>{esc(tip)}</title>" if tip else ""
        self.items.append(f'<g class="{cls}">{t}<line x1="{X:.1f}" x2="{X:.1f}" y1="{self.m["t"]}" '
                          f'y2="{self.h - self.m["b"]}"/>' + (
                              f'<text x="{X + 3:.1f}" y="{self.m["t"] + 10}">{esc(label)}</text>' if label else "") + "</g>")

    def line(self, pts, cls="ev-s1", dash=False, dot=False):
        pts = [(x, y) for x, y in pts if y is not None and not (isinstance(y, float) and math.isnan(y))]
        if len(pts) < 2:
            return
        d = " ".join(f"{self.px(x):.1f},{self.py(self.clip_y(y)):.1f}" for x, y in pts)
        self.items.append(f'<polyline class="{cls} ev-line{" ev-dash" if dash else ""}{" ev-dot" if dot else ""}" points="{d}"/>')

    def point(self, x, y, shape="circle", cls="ev-s1", tip="", r=3.6):
        if y is None or (isinstance(y, float) and math.isnan(y)):
            y = self.y.hi if shape == "arrow" else self.y.lo
        X, Y = self.px(x), self.py(self.clip_y(y))
        t = f"<title>{esc(tip)}</title>" if tip else ""
        self.used.add(shape)
        if shape == "circle":
            g = f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="{r}"/>'
        elif shape == "ring":
            g = f'<circle class="ev-hollow" cx="{X:.1f}" cy="{Y:.1f}" r="{r}"/>'
        elif shape == "square":
            g = f'<rect x="{X - r:.1f}" y="{Y - r:.1f}" width="{2 * r:.1f}" height="{2 * r:.1f}"/>'
        elif shape == "diamond":
            g = (f'<polygon class="ev-hollow" points="{X:.1f},{Y - r - 1:.1f} {X + r + 1:.1f},{Y:.1f} '
                 f'{X:.1f},{Y + r + 1:.1f} {X - r - 1:.1f},{Y:.1f}"/>')
        elif shape == "declined":       # a "no entry" sign: hollow circle with a bar
            g = (f'<circle class="ev-hollow" cx="{X:.1f}" cy="{Y:.1f}" r="{r + 0.6:.1f}"/>'
                 f'<line class="ev-stroke" x1="{X - r + 0.8:.1f}" x2="{X + r - 0.8:.1f}" y1="{Y:.1f}" y2="{Y:.1f}"/>')
        elif shape == "arrow":
            g = (f'<line class="ev-stroke" x1="{X:.1f}" x2="{X:.1f}" y1="{Y + 9:.1f}" y2="{Y:.1f}"/>'
                 f'<polygon points="{X - 4:.1f},{Y + 3:.1f} {X + 4:.1f},{Y + 3:.1f} {X:.1f},{Y - 4:.1f}"/>')
        else:  # cross
            g = (f'<path class="ev-stroke" d="M{X - r:.1f},{Y - r:.1f}L{X + r:.1f},{Y + r:.1f}'
                 f'M{X - r:.1f},{Y + r:.1f}L{X + r:.1f},{Y - r:.1f}"/>')
        self.items.append(f'<g class="ev-pt {cls}" tabindex="0">{t}{g}</g>')

    def text(self, x, y, s, anchor="start", cls="ev-note"):
        self.items.append(f'<text class="{cls}" x="{self.px(x):.1f}" y="{self.py(y):.1f}" '
                          f'text-anchor="{anchor}">{esc(s)}</text>')

    def _axes(self):
        L, R, T, B = self.m["l"], self.w - self.m["r"], self.m["t"], self.h - self.m["b"]
        out = [f'<rect class="ev-frame" x="{L}" y="{T}" width="{R - L}" height="{B - T}"/>']
        for v in self.x.ticks:
            X = self.px(v)
            out.append(f'<line class="ev-grid" x1="{X:.1f}" x2="{X:.1f}" y1="{T}" y2="{B}"/>'
                       f'<text class="ev-tick" x="{X:.1f}" y="{B + 13}" text-anchor="middle">{esc(self.x.fmt(v))}</text>')
        for v in self.y.ticks:
            Y = self.py(v)
            out.append(f'<line class="ev-grid" x1="{L}" x2="{R}" y1="{Y:.1f}" y2="{Y:.1f}"/>'
                       f'<text class="ev-tick" x="{L - 4}" y="{Y + 3:.1f}" text-anchor="end">{esc(self.y.fmt(v))}</text>')
        if self.x.label:
            out.append(f'<text class="ev-axlab" x="{(L + R) / 2:.1f}" y="{self.h - 6}" text-anchor="middle">{esc(self.x.label)}</text>')
        if self.y.label:
            out.append(f'<text class="ev-axlab" transform="translate(12,{(T + B) / 2:.1f}) rotate(-90)" '
                       f'text-anchor="middle">{esc(self.y.label)}</text>')
        if self.title:
            out.append(f'<text class="ev-ctitle" x="{L}" y="16">{esc(self.title)}</text>')
        return out

    def render(self, key=(), dashes=()) -> str:
        """The <svg>; with key (series swatches) and/or dashes, a compact legend of this chart's own
        series and of the point shapes it draws follows it. Text is sized in screen pixels at the
        chart's full width (--k scales the font to the viewBox), so every chart reads alike."""
        label = esc(self.desc or self.title or "chart")
        body = "".join(self._axes() + self.under + self.items)
        style = f"max-width:{WIDTH}px;--k:{self.w / WIDTH:.4f}" if self.w >= 200 else f"max-width:{self.w}px"
        out = (f'<svg class="ev-chart" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
               f'style="{style}" role="img" aria-label="{label}" xmlns="http://www.w3.org/2000/svg">{body}</svg>')
        if key or dashes:
            out += legend_html(key, shapes=True, only=self.used, dashes=dashes)
        return out


WIDTH = 720      # px at which every chart is drawn when the column allows it


def legend_html(series=(), shapes=True, skip=(), dashes=(), only=None) -> str:
    """A legend row: series swatches (cls, label) and the status shapes."""
    parts = [f'<span class="ev-key"><svg class="ev-chart" width="22" height="10"><line class="{c} ev-line" '
             f'x1="1" x2="21" y1="5" y2="5"/><circle class="{c}" cx="11" cy="5" r="3"/></svg>{esc(t)}</span>'
             for c, t in series]
    parts += [f'<span class="ev-key"><svg class="ev-chart" width="22" height="10"><line class="{c} ev-line {style}" '
              f'x1="1" x2="21" y1="5" y2="5"/></svg>{esc(t)}</span>' for c, style, t in dashes]
    if shapes:
        for shape, t in LEGEND:
            if shape in skip or (only is not None and (shape not in only or only == {"circle"})):
                continue
            c = Chart(Axis(0, 1, ticks=[]), Axis(0, 1, ticks=[]), width=14, height=14)
            c.m = dict(l=0, r=0, t=0, b=0)
            c.point(0.5, 0.5 if shape != "arrow" else 0.35, shape, "ev-sk", r=3.2)
            svg = c.render().replace('class="ev-frame"', 'class="ev-frame" style="display:none"')
            parts.append(f'<span class="ev-key">{svg}{esc(t)}</span>')
    return '<div class="ev-legend-row">' + "".join(parts) + "</div>"


def grid(svgs) -> str:
    return '<div class="ev-charts">' + "".join(f'<figure class="ev-fig">{s}</figure>' for s in svgs) + "</div>"


def gib(v) -> str:
    return f"{v:g}"


def n_fmt(v) -> str:
    v = float(v)
    if v >= 1e9:
        return f"{v / 1e9:g}B"
    if v >= 1e6:
        return f"{v / 1e6:g}M"
    if v >= 1e3:
        return f"{v / 1e3:g}k"
    return f"{v:g}"
