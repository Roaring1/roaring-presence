#!/usr/bin/env python3
"""Render the Discord app icon and Rich Presence art assets for roaring-presence.

Outputs 1024x1024 PNGs into ~/Pictures/roaring-presence-art:

  icon.png          -> Application icon (General Information -> App Icon)
  icon_rounded.png   -> same art, rounded-square variant (optional)
  asset_cd.png       -> art asset key "cd"     (config assets.cd)
  asset_play.png     -> art asset key "play"   (config assets.play)
  asset_pause.png    -> art asset key "pause"  (config assets.pause)
  asset_cube.png     -> art asset key "cube"   (config assets.minecraft)
  contact_sheet.png  -> preview of all of the above

Everything is drawn from primitives: no downloaded or trademarked artwork.
"""

import colorsys
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

OUT = os.path.expanduser("~/Pictures/roaring-presence-art")
S = 1024
SS = 2  # supersample factor for the vector-ish shapes

FONT_CANDIDATES = (
    "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
)


def radial_bg(size, inner=(38, 40, 52), outer=(12, 12, 16)):
    """Smooth radial gradient, drawn small and upscaled (cheap and clean)."""
    n = 96
    im = Image.new("RGB", (n, n))
    px = im.load()
    c = (n - 1) / 2.0
    for y in range(n):
        for x in range(n):
            d = min(1.0, math.hypot(x - c, y - c) / (c * 1.42))
            f = d ** 0.85
            px[x, y] = tuple(int(inner[i] + (outer[i] - inner[i]) * f) for i in range(3))
    return im.resize((size, size), Image.LANCZOS)


def disc(size, hole_ratio=0.16, hub_ratio=0.30, sheen_rot=-38.0):
    """A CD: silver body, rainbow diffraction sweep, clear hub, centre hole."""
    n = size * SS
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    radius = n // 2
    c = n / 2.0

    draw.ellipse([0, 0, n - 1, n - 1], fill=(214, 218, 228, 255))
    for i in range(60):
        t = i / 60.0
        r = radius * (1 - t * 0.999)
        v = int(150 + 95 * abs(math.sin(t * math.pi * 1.15 + 0.25)))
        draw.ellipse(
            [c - r, c - r, c + r, c + r],
            outline=(v, v + 3, v + 10, 120),
            width=max(1, int(n * 0.004)),
        )

    rain = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    rain_draw = ImageDraw.Draw(rain)
    steps = 360
    for i in range(steps):
        a0 = i * 360.0 / steps
        a1 = a0 + 360.0 / steps + 0.8
        hue = ((a0 * 2.0) / 360.0) % 1.0
        r_, g_, b_ = colorsys.hsv_to_rgb(hue, 0.85, 1.0)
        rain_draw.pieslice(
            [0, 0, n - 1, n - 1], a0, a1, fill=(int(r_ * 255), int(g_ * 255), int(b_ * 255), 255)
        )

    annulus = Image.new("L", (n, n), 0)
    ann_draw = ImageDraw.Draw(annulus)
    ann_draw.ellipse([0, 0, n - 1, n - 1], fill=255)
    inner = radius * (hub_ratio + 0.04)
    ann_draw.ellipse([c - inner, c - inner, c + inner, c + inner], fill=0)
    annulus = annulus.filter(ImageFilter.GaussianBlur(n * 0.012))

    sweep = Image.new("L", (n, n), 0)
    sweep_draw = ImageDraw.Draw(sweep)
    sweep_draw.pieslice([0, 0, n - 1, n - 1], sheen_rot - 62, sheen_rot + 62, fill=255)
    sweep_draw.pieslice([0, 0, n - 1, n - 1], sheen_rot + 128, sheen_rot + 232, fill=190)
    sweep = sweep.filter(ImageFilter.GaussianBlur(n * 0.05))

    rain.putalpha(ImageChops.multiply(annulus, sweep).point(lambda v: int(v * 0.85)))
    im = Image.alpha_composite(im, rain)

    highlight = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(highlight).pieslice(
        [0, 0, n - 1, n - 1], sheen_rot - 18, sheen_rot + 18, fill=(255, 255, 255, 120)
    )
    highlight = highlight.filter(ImageFilter.GaussianBlur(n * 0.03))
    im = Image.alpha_composite(im, highlight)

    draw = ImageDraw.Draw(im)
    hub = radius * hub_ratio
    draw.ellipse([c - hub, c - hub, c + hub, c + hub], fill=(196, 201, 212, 255))
    draw.ellipse(
        [c - hub, c - hub, c + hub, c + hub],
        outline=(120, 125, 138, 255),
        width=max(2, int(n * 0.006)),
    )
    ring = radius * (hub_ratio - 0.075)
    draw.ellipse(
        [c - ring, c - ring, c + ring, c + ring],
        fill=(232, 235, 242, 255),
        outline=(150, 155, 168, 255),
        width=max(2, int(n * 0.004)),
    )
    hole = radius * hole_ratio
    draw.ellipse([c - hole, c - hole, c + hole, c + hole], fill=(0, 0, 0, 0))
    draw.ellipse(
        [c - hole, c - hole, c + hole, c + hole],
        outline=(90, 94, 105, 255),
        width=max(2, int(n * 0.005)),
    )
    draw.ellipse([1, 1, n - 2, n - 2], outline=(96, 100, 112, 255), width=max(2, int(n * 0.006)))
    return im.resize((size, size), Image.LANCZOS)


def rounded_mask(size, radius_frac=0.22):
    n = size * SS
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, n - 1, n - 1], radius=int(n * radius_frac), fill=255
    )
    return mask.resize((size, size), Image.LANCZOS)


def glow(size, box, colour=(120, 160, 255, 70)):
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(box, fill=colour)
    return layer.filter(ImageFilter.GaussianBlur(size * 0.045))


def badge(kind, fg=(245, 247, 252), bg=(26, 28, 36), rim=(52, 56, 72)):
    """Small circular play/pause badge, legible down to ~20px."""
    n = S * SS
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.ellipse([0, 0, n - 1, n - 1], fill=bg)
    draw.ellipse(
        [int(n * 0.045), int(n * 0.045), int(n * 0.955), int(n * 0.955)],
        outline=rim,
        width=int(n * 0.035),
    )
    c = n / 2.0
    if kind == "play":
        w, h = n * 0.30, n * 0.34
        draw.polygon([(c - w * 0.45, c - h), (c - w * 0.45, c + h), (c + w * 0.95, c)], fill=fg)
    else:
        bw, gap, h = n * 0.115, n * 0.085, n * 0.30
        draw.rounded_rectangle([c - gap - bw, c - h, c - gap, c + h], radius=int(bw * 0.35), fill=fg)
        draw.rounded_rectangle([c + gap, c - h, c + gap + bw, c + h], radius=int(bw * 0.35), fill=fg)
    return im.resize((S, S), Image.LANCZOS)


def voxel_cube():
    """Generic grass-topped voxel block for the Minecraft provider asset."""
    n = S * SS
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.ellipse([0, 0, n - 1, n - 1], fill=(24, 28, 24, 255))
    c = n / 2.0
    s = n * 0.30
    top = [(c, c - s * 1.12), (c + s, c - s * 0.55), (c, c + s * 0.02), (c - s, c - s * 0.55)]
    left = [(c - s, c - s * 0.55), (c, c + s * 0.02), (c, c + s * 1.16), (c - s, c + s * 0.60)]
    right = [(c + s, c - s * 0.55), (c, c + s * 0.02), (c, c + s * 1.16), (c + s, c + s * 0.60)]
    draw.polygon(top, fill=(126, 196, 84, 255))
    draw.polygon(left, fill=(112, 84, 56, 255))
    draw.polygon(right, fill=(140, 104, 70, 255))
    for poly in (top, left, right):
        draw.line(poly + [poly[0]], fill=(30, 34, 30, 220), width=int(n * 0.008))
    return im.resize((S, S), Image.LANCZOS)


def load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def main() -> int:
    os.makedirs(OUT, exist_ok=True)

    # 1. application icon: disc on a dark radial plate
    diameter = int(S * 0.80)
    offset = (S - diameter) // 2
    plate = radial_bg(S).convert("RGBA")
    halo = glow(S, [offset - 18, offset - 18, offset + diameter + 18, offset + diameter + 18])
    icon = Image.alpha_composite(plate, halo)
    icon.alpha_composite(disc(diameter), (offset, offset))
    icon.convert("RGB").save(os.path.join(OUT, "icon.png"))
    rounded = icon.copy()
    rounded.putalpha(rounded_mask(S))
    rounded.save(os.path.join(OUT, "icon_rounded.png"))

    # 2. "cd" asset: full-bleed disc, used when no cover art resolves
    big = int(S * 0.92)
    off2 = (S - big) // 2
    cd = Image.alpha_composite(
        radial_bg(S, (30, 32, 44), (10, 10, 14)).convert("RGBA"),
        glow(S, [off2 - 14, off2 - 14, off2 + big + 14, off2 + big + 14]),
    )
    cd.alpha_composite(disc(big, sheen_rot=-120), (off2, off2))
    cd.convert("RGB").save(os.path.join(OUT, "asset_cd.png"))

    # 3/4. play + pause small images
    badge("play").convert("RGB").save(os.path.join(OUT, "asset_play.png"))
    badge("pause").convert("RGB").save(os.path.join(OUT, "asset_pause.png"))

    # 5. voxel cube for the minecraft provider
    voxel_cube().convert("RGB").save(os.path.join(OUT, "asset_cube.png"))

    # contact sheet
    sheet_items = (
        ("icon.png", "app icon"),
        ("icon_rounded.png", "icon (rounded)"),
        ("asset_cd.png", 'asset key "cd"'),
        ("asset_play.png", 'asset key "play"'),
        ("asset_pause.png", 'asset key "pause"'),
        ("asset_cube.png", 'asset key "cube"'),
    )
    tile_w, tile_h = 300, 340
    sheet = Image.new("RGB", (tile_w * 3, tile_h * 2), (18, 18, 22))
    sheet_draw = ImageDraw.Draw(sheet)
    font = load_font(22)
    for index, (name, label) in enumerate(sheet_items):
        thumb = Image.open(os.path.join(OUT, name)).convert("RGB").resize((280, 280), Image.LANCZOS)
        x = (index % 3) * tile_w + 10
        y = (index // 3) * tile_h + 8
        sheet.paste(thumb, (x, y))
        sheet_draw.text((x + 4, y + 288), label, fill=(225, 228, 235), font=font)
    sheet.save(os.path.join(OUT, "contact_sheet.png"))

    for name in sorted(os.listdir(OUT)):
        path = os.path.join(OUT, name)
        with Image.open(path) as im:
            print("  %-20s %4dx%-4d %7.1f KiB" % (name, im.width, im.height, os.path.getsize(path) / 1024))
    print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
