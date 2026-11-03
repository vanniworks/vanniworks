#!/usr/bin/env python3
"""Inject the 0/1 portrait into assets/banner.svg.

The portrait is drawn as 0/1 characters (same idea as heroPortrait.js on
vanniworks.com). The scan line reveals it on one sweep and wipes it on the
next, while the VANNI wordmark dims so the face reads through.

Usage: python3 scripts/face.py path/to/portrait.(png|webp|jpg)
Needs macOS `sips` to downsample the image (no Python deps).
"""
import os
import random
import re
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANNER = os.path.join(ROOT, "assets", "banner.svg")

W, H = 1280, 460
CELL = 6.5            # row height / font size
CW = CELL * 0.6       # char advance, forced with textLength
DRAW_H = 460.0
CX = 640.0
CYCLE = 11            # two scan sweeps of 5.5s
EASE = "cubic-bezier(.16,1,.3,1)"
COLORS = ["#5a160c", "#a02a18", "#F0402A", "#FF8A1F", "#FFD23A"]
LEVELS = [0.10, 0.26, 0.46, 0.70]


def read_bmp(path):
    data = open(path, "rb").read()
    off = struct.unpack_from("<I", data, 10)[0]
    w, h = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    bypp = bpp // 8
    stride = (w * bypp + 3) & ~3
    flip = h > 0
    h = abs(h)
    px = []
    for y in range(h):
        sy = h - 1 - y if flip else y
        row = []
        for x in range(w):
            i = off + sy * stride + x * bypp
            b, g, r = data[i], data[i + 1], data[i + 2]
            row.append((0.299 * r + 0.587 * g + 0.114 * b) / 255)
        px.append(row)
    return w, h, px


def sample(src):
    iw, ih = map(int, re.findall(r"pixel(?:Width|Height): (\d+)",
                                 subprocess.check_output(["sips", "-g", "pixelWidth", "-g", "pixelHeight", src], text=True)))
    draw_w = DRAW_H * iw / ih
    cols = int(draw_w / CW)
    rows = int(DRAW_H / CELL)
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "p.bmp")
        subprocess.check_call(["sips", "-s", "format", "bmp", "-z", str(rows), str(cols), src, "--out", out],
                              stdout=subprocess.DEVNULL)
        return read_bmp(out)


def build(src):
    random.seed(7)
    cols, rows, px = sample(src)
    ox = CX - cols * CW / 2
    # unsharp mask so the eyes, brows and mouth survive the downsample
    blur = [[sum(px[min(rows - 1, max(0, y + j))][min(cols - 1, max(0, x + i))]
                 for i in (-1, 0, 1) for j in (-1, 0, 1)) / 9 for x in range(cols)] for y in range(rows)]
    px = [[px[y][x] + 1.4 * (px[y][x] - blur[y][x]) for x in range(cols)] for y in range(rows)]
    flat = sorted(p for r in px for p in r)
    lo, hi = flat[int(len(flat) * 0.05)], flat[int(len(flat) * 0.985)]
    lines = []
    for y in range(rows):
        buckets = [[" "] * cols for _ in COLORS]
        for x in range(cols):
            dx = (x - cols / 2) / (cols / 2)
            dy = (y / rows - 0.5) / 0.62
            v = max(0.0, 1 - min(1.0, (dx * dx * 0.9 + dy * dy * 0.8) ** 0.5) ** 2.4)
            l = (min(1.0, max(0.0, (px[y][x] - lo) / (hi - lo))) ** 1.6) * v
            if l < LEVELS[0] * 0.8:
                continue
            b = sum(l > t for t in LEVELS)
            buckets[b][x] = random.choice("01")
        for b, chars in enumerate(buckets):
            s = "".join(chars).rstrip()
            if not s.strip():
                continue
            yy = y * CELL + CELL
            cls = ' class="fh"' if b == 4 and y % 3 == 0 else ""
            lines.append(f'<text x="{ox:.1f}" y="{yy:.0f}" fill="{COLORS[b]}" '
                         f'textLength="{len(s) * CW:.1f}"{cls}>{s}</text>')
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    svg = open(BANNER).read()
    svg = re.sub(r"\n?<!--face-css-->.*?<!--/face-css-->", "", svg, flags=re.S)
    svg = re.sub(r"\n?<!--face-->.*?<!--/face-->", "", svg, flags=re.S)
    svg = re.sub(r'<svg class="lg" ', "<svg ", svg)

    css = f"""<!--face-css-->
.face text{{font-size:{CELL:.0f}px;font-weight:700;white-space:pre}}
.fa{{animation:fa {CYCLE}s infinite}}
@keyframes fa{{0%{{transform:translateY(0);animation-timing-function:{EASE}}}50%,100%{{transform:translateY(540px)}}}}
.fb{{animation:fb {CYCLE}s infinite}}
@keyframes fb{{0%,50%{{transform:translateY(0);animation-timing-function:{EASE}}}100%{{transform:translateY(540px)}}}}
.lg{{animation:lg {CYCLE}s infinite}}
@keyframes lg{{0%,3%{{opacity:1}}14%,47%{{opacity:.16}}56%,100%{{opacity:1}}}}
.fh{{animation:fh 2.2s steps(1) infinite}}
@keyframes fh{{0%,100%{{fill:#FFD23A}}40%{{fill:#FFF1C2}}46%{{fill:#FFD23A}}}}
<!--/face-css-->"""
    svg = svg.replace("@media (prefers-reduced-motion:reduce)", css + "\n@media (prefers-reduced-motion:reduce)", 1)

    face = f"""<!--face-->
<mask id="fmk" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">
<rect class="fa" x="0" y="-600" width="{W}" height="600" fill="#fff"/>
<rect class="fb" x="0" y="-600" width="{W}" height="600" fill="#000"/>
</mask>
<g class="face" mask="url(#fmk)" opacity=".8" xml:space="preserve">
{build(sys.argv[1])}
</g>
<!--/face-->"""
    # face sits above the glow and frame, under the wordmark
    anchor = '<svg x="260.0" y="92"'
    svg = svg.replace(anchor, face + "\n" + anchor.replace("<svg ", '<svg class="lg" '), 1)
    open(BANNER, "w").write(svg)
    print("banner.svg updated")


if __name__ == "__main__":
    main()
