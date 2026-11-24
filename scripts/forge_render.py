"""Renders assets/forge.webp: scripts/forge/forge.html (WebGL2 volumetric fire + the V)
is rendered frame by frame in headless Chrome (GPU), then bloom, film grain, rising
binary digits and the HUD are composited here and the loop is encoded as animated WebP.

usage: python scripts/forge_render.py            # full loop -> assets/forge.webp
       python scripts/forge_render.py preview 30 # one frame (index of 120) -> /tmp-ish png
needs Pillow and fonts/JetBrainsMono.ttf (see ui3d.py)
"""
import base64
import io
import json
import math
import os
import random
import re
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGE = os.path.join(ROOT, "scripts", "forge", "forge.html")
W, H, N, FPS = 1280, 360, 120, 24
ORA, YEL, GRAY, DIMG = (255, 138, 31), (255, 210, 58), (156, 156, 156), (92, 92, 92)


def render(only=None, ss=2):
    q = f"?w={W}&h={H}&n={N}&ss={ss}" + (f"&only={only}" if only is not None else "")
    p = subprocess.run([CHROME, "--headless=new", "--use-angle=metal", "--enable-gpu", "--allow-file-access-from-files",
                        "--virtual-time-budget=600000", "--dump-dom", "file://" + PAGE + q],
                       capture_output=True, text=True, timeout=1800)
    m = re.search(r'<pre id="o">(.*?)</pre>', p.stdout, re.S)
    data = json.loads(m.group(1).replace("&amp;", "&"))
    if data and data[0].startswith("ERROR"):
        raise SystemExit(data[0])
    return [Image.open(io.BytesIO(base64.b64decode(d.split(",", 1)[1]))).convert("RGB") for d in data]


def font(size, wght=500):
    f = ImageFont.truetype(os.path.join(ROOT, "fonts", "JetBrainsMono.ttf"), size)
    try:
        f.set_variation_by_axes([wght])
    except Exception:
        pass
    return f


F_HUD, F_BIT, F_BIT2 = font(13, 500), font(15, 700), font(11, 700)
rnd = random.Random(5)
BITS = [dict(x=rnd.uniform(0.2, 0.8), s=rnd.random(), k=1 + rnd.randrange(2), ch=rnd.choice("01"),
             big=rnd.random() < 0.35, sway=rnd.uniform(6, 18)) for _ in range(46)]


def overlay(img, i):
    t = i / N
    base = img.copy()
    # bloom: bright pass, wide + tight blur, added back
    bright = base.point(lambda v: max(0, v - 175) * 2)
    glow = ImageChops.add(bright.filter(ImageFilter.GaussianBlur(18)), bright.filter(ImageFilter.GaussianBlur(5)))
    base = ImageChops.add(base, glow.point(lambda v: int(v * 0.45)))
    # binary digits rising out of the fire, with their own glow
    layer = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(layer)
    for b in BITS:
        life = (b["s"] + t * b["k"]) % 1.0
        fade = min(1.0, life / 0.12) * (1 - max(0.0, (life - 0.55) / 0.45))
        if fade <= 0:
            continue
        x = W * b["x"] + b["sway"] * math.sin(2 * math.pi * (life + b["s"]))
        y = H * 0.72 - life * H * 0.62
        hot = 1 - life
        col = tuple(int(c * fade) for c in ((255, int(170 + 70 * hot), int(60 + 120 * hot * hot))))
        d.text((x, y), b["ch"], font=F_BIT if b["big"] else F_BIT2, fill=col)
    base = ImageChops.add(base, ImageChops.add(layer, layer.filter(ImageFilter.GaussianBlur(4))))
    # film grain (fresh every frame, like film)
    g = Image.effect_noise((W, H), 14).convert("RGB")
    base = ImageChops.add(base, g.point(lambda v: max(0, v - 128) // 6))
    base = ImageChops.subtract(base, g.point(lambda v: max(0, 128 - v) // 6))
    # HUD
    d = ImageDraw.Draw(base)
    for x0, y0, dx, dy in ((18, 18, 1, 1), (W - 19, 18, -1, 1), (18, H - 19, 1, -1), (W - 19, H - 19, -1, -1)):
        d.line([(x0, y0 + dy * 26), (x0, y0), (x0 + dx * 26, y0)], fill=ORA, width=2)
    d.text((42, 38), "> exit 0", font=F_HUD, fill=GRAY)
    if int(t * N / (FPS / 2)) % 2 == 0:
        w = d.textlength("> exit 0 ", font=F_HUD)
        d.rectangle([42 + w, 39, 42 + w + 8, 53], fill=ORA)
    s = "[ ohrid / skopje, mk ]"
    d.text((W - 42 - d.textlength(s, font=F_HUD), 38), s, font=F_HUD, fill=GRAY)
    d.text((42, H - 54), "built in 0 and 1", font=F_HUD, fill=ORA)
    s = "vanniworks / forge"
    d.text((W - 42 - d.textlength(s, font=F_HUD), H - 54), s, font=F_HUD, fill=DIMG)
    return base


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        k = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.environ.get("TMPDIR", "/tmp"), f"forge_{k}.png")
        overlay(render(k)[0], k).save(out)
        print(out)
    else:
        frames = [overlay(f, i) for i, f in enumerate(render())]
        path = os.path.join(ROOT, "assets", "forge.webp")
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=round(1000 / FPS), loop=0,
                       quality=int(os.environ.get("Q", 70)), method=6)
        print(path, f"{os.path.getsize(path) / 1e6:.2f} MB", len(frames), "frames")
