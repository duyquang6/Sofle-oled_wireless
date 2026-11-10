"""Right-half OLED animation from a GIF: 16 frames of edge lines, drop-in for crystal.c.

Takes GIF frames 31..62 (the wide shot where the face is visible), finds edges on the
full frame, crops a portrait strip over the face, and rotates it for the portrait OLED.
usage: python3 -I make_gif_frames.py <in.gif> <out crystal.c> [preview.png]
"""
import sys
from PIL import Image, ImageFilter, ImageOps
sys.path.insert(0, __import__("os").path.dirname(__file__))
from make_tsaritsa import W, H, TOP, PW, PH, to_c

THRESH, BLUR = 100, 1.0
CROP_X0, CROP_W = 125, 230

def frames(path):
    im = Image.open(path)
    picks = [31 + round(i * 31 / 16) for i in range(16)]
    out, upright = [], []
    for i in picks:
        im.seek(i)
        g = ImageOps.grayscale(im.convert("RGB")).filter(ImageFilter.GaussianBlur(BLUR))
        e = g.filter(ImageFilter.FIND_EDGES).crop((CROP_X0, 4, CROP_X0 + CROP_W, 4 + CROP_W * PH // PW))
        e = ImageOps.autocontrast(e.resize((PW, PH), Image.LANCZOS), cutoff=1)
        up = e.point(lambda v: 255 if v > THRESH else 0).convert("1", dither=Image.NONE)
        for x in range(PW):  # FIND_EDGES leaves a bright last row
            up.putpixel((x, PH - 1), 0)
        upright.append(up)
        img = Image.new("1", (W, H), 0)
        img.paste(up.transpose(Image.ROTATE_270), (0, TOP))
        out.append(img)
    return out, upright

imgs, upright = frames(sys.argv[1])
open(sys.argv[2], "w").write(to_c(imgs))
if len(sys.argv) > 3:
    sc = 5
    sheet = Image.new("L", ((PW + 2) * sc * 8, (PH + 2) * sc * 2), 90)
    for i, up in enumerate(upright):
        sheet.paste(up.convert("L").resize((PW * sc, PH * sc), Image.NEAREST), ((i % 8) * (PW + 2) * sc, (i // 8) * (PH + 2) * sc))
    sheet.save(sys.argv[3])
