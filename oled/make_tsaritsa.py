"""Builds the right-half OLED animation: Tsaritsa portrait with falling snow.

Writes a drop-in replacement for zmk-nice-oled's assets/crystal.c (16 frames,
69x68, 1-bit; only rows 18..49 are visible on the 128x32 Sofle OLED).
usage: python3 -I make_tsaritsa.py <Anastasya_Icon.png> <out crystal.c> [preview.png]
"""
import random, sys
from PIL import Image, ImageChops, ImageOps

W, H, TOP, VIS, FRAMES = 69, 68, 18, 32, 16

def portrait(path):
    im = Image.open(path).convert("RGBA").crop((40, 0, 216, 190))
    w = round(im.width * VIS / im.height)
    im = im.resize((w, VIS), Image.LANCZOS)
    alpha = im.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    gray = ImageOps.autocontrast(ImageOps.grayscale(im.convert("RGB")), cutoff=1)
    lit = gray.point(lambda v: 255 if v > 185 else 0)
    return ImageChops.multiply(alpha, lit).convert("1", dither=Image.NONE)

def frames(face):
    rnd = random.Random(7)
    px0 = (W - face.width) // 2
    free = [x for x in range(1, W - 2) if x < px0 - 2 or x > px0 + face.width + 1]
    flakes = [(rnd.choice(free), rnd.randrange(VIS), rnd.choice((1, 1, 2)), rnd.random() < 0.3)
              for _ in range(12)]
    out = []
    for f in range(FRAMES):
        img = Image.new("1", (W, H), 0)
        img.paste(face, (px0, TOP))
        for x, y0, speed, big in flakes:
            y = TOP + (y0 + f * 2 * speed) % VIS  # 2px*speed per frame wraps exactly in 16 frames
            pts = [(x, y)] + ([(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)] if big else [])
            for p in pts:
                if 0 <= p[0] < W and TOP <= p[1] < TOP + VIS:
                    img.putpixel(p, 1)
        out.append(img)
    return out

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
imgs = frames(face)
open(sys.argv[2], "w").write(to_c(imgs))
if len(sys.argv) > 3:
    sc = 5
    sheet = Image.new("L", ((W + 2) * sc * 4, (VIS + 2) * sc * 4), 90)
    for i, img in enumerate(imgs):
        v = img.crop((0, TOP, W, TOP + VIS)).convert("L").resize((W * sc, VIS * sc), Image.NEAREST)
        sheet.paste(v, ((i % 4) * (W + 2) * sc, (i // 4) * (VIS + 2) * sc))
    sheet.save(sys.argv[3])
