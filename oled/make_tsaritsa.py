"""Builds the right-half OLED animation: static Tsaritsa portrait with primogems falling above her.

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

GEM_BIG = ["...#...", "...#...", "..###..", "###.###", "..###..", "...#...", "...#..."]
GEM_SMALL = ["..#..", ".###.", "##.##", ".###.", "..#.."]

def frames(face):
    """16-frame loop: static portrait with primogems falling above her head."""
    py0 = PH - face.height
    # (x, start y, speed, sprite): columns spread so gems never overlap
    gems = [(1, 0, 1, GEM_BIG), (11, 40, 1, GEM_SMALL), (19, 14, 2, GEM_SMALL),
            (25, 30, 1, GEM_BIG), (6, 52, 2, GEM_SMALL), (14, 24, 1, GEM_BIG)]
    out, upright = [], []
    for f in range(FRAMES):
        up = Image.new("1", (PW, PH), 0)
        for x0, y0, speed, sprite in gems:
            y = (y0 + f * 4 * speed) % 64 - 8  # 4px*speed per frame wraps exactly in 16 frames
            for dy, row in enumerate(sprite):
                for dx, c in enumerate(row):
                    if c == "#" and 0 <= y + dy < py0:
                        up.putpixel((x0 + dx, y + dy), 1)
        up.paste(face, (0, py0))
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

if __name__ == "__main__":
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
