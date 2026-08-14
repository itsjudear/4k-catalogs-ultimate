"""Spectrum text treatment applied to the three plain tiles."""
import numpy as np
import design as D, badge as B, tiles as T
from PIL import Image, ImageDraw

W, H = 1280, 720
L, RULE, RULE_W = 150, (78, 78, 78), 566
FONT = "fonts/BebasNeue.ttf"

def chroma_line(im, x, y, text, font, tr=2, strength=0.30):
    """Red/cyan offset copies composited additively, then white on top."""
    for dx, col in ((-3, (255, 40, 60)), (3, (0, 220, 255))):
        g = Image.new("RGB", (W, H), (0, 0, 0))
        gd = ImageDraw.Draw(g)
        D.tracked(gd, (x + dx, y), text, font, col, tr)
        im = Image.fromarray(np.clip(
            np.asarray(im).astype(np.int16) +
            (np.asarray(g).astype(np.int16) * strength).astype(np.int16), 0, 255
        ).astype("uint8"))
    d = ImageDraw.Draw(im)
    D.tracked(d, (x, y), text, font, (255, 255, 255), tr)
    return im

def build(src, lines, out, size=132, dy=8, **kw):
    im = D.diagonal_fade(T.plate(src, kw.get("shift", 0.62), kw.get("brighten", 1.0),
                                 kw.get("saturate", 1.0), kw.get("vshift", 0.5)),
                         kw.get("a", 0.40), kw.get("b", 0.88), kw.get("slope", -0.20))
    from PIL import ImageFont
    f = ImageFont.truetype(FONT, size)

    top = 190 - dy
    d = ImageDraw.Draw(im)
    d.line((L, top + 40, RULE_W, top + 40), fill=RULE, width=1)

    y = top + 60
    for line in lines:
        im = chroma_line(im, L, y, line, f)   # leading == font size: lines lock up
        y += size
    y += 40
    d = ImageDraw.Draw(im)
    d.line((L, y, RULE_W, y), fill=RULE, width=1)
    y += 24
    B.draw_badge(im, L, y, 58)

    im = D.grain(im, 8, seed=3)
    im.save(out); print("wrote", out)

if __name__ == "__main__":
    U = "/sessions/zen-adoring-goldberg/mnt/uploads/"
    build(U+"tyson-moultrie-BQTHOGNHo08-unsplash.jpg", ("RECENTLY", "UPGRADED"),
          "spec-upgraded.png")
    build(U+"felix-mooneeram-evlkOfkQ5rE-unsplash.jpg", ("JUST", "RELEASED"),
          "spec-justreleased.png", shift=0.72, vshift=1.0, brighten=1.34, saturate=1.14)
    build(U+"qui-nguyen-1QOAMXcpGBs-unsplash.jpg", ("MOVIES",),
          "spec-movies.png", dy=-58, vshift=0.42, brighten=1.12, saturate=1.05)
