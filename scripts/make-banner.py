#!/usr/bin/env python3
"""Generate a banner image for the local-ai repo. Pure Pillow (no external deps)."""
import math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1600, 800
WIDTH, HEIGHT = W, H
random.seed(42)

MONO = "/System/Library/Fonts/SFNSMono.ttf"
HELV = "/System/Library/Fonts/Helvetica.ttc"

def font(path, size):
    return ImageFont.truetype(path, size)

# ---------------- background gradient ----------------
def make_gradient(w, h, c1, c2, c3=None, angle=90):
    """Vertical-ish gradient; optionally 3-stop."""
    img = Image.new("RGB", (int(w), int(h)))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        if c3 is None:
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
        else:
            if t < 0.5:
                tt = t * 2
                a, b_ = c1, c2
            else:
                tt = (t - 0.5) * 2
                a, b_ = c2, c3
            r = int(a[0] + (b_[0] - a[0]) * tt)
            g = int(a[1] + (b_[1] - a[1]) * tt)
            b = int(a[2] + (b_[2] - a[2]) * tt)
        d.line([(0, y), (w, y)], fill=(r, g, b))
    return img

base = make_gradient(W, H, (7, 9, 26), (16, 14, 46), (8, 20, 34))

# ---------------- neural network graph ----------------
neo_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
nd = ImageDraw.Draw(neo_layer)

def node_layer(y, n, x0, x1, jitter):
    xs = [x0 + (x1 - x0) * i / max(1, n - 1) for i in range(n)]
    nodes = []
    for x in xs:
        nodes.append((x + random.uniform(-jitter, jitter), y + random.uniform(-jitter, jitter)))
    return nodes

layers = []
y0 = H * 0.16
for i, n in enumerate([5, 9, 12, 9, 6]):
    layers.append(node_layer(y0 + i * (H * 0.16), n, W * 0.06, W * 0.94, 26))

# glow pass on lines then circles
lines = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ld = ImageDraw.Draw(lines)
cyan = (56, 208, 255)
magenta = (255, 82, 205)
for li in range(len(layers) - 1):
    for a in layers[li]:
        for b in layers[li + 1]:
            if random.random() < 0.55:
                col = cyan if random.random() < 0.6 else magenta
                ld.line([a, b], fill=col + (40,), width=1)
lines = lines.filter(ImageFilter.GaussianBlur(2))
neo_layer.alpha_composite(lines)

for i, layer in enumerate(layers):
    for (x, y) in layer:
        glow_col = magenta if i % 2 == 0 else cyan
        nd.ellipse([x - 9, y - 9, x + 9, y + 9], fill=glow_col + (50,))
        nd.ellipse([x - 3.6, y - 3.6, x + 3.6, y + 3.6], fill=glow_col + (255,))

# ---------------- faint dot grid ----------------
grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(grid)
step = 60
for gx in range(0, W, step):
    for gy in range(0, H, step):
        gd.ellipse([gx - 1.2, gy - 1.2, gx + 1.2, gy + 1.2], fill=(140, 190, 255, 36))
neo_layer.alpha_composite(grid)

# ---------------- left panel: dark glass card ----------------
card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
cd = ImageDraw.Draw(card)
x0, y0c, x1, y1c = 70, 150, 620, 690
cd.rounded_rectangle([x0, y0c, x1, y1c], radius=28, fill=(10, 14, 34, 235),
                     outline=(88, 120, 255, 110), width=2)
# subtle top highlight
cd.rounded_rectangle([x0, y0c, x1, y0c + 90], radius=28, fill=(255, 255, 255, 10))
cd.rectangle([x0, y0c + 60, x1, y0c + 90], fill=(10, 14, 34, 235))  # blend
neo_layer.alpha_composite(card)

# ---------------- text ----------------
txt_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
td = ImageDraw.Draw(txt_layer)
white = (238, 243, 254)
dim = (150, 165, 200)

# small eyebrow tag
tag_font = font(MONO, 34)
td.text((95, 200), "// personal ai stack", font=tag_font, fill=(110, 180, 255))
td.rectangle([95, 232, 690, 234], fill=(110, 180, 255, 120))

# big title with `>` prompt char
big = font(MONO, 150)
td.text((90, 268), ">", font=big, fill=(56, 208, 255))
title = "local-ai"
tw = td.textlength(title, font=big)
# gradient fill the title text via mask
title_img = Image.new("RGBA", (int(tw) + 20, 210), (0, 0, 0, 0))
tid = ImageDraw.Draw(title_img)
tid.text((0, 0), title, font=big, fill=(255, 255, 255))
mask = title_img.split()[3]
grad = make_gradient(tw + 20, 210, (56, 208, 255), (120, 120, 255), (255, 82, 205))
grad = grad.convert("RGBA")
grad.putalpha(mask)
txt_layer.alpha_composite(grad, (170, 268))

# subtitle
sub = font(MONO, 40)
sub_txt = "deepseek v4  .  self-hosted  .  always-on dsh service"
td.text((95, 500), sub_txt, font=sub, fill=dim)

# tags row
def tag(text, x, color):
    f = font(MONO, 34)
    w = td.textlength(text, font=f)
    td.rounded_rectangle([x, 570, x + w + 44, 622], radius=16, outline=color + (160,), width=2)
    td.text((x + 22, 576), text, font=f, fill=color)

tag("  opencode", 95, (56, 208, 255))
tag("  pi", 310, (140, 120, 255))
tag("  dsh", 435, (255, 82, 205))

# ---------------- right panel: cpu/neural node icon ----------------
icon = Image.new("RGBA", (W, H), (0, 0, 0, 0))
idd = ImageDraw.Draw(icon)
cx, cy, R = 1240, 400, 158
# glow underlay
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gl = ImageDraw.Draw(glow)
gl.ellipse([cx - R - 26, cy - R - 26, cx + R + 26, cy + R + 26], fill=(56, 208, 255, 60))
glow = glow.filter(ImageFilter.GaussianBlur(24))
icon.alpha_composite(glow)

# outer ring (rotating dashes)
for k in range(0, 360, 8):
    a0 = math.radians(k)
    a1 = math.radians(k + 4)
    r0, r1 = R + 20, R + 26
    idd.line([(cx + r0 * math.cos(a0), cy + r0 * math.sin(a0)),
              (cx + r1 * math.cos(a1), cy + r1 * math.sin(a1))], fill=(120, 200, 255, 220), width=5)

# cpu body
idd.rounded_rectangle([cx - R, cy - R, cx + R, cy + R], radius=34, fill=(13, 18, 44),
                      outline=(92, 130, 255, 200), width=3)
# inner neural node
inner = 118
idd.ellipse([cx - inner, cy - inner, cx + inner, cy + inner],
            outline=(56, 208, 255, 220), width=2)
idd.ellipse([cx - 56, cy - 56, cx + 56, cy + 56], fill=(16, 24, 56),
            outline=(255, 82, 205, 200), width=2)
# nucleus
idd.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=(56, 208, 255, 230))

# pins around the cpu
pins = [(cx - R - 30, cy - 70), (cx - R - 30, cy - 20), (cx - R - 30, cy + 30), (cx - R - 30, cy + 80),
        (cx + R + 6, cy - 70), (cx + R + 6, cy - 20), (cx + R + 6, cy + 30), (cx + R + 6, cy + 80),
        (cx - 70, cy - R - 30), (cx - 20, cy - R - 30), (cx + 30, cy - R - 30), (cx + 80, cy - R - 30),
        (cx - 70, cy + R + 6), (cx - 20, cy + R + 6), (cx + 30, cy + R + 6), (cx + 80, cy + R + 6)]
for px, py in pins:
    idd.ellipse([px - 10, py - 10, px + 10, py + 10], fill=(120, 170, 255), outline=(200, 225, 255))

neo_layer.alpha_composite(icon)

# ---------------- bottom bar ----------------
bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
bd = ImageDraw.Draw(bar)
bd.rectangle([0, H - 8, W, H], fill=(20, 26, 54, 255))
for bx in range(0, W, 22):
    bd.rectangle([bx, H - 8, bx + 11, H], fill=(56, 208, 255, 120))

neo_layer.alpha_composite(bar)

# ---------------- compose ----------------
final = base.convert("RGBA")
final.alpha_composite(neo_layer)
final.alpha_composite(txt_layer)

# vignette
vig = Image.new("L", (W, H), 0)
vd = ImageDraw.Draw(vig)
vd.rounded_rectangle([60, 40, W - 60, H - 40], radius=40, fill=255)
vig = vig.filter(ImageFilter.GaussianBlur(90))
dark = Image.new("RGBA", (W, H), (0, 0, 0, 110))
dark.putalpha(vig.point(lambda v: 255 - v))
final = Image.alpha_composite(final, dark)

out = final.convert("RGB")
out = out.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=2))
out.save("assets/local-ai-banner.png")
out.save("assets/local-ai-banner.jpg", quality=92)
print("wrote assets/local-ai-banner.png and .jpg  (%dx%d)" % out.size)
