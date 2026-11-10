"""Builds oled/icons.c for the left OLED: flag_vn / flag_en (input method from
fcitx5 via Raw HID) and logo_k (Keychron K badge from its 180px PNG).
usage: python3 -I make_icons.py <keychron icon.png> <out icons.c> [preview.png]
"""
import math, sys
from PIL import Image, ImageDraw

FW, FH = 30, 20

def star(d, cx, cy, r_out, r_in, fill):
    pts = []
    for k in range(10):
        r = r_out if k % 2 == 0 else r_in
        a = -math.pi / 2 + k * math.pi / 5
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=fill)

def flag_vn():
    im = Image.new("1", (FW, FH), 0); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, FW - 1, FH - 1), outline=1)
    star(d, FW / 2 - 0.5, FH / 2, 8, 3.2, 1)
    return im

def flag_en():  # US flag: canton with dots, stripes
    im = Image.new("1", (FW, FH), 0); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, FW - 1, FH - 1), outline=1)
    for y in range(2, FH - 1, 2):
        d.line((1, y, FW - 2, y), fill=1)
    d.rectangle((1, 1, 13, 10), fill=0)
    d.rectangle((0, 0, 14, 11), outline=1)
    for y in range(2, 10, 2):
        for x in range(2 + (y // 2) % 2, 13, 2):
            d.point((x, y), fill=1)
    return im

def logo_k(path, size=24):
    im = Image.open(path).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    bg = Image.new("RGBA", im.size, (0, 0, 0, 255)); bg.alpha_composite(im)
    g = bg.convert("L").resize((size, size), Image.LANCZOS)
    return g.point(lambda v: 255 if v > 110 else 0).convert("1")  # white strokes -> lit, disc stays dark

def to_c(name, img):
    w, h = img.size; stride = (w + 7) // 8
    data = bytearray(stride * h)
    for y in range(h):
        for x in range(w):
            if img.getpixel((x, y)):
                data[y * stride + x // 8] |= 0x80 >> (x % 8)
    hexs = ",".join(f"0x{b:02x}" for b in data)
    return f"""
const LV_ATTRIBUTE_MEM_ALIGN LV_ATTRIBUTE_LARGE_CONST uint8_t {name}_map[] = {{
#if CONFIG_NICE_OLED_WIDGET_INVERTED
    0x00, 0x00, 0x00, 0xff, 0xff, 0xff, 0xff, 0xff,
#else
    0xff, 0xff, 0xff, 0xff, 0x00, 0x00, 0x00, 0xff,
#endif
    {hexs}
}};
const lv_img_dsc_t {name} = {{
    .header.cf = LV_IMG_CF_INDEXED_1BIT, .header.always_zero = 0, .header.reserved = 0,
    .header.w = {w}, .header.h = {h}, .data_size = {len(data) + 8}, .data = {name}_map,
}};
"""

icons = {"flag_vn": flag_vn(), "flag_en": flag_en(), "logo_k": logo_k(sys.argv[1])}
src = "#include <lvgl.h>\n#ifndef LV_ATTRIBUTE_MEM_ALIGN\n#define LV_ATTRIBUTE_MEM_ALIGN\n#endif\n"
src += "".join(to_c(n, im) for n, im in icons.items())
open(sys.argv[2], "w").write(src)
if len(sys.argv) > 3:
    sc = 10
    sheet = Image.new("L", (110 * sc, 26 * sc), 90); x = 0
    for im in icons.values():
        sheet.paste(im.convert("L").resize((im.width * sc, im.height * sc), Image.NEAREST), (x * sc, 0))
        x += im.width + 4
    sheet.save(sys.argv[3])
