#!/usr/bin/env python3
"""Generate an abstract banner for the local-ai repo. Pure Pillow (no external deps).

Artistic concept: a local AI "stack" — a luminous central core (the self-hosted
DeepSeek box) fed by a cascade of neural layers that funnel in from the left, while
three translucent strata (the opencode / pi / dsh layers) stack up and orbit it.
No text, only shape, glow and flow.
"""
import math, random
from PIL import Image, ImageDraw, ImageFilter

W, H = 1600, 800
random.seed(7)

CYAN   = (56, 208, 255)
MAGENTA= (255, 82, 205)
PERIW  = (120, 150, 255)
CRIMSON= (255, 90, 120)

# ---------------- background gradient ----------------
def make_gradient(w, h, c1, c2, c3):
    img = Image.new("RGB", (int(w), int(h)))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        if t < 0.5:
            tt = t * 2; a, b = c1, c2
        else:
            tt = (t - 0.5) * 2; a, b = c2, c3
        r = int(a[0] + (b[0] - a[0]) * tt)
        g = int(a[1] + (b[1] - a[1]) * tt)
        bl = int(a[2] + (b[2] - a[2]) * tt)
        d.line([(0, y), (w, y)], fill=(r, g, bl))
    return img

base = make_gradient(W, H, (5, 7, 22), (16, 12, 46), (7, 18, 32))

top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
td = ImageDraw.Draw(top)

# ---------------- faint dot grid ----------------
for gx in range(0, W, 54):
    for gy in range(0, H, 54):
        td.ellipse([gx - 1.2, gy - 1.2, gx + 1.2, gy + 1.2], fill=(140, 190, 255, 30))

# ---------------- background nebula glow ----------------
neb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ndb = ImageDraw.Draw(neb)
ndb.ellipse([W*0.58, H*0.12, W*1.18, H*0.9], fill=(80, 65, 210, 60))
ndb.ellipse([W*0.02, H*0.05, W*0.55, H*1.05], fill=(22, 130, 170, 42))
ndb.ellipse([W*-0.08, H*0.25, W*0.22, H*0.78], fill=(255, 82, 170, 22))
neb = neb.filter(ImageFilter.GaussianBlur(120))
top.alpha_composite(neb)

# ---------------- three translucent stack strata ----------------
strata = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(strata)
slab_colors = [(56, 208, 255), (140, 120, 255), (255, 82, 205)]
for i, col in enumerate(slab_colors):
    y = H * (0.24 + i * 0.22)
    amp = 26 + i * 8
    # wavy band
    pts = []
    steps = 140
    for s in range(steps + 1):
        x = W * s / steps
        wob = math.sin(x * 0.004 + i * 2.1) * amp + math.sin(x * 0.011 - i) * (amp * 0.4)
        pts.append((x, y + wob))
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    bd.line(pts, fill=col + (70,), width=3)
    for x in range(0, W, 9):
        yy = y + math.sin(x * 0.004 + i * 2.1) * amp + math.sin(x * 0.011 - i) * (amp * 0.4)
        bd.ellipse([x - 2, yy - 2, x + 2, yy + 2], fill=col + (90,))
    band = band.filter(ImageFilter.GaussianBlur(7))
    strata.alpha_composite(band)
top.alpha_composite(strata)

# ---------------- neural funnel converging on the core ----------------
funnel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
fd = ImageDraw.Draw(funnel)
core = (W * 0.76, H * 0.5)

# faint sonar rings far left — the distant source the signal travels from
sonar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(sonar)
for srad in (90, 160, 235):
    sd.ellipse([W*0.13 - srad, H*0.5 - srad*0.62, W*0.13 + srad, H*0.5 + srad*0.62],
               outline=CYAN + (36,), width=2)
for srad in (90, 160, 235):
    a0 = math.radians(-18); a1 = math.radians(30)
    sd.arc([W*0.13 - srad, H*0.48 - srad*0.62, W*0.13 + srad, H*0.48 + srad*0.62],
           a0, a1, fill=MAGENTA + (60,), width=2)
sonar = sonar.filter(ImageFilter.GaussianBlur(1.5))
funnel.alpha_composite(sonar)

def ring_nodes(cx, cy, r, n, jitter):
    out = []
    for i in range(n):
        a = i / n * 2 * math.pi + random.uniform(0, 0.4)
        out.append((cx + (r + random.uniform(-jitter, jitter)) * math.cos(a),
                    cy + (r + random.uniform(-jitter, jitter)) * math.sin(a)))
    return out

# three concentric source rings mid-left
rings = [
    (core[0] - 470, core[1] - 60, 150, 5, 26),
    (core[0] - 300, core[1] + 40, 120, 6, 24),
    (core[0] - 150, core[1] - 20, 90, 5, 22),
]
all_nodes = []
for cx, cy, r, n, jit in rings:
    all_nodes.append(ring_nodes(cx, cy, r, n, jit))

# connective mesh between source nodes and the core (data flowing inward)
line_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ld = ImageDraw.Draw(line_layer)
for layer in all_nodes:
    for (x, y) in layer:
        if random.random() < 0.7:
            # inward curve toward core
            mx = (x + core[0]) / 2
            my = (y + core[1]) / 2 - random.uniform(-40, 40)
            col = CYAN if random.random() < 0.55 else MAGENTA
            ld.line([(x, y), (mx, my), core], fill=col + (36,), width=1, joint="curve")
        if random.random() < 0.3:  # occasional cross-layer link
            other = random.choice(all_nodes)
            ob = random.choice(other)
            col = PERIW
            ld.line([(x, y), ob], fill=col + (22,), width=1)
line_layer = line_layer.filter(ImageFilter.GaussianBlur(2))
funnel.alpha_composite(line_layer)

# draw source nodes w/ glow
for layer in all_nodes:
    for (x, y) in layer:
        col = MAGENTA if random.random() < 0.4 else CYAN
        fd.ellipse([x - 9, y - 9, x + 9, y + 9], fill=col + (55,))
        fd.ellipse([x - 3.5, y - 3.5, x + 3.5, y + 3.5], fill=col + (255,))
top.alpha_composite(funnel)

# ---------------- the core: layered glowing star ----------------
core_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
kd = ImageDraw.Draw(core_layer)
cx, cy = core
# halo
halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
hd = ImageDraw.Draw(halo)
hd.ellipse([cx - 190, cy - 190, cx + 190, cy + 190], fill=(120, 190, 255, 70))
hd.ellipse([cx - 120, cy - 120, cx + 120, cy + 120], fill=(200, 120, 255, 60))
halo = halo.filter(ImageFilter.GaussianBlur(45))
core_layer.alpha_composite(halo)

# rotating dashed orbit (data always-on)
for k in range(0, 360, 7):
    a0 = math.radians(k); a1 = math.radians(k + 3)
    r0, r1 = 168, 176
    if random.random() < 0.85:
        kd.line([(cx + r0*math.cos(a0), cy + r0*math.sin(a0)),
                 (cx + r1*math.cos(a1), cy + r1*math.sin(a1))], fill=(150, 210, 255, 200), width=5)

# outer orbit satellite rings (tilted)
for tilt, rad, col in [(0.35, 135, CYAN), (-0.5, 105, MAGENTA)]:
    for a in [t for t in range(0, 36000, 300)]:
        a = a / 100.0
        x = cx + rad * math.cos(a)
        y = cy + rad * math.sin(a) * 0.5 + tilt * 30
        kd.ellipse([x - 2.4, y - 2.4, x + 2.4, y + 2.4], fill=col + (230,))

# nucleus: concentric
kd.ellipse([cx - 74, cy - 74, cx + 74, cy + 74], fill=(14, 20, 48),
           outline=(90, 130, 255, 210), width=3)
kd.ellipse([cx - 52, cy - 52, cx + 52, cy + 52],
           outline=(56, 208, 255, 220), width=2)
kd.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=(255, 82, 205, 210),
           outline=(255, 180, 240, 255), width=2)
# white-hot center
kd.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=(240, 250, 255))
top.alpha_composite(core_layer)

# ---------------- scattered particles / constellation / signal streams ----------------
particles = Image.new("RGBA", (W, H), (0, 0, 0, 0))
pd = ImageDraw.Draw(particles)
for _ in range(150):
    x = random.uniform(0, W); y = random.uniform(0, H)
    r = random.uniform(0.8, 2.8)
    col = random.choice([CYAN, MAGENTA, PERIW])
    alpha = random.randint(60, 200)
    pd.ellipse([x - r, y - r, x + r, y + r], fill=col + (alpha,))
# dotted signal streams curving toward the core (like data carriers)
for _ in range(11):
    y0 = random.uniform(H*0.18, H*0.82)
    col = random.choice([CYAN, MAGENTA, PERIW])
    for t in range(0, 100, 5):
        tt = t / 100.0
        x = W*0.06 + tt * (core[0] - W*0.06)
        y = y0 + math.sin(tt * 4.2 + y0) * 42 - tt * (y0 - core[1]) * 0.6
        if random.random() < 0.6:
            pd.ellipse([x-1.6, y-1.6, x+1.6, y+1.6], fill=col + (70,))
top.alpha_composite(particles)

# ---------------- bottom data bar ----------------
bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
bd = ImageDraw.Draw(bar)
bd.rectangle([0, H - 7, W, H], fill=(24, 30, 60, 255))
for bx in range(0, W, 20):
    bh = random.randint(4, 9)
    bd.rectangle([bx, H - 7, bx + 9, H - 7 + bh], fill=CYAN + (130,))
top.alpha_composite(bar)

# ---------------- compose + vignette ----------------
final = base.convert("RGBA")
final.alpha_composite(top)

vig = Image.new("L", (W, H), 0)
vd = ImageDraw.Draw(vig)
vd.rounded_rectangle([70, 45, W - 70, H - 45], radius=46, fill=255)
vig = vig.filter(ImageFilter.GaussianBlur(100))
dark = Image.new("RGBA", (W, H), (0, 0, 0, 120))
dark.putalpha(vig.point(lambda v: 255 - v))
final = Image.alpha_composite(final, dark).convert("RGB")
final = final.filter(ImageFilter.UnsharpMask(radius=2, percent=110, threshold=2))

final.save("assets/local-ai-banner.png")
final.save("assets/local-ai-banner.jpg", quality=92)
print("wrote assets/local-ai-banner.png and .jpg  (%dx%d)" % final.size)
