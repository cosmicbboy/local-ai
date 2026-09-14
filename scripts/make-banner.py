#!/usr/bin/env python3
"""Generate the local-ai logo + banner. Pure Pillow (no external deps).

Mark concept: three accent nodes — opencode / pi / dsh — wired into a single
core, set inside a hexagonal chip badge with a cyan -> violet -> magenta
gradient edge. The three tools feeding one self-hosted DeepSeek stack.

Everything is drawn at SS x resolution and downsampled with Lanczos so edges,
strokes and text stay crisp rather than painterly.
"""
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SS = 4  # supersample factor

# ---------------- palette ----------------
BG_TOP   = (17, 20, 42)
BG_MID   = (10, 12, 28)
BG_BOT   = (6, 7, 16)
CARD     = (14, 17, 36)
FROST    = (235, 240, 255)
SLATE    = (134, 145, 176)
CYAN     = (56, 208, 255)
VIOLET   = (150, 120, 255)
MAGENTA  = (255, 82, 205)
NODE_COLORS = [CYAN, VIOLET, MAGENTA]

SFMONO = "/System/Library/Fonts/SFNSMono.ttf"


def font(weight, size):
    f = ImageFont.truetype(SFMONO, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def vgradient(w, h, stops):
    """stops: [(t, (r,g,b)), ...] sorted by t, t0 == 0, tN == 1."""
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t <= t1 or i == len(stops) - 2:
                lt = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                col = lerp(c0, c1, max(0.0, min(1.0, lt)))
                break
        d.line([(0, y), (w, y)], fill=col)
    return img


def hex_vertices(cx, cy, r, rotation=-90):
    pts = []
    for i in range(6):
        a = math.radians(rotation + i * 60)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def radial_glow(size, cx, cy, r, color, peak_alpha, blur):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (peak_alpha,))
    return layer.filter(ImageFilter.GaussianBlur(blur))


def draw_mark(S, cx, cy, R):
    """Draw the hex-chip mark onto a fresh RGBA layer of size (S,S) and return it."""
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # halo behind the badge
    layer.alpha_composite(radial_glow((S, S), cx, cy, R * 1.5, VIOLET, 60, R * 0.35))
    layer.alpha_composite(radial_glow((S, S), cx, cy, R * 0.9, CYAN, 55, R * 0.22))
    d = ImageDraw.Draw(layer)

    verts = hex_vertices(cx, cy, R, rotation=-90)

    # badge fill
    d.polygon(verts, fill=CARD + (255,))

    # gradient edge (cyan -> violet -> magenta -> back to cyan across the 6 edges)
    stroke_w = max(2, int(S * 0.011))
    edge_cols = []
    for i in range(6):
        t = i / 5
        if t <= 0.5:
            col = lerp(CYAN, VIOLET, t / 0.5)
        else:
            col = lerp(VIOLET, MAGENTA, (t - 0.5) / 0.5)
        edge_cols.append(col)
    for i in range(6):
        p0, p1 = verts[i], verts[(i + 1) % 6]
        d.line([p0, p1], fill=edge_cols[i] + (255,), width=stroke_w)
    for i, (x, y) in enumerate(verts):
        col = edge_cols[i]
        r = stroke_w / 2
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (255,))

    # chip pins: short ticks outward from each vertex
    for i, (x, y) in enumerate(verts):
        ang = math.atan2(y - cy, x - cx)
        x2 = x + math.cos(ang) * S * 0.045
        y2 = y + math.sin(ang) * S * 0.045
        col = edge_cols[i]
        d.line([(x, y), (x2, y2)], fill=col + (230,), width=max(2, int(S * 0.007)))

    # inner triad: three nodes wired to one core
    core_r = R * 0.155
    node_r = R * 0.60
    node_pts = []
    for i in range(3):
        ang = math.radians(-90 + i * 120)
        node_pts.append((cx + node_r * math.cos(ang), cy + node_r * math.sin(ang)))

    wire_w = max(2, int(S * 0.0065))
    for (x, y), col in zip(node_pts, NODE_COLORS):
        d.line([(cx, cy), (x, y)], fill=col + (200,), width=wire_w)

    # core glow + dot
    layer.alpha_composite(radial_glow((S, S), cx, cy, core_r * 2.6, (255, 255, 255), 130, core_r * 0.9))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - core_r, cy - core_r, cx + core_r, cy + core_r], fill=(250, 253, 255, 255))

    # node glows + dots
    node_r_px = R * 0.105
    for (x, y), col in zip(node_pts, NODE_COLORS):
        layer.alpha_composite(radial_glow((S, S), x, y, node_r_px * 2.4, col, 110, node_r_px * 1.1))
    d = ImageDraw.Draw(layer)
    for (x, y), col in zip(node_pts, NODE_COLORS):
        d.ellipse([x - node_r_px, y - node_r_px, x + node_r_px, y + node_r_px],
                   fill=col + (255,), outline=(255, 255, 255, 220), width=max(1, int(S * 0.003)))

    return layer


def dot_grid(size, spacing, color, alpha):
    w, h = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r = max(1, spacing * 0.03)
    for gx in range(0, w, spacing):
        for gy in range(0, h, spacing):
            d.ellipse([gx - r, gy - r, gx + r, gy + r], fill=color + (alpha,))
    return layer


def draw_text_spaced(d, xy, text, fnt, fill, tracking=0):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + tracking
    return x


def pill(img, xy, label, fnt, col):
    """Opaque, high-contrast tag: dark tinted fill + solid accent border + frost text.

    Everything here is drawn fully opaque (alpha=255). A previous version relied on
    a low-alpha white fill for a "subtle tint" look, but the final RGBA -> RGB
    conversion at the end of make_banner() discards alpha rather than compositing
    it, so a low-alpha fill silently rendered as solid white — washing out the
    label text and blowing out the border into a glowing tube. Keeping every draw
    call opaque avoids that trap entirely.
    """
    d = ImageDraw.Draw(img)
    x, y = xy
    pad_l, pad_r, pad_y = 42 * SS, 24 * SS, 14 * SS
    tw = d.textlength(label, font=fnt)
    th = fnt.size
    box_h = th + pad_y * 2
    box = [x, y, x + pad_l + tw + pad_r, y + box_h]

    # soft halo behind the pill, on its own layer so it blends correctly
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    img.alpha_composite(radial_glow(img.size, cx, cy, (box[2] - box[0]) * 0.5, col, 60, box_h * 0.6))
    d = ImageDraw.Draw(img)

    fill = lerp(CARD, col, 0.16)
    d.rounded_rectangle(box, radius=box_h / 2, fill=fill + (255,),
                         outline=col + (255,), width=max(1, int(2.2 * SS)))

    dot_r = 5.5 * SS
    dot_cx, dot_cy = x + 21 * SS, y + box_h / 2
    d.ellipse([dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r],
              fill=col + (255,), outline=(255, 255, 255, 255), width=max(1, int(SS)))

    d.text((x + pad_l, y + pad_y - 2 * SS), label, font=fnt, fill=FROST + (255,))
    return box[2]


# =========================================================================
# LOGO — square badge, standalone mark on a soft card
# =========================================================================
def make_logo(size=1024):
    S = size * SS
    bg = vgradient(S, S, [(0.0, (24, 22, 52)), (0.55, (12, 13, 30)), (1.0, (5, 6, 13))])
    img = bg.convert("RGBA")

    mark = draw_mark(S, S / 2, S / 2, S * 0.34)
    img.alpha_composite(mark)

    # gentle vignette so the badge reads as a contained icon
    vig = Image.new("L", (S, S), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([S * -0.15, S * -0.15, S * 1.15, S * 1.15], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(S * 0.05))
    dark = Image.new("RGBA", (S, S), (0, 0, 0, 140))
    dark.putalpha(vig.point(lambda v: 255 - v))
    img = Image.alpha_composite(img, dark)

    img = img.convert("RGB").resize((size, size), Image.LANCZOS)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=110, threshold=2))
    return img


# =========================================================================
# BANNER — wide lockup: mark + wordmark + tagline + tool pills
# =========================================================================
def make_banner(w=1600, h=800):
    W, H = w * SS, h * SS
    bg = vgradient(W, H, [(0.0, BG_TOP), (0.5, BG_MID), (1.0, BG_BOT)])
    img = bg.convert("RGBA")

    # background texture: faint dot grid + big soft off-canvas glows
    img.alpha_composite(dot_grid((W, H), int(46 * SS), (150, 170, 220), 22))
    img.alpha_composite(radial_glow((W, H), W * 0.86, H * 0.18, W * 0.32, VIOLET, 46, W * 0.09))
    img.alpha_composite(radial_glow((W, H), W * 0.06, H * 0.92, W * 0.28, CYAN, 34, W * 0.09))

    # oversized faint hex watermark bleeding off the right edge
    wm = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wm)
    wcx, wcy, wr = W * 1.02, H * 0.5, H * 0.62
    wd.polygon(hex_vertices(wcx, wcy, wr), outline=(120, 150, 230, 26), width=int(3 * SS))
    img.alpha_composite(wm)

    d = ImageDraw.Draw(img)

    # --- mark, left side ---
    # draw_mark expects a square canvas; build one sized to the mark and paste at offset
    mark_r = H * 0.28
    mark_cx, mark_cy = W * 0.145, H * 0.5
    S = int(mark_r * 3.6)
    sub = draw_mark(S, S / 2, S / 2, mark_r)
    img.alpha_composite(sub, (int(mark_cx - S / 2), int(mark_cy - S / 2)))

    d = ImageDraw.Draw(img)

    # --- wordmark ---
    text_x = int(W * 0.30)
    caret_f = font("Bold", int(H * 0.11))
    word_f = font("Bold", int(H * 0.11))
    caret = "> "
    caret_w = d.textlength(caret, font=caret_f)
    word_y = int(H * 0.315)
    d.text((text_x, word_y), caret, font=caret_f, fill=CYAN + (255,))
    draw_text_spaced(d, (text_x + caret_w, word_y), "local-ai", word_f, FROST + (255,), tracking=int(2 * SS))

    # blinking-cursor accent block after the wordmark
    word_w = d.textlength("local-ai", font=word_f) + int(2 * SS) * 8
    cur_x = text_x + caret_w + word_w + 14 * SS
    cur_h = int(H * 0.085)
    d.rectangle([cur_x, word_y + int(H * 0.012), cur_x + int(H * 0.045), word_y + int(H * 0.012) + cur_h],
                fill=MAGENTA + (255,))

    # --- tagline ---
    tag_f = font("Regular", int(H * 0.032))
    tag_y = int(H * 0.315) + int(H * 0.135)
    draw_text_spaced(d, (text_x + caret_w, tag_y), "self-hosted deepseek stack, wired for one machine",
                      tag_f, SLATE + (255,), tracking=int(1.2 * SS))

    # --- tool pills ---
    pill_f = font("Semibold", int(H * 0.028))
    px = text_x + caret_w
    py = int(H * 0.315) + int(H * 0.135) + int(H * 0.075)
    for label, col in zip(["opencode", "pi", "dsh"], NODE_COLORS):
        px = pill(img, (px, py), label, pill_f, col) + 18 * SS
    d = ImageDraw.Draw(img)

    # --- bottom brand rule: cyan -> violet -> magenta ---
    bar_h = max(2, int(H * 0.006))
    for x in range(0, W, 4):
        t = x / W
        col = lerp(CYAN, VIOLET, t / 0.5) if t <= 0.5 else lerp(VIOLET, MAGENTA, (t - 0.5) / 0.5)
        d.rectangle([x, H - bar_h, x + 4, H], fill=col + (255,))

    # soft frame vignette
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    vd.rounded_rectangle([W * 0.01, H * 0.02, W * 0.99, H * 0.98], radius=int(H * 0.05), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(H * 0.08))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 110))
    dark.putalpha(vig.point(lambda v: 255 - v))
    img = Image.alpha_composite(img, dark)

    img = img.convert("RGB").resize((w, h), Image.LANCZOS)
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=110, threshold=2))
    return img


if __name__ == "__main__":
    logo = make_logo(1024)
    logo.save("assets/local-ai-logo.png")

    banner = make_banner(1600, 800)
    banner.save("assets/local-ai-banner.png")
    banner.save("assets/local-ai-banner.jpg", quality=92)

    print("wrote assets/local-ai-logo.png (1024x1024)")
    print("wrote assets/local-ai-banner.png and .jpg (1600x800)")
