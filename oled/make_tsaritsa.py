"""Builds the right-half OLED animation: Tsaritsa casting a Cryo burst (charge, snowflake, flash, ice shards).

Writes a drop-in replacement for zmk-nice-oled's assets/crystal.c (16 frames,
69x68, 1-bit; only rows 18..49 are visible on the 128x32 Sofle OLED). The OLED is
mounted portrait, so frames are drawn upright at 32x69 and rotated 90 degrees clockwise.
usage: python3 -I make_tsaritsa.py <Anastasya_Icon.png> <out crystal.c> [preview.png]
"""
import random, sys
from PIL import Image, ImageChops, ImageOps

W, H, TOP, VIS, FRAMES = 69, 68, 18, 32, 16
PW, PH = VIS, W  # upright portrait canvas

def portrait(path):
    im = Image.open(path).convert("RGBA").crop((30, 0, 226, 256))
    h = round(im.height * PW / im.width)
    im = im.resize((PW, h), Image.LANCZOS)
    alpha = im.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    gray = ImageOps.autocontrast(ImageOps.grayscale(im.convert("RGB")), cutoff=1)
    lit = gray.point(lambda v: 255 if v > 185 else 0)
    return ImageChops.multiply(alpha, lit).convert("1", dither=Image.NONE)

def frames(face):
    """16-frame loop: idle snow, charge, Cryo snowflake grows, flash + ice shards, fade."""
    import math
    from PIL import ImageDraw, ImageChops
    rnd = random.Random(7)
    py0 = PH - face.height
    cx, cy = PW // 2, py0 // 2  # effect centre above her head
    snow = [(rnd.randrange(1, PW - 1), rnd.randrange(64), rnd.choice((1, 2))) for _ in range(8)]
    sparks = [rnd.random() * 2 * math.pi for _ in range(8)]
    shards = [(i * 2 * math.pi / 10 + rnd.uniform(-0.15, 0.15), rnd.uniform(0.8, 1.2)) for _ in range(1) for i in range(10)]

    def snowflake(d, r):
        for k in range(6):
            t = k * math.pi / 3 - math.pi / 2
            x2, y2 = cx + r * math.cos(t), cy + r * math.sin(t)
            d.line((cx, cy, x2, y2), fill=1)
            if r >= 6:  # side barbs
                bx, by = cx + r * 0.6 * math.cos(t), cy + r * 0.6 * math.sin(t)
                for s_ in (-1, 1):
                    tt = t + s_ * math.pi / 4
                    d.line((bx, by, bx + 3 * math.cos(tt), by + 3 * math.sin(tt)), fill=1)
        d.point((cx, cy), fill=1)

    out, upright = [], []
    for f in range(FRAMES):
        up = Image.new("1", (PW, PH), 0)
        up.paste(face, (0, py0))
        d = ImageDraw.Draw(up)
        if f <= 2 or f >= 14:  # idle snow
            for x, y0, sp in snow:
                y = (y0 + f * 4 * sp) % 64
                if y < py0:
                    d.point((x, y), fill=1)
        elif f <= 5:  # charge: sparks spiral in
            r = 14 - (f - 3) * 5
            for a0 in sparks:
                a1 = a0 + (f - 3) * 0.9
                d.point((cx + r * math.cos(a1), cy + r * math.sin(a1)), fill=1)
            d.point((cx, cy), fill=1)
        elif f <= 8:  # snowflake grows
            snowflake(d, 3 + (f - 6) * 4)
        else:  # burst: flash, then shards fly out and fade
            k = f - 9
            if k == 0:
                snowflake(d, 12)
                up = ImageChops.invert(up.convert("L")).convert("1")  # flash
                d = ImageDraw.Draw(up)
            else:
                for t, sp in shards:
                    r0 = (4 + k * 5) * sp
                    if k >= 4 and (hash((t, k)) & 1):
                        continue  # thin out while fading
                    x1, y1 = cx + r0 * math.cos(t), cy + r0 * math.sin(t)
                    x2, y2 = cx + (r0 + 4) * math.cos(t), cy + (r0 + 4) * math.sin(t)
                    d.line((x1, y1, x2, y2), fill=1)
        upright.append(up)
        img = Image.new("1", (W, H), 0)
        img.paste(up.transpose(Image.ROTATE_270), (0, TOP))
        out.append(img)
    return out, upright

def to_c(imgs):
    stride = (W + 7) // 8
    parts = ["#include <lvgl.h>\n\n#ifndef LV_ATTRIBUTE_MEM_ALIGN\n#define LV_ATTRIBUTE_MEM_ALIGN\n#endif\n"]
    for i, img in enumerate(imgs, 1):
        n = f"crystal_{i:02d}"
        data = bytearray(stride * H)
        for y in range(H):
            for x in range(W):
                if img.getpixel((x, y)):
                    data[y * stride + x // 8] |= 0x80 >> (x % 8)
        hexs = ",".join(f"0x{b:02x}" for b in data)
        parts.append(f"""
const LV_ATTRIBUTE_MEM_ALIGN LV_ATTRIBUTE_LARGE_CONST uint8_t {n}_map[] = {{
#if CONFIG_NICE_OLED_WIDGET_INVERTED
    0x00, 0x00, 0x00, 0xff, 0xff, 0xff, 0xff, 0xff,
#else
    0xff, 0xff, 0xff, 0xff, 0x00, 0x00, 0x00, 0xff,
#endif
    {hexs}
}};

const lv_img_dsc_t {n} = {{
    .header.cf = LV_IMG_CF_INDEXED_1BIT,
    .header.always_zero = 0,
    .header.reserved = 0,
    .header.w = {W},
    .header.h = {H},
    .data_size = {len(data) + 8},
    .data = {n}_map,
}};
""")
    return "".join(parts)

face = portrait(sys.argv[1])
imgs, upright = frames(face)
open(sys.argv[2], "w").write(to_c(imgs))
if len(sys.argv) > 3:
    sc = 5
    sheet = Image.new("L", ((PW + 2) * sc * 8, (PH + 2) * sc * 2), 90)
    for i, up in enumerate(upright):
        v = up.convert("L").resize((PW * sc, PH * sc), Image.NEAREST)
        sheet.paste(v, ((i % 8) * (PW + 2) * sc, (i // 8) * (PH + 2) * sc))
    sheet.save(sys.argv[3])
