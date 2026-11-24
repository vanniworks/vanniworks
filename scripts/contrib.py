#!/usr/bin/env python3
"""Build assets/contrib.svg.

Two armoured 3D fighters punch spinning contribution cubes at
each other across a 3D city of contribution bars, seen in perspective. Every hit
sends a shockwave across the floor and glitches the count, an extruded 3D number
built from 0/1 cells.

Built to stay light to animate (phones): the city is a few dozen merged paths,
and the two fighters are a 3D model (scripts/creatures.js: RobotExpressive by
Tomás Laulhé, CC0, restyled) rendered once by `npm run bake` into strips of frames
in assets/src/figures.json. Without that file they fall back to 0/1 text figures.

The grid is made up (it spells VANNI). The numbers are real, from the GitHub
GraphQL API.

Env: GH_TOKEN (or GITHUB_TOKEN), GH_LOGIN (default: vanniworks).
Without a token it reuses the numbers cached in assets/contrib.json.
Pure stdlib.
"""
import datetime as dt
import json
import math
import os
import random
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "contrib.svg")
CACHE = os.path.join(ROOT, "assets", "contrib.json")
LOGIN = os.environ.get("GH_LOGIN", "vanniworks")

W, H = 1280, 540
FONT = "ui-monospace,'JetBrains Mono',SFMono-Regular,Menlo,Consolas,monospace"
CREAM, YEL, ORA, RED = "#FFF1C2", "#FFD23A", "#FF8A1F", "#F0402A"
GRID_LV = ["#121212", "#3a0e07", "#7a1d10", "#c4321d", ORA, YEL]
T = 3.6  # one full exchange, seconds


# ------------------------------------------------------------------ data

def gql(query, variables, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "vanniworks-readme"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        with open(CACHE) as f:
            return json.load(f)
    q = """query($l:String!){user(login:$l){contributionsCollection{
      contributionYears contributionCalendar{totalContributions weeks{contributionDays{contributionCount}}}}}}"""
    u = gql(q, {"l": LOGIN}, token)["user"]["contributionsCollection"]
    cal = u["contributionCalendar"]
    counts = [d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]]
    total_all = 0
    for y in u["contributionYears"]:
        qy = """query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){
          contributionsCollection(from:$f,to:$t){contributionCalendar{totalContributions}}}}"""
        d = gql(qy, {"l": LOGIN, "f": f"{y}-01-01T00:00:00Z", "t": f"{y}-12-31T23:59:59Z"}, token)
        total_all += d["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    best = run = 0
    for c in counts:
        run = run + 1 if c else 0
        best = max(best, run)
    cur = 0
    for i, c in enumerate(reversed(counts)):
        if c:
            cur += 1
        elif i > 0:  # today may still be empty
            break
    data = {
        "year": cal["totalContributions"],
        "all": total_all,
        "best_day": max(counts or [0]),
        "streak": cur,
        "best_streak": best,
        "updated": dt.date.today().isoformat(),
    }
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=2)
    return data


# ------------------------------------------------------------------ helpers

def cells_to_rects(cells, size, gap=1, rng=None):
    out = []
    for (c, r) in sorted(cells, key=lambda k: (k[1], k[0])):
        out.append(f'<rect x="{c * size}" y="{r * size}" width="{size - gap}" height="{size - gap}"/>')
    return "".join(out)


def rows_to_text(cells, cw, ch, fill=None):
    """cells: dict (col,row) -> char. One <text> per row with spaces between;
    textLength pins the advance so any monospace font lines up."""
    by_row = {}
    for (c, r), v in cells.items():
        by_row.setdefault(r, {})[c] = v
    out = []
    for r in sorted(by_row):
        row = by_row[r]
        c0, c1 = min(row), max(row)
        s = "".join(row.get(c, " ") for c in range(c0, c1 + 1))
        f = f' fill="{fill}"' if fill else ""
        out.append(f'<text x="{c0 * cw:.1f}" y="{(r + 1) * ch - 1:.1f}" textLength="{len(s) * cw:.1f}"{f}>{s}</text>')
    return "".join(out)


# ------------------------------------------------------------------ the number

SEG = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
       "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg"}
DW, DH = 12, 16  # digit size in cells


def seg_cells(segs):
    s = set()
    for g in segs:
        if g == "a":
            s |= {(c, r) for c in range(DW) for r in (0, 1)}
        if g == "g":
            s |= {(c, r) for c in range(DW) for r in (7, 8)}
        if g == "d":
            s |= {(c, r) for c in range(DW) for r in (14, 15)}
        if g == "f":
            s |= {(c, r) for c in range(3) for r in range(0, 9)}
        if g == "b":
            s |= {(c, r) for c in range(DW - 3, DW) for r in range(0, 9)}
        if g == "e":
            s |= {(c, r) for c in range(3) for r in range(7, DH)}
        if g == "c":
            s |= {(c, r) for c in range(DW - 3, DW) for r in range(7, DH)}
    for corner in ((0, 0), (DW - 1, 0), (0, DH - 1), (DW - 1, DH - 1)):
        s.discard(corner)
    return s


def number_cells(text, rng, ghost=False):
    cells, x = {}, 0
    for chx in text:
        if chx == ",":
            for c, r in ((0, 13), (1, 13), (0, 14), (1, 14), (0, 15)):
                cells[(x + c, r)] = rng.choice("01")
            x += 4
            continue
        if chx == "1" and not ghost:
            for c, r in ((6, 0), (7, 0), (8, 0), (7, 1), (8, 1)):
                cells[(x + c, r)] = rng.choice("01")
        for c, r in seg_cells("abcdefg" if ghost else SEG[chx]):
            cells[(x + c, r)] = rng.choice("01")
        x += DW + 3
    return cells, x - 3


# ------------------------------------------------------------------ the entities

FW, FH = 160, 330          # figure box, px
FCW, FCH = 3.6, 6.0        # figure char cell
FCOLS, FROWS = int(FW / FCW), int(FH / FCH)


def bez(p0, p1, p2, t):
    a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
    return a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def in_poly(x, y, pts):
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def horn_hit(x, y, p0, p1, p2, w0, w1):
    for i in range(24):
        t = i / 23
        hx, hy = bez(p0, p1, p2, t)
        if math.hypot(x - hx, y - hy) < w0 + (w1 - w0) * t:
            return True
    return False


def shape(x, y, hem):
    """Canonical figure, facing right. 0 outside, 1 body, 2 void inside the hood."""
    if horn_hit(x, y, (68, 60), (34, 46), (26, 4), 10, 2.5):
        return 1
    if horn_hit(x, y, (96, 58), (132, 40), (128, 0), 10, 2.5):
        return 1
    if ((x - 84) / 30) ** 2 + ((y - 82) / 34) ** 2 < 1:
        if ((x - 90) / 16) ** 2 + ((y - 86) / 19) ** 2 < 1:
            return 2
        return 1
    if in_poly(x, y, [(40, 112), (128, 112), (140, 150), (124, 214), (48, 214), (30, 150)]):
        return 1
    if seg_dist(x, y, 44, 124, 24, 226) < 9 or seg_dist(x, y, 24, 226, 30, 246) < 5:
        return 1
    if in_poly(x, y, [(48, 200), (124, 200), (154, FH), (8, FH)]):
        return 0 if y > hem(x) else 1
    return 0


def figure(facing, rng, pal):
    """facing 1 looks right, -1 looks left (mirrored geometry, glyphs stay readable)."""
    hem_pts = [FH - 26 + 14 * math.sin(i * 0.9) + rng.uniform(-10, 10) for i in range(FCOLS + 1)]

    def hem(x):
        return hem_pts[min(FCOLS, max(0, int(x / FCW)))]

    grid = {}
    for r in range(FROWS):
        for c in range(FCOLS):
            cx, cy = (c + 0.5) * FCW, (r + 0.5) * FCH
            v = shape(cx if facing == 1 else FW - cx, cy, hem)
            if v:
                grid[(c, r)] = v
    # distance to the outline in cells, for rim light
    dist = {}
    for (c, r) in grid:
        edge = any((c + dc, r + dr) not in grid for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        dist[(c, r)] = 0 if edge else 99
    for _ in range(6):
        for (c, r) in grid:
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (c + dc, r + dr)
                if n in dist and dist[n] + 1 < dist[(c, r)]:
                    dist[(c, r)] = dist[n] + 1

    buckets = [dict() for _ in pal]
    flash = {}
    for (c, r), v in grid.items():
        cx = (c + 0.5) * FCW
        toward = cx / FW if facing == 1 else 1 - cx / FW  # side facing the opponent is lit
        rim = math.exp(-dist[(c, r)] / 1.6)
        lum = 0.2 + rim * (0.2 + 0.75 * toward) + 0.14 * (r / FROWS) + 0.1 * toward + rng.uniform(-0.07, 0.07)
        if v == 2:
            lum = 0.03 + rng.uniform(0, 0.04)
        if r * FCH > FH - 70 and rng.random() < (r * FCH - (FH - 70)) / 90:
            continue  # the hem dissolves
        b = 0 if lum < 0.16 else 1 if lum < 0.3 else 2 if lum < 0.48 else 3 if lum < 0.68 else 4
        ch = rng.choice("01")
        buckets[b][(c, r)] = ch
        flash[(c, r)] = ch
    body = "".join(rows_to_text(b, FCW, FCH, fill=pal[i]) for i, b in enumerate(buckets) if b)
    flash_svg = rows_to_text(flash, FCW, FCH, fill=CREAM)

    eyes = [(80, 84), (97, 84)]
    if facing == -1:
        eyes = [(FW - x, y) for x, y in eyes]
    shoulder = (124, 124) if facing == 1 else (FW - 124, 124)
    chest = (FW / 2 + 10 * facing, 160)
    return body, flash_svg, eyes, shoulder, chest


def arm(facing, rng, fill):
    """Throwing arm in pivot-local coords (pivot = shoulder), raised forward, clawed."""
    cells = {}
    segs = [((0, 0), (40, -46), 6.5), ((40, -46), (54, -54), 3), ((40, -46), (56, -44), 3), ((40, -46), (46, -62), 3)]
    for r in range(-12, 4):
        for c in range(-4, 16):
            x, y = (c + 0.5) * FCW, (r + 0.5) * FCH
            if any(seg_dist(x, y, *a, *b) < w for a, b, w in segs):
                cells[(c, r)] = rng.choice("01")
    if facing == -1:
        cells = {(-c - 1, r): v for (c, r), v in cells.items()}
    return rows_to_text(cells, FCW, FCH, fill=fill), (54 * facing, -54)


# ------------------------------------------------------------------ build


FIGS_JSON = os.path.join(ROOT, "assets", "src", "figures.json")

GCOLS, GROWS = 53, 7
LEVEL_H = [0.06, 0.2, 0.36, 0.52, 1.0, 1.35]  # bar heights per level, world units (the letters are 5)
ROW_P, BAR_D = 1.25, 1.0  # the rows' spacing and the bars' depth: near-square cells, so the letters read
LEVEL_TOP = ["#191919", "#5a160c", "#a02a18", "#e0401f", ORA, YEL]


def shade(hex_, k):
    """darker (k < 1) or toward cream (k > 1)"""
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    if k <= 1:
        r, g, b = r * k, g * k, b * k
    else:
        t = k - 1
        r, g, b = r + (255 - r) * t, g + (241 - g) * t, b + (194 - b) * t
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


class Cam:
    """A pinhole camera above the front of the city, tilted down at it."""

    def __init__(self, cx, cy, f, pos, pitch_deg):
        self.cx, self.cy, self.f, self.pos = cx, cy, f, pos
        a = math.radians(pitch_deg)
        self.ca, self.sa = math.cos(a), math.sin(a)

    def p(self, x, y, z):
        vx, vy, vz = x - self.pos[0], y - self.pos[1], z - self.pos[2]
        yc = vy * self.ca + vz * self.sa
        zc = -vy * self.sa + vz * self.ca
        return self.cx + self.f * vx / zc, self.cy - self.f * yc / zc


def poly(pts):
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"


def make_grid(rng):
    """Made-up activity that spells VANNI, levels 0..5 (same recipe as before)."""
    cells = [[0] * GCOLS for _ in range(GROWS)]
    # 5 wide, so the N gets its diagonal and every letter reads from above
    font = {"V": ["10001", "10001", "10001", "01010", "00100"], "A": ["01110", "10001", "11111", "10001", "10001"],
            "N": ["10001", "11001", "10101", "10011", "10001"], "I": ["11111", "00100", "00100", "00100", "11111"]}
    for x in range(GCOLS):
        wave = 0.5 + 0.5 * math.sin(x / 4.3)
        for y in range(GROWS):
            r = rng.random()
            cells[y][x] = 0 if r < 0.42 - wave * 0.18 else 1 if r < 0.74 else 2 if r < 0.92 else 3
    word = "VANNI"
    start = (GCOLS - (len(word) * 6 - 1)) // 2
    for i, chx in enumerate(word):
        for y, line in enumerate(font[chx]):
            for dx, bit in enumerate(line):
                if bit == "1":
                    cells[y + 1][start + i * 6 + dx] = 5  # every letter cell the same: tall and bright
    return cells


def city(cam, cells, rows_css):
    """The grid as bars in perspective. Painted back row first; within a row the side faces,
    then the tops, then the fronts, each merged into one path per colour, so the whole city
    is a few dozen paths however many bars it has."""
    out = []
    size = 0.8
    for r in range(GROWS - 1, -1, -1):  # far to near
        z0 = r * ROW_P
        z1 = z0 + BAR_D
        faces = {}  # (kind, level) -> [paths]
        for c in range(GCOLS):
            lv = cells[GROWS - 1 - r][c]
            h = LEVEL_H[lv]
            x0 = (c - GCOLS / 2) * 1.0
            x1 = x0 + size
            # the side you can see: the one facing the camera's middle
            if x1 < cam.pos[0]:
                side = [cam.p(x1, 0, z0), cam.p(x1, 0, z1), cam.p(x1, h, z1), cam.p(x1, h, z0)]
            elif x0 > cam.pos[0]:
                side = [cam.p(x0, 0, z0), cam.p(x0, 0, z1), cam.p(x0, h, z1), cam.p(x0, h, z0)]
            else:
                side = None
            top = [cam.p(x0, h, z0), cam.p(x1, h, z0), cam.p(x1, h, z1), cam.p(x0, h, z1)]
            front = [cam.p(x0, 0, z0), cam.p(x1, 0, z0), cam.p(x1, h, z0), cam.p(x0, h, z0)]
            if side and lv:
                faces.setdefault(("s", lv), []).append(poly(side))
            faces.setdefault(("t", lv), []).append(poly(top))
            if lv:
                faces.setdefault(("f", lv), []).append(poly(front))
        g = []
        for kind in ("s", "t", "f"):
            for lv in range(6):
                d = faces.get((kind, lv))
                if not d:
                    continue
                top = LEVEL_TOP[lv]
                fill = f"url(#wv{lv})" if kind == "t" else shade(top, 0.62 if kind == "f" else 0.4)
                g.append(f'<path d="{"".join(d)}" fill="{fill}"/>')
        # each row rises out of the floor, front rows first
        out.append(f'<g class="rw" style="animation-delay:{0.25 + (GROWS - 1 - r) * 0.0 + r * 0.09:.2f}s">{"".join(g)}</g>')
    return "".join(out)


def cube(s, cols):
    """a small cube seen from above-front: top, left and right faces"""
    a, b = s * 0.5, s * 0.29
    top = poly([(0, -b * 2), (a, -b), (0, 0), (-a, -b)])
    left = poly([(-a, -b), (0, 0), (0, s * 0.62), (-a, s * 0.62 - b)])
    right = poly([(a, -b), (0, 0), (0, s * 0.62), (a, s * 0.62 - b)])
    return (f'<path d="{top}" fill="{cols[0]}"/><path d="{left}" fill="{cols[1]}"/>'
            f'<path d="{right}" fill="{cols[2]}"/>')


def figure_parts(rng):
    """The two entities, as vector 0/1 text (what gets baked), plus where their eyes, hands
    and chests are."""
    pal_l = ["#1f0905", "#5a160c", "#a02a18", ORA, YEL]
    pal_r = ["#1a0604", "#4a0f08", "#8a1c10", RED, ORA]
    parts = {}
    for side, facing, pal in (("L", 1, pal_l), ("R", -1, pal_r)):
        fbody, fflash, eyes, shoulder, chest = figure(facing, rng, pal)
        arm_svg, hand = arm(facing, rng, pal[3])
        parts[side] = dict(body=fbody, flash=fflash, arm=arm_svg, eyes=eyes, shoulder=shoulder, chest=chest, hand=hand)
    return parts


def build(d):
    rng = random.Random(1337)
    parts = figure_parts(random.Random(1337))
    try:
        with open(FIGS_JSON) as f:
            baked = json.load(f)
    except OSError:
        baked = {}

    css = [
        f"text{{font-family:{FONT}}}",
        ".fig text,.arm text{font-size:6px;font-weight:700;white-space:pre}",
        ".ash text{font-size:9px;font-weight:700}",
    ]
    defs, body = [], []
    lx, rx, fy = 34, W - 34 - FW, H - 18 - FH
    num_y = 70

    flight = 1.0
    throws = {"L": 0.45, "R": 2.25}
    hits = {"R": throws["L"] + flight, "L": throws["R"] + flight}

    # ---------- backdrop
    defs.append(f'<radialGradient id="rg" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{ORA}" stop-opacity=".26"/><stop offset="1" stop-color="{ORA}" stop-opacity="0"/></radialGradient>')
    defs.append(f'<radialGradient id="rr" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{RED}" stop-opacity=".32"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></radialGradient>')
    defs.append(f'<radialGradient id="ey" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{YEL}" stop-opacity=".9"/><stop offset="1" stop-color="{YEL}" stop-opacity="0"/></radialGradient>')
    defs.append(f'<linearGradient id="fl" x1="0" x2="1"><stop offset="0" stop-color="{ORA}" stop-opacity="0"/><stop offset=".5" stop-color="{ORA}" stop-opacity=".55"/><stop offset="1" stop-color="{ORA}" stop-opacity="0"/></linearGradient>')
    defs.append('<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000"/></linearGradient>')
    defs.append('<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".5"/></pattern>')
    body.append(f'<ellipse cx="{W / 2}" cy="{num_y + 70}" rx="380" ry="130" fill="url(#rg)"/>')
    body.append(f'<ellipse cx="{lx + FW / 2}" cy="{fy + 170}" rx="200" ry="230" fill="url(#rg)"/>')
    body.append(f'<ellipse cx="{rx + FW / 2}" cy="{fy + 170}" rx="200" ry="230" fill="url(#rr)"/>')
    body.append(f'<path d="M18.5 {H - 80}V18.5H{W - 18.5}V{H - 80}" fill="none" stroke="#1F1F1F"/>')
    body.append(f'<g fill="none" stroke="{ORA}" stroke-width="2"><path d="M18 46V18h28"/><path d="M{W - 46} 18h28v28"/></g>')
    body.append(f'<g font-size="12" fill="#9C9C9C" letter-spacing="1.5">'
                f'<text x="40" y="46"><tspan fill="{ORA}">●</tspan> git log --author=vanni --since=1.year | wc -l</text>'
                f'<text x="{W - 40}" y="46" text-anchor="end">sync {d["updated"]} <tspan fill="{ORA}">/ live</tspan></text></g>')

    # ---------- the number, extruded: 0/1 cells as one path, stacked back in depth
    year = f"{d['year']:,}"
    cells, ncols = number_cells(year, rng)
    ghost, _ = number_cells(year.translate(str.maketrans("0123456789", "8888888888")), rng, ghost=True)
    ghost = {k: v for k, v in ghost.items() if k not in cells}
    ncw = 8.0
    nh = DH * ncw
    nx = W / 2 - ncols * ncw / 2 - 8
    cell_d = "".join(f"M{c * ncw:.0f} {r * ncw:.0f}h{ncw - 1:.0f}v{ncw - 1:.0f}h-{ncw - 1:.0f}z" for c, r in sorted(cells))
    ghost_d = "".join(f"M{c * ncw:.0f} {r * ncw:.0f}h{ncw - 1:.0f}v{ncw - 1:.0f}h-{ncw - 1:.0f}z" for c, r in sorted(ghost))
    defs.append(f'<path id="num" d="{cell_d}"/>')
    defs.append(f'<linearGradient id="ng" x1="0" x2="{ncols * ncw}" gradientUnits="userSpaceOnUse">'
                f'<stop offset="0" stop-color="{YEL}"/><stop offset=".55" stop-color="{ORA}"/><stop offset="1" stop-color="{RED}"/></linearGradient>')
    # a sheen gliding across the face
    defs.append(f'<linearGradient id="sheen" x1="-160" x2="0" gradientUnits="userSpaceOnUse">'
                f'<stop offset="0" stop-color="{CREAM}" stop-opacity="0"/><stop offset=".5" stop-color="{CREAM}" stop-opacity=".75"/>'
                f'<stop offset="1" stop-color="{CREAM}" stop-opacity="0"/>'
                f'<animateTransform attributeName="gradientTransform" type="translate" values="-60 0;{ncols * ncw + 220} 0;{ncols * ncw + 220} 0" keyTimes="0;.55;1" dur="4.2s" repeatCount="indefinite"/>'
                f'</linearGradient>')
    # the depth: every cell swept back up and to the right as one solid shape, all in one path
    ex, ey = 8.4, -11.0
    e = ncw - 1
    sweep = "".join(
        f"M{c * ncw:.0f} {r * ncw + e:.0f}V{r * ncw:.0f}l{ex} {ey}h{e:.0f}v{e:.0f}l{-ex} {-ey}Z"
        for c, r in sorted(cells))
    defs.append(f'<linearGradient id="dep" x1="0" y1="0" x2="0" y2="{nh:.0f}" gradientUnits="userSpaceOnUse">'
                f'<stop offset="0" stop-color="#7a1d10"/><stop offset="1" stop-color="#2a0905"/></linearGradient>')
    num = [f'<g transform="translate({nx:.1f} {num_y})">',
           f'<path d="{ghost_d}" fill="#120705"/>',
           f'<path d="{sweep}" fill="url(#dep)"/>']
    num.append(f'<use href="#num" fill="url(#ng)"/>')
    num.append(f'<use href="#num" fill="url(#sheen)"/>')
    # on every hit the face jumps apart into red and cream for a moment
    gl_times = sorted(list(hits.values()) + [1.05, 3.05])

    def glitch_kf(name, frames, base):
        s = f"@keyframes {name}{{0%,100%{{{base}}}"
        for t in gl_times:
            p = (t % T) / T * 100
            for i, fr in enumerate(frames):
                s += f"{p + i * .7:.2f}%{{{fr}}}"
            s += f"{p + len(frames) * .7:.2f}%{{{base}}}"
        return s + "}"

    hidden = "transform:translate(0,0);opacity:0"
    css.append(glitch_kf("rgbA", ["transform:translate(-6px,1px);opacity:.9", "transform:translate(4px,-1px);opacity:.7", "transform:translate(-2px,0);opacity:.5"], hidden))
    css.append(glitch_kf("rgbB", ["transform:translate(6px,-1px);opacity:.9", "transform:translate(-5px,1px);opacity:.7", "transform:translate(3px,0);opacity:.4"], hidden))
    css.append(f".rgbA{{animation:rgbA {T}s steps(1) infinite}}.rgbB{{animation:rgbB {T}s steps(1) infinite}}")
    num.append(f'<use class="rgb rgbA" href="#num" fill="{RED}" opacity="0"/>')
    num.append(f'<use class="rgb rgbB" href="#num" fill="{CREAM}" opacity="0"/>')
    num.append(f'<rect x="-10" y="-14" width="{ncols * ncw + 30}" height="{nh + 18}" fill="url(#scan)"/>')
    num.append("</g>")
    body.append("".join(num))

    # ---------- label + stat boxes
    label_y = num_y + nh + 34
    css.append(".car{animation:c 1s steps(1) infinite}@keyframes c{50%{opacity:0}}")
    body.append(f'<text x="{W / 2}" y="{label_y}" text-anchor="middle" font-size="13" fill="#F5F3F1" letter-spacing="4">'
                f'CONTRIBUTIONS / LAST 365 DAYS<tspan class="car" fill="{ORA}">_</tspan></text>')
    stats = [("all time", f"{d['all']:,}"), ("streak", f"{d['streak']}d"), ("best streak", f"{d['best_streak']}d"), ("best day", f"{d['best_day']}")]
    bw, bh, bg = 150, 46, 12
    bx0 = W / 2 - (len(stats) * bw + (len(stats) - 1) * bg) / 2
    by = label_y + 16
    for i, (k, v) in enumerate(stats):
        x = bx0 + i * (bw + bg)
        body.append(f'<rect x="{x + .5}" y="{by + .5}" width="{bw}" height="{bh}" fill="#070707" stroke="#1F1F1F"/>'
                    f'<rect x="{x}" y="{by}" width="14" height="2" fill="{ORA}"/>'
                    f'<text x="{x + 12}" y="{by + 18}" font-size="10" fill="#6a6a6a" letter-spacing="1.5">{k.upper()}</text>'
                    f'<text x="{x + 12}" y="{by + 37}" font-size="16" font-weight="800" fill="{YEL if i == 0 else CREAM}">{v}</text>')

    # ---------- the city
    cam = Cam(W / 2, 402, 410, (0.0, 30.0, -4.0), 70)
    cells_g = make_grid(rng)
    # a light band sweeping across every top, left to right
    x_left, _ = cam.p(-GCOLS / 2, 0, 0)
    x_right, _ = cam.p(GCOLS / 2, 0, 0)
    span = x_right - x_left
    for lv, top in enumerate(LEVEL_TOP):
        if lv == 0:
            # the empty days (most of the tiles) stay still: the band barely showed on them
            defs.append(f'<linearGradient id="wv0"><stop stop-color="{top}"/></linearGradient>')
            continue
        bright = shade(top, 1.55)
        defs.append(f'<linearGradient id="wv{lv}" gradientUnits="userSpaceOnUse" x1="{x_left - 260:.0f}" x2="{x_left - 20:.0f}" y1="0" y2="0">'
                    f'<stop offset="0" stop-color="{top}"/><stop offset=".42" stop-color="{top}"/><stop offset=".5" stop-color="{bright}"/>'
                    f'<stop offset=".58" stop-color="{top}"/><stop offset="1" stop-color="{top}"/>'
                    f'<animateTransform attributeName="gradientTransform" type="translate" values="0 0;{span + 320:.0f} 0;{span + 320:.0f} 0" keyTimes="0;.7;1" dur="5s" repeatCount="indefinite"/>'
                    f'</linearGradient>')
    # a warm pool of light on the floor under it
    fx0, fy0 = cam.p(0, 0, GROWS * ROW_P / 2)
    defs.append(f'<radialGradient id="floor" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{ORA}" stop-opacity=".22"/><stop offset="1" stop-color="{ORA}" stop-opacity="0"/></radialGradient>')
    body.append(f'<ellipse cx="{fx0:.0f}" cy="{fy0:.0f}" rx="{span * 0.62:.0f}" ry="95" fill="url(#floor)"/>')
    css.append(".rw{transform-box:fill-box;transform-origin:50% 100%;animation:rw 1.1s cubic-bezier(.16,1,.3,1) both}"
               "@keyframes rw{from{transform:scaleY(.02);opacity:0}to{transform:scaleY(1);opacity:1}}")
    body.append(city(cam, cells_g, css))

    # ---------- the two entities, standing at the ends
    css.append(".hov{animation:hv 2.2s ease-in-out infinite alternate}@keyframes hv{from{transform:translateY(0)}to{transform:translateY(-9px)}}")
    css.append(".eye{animation:ey 2.8s steps(1) infinite}@keyframes ey{0%,100%{opacity:1}44%{opacity:.55}46%{opacity:1}90%{opacity:0}92%{opacity:1}}")
    figs = {}
    for side, x0, facing, glowc in (("L", lx, 1, YEL), ("R", rx, -1, ORA)):
        tp, hp = (throws[side] % T) / T * 100, (hits[side] % T) / T * 100
        s = facing
        css.append(f"@keyframes k{side}{{0%,{hp:.2f}%{{transform:translateX(0)}}{hp + 1.5:.2f}%{{transform:translateX({-22 * s}px)}}"
                   f"{hp + 14:.2f}%,100%{{transform:translateX(0)}}}}.k{side}{{animation:k{side} {T}s cubic-bezier(.16,1,.3,1) infinite}}")
        sp = baked.get("sprite" + side)
        if sp:
            # the 3D fighter: one strip of frames, stepped through on the fight's own timeline
            fw, fh, bx, by_ = sp["box"]["w"], sp["box"]["h"], sp["box"]["x"], sp["box"]["y"]
            n_idle, n_punch, n_hit = sp["frames"]["idle"], sp["frames"]["punch"], sp["frames"]["hit"]
            total = n_idle + n_punch + n_hit
            pd = 0.8 / (n_punch - 1)  # a punch frame, seconds
            hd = 0.075  # a hit frame
            p_start = throws[side] - sp["punchAt"] * pd  # the fist is furthest out at the throw
            h_start = hits[side]

            def frame_at(t):
                for start, n, d, first in ((p_start, n_punch, pd, n_idle), (h_start, n_hit, hd, n_idle + n_punch)):
                    k = (t - start) % T
                    if k < n * d:
                        return first + int(k / d)
                return int(t / (3.33 / n_idle)) % n_idle  # breathing

            kf, last = [], None
            steps = int(T * 24)
            for i in range(steps):
                t = i * T / steps
                f = frame_at(t)
                if f != last:
                    kf.append(f"{i / steps * 100:.2f}%{{transform:translateX({-f * fw}px)}}")
                    last = f
            css.append(f"@keyframes s{side}{{{''.join(kf)}100%{{transform:translateX({-frame_at(0) * fw}px)}}}}"
                       f".s{side}{{animation:s{side} {T}s steps(1) infinite}}")
            body.append(
                f'<g transform="translate({x0} {fy})"><g class="k{side}">'
                f'<svg x="{bx}" y="{by_}" width="{fw}" height="{fh}" viewBox="0 0 {fw} {fh}" overflow="hidden">'
                f'<image class="s{side}" width="{fw * total}" height="{fh}" preserveAspectRatio="none" href="{sp["href"]}"/></svg>'
                f"</g></g>"
            )
            figs[side] = dict(hand=(x0 + sp["points"]["hand"][0], fy + sp["points"]["hand"][1]),
                              chest=(x0 + sp["points"]["chest"][0], fy + sp["points"]["chest"][1]))
            continue

        # no baked fighters: the old 0/1 figures, as vector text
        p = dict(parts[side])
        css.append(".hov{animation:hv 2.2s ease-in-out infinite alternate}@keyframes hv{from{transform:translateY(0)}to{transform:translateY(-9px)}}")
        css.append(".eye{animation:ey 2.8s steps(1) infinite}@keyframes ey{0%,100%{opacity:1}44%{opacity:.55}46%{opacity:1}90%{opacity:0}92%{opacity:1}}")
        css.append(f"@keyframes a{side}{{0%,{tp - 13:.2f}%{{transform:rotate(0)}}{tp - 1:.2f}%{{transform:rotate({-75 * s}deg)}}"
                   f"{tp + 2:.2f}%{{transform:rotate({48 * s}deg)}}{tp + 18:.2f}%,100%{{transform:rotate(0)}}}}"
                   f".a{side}{{animation:a{side} {T}s cubic-bezier(.16,1,.3,1) infinite}}"
                   f"@keyframes f{side}{{0%,{hp:.2f}%{{opacity:0}}{hp + .3:.2f}%{{opacity:.95}}{hp + 2:.2f}%{{opacity:.2}}{hp + 2.8:.2f}%{{opacity:.7}}{hp + 7:.2f}%,100%{{opacity:0}}}}"
                   f".f{side}{{animation:f{side} {T}s linear infinite}}")
        eye_svg = "".join(
            f'<ellipse cx="{ex}" cy="{ey}" rx="16" ry="8" fill="url(#ey)" opacity=".7"/>'
            f'<rect class="eye" x="{ex - 6}" y="{ey - 1.5}" width="12" height="3" fill="{CREAM}"/>'
            for ex, ey in p["eyes"])
        sh = p["shoulder"]
        body.append(
            f'<g transform="translate({x0} {fy})"><g class="k{side}"><g class="hov" style="animation-delay:-{1.1 if side == "R" else 0}s">'
            f'<g class="fig">{p["body"]}</g>'
            f'<g transform="translate({sh[0]} {sh[1]})"><g class="a{side}"><g class="arm">{p["arm"]}</g></g></g>'
            f'{eye_svg}'
            f'<g class="f{side}" opacity="0"><g class="fig">{p["flash"]}</g></g>'
            f"</g></g></g>"
        )
        figs[side] = dict(hand=(x0 + sh[0] + p["hand"][0], fy + sh[1] + p["hand"][1]),
                          chest=(x0 + p["chest"][0], fy + p["chest"][1]))

    body.append(f'<rect x="60" y="{H - 18}" width="{W - 120}" height="1" fill="url(#fl)"/>')

    # ---------- volleys: three spinning 3D cubes per throw, arcing over the city
    proj = []
    css.append(".spin{animation:sp .7s linear infinite}@keyframes sp{to{transform:rotate(360deg)}}")
    for side, other, cols in (("L", "R", [(CREAM, YEL, ORA), (YEL, ORA, "#a02a18"), (ORA, RED, "#7a1d10")]),
                              ("R", "L", [(CREAM, ORA, RED), (ORA, RED, "#7a1d10"), (YEL, ORA, "#a02a18")])):
        sx, sy = figs[side]["hand"]
        ex, ey = figs[other]["chest"]
        t0 = throws[side]
        for i in range(3):
            lag = i * 0.07
            a = (t0 + lag) / T * 100
            b = (t0 + lag + flight) / T * 100
            m = (a + b) / 2
            dx = ex - sx + rng.randint(-14, 14)
            dy_end = ey - sy + rng.randint(-20, 20)
            pk = rng.randint(170, 220)
            k = f"p{side}{i}"
            css.append(
                f"@keyframes {k}x{{0%,{a:.2f}%{{transform:translateX(0);opacity:0}}{a + .1:.2f}%{{opacity:1}}"
                f"{b:.2f}%{{transform:translateX({dx}px);opacity:1}}{b + .1:.2f}%,100%{{transform:translateX({dx}px);opacity:0}}}}"
                f"@keyframes {k}y{{0%,{a:.2f}%{{transform:translateY(0);animation-timing-function:cubic-bezier(.25,.6,.45,1)}}"
                f"{m:.2f}%{{transform:translateY({-pk}px);animation-timing-function:cubic-bezier(.55,0,.75,.4)}}"
                f"{b:.2f}%,100%{{transform:translateY({dy_end}px)}}}}"
            )
            size = (16, 12, 10)[i]
            proj.append(
                f'<g class="proj" transform="translate({sx} {sy})"><g style="animation:{k}x {T}s linear infinite">'
                f'<g style="animation:{k}y {T}s infinite"><g class="spin" style="animation-delay:-{i * .2:.1f}s">{cube(size, cols[i])}</g></g></g></g>'
            )

    # ---------- impacts: a ring, shards, +1, and a shockwave across the floor
    for side in ("L", "R"):
        x, y = figs[side]["chest"]
        p = (hits[side] % T) / T * 100
        css.append(f"@keyframes b{side}{{0%,{p:.2f}%{{transform:scale(.1);opacity:0}}{p + .3:.2f}%{{opacity:1}}"
                   f"{p + 10:.2f}%,100%{{transform:scale(1);opacity:0}}}}"
                   f".b{side}{{animation:b{side} {T}s cubic-bezier(.16,1,.3,1) infinite}}"
                   f"@keyframes r{side}{{0%,{p:.2f}%{{transform:scale(.2);opacity:0}}{p + .3:.2f}%{{opacity:.9}}"
                   f"{p + 6:.2f}%,100%{{transform:scale(1);opacity:0}}}}"
                   f".r{side}{{animation:r{side} {T}s cubic-bezier(.16,1,.3,1) infinite}}"
                   f"@keyframes t{side}{{0%,{p:.2f}%{{transform:translateY(0);opacity:0}}{p + .6:.2f}%{{opacity:1}}"
                   f"{p + 18:.2f}%,100%{{transform:translateY(-60px);opacity:0}}}}"
                   f".t{side}{{animation:t{side} {T}s cubic-bezier(.16,1,.3,1) infinite}}"
                   f"@keyframes w{side}{{0%,{p:.2f}%{{transform:scale(.05);opacity:0}}{p + .4:.2f}%{{opacity:.85}}"
                   f"{p + 22:.2f}%,100%{{transform:scale(1);opacity:0}}}}"
                   f".w{side}{{animation:w{side} {T}s cubic-bezier(.16,1,.3,1) infinite}}")
        shards = []
        for k in range(8):
            ang = k / 8 * 6.283 + rng.uniform(-.25, .25)
            rr = rng.randint(44, 90)
            shards.append(f'<g transform="translate({math.cos(ang) * rr:.1f} {math.sin(ang) * rr:.1f})">'
                          f'{cube(rng.choice([7, 9, 11]), rng.choice([(CREAM, YEL, ORA), (YEL, ORA, RED), (ORA, RED, "#7a1d10")]))}</g>')
        # the shockwave: an ellipse lying flat on the floor, running out from the struck end
        wx, wy = cam.p((-GCOLS / 2 + 3) if side == "L" else (GCOLS / 2 - 3), 0, GROWS * ROW_P / 2)
        body.append(
            f'<g class="proj" transform="translate({wx:.0f} {wy:.0f})"><ellipse class="w{side}" rx="380" ry="80" fill="none" stroke="{CREAM}" stroke-width="2" opacity="0"/></g>'
            f'<g class="proj" transform="translate({x} {y})">'
            f'<g class="r{side}"><rect x="-46" y="-46" width="92" height="92" fill="none" stroke="{CREAM}" stroke-width="2"/></g>'
            f'<g class="b{side}">{"".join(shards)}</g></g>'
            f'<g class="proj" transform="translate({x} {y - 70})"><text class="t{side}" text-anchor="middle" font-size="18" font-weight="800" fill="{CREAM}">+1</text></g>'
        )

    # ---------- ash: a few 0/1 rising off the figures
    ash = ['<g class="ash">']
    css.append(".as{animation:as 3.4s linear infinite}@keyframes as{0%{transform:translateY(0);opacity:0}15%{opacity:.9}100%{transform:translateY(-170px);opacity:0}}")
    for i in range(12):
        ax = rng.choice([lx, rx]) + rng.randint(10, FW - 10)
        ash.append(f'<text class="as" x="{ax}" y="{H - 30 - rng.randint(0, 60)}" fill="{rng.choice([ORA, RED, YEL, "#7a1d10"])}" '
                   f'style="animation-delay:-{rng.random() * 3.4:.2f}s;animation-duration:{2.6 + rng.random() * 2.2:.2f}s">{rng.choice("01")}</text>')
    ash.append("</g>")
    body.append("".join(ash))
    body.extend(proj)

    css.append("@media (prefers-reduced-motion:reduce){*{animation:none!important}.proj,.rgb{display:none}}")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{d['year']} contributions in the last year">
<title>{d['year']} contributions in the last year</title>
<style>{''.join(css)}</style>
<defs>{''.join(defs)}</defs>
<rect width="{W}" height="{H}" fill="#000"/>
<g xml:space="preserve">
{''.join(body)}
</g>
<rect x="0" y="{H - 60}" width="{W}" height="60" fill="url(#fade)"/>
</svg>
"""


def main():
    d = fetch()
    with open(OUT, "w") as f:
        f.write(build(d))
    print(f"contrib.svg: {d['year']} last year, {d['all']} all time")


if __name__ == "__main__":
    main()
