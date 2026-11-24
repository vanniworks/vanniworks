"""3D UI for the profile README: keycap buttons, extruded headers, the binary bio
line and the forge (binary fire around the V).

Every 3D bit is projected here (perspective, backface culling, lighting) and baked
into SMIL/CSS, so it runs inside GitHub's <img> sandbox: no JS, no filters, no
external fonts (all type is converted to paths).

run: python scripts/ui3d.py   (needs fonttools, and fonts/JetBrainsMono.ttf =
JetBrainsMono[wght].ttf from github.com/google/fonts, OFL)
"""
import math
import os
import random

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
FONTS = os.path.join(ROOT, "fonts")

BLACK = "#000000"
BONE = "#F5F3F1"
GRAY = "#9C9C9C"
DIM = "#1F1F1F"
YEL = "#FFD23A"
ORA = "#FF8A1F"
RED = "#F0402A"
CREAM = "#FFF1C2"
W = 1280
TAU = 2 * math.pi
RM = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"


def n(v):
    s = f"{v:.1f}"
    if s.endswith(".0"):
        s = s[:-2]
    return "0" if s == "-0" else s


class Font:
    def __init__(self, file, wght):
        f = instantiateVariableFont(TTFont(os.path.join(FONTS, file)), {"wght": wght})
        self.gs, self.cmap, self.upm, self.hmtx = f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm, f["hmtx"]

    def glyphs(self, text, size, x, y, tracking=0.0, anchor="start"):
        s = size / self.upm
        names = [self.cmap[ord(c)] for c in text]
        width = sum(self.hmtx[g][0] * s for g in names) + tracking * (len(text) - 1)
        x -= width / 2 if anchor == "middle" else width if anchor == "end" else 0
        out, cx = [], x
        for c, g in zip(text, names):
            pen = SVGPathPen(self.gs, ntos=n)
            self.gs[g].draw(TransformPen(pen, (s, 0, 0, -s, cx, y)))
            adv = self.hmtx[g][0] * s
            out.append((c, pen.getCommands(), cx, adv))
            cx += adv + tracking
        return out, width

    def path(self, text, size, x, y, tracking=0.0, anchor="start"):
        gl, w = self.glyphs(text, size, x, y, tracking, anchor)
        return "".join(g[1] for g in gl), w


M4 = Font("JetBrainsMono.ttf", 400)
M5 = Font("JetBrainsMono.ttf", 500)
M7 = Font("JetBrainsMono.ttf", 700)
M8 = Font("JetBrainsMono.ttf", 800)


def txt(t, size, x, y, fill=GRAY, font=M5, anchor="start", tracking=None, extra=""):
    tr = size * 0.08 if tracking is None else tracking
    d, _ = font.path(t, size, x, y, tr, anchor)
    return f'<path d="{d}" fill="{fill}"{extra}/>'


def width_of(t, size, font=M5, tracking=None):
    tr = size * 0.08 if tracking is None else tracking
    return font.path(t, size, 0, 0, tr)[1]


# ---------------------------------------------------------------- 3D math
def rot(p, yaw, pitch, roll=0.0):
    x, y, z = p
    c, s = math.cos(yaw), math.sin(yaw)
    x, z = x * c + z * s, -x * s + z * c
    c, s = math.cos(pitch), math.sin(pitch)
    y, z = y * c - z * s, y * s + z * c
    if roll:
        c, s = math.cos(roll), math.sin(roll)
        x, y = x * c - y * s, x * s + y * c
    return (x, y, z)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(v):
    l = math.sqrt(dot(v, v)) or 1
    return tuple(a / l for a in v)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def ramp(stops, t):
    """color along [(pos, hex), ...]"""
    t = max(stops[0][0], min(stops[-1][0], t))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            return mix(c0, c1, (t - p0) / (p1 - p0 or 1))
    return stops[-1][1]


def A(dur):
    return f'dur="{dur}s" repeatCount="indefinite"'


def discrete(vals, attr, dur):
    N = len(vals)
    if all(v == vals[0] for v in vals):
        return "", vals[0]
    kt, vv = [], []
    for i, v in enumerate(vals):
        if i == 0 or v != vals[i - 1]:
            kt.append(f"{i / N:.4f}")
            vv.append(str(v))
    return f'<animate attributeName="{attr}" calcMode="discrete" keyTimes="{";".join(kt)}" values="{";".join(vv)}" {A(dur)}/>', vals[0]


class Cam:
    def __init__(self, F, CX, CY):
        self.F, self.CX, self.CY = F, CX, CY

    def p(self, v):
        return self.CX + self.F * v[0] / v[2], self.CY - self.F * v[1] / v[2]

    def affine(self, P, ex, ey, unit=1.0):
        """screen affine of a plane through P with 3D axes ex, ey (per local unit), decomposed for SMIL"""
        X, Y, Z = P
        F = self.F

        def J(v):
            return (F / Z * (v[0] - X / Z * v[2]) * unit, -F / Z * (v[1] - Y / Z * v[2]) * unit)

        a, b = J(ex)
        c, d = J(ey)
        th = math.atan2(-c, d)
        sy = math.hypot(c, d)
        sx = math.cos(th) * a + math.sin(th) * b
        k = -math.sin(th) * a + math.cos(th) * b
        e, f = self.p(P)
        return dict(e=e, f=f, th=math.degrees(th), sx=sx, sy=sy, psi=math.degrees(math.atan(k / sy)), J=J)


def aff_anim(fr, dur):
    f0 = fr[0]
    tf = f'translate({n(f0["e"])} {n(f0["f"])}) rotate({f0["th"]:.2f}) scale({f0["sx"]:.4f} {f0["sy"]:.4f}) skewY({f0["psi"]:.2f})'
    a = A(dur)
    an = (f'<animateTransform attributeName="transform" type="translate" values="{";".join(n(x["e"]) + " " + n(x["f"]) for x in fr)}" {a}/>'
          f'<animateTransform attributeName="transform" type="rotate" additive="sum" values="{";".join(f"{x["th"]:.2f}" for x in fr)}" {a}/>'
          f'<animateTransform attributeName="transform" type="scale" additive="sum" values="{";".join(f"{x["sx"]:.4f} {x["sy"]:.4f}" for x in fr)}" {a}/>'
          f'<animateTransform attributeName="transform" type="skewY" additive="sum" values="{";".join(f"{x["psi"]:.2f}" for x in fr)}" {a}/>')
    return tf, an


def poly_anim(frames_pts, fills, vis, dur, stroke="", extra=""):
    """one 3D face: per-frame screen polygons, fills and visibility"""
    ds = ["M" + " ".join(f"{n(x)} {n(y)}" for x, y in pts) + "Z" for pts in frames_pts]
    va, v0 = discrete(vis, "opacity", dur) if vis is not None else ("", 1)
    if vis is not None and not va and v0 == 0:
        return ""
    fa = f'<animate attributeName="fill" values="{";".join(fills)}" {A(dur)}/>' if len(set(fills)) > 1 else ""
    return (f'<path d="{ds[0]}" fill="{fills[0]}" opacity="{v0}"{stroke}{extra}>'
            f'<animate attributeName="d" values="{";".join(ds)}" {A(dur)}/>{fa}{va}</path>')


def write(name, svg):
    svg = "\n".join(l.strip() for l in svg.splitlines() if l.strip())
    with open(os.path.join(ASSETS, name), "w") as f:
        f.write(svg)
    print(f"{name:20s} {len(svg) / 1024:7.1f} KB")


def corners(w, h, inset=18, arm=26, col=ORA, op=1):
    return (f'<path d="M{inset} {inset + arm}V{inset}H{inset + arm}M{w - inset - arm} {inset}H{w - inset}V{inset + arm}'
            f'M{w - inset} {h - inset - arm}V{h - inset}H{w - inset - arm}M{inset + arm} {h - inset}H{inset}V{h - inset - arm}" '
            f'fill="none" stroke="{col}" stroke-width="2" opacity="{op}"/>')


# ---------------------------------------------------------------- extruded headers
def header(fname, cmd, title):
    H = 150
    K = 16
    N = 48
    DUR = 9
    size = 66
    tx, ty = 4, 112
    d, tw = M8.path(title, size, tx, ty, -1.5)
    cur, _ = M8.path("_", size, tx + tw + 2, ty, 0)
    # the extrusion swings like a slow camera orbit
    offs = []
    for i in range(N + 1):
        a = math.radians(38 + 22 * math.sin(TAU * i / N))
        offs.append((math.cos(a), math.sin(a)))
    layers = []
    for k in range(K, 0, -1):
        t = k / K
        col = ramp([(0, "#FFE08A"), (0.18, ORA), (0.55, RED), (1, "#2a0703")], t)
        vals = ";".join(f"{n(dx * k * 1.05)} {n(dy * k * 1.05)}" for dx, dy in offs)
        layers.append(f'<g transform="translate({n(offs[0][0] * k * 1.05)} {n(offs[0][1] * k * 1.05)})">'
                      f'<animateTransform attributeName="transform" type="translate" values="{vals}" {A(DUR)}/>'
                      f'<use href="#t" fill="{col}"/><use href="#c" class="cur" fill="{mix(col, "#000000", .1)}"/></g>')
    prompt = txt(">", 13, 0, 24, ORA, M5) + txt(cmd, 13, 16, 24, GRAY, M4)
    css = (".cur{animation:blink 1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
           ".bar{transform-box:fill-box;transform-origin:left;animation:grow 1.4s cubic-bezier(.16,1,.3,1) both}"
           "@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
           ".spark{animation:sp 4.5s cubic-bezier(.6,0,.4,1) infinite}@keyframes sp{from{transform:translateX(-160px)}to{transform:translateX(1440px)}}"
           ".in{animation:in 1.1s cubic-bezier(.16,1,.3,1) both}@keyframes in{from{opacity:0;transform:translate(-30px,0)}to{opacity:1;transform:none}}"
           + RM)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{title}">
<title>{title}</title>
<defs><style>{css}</style>
<path id="t" d="{d}"/><path id="c" d="{cur}"/>
<linearGradient id="face" gradientUnits="userSpaceOnUse" x1="0" y1="{ty - size * .75}" x2="0" y2="{ty}"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#E9E2D6"/></linearGradient>
<linearGradient id="heat" gradientUnits="userSpaceOnUse" x1="-300" y1="0" x2="0" y2="0">
<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="{YEL}" stop-opacity=".85"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
<animateTransform attributeName="gradientTransform" type="translate" values="0 0;{int(tw) + 600} 0;{int(tw) + 600} 0" keyTimes="0;.5;1" dur="5s" repeatCount="indefinite"/></linearGradient>
<linearGradient id="f" x1="0" x2="1"><stop offset="0" stop-color="{YEL}"/><stop offset=".5" stop-color="{ORA}"/><stop offset="1" stop-color="{RED}"/></linearGradient>
<linearGradient id="sg" x1="0" x2="1"><stop offset="0" stop-color="{ORA}" stop-opacity="0"/><stop offset="1" stop-color="{YEL}"/></linearGradient>
</defs>
{prompt}
<g class="in">
{"".join(layers)}
<use href="#t" fill="url(#face)"/><use href="#t" fill="url(#heat)"/>
<use href="#c" class="cur" fill="{ORA}"/>
</g>
<rect x="0" y="{H - 10}" width="{W}" height="1" fill="{DIM}"/>
<rect class="bar" x="0" y="{H - 11}" width="240" height="3" fill="url(#f)"/>
<rect class="spark" x="0" y="{H - 11}" width="160" height="3" fill="url(#sg)"/>
</svg>'''
    write(fname, svg)


# ---------------------------------------------------------------- bio line
def about():
    H = 150
    lines = ["software engineer and student at finki.", "i build websites, saas products and apps for clients locally and globally."]
    full = " ".join(lines)
    size = 23
    rnd = random.Random(7)
    chars, clips = [], []
    css = [".ch{animation:ch .5s steps(1) both}@keyframes ch{from{opacity:0}to{opacity:1}}",
           ".bn{animation:bn .5s steps(1) both}@keyframes bn{0%{opacity:0}1%{opacity:1}99%{opacity:1}100%{opacity:0}}",
           ".car{animation:blink 1s steps(1) infinite}@keyframes blink{50%{opacity:0}}",
           ".glint{animation:gl 7s ease-in-out 3s infinite}@keyframes gl{0%{transform:translateX(-300px)}40%,100%{transform:translateX(1500px)}}",
           RM]
    k = 0
    car = None
    for li, line in enumerate(lines):
        gl, lw = M5.glyphs(line, size, 0, 0, 0.3)
        x0 = (W - lw) / 2
        y = 62 + li * 40
        col = BONE if li else YEL
        for c, d, cx, adv in gl:
            k += 1
            if c == " ":
                continue
            delay = 0.25 + k * 0.014
            bit, _ = M7.path(rnd.choice("01"), size, x0 + cx, y, 0)
            chars.append(f'<path class="bn" style="animation-delay:{delay - 0.5:.3f}s" d="{bit}" fill="{ORA}"/>')
            dd, _ = M5.path(c, size, x0 + cx, y, 0)
            chars.append(f'<path class="ch" style="animation-delay:{delay - 0.5:.3f}s" d="{dd}" fill="{col}"/>')
        clips.append(M5.path(line, size, x0, y, 0.3)[0])
        car = (x0 + lw + 8, y)
        if li == 0:
            chars.append(txt(">", size, x0 - 30, y, ORA, M7, tracking=0))
    sub = txt("// whoami", 13, W / 2, 22, "#5c5c5c", M4, anchor="middle", tracking=2)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{full}">
<title>{full}</title>
<defs><style>{"".join(css)}</style>
<linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<clipPath id="tc"><path d="{"".join(clips)}"/></clipPath></defs>
{sub}
{"".join(chars)}
<g clip-path="url(#tc)"><rect class="glint" x="0" y="30" width="260" height="{H - 30}" fill="url(#g)" opacity=".8"/></g>
<rect class="car" x="{n(car[0])}" y="{car[1] - 19}" width="12" height="23" fill="{ORA}"/>
</svg>'''
    write("about.svg", svg)


# ---------------------------------------------------------------- keycaps
def icon_svg(kind, col):
    if kind == "globe":
        return (f'<g fill="none" stroke="{col}" stroke-width="2.4"><circle r="13"/><ellipse rx="5.5" ry="13"/>'
                f'<path d="M-13 0H13M-11 -6.5H11M-11 6.5H11"/></g>')
    if kind == "in":
        d, _ = M8.path("in", 15, 0, 5.2, -0.5, "middle")
        return f'<rect x="-13" y="-13" width="26" height="26" rx="5" fill="{col}"/><path d="{d}" fill="#0b0b0b"/>'
    if kind == "ig":
        return (f'<g fill="none" stroke="{col}" stroke-width="2.6"><rect x="-13" y="-13" width="26" height="26" rx="8"/><circle r="6"/></g>'
                f'<circle cx="7.6" cy="-7.6" r="1.9" fill="{col}"/>')
    if kind == "live":
        return (f'<circle r="6.5" fill="#0b0b0b"/><circle r="6.5" fill="none" stroke="#0b0b0b" stroke-width="2" class="ping"/>')
    return ""


def footprint(hw, hd, r, seg=4, dz=0.0):
    pts = []
    for cx, cz, a0 in ((hw - r, -hd + r, -90), (hw - r, hd - r, 0), (-hw + r, hd - r, 90), (-hw + r, -hd + r, 180)):
        for j in range(seg + 1):
            a = math.radians(a0 + 90 * j / seg)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a) + dz))
    return pts


def frustum(bot, top, y0, y1):
    """faces of a convex frustum between two footprints: [top, side, side, ...]"""
    B = [(x, y0, z) for x, z in bot]
    T = [(x, y1, z) for x, z in top]
    m = len(B)
    return [T] + [[B[i], B[(i + 1) % m], T[(i + 1) % m], T[i]] for i in range(m)]


def keycap(fname, label, sub_label, accent, icon, phase, wide=3.3, w_px=420, h_px=180, cap="#1b1b1b", legend=None, aria=""):
    N, DUR = 120, 7.0
    cam = Cam(600, w_px / 2, h_px / 2 - 2)
    hw, hd, Hc = wide / 2, 0.7, 0.4
    INS, ZF, ZB = 0.15, 0.2, 0.08
    PRESS = 0.16
    legend = legend or accent
    light = norm((-0.4, 0.8, -0.45))
    DIST = 6.1
    t_hw, t_hd, t_dz = hw - INS, hd - (ZF + ZB) / 2, (ZF - ZB) / 2
    bot = footprint(hw, hd, 0.16)
    topf = footprint(t_hw, t_hd, 0.13, dz=t_dz)
    pbot = footprint(hw + 0.09, hd + 0.09, 0.2)

    def pose(t):
        yaw = math.radians(9 * math.sin(TAU * (t + phase)))
        pitch = math.radians(-52 + 2.5 * math.sin(TAU * (2 * t + phase)))
        u = (t - phase) % 1.0
        press = PRESS * math.sin(math.pi * u / 0.08) if u < 0.08 else 0.0
        return yaw, pitch, press

    def world(p, yaw, pitch):
        r = rot(p, yaw, pitch)
        return (r[0], r[1] + 0.02, r[2] + DIST)

    plate = frustum(pbot, pbot, -0.16, 0.0)
    nplate, ncap = len(plate), len(bot) + 1
    P = {k: [[] for _ in range(m)] for k, m in (("pp", nplate), ("pf", nplate), ("pv", nplate), ("cp", ncap), ("cf", ncap), ("cv", ncap))}
    top_aff, glow_op = [], []
    for i in range(N + 1):
        t = i / N
        yaw, pitch, press = pose(t)
        capf = frustum(bot, topf, 0.0, Hc - press)
        for faces, center, kp, kf, kv, base in ((plate, (0, -0.08, 0), "pp", "pf", "pv", "#070707"),
                                                (capf, (0, (Hc - press) / 2, 0), "cp", "cf", "cv", cap)):
            wc = world(center, yaw, pitch)
            for fi, f in enumerate(faces):
                wp = [world(p, yaw, pitch) for p in f]
                nr = norm(cross(sub(wp[1], wp[0]), sub(wp[2], wp[0])))
                if dot(nr, sub(wp[0], wc)) < 0:
                    nr = tuple(-a for a in nr)
                lit = max(0.0, dot(nr, light))
                P[kp][fi].append([cam.p(p) for p in wp])
                if i < N:
                    P[kv][fi].append(1 if dot(nr, wp[0]) < 0 else 0)
                    P[kf][fi].append(mix(mix(base, "#000000", .62), mix(base, "#ffffff", .2), lit ** 1.25))
        Pc = world((0, Hc - press, t_dz), yaw, pitch)
        top_aff.append(cam.affine(Pc, rot((1, 0, 0), yaw, pitch), rot((0, 0, -1), yaw, pitch), unit=0.01))
        glow_op.append(f"{0.45 + 0.55 * press / PRESS:.2f}")
    for k in ("pf", "cf"):
        for f in P[k]:
            f.append(f[0])
    xs = [x for k in ("pp", "cp") for face in P[k] for fr_ in face for x, _ in fr_]
    ys = [y for k in ("pp", "cp") for face in P[k] for fr_ in face for _, y in fr_]
    fit = min((w_px - 24) / (max(xs) - min(xs)), (h_px - 34) / (max(ys) - min(ys)))
    fx = w_px / 2 - fit * (max(xs) + min(xs)) / 2
    fyy = h_px / 2 - fit * (max(ys) + min(ys)) / 2 - 2
    wrap = f'translate({n(fx)} {n(fyy)}) scale({fit:.4f})'
    edge = f' stroke="{mix(cap, "#ffffff", .3)}" stroke-opacity=".28" stroke-width=".7" stroke-linejoin="round"'
    plate_svg = "".join(poly_anim(P["pp"][k], P["pf"][k], P["pv"][k], DUR) for k in range(1, nplate))
    rim = poly_anim(P["pp"][0], P["pf"][0], None, DUR, stroke=f' stroke="{accent}" stroke-width="1.4" stroke-linejoin="round"',
                    extra=f' class="rim"')
    cap_svg = "".join(poly_anim(P["cp"][k], P["cf"][k], P["cv"][k], DUR, stroke=edge) for k in range(1, ncap))
    top_svg = poly_anim(P["cp"][0], P["cf"][0], None, DUR, stroke=edge)
    tf, an = aff_anim(top_aff, DUR)
    tw, td = 2 * t_hw * 100, 2 * t_hd * 100
    lab_size = 40 if len(label) < 12 else 32
    lw = width_of(label, lab_size, M8, -0.5)
    has_icon = bool(icon)
    gx = -(lw + (56 if has_icon else 0)) / 2
    oy = -7 if sub_label else 0
    legend_svg = f'<g transform="translate({n(gx + 16)} {n(oy - 12)}) scale(1.25)">{icon_svg(icon, legend)}</g>' if has_icon else ""
    lx = gx + (56 if has_icon else 0)
    legend_svg += txt(label, lab_size, lx, oy + 1, legend, M8, tracking=-0.5)
    if sub_label:
        legend_svg += txt(sub_label, 19, lx + 1, oy + 31, mix(legend, cap, .45) if cap == ORA else mix(BONE, cap, .4), M5, tracking=0.6)
    dish = (f'<path d="M{n(-tw / 2)} {n(-td / 2)}h{n(tw)}v{n(td)}h{n(-tw)}z" fill="url(#dish)"/>')
    sheen = f'<rect class="sheen" x="{n(-tw)}" y="{n(-td / 2)}" width="{n(tw * 0.45)}" height="{n(td)}" fill="url(#sh)"/>'
    clip = f'<clipPath id="tc"><rect x="{n(-tw / 2)}" y="{n(-td / 2)}" width="{n(tw)}" height="{n(td)}" rx="12"/></clipPath>'
    gcx, gcy = cam.p(world((0, -0.1, 0), 0, math.radians(-52)))
    css = (f".sheen{{animation:sh {DUR}s ease-in-out infinite;animation-delay:{phase * DUR + 0.3:.2f}s}}"
           f"@keyframes sh{{0%{{transform:translateX(0)}}30%,100%{{transform:translateX({n(tw * 2)}px)}}}}"
           ".ping{transform-box:fill-box;transform-origin:center;animation:ping 1.6s ease-out infinite}"
           "@keyframes ping{from{transform:scale(1);opacity:.9}to{transform:scale(2.6);opacity:0}}"
           ".rim{animation:rim 2.4s ease-in-out infinite alternate}@keyframes rim{from{stroke-opacity:.35}to{stroke-opacity:.9}}" + RM)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w_px} {h_px}" width="{w_px}" height="{h_px}" role="img" aria-label="{aria or label}">
<title>{aria or label}</title>
<defs><style>{css}</style>
<radialGradient id="ug"><stop offset="0" stop-color="{accent}" stop-opacity=".7"/><stop offset=".45" stop-color="{accent}" stop-opacity=".2"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>
<radialGradient id="dish" cx=".5" cy=".38" r=".75"><stop offset="0" stop-color="#fff" stop-opacity=".09"/><stop offset=".55" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".35"/></radialGradient>
<linearGradient id="sh" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".14"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
{clip}</defs>
<g transform="{wrap}">
<ellipse cx="{n(gcx)}" cy="{n(gcy + 6)}" rx="{n(w_px * .5)}" ry="{n(h_px * .34)}" fill="url(#ug)" opacity="{glow_op[0]}"><animate attributeName="opacity" values="{";".join(glow_op)}" {A(DUR)}/></ellipse>
{plate_svg}
{rim}
{cap_svg}
{top_svg}
<g transform="{tf}">{an}<g clip-path="url(#tc)">{dish}{sheen}</g>{legend_svg}</g>
</g>
</svg>'''
    write(fname, svg)


# ---------------------------------------------------------------- the forge
V_POLY = [(8, 10), (30, 10), (50, 68), (70, 10), (92, 10), (62, 92), (38, 92)]


def forge():
    H = 380
    cam = Cam(900, W / 2, 132)
    FLOOR = -1.6
    rnd = random.Random(11)

    def fy(z):
        return cam.CY - cam.F * FLOOR / z

    # ---- the V: extruded with depth layers, swaying in the heat
    N, DUR = 120, 12
    VS = 1.55  # world height
    VZ = 9.0
    DL = 15  # extrusion depth in V-local units
    vfr = []
    for i in range(N + 1):
        t = i / N
        yaw = math.radians(24 * math.sin(TAU * t))
        pitch = math.radians(-6 + 3 * math.sin(TAU * 2 * t))
        bob = 0.08 * math.sin(TAU * 2 * t)
        P = (0, -0.05 + bob, VZ)
        ex, ey = rot((1, 0, 0), yaw, pitch), rot((0, -1, 0), yaw, pitch)
        f = cam.affine(P, ex, ey, unit=VS / 100)
        f["ox"], f["oy"] = f["J"](rot((0, 0, 1), yaw, pitch))
        f["lit"] = max(0.0, -math.sin(yaw))
        vfr.append(f)
    tf, an = aff_anim(vfr, DUR)
    vpts = [((x - 50) * 1.02, (y - 51) * 1.1) for x, y in V_POLY]
    vpath = "M" + "L".join(f"{n(x)} {n(y)}" for x, y in vpts) + "Z"
    inset = [((x - 50) * 0.96, (y - 51) * 1.04) for x, y in V_POLY]
    vin = "M" + "L".join(f"{n(x)} {n(y)}" for x, y in inset) + "Z"
    K = 12
    vlayers = []
    for k in range(K, 0, -1):
        dl = DL * k / K
        vals = ";".join(f"{n(f['ox'] * dl)} {n(f['oy'] * dl)}" for f in vfr)
        vlayers.append(f'<g transform="translate({vals.split(";")[0]})"><animateTransform attributeName="transform" type="translate" values="{vals}" {A(DUR)}/>'
                       f'<use href="#vb" fill="url(#vside)"/></g>')
    vdefs = f'<g id="vb" transform="{tf}">{an}<path d="{vpath}"/></g>'
    vface = (f'<g transform="{tf}">{an}<path d="{vpath}" fill="url(#vface)"/>'
             f'<path d="{vpath}" fill="url(#vsheen)" />'
             f'<path class="vline" d="{vin}" pathLength="1" fill="none" stroke="url(#vstroke)" stroke-width="1.6" stroke-linejoin="round"/>'
             f'<path d="{vpath}" fill="none" stroke="{ORA}" stroke-opacity=".55" stroke-width=".8" stroke-linejoin="round"/></g>')
    v_sx, v_sy = cam.p((0, -0.05, VZ))

    # ---- fire: flame tongues that flicker, binary particles in the flames, sparks
    tongues = [(-3.4, 10.2, .55), (-2.3, 9.6, .8), (-1.2, 9.4, 1.0), (0, 9.8, 1.15), (1.2, 9.3, 1.0), (2.4, 9.7, .8),
               (3.5, 10.3, .55), (-0.6, 7.7, .42), (0.7, 7.6, .42), (-4.6, 11.2, .5), (4.8, 11.4, .5), (-0.6, 11.6, .9),
               (-1.8, 12.5, .7), (1.9, 12.8, .7), (0.6, 13.6, .75), (-3.2, 13.8, .5), (3.4, 14, .5)]
    flames_b, flames_f = [], []
    for tx, tz, st in sorted(tongues, key=lambda q: -q[1]):
        sx, sy = cam.p((tx, FLOOR, tz))
        sc = cam.F / tz
        for wm, hm, grad, op, off in ((1.25, 1.0, "fl0", .55, 0), (0.8, 0.62, "fl0", .45, .42), (0.8, 0.7, "fl0", .45, -.38),
                                      (0.74, 0.72, "fl1", .8, 0), (0.38, 0.46, "fl2", 1, 0)):
            w, h = sc * 0.95 * st * wm, sc * 2.3 * st * hm
            tip = w * rnd.uniform(-0.3, 0.3)
            ox = off * sc * 0.95 * st
            d = (f"M{n(ox - w / 2)} 0C{n(ox - w / 2)} {n(-h * .3)} {n(ox - w * .3 + tip * .4)} {n(-h * .55)} {n(ox + tip)} {n(-h)}"
                 f"C{n(ox + w * .18 + tip * .2)} {n(-h * .58)} {n(ox + w / 2)} {n(-h * .3)} {n(ox + w / 2)} 0Z")
            fd = rnd.uniform(0.7, 1.3)
            el = (f'<g transform="translate({n(sx + rnd.uniform(-3, 3))} {n(sy + 4)})"><path class="fk" d="{d}" fill="url(#{grad})" opacity="{op}" '
                  f'style="animation-duration:{fd:.2f}s;animation-delay:{-rnd.uniform(0, fd):.2f}s"/></g>')
            (flames_b if tz > VZ else flames_f).append(el)

    parts = []
    weights = [st for _, _, st in tongues]
    for _ in range(430):
        tx, tz, st = rnd.choices(tongues, weights)[0]
        x, z = tx + rnd.gauss(0, 0.3 + 0.2 * st), tz + rnd.gauss(0, 0.4)
        parts.append((z, x, max(0.15, st * math.exp(-((x - tx) / (0.5 * st + 0.2)) ** 2)), "d"))
    for _ in range(110):
        z = rnd.uniform(6.5, 16)
        parts.append((z, rnd.uniform(-1, 1) * z * 0.8, rnd.uniform(0.06, 0.2), "d"))
    for _ in range(55):
        tx, tz, st = rnd.choices(tongues, weights)[0]
        parts.append((tz, tx + rnd.gauss(0, 0.4), st, "s"))
    parts.sort(key=lambda p: -p[0])
    back, front = [], []
    css = []
    rises = set()
    for z, x, h, kind in parts:
        sx, sy = cam.p((x, FLOOR, z))
        s = cam.F / z * 0.0105
        if kind == "s":
            dur = rnd.uniform(1.1, 2.2)
            el = (f'<g transform="translate({n(sx)} {n(sy - 10)}) scale({s:.3f})"><circle r="1.3" fill="#FFF1C2" class="sp sp{rnd.randint(0, 3)}" '
                  f'style="animation-duration:{dur:.2f}s;animation-delay:{-rnd.uniform(0, dur):.2f}s"/></g>')
        else:
            key = int((30 + 170 * h) // 10) * 10
            rises.add(key)
            dur = rnd.uniform(1.3, 2.4) * (0.8 + 0.5 * h)
            sw = rnd.uniform(1.6, 3.2)
            el = (f'<g transform="translate({n(sx)} {n(sy)}) scale({s:.3f})"><g class="sw" style="animation-duration:{sw:.2f}s;animation-delay:{-rnd.uniform(0, sw):.2f}s">'
                  f'<use href="#g{rnd.choice("01")}" class="p r{key}" style="animation-duration:{dur:.2f}s;animation-delay:{-rnd.uniform(0, dur):.2f}s"/></g></g>')
        (back if z > VZ else front).append(el)
    life = (f"0%{{fill:#FFFBEA;opacity:0}}5%{{fill:#FFF1C2;opacity:1}}20%{{fill:{YEL}}}45%{{fill:{ORA};opacity:.95}}"
            f"72%{{fill:{RED};opacity:.7}}100%{{fill:#3a0b05;opacity:0}}")
    for key in sorted(rises):
        css.append(f"@keyframes r{key}{{from{{transform:translateY(0) scale(1)}}to{{transform:translateY(-{key}px) scale(.5)}}}}"
                   f".r{key}{{animation-name:r{key},life}}")
    css.append(".p{animation-timing-function:cubic-bezier(.3,.5,.6,1),linear;animation-iteration-count:infinite}@keyframes life{" + life + "}")
    css.append(".sw{animation:sw 2.4s ease-in-out infinite alternate}@keyframes sw{from{transform:translateX(-5px)}to{transform:translateX(5px)}}")
    for k, dx in enumerate((-40, -14, 14, 40)):
        css.append(f".sp{k}{{animation-name:sp{k}}}@keyframes sp{k}{{0%{{transform:translate(0,0);opacity:0}}10%{{opacity:1}}"
                   f"100%{{transform:translate({dx}px,-260px);opacity:0}}}}")
    css.append(".sp{animation-timing-function:cubic-bezier(.2,.6,.4,1);animation-iteration-count:infinite}")
    css.append(".fk{transform-box:fill-box;transform-origin:50% 100%;animation:fk 1s ease-in-out infinite alternate}"
               "@keyframes fk{0%{transform:scale(1,1) skewX(0deg)}33%{transform:scale(.9,1.14) skewX(-5deg)}"
               "66%{transform:scale(1.07,.9) skewX(4deg)}100%{transform:scale(.96,1.07) skewX(-2deg)}}")
    css.append(".vline{stroke-dasharray:.22 .78;animation:vl 3.2s linear infinite}@keyframes vl{to{stroke-dashoffset:-1}}")
    css.append(".flick{animation:fl 2.3s steps(9) infinite}@keyframes fl{0%{opacity:.8}20%{opacity:1}35%{opacity:.7}50%{opacity:.95}70%{opacity:.75}85%{opacity:1}100%{opacity:.85}}")
    css.append(RM + "@media (prefers-reduced-motion:reduce){.p{opacity:.8}}")

    # ---- ember cubes drifting up
    def ember(x0, z0, size, ph, spin):
        NE, DE = 60, 6.0
        faces = []
        for ax in range(3):
            for sg in (1, -1):
                q = []
                for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    p = [0, 0, 0]
                    others = [i for i in range(3) if i != ax]
                    p[ax] = sg
                    p[others[0]], p[others[1]] = u, v
                    q.append(tuple(c * size for c in p))
                nm = [0, 0, 0]
                nm[ax] = sg
                faces.append((q, tuple(nm)))
        paths = [[] for _ in faces]
        fills = [[] for _ in faces]
        vis = [[] for _ in faces]
        ops = []
        for i in range(NE + 1):
            t = ((i / NE) + ph) % 1.0
            yaw, pitch = TAU * spin[0] * i / NE, TAU * spin[1] * i / NE
            pos = (x0 + 0.25 * math.sin(TAU * t * 2), FLOOR + 0.3 + 3.2 * t, z0)
            for fi, (q, nm) in enumerate(faces):
                wp = [tuple(a + b for a, b in zip(rot(p, yaw, pitch), pos)) for p in q]
                nr = rot(nm, yaw, pitch)
                paths[fi].append([cam.p(p) for p in wp])
                if i < NE:
                    vis[fi].append(1 if dot(nr, wp[0]) < 0 else 0)
                    fills[fi].append(ramp([(0, "#FFF1C2"), (.35, YEL), (.7, ORA), (1, RED)], 1 - max(0, dot(nr, norm((0, -1, -0.4))))))
            ops.append(f"{(1 - t) * min(1, t * 6):.2f}")
        out = ""
        for fi in range(len(faces)):
            fills[fi].append(fills[fi][0])
            out += poly_anim(paths[fi], fills[fi], vis[fi], DE)
        return f'<g opacity="{ops[0]}"><animate attributeName="opacity" values="{";".join(ops)}" {A(DE)}/>{out}</g>'

    embers_b = ember(-2.6, 10.5, 0.07, 0.1, (1, 2)) + ember(3.2, 11.5, 0.06, 0.55, (-2, 1))
    embers_f = ember(-1.5, 7.4, 0.05, 0.35, (2, -1)) + ember(1.9, 7.2, 0.06, 0.8, (1, 1))

    # ---- floor grid glowing from below
    gl = ""
    x = -14.0
    while x <= 14.01:
        gl += f"M{n(cam.p((x, FLOOR, 5.4))[0])} {n(fy(5.4))}L{n(cam.p((x, FLOOR, 40))[0])} {n(fy(40))}"
        x += 0.9
    z = 5.4
    while z < 40:
        gl += f"M0 {n(fy(z))}H{W}"
        z *= 1.12

    d0, _ = M7.path("0", 13, -4, 5, 0)
    d1, _ = M7.path("1", 13, -4, 5, 0)
    hud = (txt("> exit 0", 12, 40, 50, GRAY, M5, tracking=1) + f'<rect class="cur" x="{n(40 + width_of("> exit 0", 12, M5, 1) + 5)}" y="40" width="8" height="13" fill="{ORA}"/>'
           + txt("[ ohrid / skopje, mk ]", 12, W - 40, 50, GRAY, M5, anchor="end", tracking=1)
           + txt("built in 0 and 1", 12, 40, H - 34, ORA, M5, tracking=1.5)
           + txt("vanniworks / forge", 12, W - 40, H - 34, "#5c5c5c", M5, anchor="end", tracking=1.5))
    css.append(".cur{animation:blink 1s steps(1) infinite}@keyframes blink{50%{opacity:0}}")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="binary fire around the V">
<title>forge</title>
<defs><style>{"".join(css)}</style>
<path id="g0" d="{d0}"/><path id="g1" d="{d1}"/>
{vdefs}
<radialGradient id="base" cx=".5" cy="1" r=".75"><stop offset="0" stop-color="{ORA}" stop-opacity=".55"/><stop offset=".35" stop-color="{RED}" stop-opacity=".22"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
<radialGradient id="core" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{YEL}" stop-opacity=".35"/><stop offset=".4" stop-color="{ORA}" stop-opacity=".15"/><stop offset="1" stop-color="{ORA}" stop-opacity="0"/></radialGradient>
<linearGradient id="gridfade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000"/><stop offset=".5" stop-color="#000" stop-opacity="0"/></linearGradient>
<linearGradient id="vside" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1a0a04"/><stop offset=".55" stop-color="#5a1a08"/><stop offset=".85" stop-color="{RED}"/><stop offset="1" stop-color="{YEL}"/></linearGradient>
<linearGradient id="vface" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1f1c19"/><stop offset=".6" stop-color="#16120f"/><stop offset="1" stop-color="#4a1d0a"/></linearGradient>
<linearGradient id="vsheen" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".45" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#ffd9a8" stop-opacity=".18"/><stop offset=".56" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
<animateTransform attributeName="gradientTransform" type="translate" values="-1 0;1 0;1 0" keyTimes="0;.45;1" dur="5s" repeatCount="indefinite"/></linearGradient>
<radialGradient id="bed"><stop offset="0" stop-color="{YEL}" stop-opacity=".9"/><stop offset=".4" stop-color="{ORA}" stop-opacity=".45"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></radialGradient>
<linearGradient id="fl0" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{ORA}"/><stop offset=".45" stop-color="{RED}" stop-opacity=".7"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></linearGradient>
<linearGradient id="fl1" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{YEL}"/><stop offset=".5" stop-color="{ORA}" stop-opacity=".8"/><stop offset="1" stop-color="{ORA}" stop-opacity="0"/></linearGradient>
<linearGradient id="fl2" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#FFFBEA"/><stop offset=".45" stop-color="{YEL}" stop-opacity=".85"/><stop offset="1" stop-color="{YEL}" stop-opacity="0"/></linearGradient>
<linearGradient id="vstroke" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{YEL}"/><stop offset=".6" stop-color="{ORA}"/><stop offset="1" stop-color="#fff"/></linearGradient>
<clipPath id="cl"><rect width="{W}" height="{H}"/></clipPath>
</defs>
<g clip-path="url(#cl)">
<rect width="{W}" height="{H}" fill="#000"/>
<path d="{gl}" stroke="#3a1206" fill="none"/>
<rect width="{W}" height="{n(fy(14))}" fill="url(#gridfade)"/>
<rect class="flick" y="{n(H * .2)}" width="{W}" height="{n(H * .8)}" fill="url(#base)"/>
<ellipse class="flick" cx="{n(v_sx)}" cy="{n(v_sy + 40)}" rx="330" ry="170" fill="url(#core)"/>
{embers_b}
<ellipse class="flick" cx="{n(v_sx)}" cy="{n(fy(10))}" rx="420" ry="26" fill="url(#bed)"/>
<g style="mix-blend-mode:screen">{"".join(flames_b)}</g>
<g>{"".join(back)}</g>
{"".join(vlayers)}
{vface}
<g style="mix-blend-mode:screen">{"".join(flames_f)}</g>
<g>{"".join(front)}</g>
{embers_f}
{corners(W, H)}
{hud}
</g>
</svg>'''
    write("fire.svg", svg)


if __name__ == "__main__":
    header("h-contrib.svg", "./git-stats.sh", "contributions")
    header("h-contact.svg", "./say-hi.sh", "contact")
    about()
    keycap("btn-live.svg", "vanniworks.com", "live / open the site", ORA, "live", 0.0, wide=4.2, w_px=560, h_px=200,
           cap=ORA, legend="#0b0b0b", aria="vanniworks.com")
    keycap("btn-site.svg", "site", "vanniworks.com", ORA, "globe", 0.12, aria="site: vanniworks.com")
    keycap("btn-linkedin.svg", "linkedin", "jovanvasilevski", YEL, "in", 0.22, aria="linkedin: jovanvasilevski")
    keycap("btn-instagram.svg", "instagram", "@vasilevski_j", RED, "ig", 0.32, aria="instagram: @vasilevski_j")
    forge()
