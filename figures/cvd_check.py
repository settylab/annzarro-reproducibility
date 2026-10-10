"""Colour-vision check for figure colour pairs: CIEDE2000 difference under normal vision and simulated
protanopia, deuteranopia and tritanopia (Machado, Oliveira & Fernandes 2009, severity 1.0, applied in linear sRGB).

Usage: python figures/cvd_check.py            # Fig. 1c: Cells-strip colour against the figure's other colours
       python figures/cvd_check.py '#aabbcc' '#ddeeff' ...   # every pair of the given colours
A pair is distinguishable when its smallest difference over the four kinds of vision is at least 20 (ΔE2000).
"""
import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MACHADO = {
    "normal": np.eye(3),
    "protan": np.array([[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]]),
    "deutan": np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]]),
    "tritan": np.array([[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]),
}
THRESHOLD = 20.0


def _lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _hex(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


def _lab(lin_rgb):
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = m @ np.clip(lin_rgb, 0, 1) / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def de2000(a, b):
    L1, a1, b1 = a; L2, a2, b2 = b
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2); Cm = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p, h2p = np.degrees(np.arctan2(b1, a1p)) % 360, np.degrees(np.arctan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dh = h2p - h1p
    if C1p * C2p == 0: dh = 0
    elif dh > 180: dh -= 360
    elif dh < -180: dh += 360
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2))
    Lm, Cmp = (L1 + L2) / 2, (C1p + C2p) / 2
    hs = h1p + h2p
    hm = hs if C1p * C2p == 0 else (hs / 2 if abs(h1p - h2p) <= 180 else ((hs + 360) / 2 if hs < 360 else (hs - 360) / 2))
    T = 1 - 0.17 * np.cos(np.radians(hm - 30)) + 0.24 * np.cos(np.radians(2 * hm)) + 0.32 * np.cos(np.radians(3 * hm + 6)) - 0.20 * np.cos(np.radians(4 * hm - 63))
    SL = 1 + 0.015 * (Lm - 50) ** 2 / np.sqrt(20 + (Lm - 50) ** 2); SC = 1 + 0.045 * Cmp; SH = 1 + 0.015 * Cmp * T
    RT = -2 * np.sqrt(Cmp ** 7 / (Cmp ** 7 + 25 ** 7)) * np.sin(np.radians(60 * np.exp(-(((hm - 275) / 25) ** 2))))
    return float(np.sqrt((dLp / SL) ** 2 + (dCp / SC) ** 2 + (dHp / SH) ** 2 + RT * (dCp / SC) * (dHp / SH)))


def diffs(c1, c2):
    out = {}
    for k, M in MACHADO.items():
        out[k] = de2000(_lab(M @ _lin(_hex(c1))), _lab(M @ _lin(_hex(c2))))
    return out


def report(pairs):
    ok = True
    print(f"{'pair':34} {'normal':>7} {'protan':>7} {'deutan':>7} {'tritan':>7}   min")
    for (n1, c1), (n2, c2) in pairs:
        d = diffs(c1, c2); m = min(d.values()); ok &= m >= THRESHOLD
        print(f"{n1 + ' vs ' + n2:34} " + " ".join(f"{d[k]:7.1f}" for k in MACHADO) + f"   {m:5.1f} {'ok' if m >= THRESHOLD else 'LOW'}")
    return ok


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cs = [(c, c) for c in sys.argv[1:]]
        sys.exit(0 if report(list(itertools.combinations(cs, 2))) else 1)
    from figures import fig_comparison as fc
    from figures.style import INK, MUTED, SECONDARY
    strip = ("strip " + fc.STRIP_COLOR, fc.STRIP_COLOR)
    others = [("matrix Y " + fc.ACCENT, fc.ACCENT), ("white", "#ffffff"), ("band " + fc.BAND, fc.BAND),
              ("ink " + INK, INK), ("muted " + MUTED, MUTED), ("secondary " + SECONDARY, SECONDARY)]
    sys.exit(0 if report([(strip, o) for o in others]) else 1)
