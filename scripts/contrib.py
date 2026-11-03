#!/usr/bin/env python3
"""Build assets/contrib.svg.

Two horned entities drawn in 0/1 characters hurl contribution squares at each
other over a contribution grid. Every hit shakes the scene and glitches the
contribution count, which is itself built from 0/1 characters.

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

def build(d):
    rng = random.Random(1337)
    css = [
        f"text{{font-family:{FONT}}}",
        ".fig text,.arm text{font-size:6px;font-weight:700;white-space:pre}",
        ".num text{font-size:8px;font-weight:800;white-space:pre}",
        ".ash text{font-size:9px;font-weight:700}",
    ]
    defs, body = [], []

    lx, rx, fy = 34, W - 34 - FW, H - 18 - FH
    num_y = 74
    grid_x, grid_y, cs, gap = 269, 352, 11, 3

    flight = 1.0
    throws = {"L": 0.45, "R": 2.25}
    hits = {"R": throws["L"] + flight, "L": throws["R"] + flight}

    # ---------- shake the whole scene on every hit
    sk = []
    for t in hits.values():
        p = (t % T) / T * 100
        sk.append(f"{p:.2f}%{{transform:translate(0,0)}}{p + .4:.2f}%{{transform:translate(7px,-4px)}}"
                  f"{p + 1.1:.2f}%{{transform:translate(-6px,3px)}}{p + 1.9:.2f}%{{transform:translate(4px,2px)}}"
                  f"{p + 2.8:.2f}%{{transform:translate(-2px,-1px)}}{p + 3.8:.2f}%{{transform:translate(0,0)}}")
    css.append("@keyframes shk{0%,100%{transform:translate(0,0)}" + "".join(sk) + "}"
               f".shk{{animation:shk {T}s linear infinite}}")

    # ---------- backdrop
    defs.append(f'<radialGradient id="rg" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{ORA}" stop-opacity=".30"/><stop offset="1" stop-color="{ORA}" stop-opacity="0"/></radialGradient>')
    defs.append(f'<radialGradient id="rr" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{RED}" stop-opacity=".35"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></radialGradient>')
    defs.append(f'<radialGradient id="ey" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{YEL}" stop-opacity=".9"/><stop offset="1" stop-color="{YEL}" stop-opacity="0"/></radialGradient>')
    defs.append(f'<linearGradient id="fl" x1="0" x2="1"><stop offset="0" stop-color="{ORA}" stop-opacity="0"/><stop offset=".5" stop-color="{ORA}" stop-opacity=".55"/><stop offset="1" stop-color="{ORA}" stop-opacity="0"/></linearGradient>')
    defs.append('<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000"/></linearGradient>')
    defs.append('<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".55"/></pattern>')
    css.append(".glow{animation:gl 2.4s ease-in-out infinite alternate}@keyframes gl{from{opacity:.35}to{opacity:.8}}")
    body.append(f'<ellipse class="glow" cx="{W / 2}" cy="{num_y + 70}" rx="380" ry="130" fill="url(#rg)"/>')
    body.append(f'<ellipse class="glow" cx="{lx + FW / 2}" cy="{fy + 170}" rx="200" ry="230" fill="url(#rg)" style="animation-delay:-.8s"/>')
    body.append(f'<ellipse class="glow" cx="{rx + FW / 2}" cy="{fy + 170}" rx="200" ry="230" fill="url(#rr)" style="animation-delay:-1.6s"/>')

    body.append(f'<path d="M18.5 {H - 80}V18.5H{W - 18.5}V{H - 80}" fill="none" stroke="#1F1F1F"/>')
    body.append(f'<g fill="none" stroke="{ORA}" stroke-width="2"><path d="M18 46V18h28"/><path d="M{W - 46} 18h28v28"/></g>')
    body.append(f'<g font-size="12" fill="#9C9C9C" letter-spacing="1.5">'
                f'<text x="40" y="46"><tspan fill="{ORA}">●</tspan> git log --author=vanni --since=1.year | wc -l</text>'
                f'<text x="{W - 40}" y="46" text-anchor="end">sync {d["updated"]} <tspan fill="{ORA}">/ live</tspan></text></g>')

    # ---------- the number: 0/1 seven-segment digits over a dim "8" ghost
    year = f"{d['year']:,}"
    cells, ncols = number_cells(year, rng)
    ghost, _ = number_cells(year.translate(str.maketrans("0123456789", "8888888888")), rng, ghost=True)
    ghost = {k: v for k, v in ghost.items() if k not in cells}
    ncw, nch, nscale = 8.0, 8.0, 1.0
    nh = DH * nch
    nx = W / 2 - ncols * ncw * nscale / 2
    defs.append(f'<linearGradient id="ng" x1="0" x2="{ncols * ncw}" gradientUnits="userSpaceOnUse">'
                f'<stop offset="0" stop-color="{YEL}"/><stop offset=".55" stop-color="{ORA}"/><stop offset="1" stop-color="{RED}"/></linearGradient>')
    defs.append(f'<g id="num">{cells_to_rects(cells, ncw)}</g>')
    digits = [c for c in year if c != ","]
    scr = "".join(rng.choice("0123456789") if c != "," else "," for c in year)
    scells, _ = number_cells(scr, rng)
    defs.append(f'<g id="nscr">{cells_to_rects(scells, ncw)}</g>')

    glitch_times = list(hits.values()) + [1.05, 3.05]

    def glitch_kf(name, frames, base):
        s = f"@keyframes {name}{{0%,100%{{{base}}}"
        for t in sorted(glitch_times):
            p = (t % T) / T * 100
            for i, fr in enumerate(frames):
                s += f"{p + i * .7:.2f}%{{{fr}}}"
            s += f"{p + len(frames) * .7:.2f}%{{{base}}}"
        return s + "}"

    hidden = "transform:translate(0,0);opacity:0"
    css.append(glitch_kf("rgbA", ["transform:translate(-6px,1px);opacity:.9", "transform:translate(4px,-1px);opacity:.7", "transform:translate(-2px,0);opacity:.5"], hidden))
    css.append(glitch_kf("rgbB", ["transform:translate(6px,-1px);opacity:.9", "transform:translate(-5px,1px);opacity:.7", "transform:translate(3px,0);opacity:.4"], hidden))
    css.append(glitch_kf("scr", ["opacity:1", "opacity:0", "opacity:.8"], "opacity:0"))
    css.append(glitch_kf("nmh", ["opacity:0", "opacity:1", "opacity:.3"], "opacity:1"))
    css.append(f".rgbA{{animation:rgbA {T}s steps(1) infinite}}.rgbB{{animation:rgbB {T}s steps(1) infinite}}"
               f".scr{{animation:scr {T}s steps(1) infinite}}.nwrap{{animation:nmh {T}s steps(1) infinite}}")
    num = [f'<g class="num" transform="translate({nx:.1f} {num_y}) scale({nscale})">',
           f'<g fill="#140805">{cells_to_rects(ghost, ncw)}</g>',
           f'<use class="rgb rgbA" href="#num" fill="{RED}" opacity="0"/>',
           f'<use class="rgb rgbB" href="#num" fill="{CREAM}" opacity="0"/>',
           '<g class="nwrap">']
    slices = [0, 3, 5, 9, 11, 14, DH + 1]
    for i in range(len(slices) - 1):
        y0, y1 = slices[i] * nch, slices[i + 1] * nch
        defs.append(f'<clipPath id="ns{i}"><rect x="-40" y="{y0 - 1}" width="{ncols * ncw + 80}" height="{y1 - y0 + 1}"/></clipPath>')
        frames = [f"transform:translateX({rng.choice([-1, 1]) * rng.randint(4, 22)}px)" for _ in range(3)]
        css.append(glitch_kf(f"sl{i}", frames, "transform:translateX(0)"))
        css.append(f".sl{i}{{animation:sl{i} {T}s steps(1) infinite}}")
        num.append(f'<g clip-path="url(#ns{i})"><use class="sl{i}" href="#num" fill="url(#ng)"/></g>')
    num.append("</g>")
    num.append(f'<use class="scr" href="#nscr" fill="{CREAM}" opacity="0"/>')
    defs.append(f'<linearGradient id="sw" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CREAM}" stop-opacity="0"/><stop offset="1" stop-color="{CREAM}" stop-opacity=".22"/></linearGradient>')
    css.append(f".sweep{{animation:sw 2.8s cubic-bezier(.16,1,.3,1) infinite}}@keyframes sw{{from{{transform:translateY(-30px);opacity:0}}10%{{opacity:1}}to{{transform:translateY({nh + 10}px);opacity:0}}}}")
    num.append(f'<rect x="-10" y="-2" width="{ncols * ncw + 20}" height="{nh + 4}" fill="url(#scan)"/>')
    num.append(f'<rect class="sweep" x="-10" y="0" width="{ncols * ncw + 20}" height="24" fill="url(#sw)"/>')
    num.append("</g>")
    body.append("".join(num))

    # ---------- label + stat boxes
    label_y = num_y + nh * nscale + 34
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

    # ---------- grid (made up, spells VANNI)
    gcols, grows = 53, 7
    gcells = [[0] * gcols for _ in range(grows)]
    font = {"V": ["101", "101", "101", "101", "010"], "A": ["010", "101", "111", "101", "101"],
            "N": ["101", "111", "111", "111", "101"], "I": ["111", "010", "010", "010", "111"]}
    for x in range(gcols):
        wave = 0.5 + 0.5 * math.sin(x / 4.3)
        for y in range(grows):
            r = rng.random()
            gcells[y][x] = 0 if r < 0.42 - wave * 0.18 else 1 if r < 0.74 else 2 if r < 0.92 else 3
    word = "VANNI"
    start = (gcols - (len(word) * 4 - 1)) // 2
    for i, chx in enumerate(word):
        for y, line in enumerate(font[chx]):
            for dx, bit in enumerate(line):
                if bit == "1":
                    gcells[y + 1][start + i * 4 + dx] = 5 if rng.random() < 0.55 else 4
    gw = gcols * (cs + gap) - gap
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    now = dt.date.today()
    g = ['<g font-size="10" fill="#4a4a4a" letter-spacing="1">']
    for i in range(12):
        g.append(f'<text x="{grid_x + i * gw / 12:.0f}" y="{grid_y - 8}">{months[(now.month + i) % 12]}</text>')
    g.append("</g>")
    css.append(".gp{animation:gp 2.6s steps(1) infinite}@keyframes gp{0%,100%{opacity:1}10%{opacity:.4}12%{opacity:1}58%{opacity:.6}60%{opacity:1}}")
    for y, row in enumerate(gcells):
        for x, v in enumerate(row):
            cls = f' class="gp" style="animation-delay:-{rng.random() * 2.6:.2f}s"' if v >= 4 and rng.random() < 0.2 else ""
            g.append(f'<rect x="{grid_x + x * (cs + gap)}" y="{grid_y + y * (cs + gap)}" width="{cs}" height="{cs}" fill="{GRID_LV[v]}"{cls}/>')
    body.append("".join(g))

    # ---------- the two entities
    pal_l = ["#1f0905", "#5a160c", "#a02a18", ORA, YEL]
    pal_r = ["#1a0604", "#4a0f08", "#8a1c10", RED, ORA]
    css.append(".hov{animation:hv 2.2s ease-in-out infinite alternate}@keyframes hv{from{transform:translateY(0)}to{transform:translateY(-9px)}}")
    css.append(".eye{animation:ey 2.8s steps(1) infinite}@keyframes ey{0%,100%{opacity:1}44%{opacity:.55}46%{opacity:1}90%{opacity:0}92%{opacity:1}}")
    css.append(".fl{animation:fl .6s steps(1) infinite}@keyframes fl{0%,100%{opacity:1}50%{opacity:.82}}")

    figs = {}
    for side, x0, facing, pal, glowc in (("L", lx, 1, pal_l, YEL), ("R", rx, -1, pal_r, ORA)):
        fbody, fflash, eyes, shoulder, chest = figure(facing, rng, pal)
        arm_svg, hand = arm(facing, rng, pal[3])
        tp, hp = (throws[side] % T) / T * 100, (hits[side] % T) / T * 100
        s = facing
        css.append(f"@keyframes a{side}{{0%,{tp - 13:.2f}%{{transform:rotate(0)}}{tp - 1:.2f}%{{transform:rotate({-75 * s}deg)}}"
                   f"{tp + 2:.2f}%{{transform:rotate({48 * s}deg)}}{tp + 18:.2f}%,100%{{transform:rotate(0)}}}}"
                   f".a{side}{{animation:a{side} {T}s cubic-bezier(.16,1,.3,1) infinite}}")
        css.append(f"@keyframes k{side}{{0%,{hp:.2f}%{{transform:translateX(0)}}{hp + 1.5:.2f}%{{transform:translateX({-22 * s}px)}}"
                   f"{hp + 14:.2f}%,100%{{transform:translateX(0)}}}}.k{side}{{animation:k{side} {T}s cubic-bezier(.16,1,.3,1) infinite}}"
                   f"@keyframes f{side}{{0%,{hp:.2f}%{{opacity:0}}{hp + .3:.2f}%{{opacity:.95}}{hp + 2:.2f}%{{opacity:.2}}{hp + 2.8:.2f}%{{opacity:.7}}{hp + 7:.2f}%,100%{{opacity:0}}}}"
                   f".f{side}{{animation:f{side} {T}s linear infinite}}")
        css.append(f"@keyframes o{side}{{0%,{tp - 16:.2f}%{{transform:scale(0) rotate(0);opacity:0}}{tp - 2:.2f}%{{transform:scale(1.15) rotate(180deg);opacity:1}}"
                   f"{tp:.2f}%{{transform:scale(1.5) rotate(200deg);opacity:1}}{tp + .6:.2f}%,100%{{transform:scale(0);opacity:0}}}}"
                   f".o{side}{{animation:o{side} {T}s linear infinite}}")
        eye_svg = "".join(
            f'<ellipse cx="{ex}" cy="{ey}" rx="16" ry="8" fill="url(#ey)" opacity=".7"/>'
            f'<rect class="eye" x="{ex - 6}" y="{ey - 1.5}" width="12" height="3" fill="{CREAM}"/>'
            for ex, ey in eyes)
        orb = "".join(f'<rect x="{-4 + dx}" y="{-4 + dy}" width="8" height="8" fill="{c}"/>'
                      for dx, dy, c in ((0, 0, CREAM), (-9, 0, glowc), (9, 0, glowc), (0, -9, glowc), (0, 9, glowc)))
        orb = (f'<g transform="translate({hand[0]} {hand[1]})"><g class="o{side}">'
               f'<ellipse rx="26" ry="26" fill="url(#ey)"/>{orb}</g></g>')
        body.append(
            f'<g transform="translate({x0} {fy})"><g class="k{side}"><g class="hov" style="animation-delay:-{1.1 if side == "R" else 0}s">'
            f'<g class="fig fl">{fbody}</g>'
            f'<g class="arm" transform="translate({shoulder[0]} {shoulder[1]})"><g class="a{side}">{arm_svg}{orb}</g></g>'
            f'{eye_svg}'
            f'<g class="fig f{side}" opacity="0">{fflash}</g>'
            f"</g></g></g>"
        )
        figs[side] = dict(hand=(x0 + shoulder[0] + hand[0], fy + shoulder[1] + hand[1]),
                          chest=(x0 + chest[0], fy + chest[1]))

    body.append(f'<rect x="60" y="{H - 18}" width="{W - 120}" height="1" fill="url(#fl)"/>')

    # ---------- volleys: contribution squares with trails, lighting the grid as they pass
    proj = []
    for side, other, cols in (("L", "R", [YEL, ORA, CREAM]), ("R", "L", [RED, ORA, YEL])):
        sx, sy = figs[side]["hand"]
        ex, ey = figs[other]["chest"]
        t0 = throws[side]
        for i in range(7):
            lag = i * 0.045
            a = (t0 + lag) / T * 100
            b = (t0 + lag + flight) / T * 100
            m = (a + b) / 2
            dx = ex - sx + rng.randint(-18, 18)
            dy_end = ey - sy + rng.randint(-26, 26)
            pk = rng.randint(150, 215)
            k = f"p{side}{i}"
            css.append(
                f"@keyframes {k}x{{0%,{a:.2f}%{{transform:translateX(0);opacity:0}}{a + .1:.2f}%{{opacity:1}}"
                f"{b:.2f}%{{transform:translateX({dx}px);opacity:1}}{b + .1:.2f}%,100%{{transform:translateX({dx}px);opacity:0}}}}"
                f"@keyframes {k}y{{0%,{a:.2f}%{{transform:translateY(0);animation-timing-function:cubic-bezier(.25,.6,.45,1)}}"
                f"{m:.2f}%{{transform:translateY({-pk}px);animation-timing-function:cubic-bezier(.55,0,.75,.4)}}"
                f"{b:.2f}%,100%{{transform:translateY({dy_end}px)}}}}"
            )
            size = rng.choice([10, 11, 12, 14])
            c = rng.choice(cols)
            for j, (scale, op) in enumerate(((1, 1), (.7, .45), (.45, .22))):
                delay = j * 0.035
                sz = size * scale
                proj.append(
                    f'<g class="proj" transform="translate({sx} {sy})"><g style="animation:{k}x {T}s linear {delay:.3f}s infinite">'
                    f'<g style="animation:{k}y {T}s {delay:.3f}s infinite"><rect class="spin" x="{-sz / 2:.1f}" y="{-sz / 2:.1f}" '
                    f'width="{sz:.1f}" height="{sz:.1f}" fill="{c}" opacity="{op}"/></g></g></g>'
                )
        for col in range(gcols):
            cx = grid_x + col * (cs + gap) + cs / 2
            t = t0 + flight * (cx - sx) / (ex - sx)
            if not (t0 <= t <= t0 + flight):
                continue
            p = (t % T) / T * 100
            css.append(f"@keyframes g{side}{col}{{0%,{p:.2f}%{{opacity:0}}{p + .5:.2f}%{{opacity:.55}}{p + 6:.2f}%,100%{{opacity:0}}}}")
            proj.append(f'<rect class="proj" x="{cx - cs / 2}" y="{grid_y}" width="{cs}" height="{grows * (cs + gap) - gap}" fill="{cols[0]}" '
                        f'opacity="0" style="animation:g{side}{col} {T}s linear infinite"/>')
    css.append(".spin{animation:sp .42s linear infinite;transform-box:fill-box;transform-origin:center}@keyframes sp{to{transform:rotate(360deg)}}")

    # ---------- impacts
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
                   f".t{side}{{animation:t{side} {T}s cubic-bezier(.16,1,.3,1) infinite}}")
        shards = []
        for k in range(16):
            ang = k / 16 * 6.283 + rng.uniform(-.2, .2)
            rr = rng.randint(40, 90)
            sz = rng.choice([4, 5, 6, 8])
            shards.append(f'<rect x="{math.cos(ang) * rr - sz / 2:.1f}" y="{math.sin(ang) * rr - sz / 2:.1f}" width="{sz}" height="{sz}" fill="{rng.choice([CREAM, YEL, ORA, RED])}"/>')
        body.append(
            f'<g class="proj" transform="translate({x} {y})">'
            f'<g class="r{side}"><rect x="-46" y="-46" width="92" height="92" fill="none" stroke="{CREAM}" stroke-width="2"/></g>'
            f'<g class="b{side}">{"".join(shards)}</g></g>'
            f'<g class="proj" transform="translate({x} {y - 70})"><text class="t{side}" text-anchor="middle" font-size="18" font-weight="800" fill="{CREAM}">+1</text></g>'
        )

    # ---------- ash: 0/1 chars rising off the figures (instead of fire)
    ash = ['<g class="ash">']
    css.append(".as{animation:as 3.4s linear infinite}@keyframes as{0%{transform:translateY(0);opacity:0}15%{opacity:.9}100%{transform:translateY(-170px);opacity:0}}")
    for i in range(26):
        ax = rng.choice([lx, rx]) + rng.randint(10, FW - 10)
        ash.append(f'<text class="as" x="{ax}" y="{H - 30 - rng.randint(0, 60)}" fill="{rng.choice([ORA, RED, YEL, "#7a1d10"])}" '
                   f'style="animation-delay:-{rng.random() * 3.4:.2f}s;animation-duration:{2.6 + rng.random() * 2.2:.2f}s">{rng.choice("01")}</text>')
    ash.append("</g>")
    body.append("".join(ash))
    body.extend(proj)

    css.append("@media (prefers-reduced-motion:reduce){*{animation:none!important}.proj,.rgb,.scr{display:none}}")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{d['year']} contributions in the last year">
<title>{d['year']} contributions in the last year</title>
<style>{''.join(css)}</style>
<defs>{''.join(defs)}</defs>
<rect width="{W}" height="{H}" fill="#000"/>
<g class="shk" xml:space="preserve">
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
