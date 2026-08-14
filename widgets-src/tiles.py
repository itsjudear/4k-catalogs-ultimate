"""Nuvio collection tiles — shared 'Archive Print' layout."""
import numpy as np
import design as D, badge as B
from PIL import Image, ImageDraw, ImageEnhance
from final import spectral_bar

W, H = 1280, 720
L, RULE, RULE_W = 150, (78, 78, 78), 566
DY = 8

def plate(src, shift=0.62, brighten=1.0, saturate=1.0, vshift=0.5):
    im = Image.open(src).convert("RGB")
    sw, sh = im.size; ar = W / H
    if sw / sh > ar:
        nw = int(sh * ar); left = int((sw - nw) * shift)
        im = im.crop((left, 0, left + nw, sh))
    else:
        nh = int(sw / ar); topy = int((sh - nh) * vshift)
        im = im.crop((0, topy, sw, topy + nh))
    im = im.resize((W, H), Image.LANCZOS)
    if brighten != 1.0: im = ImageEnhance.Brightness(im).enhance(brighten)
    if saturate != 1.0: im = ImageEnhance.Color(im).enhance(saturate)
    return im

def build(src, lines, out, bar=True, dy=DY, shift=0.62, vshift=0.5,
          brighten=1.0, saturate=1.0, a=0.40, b=0.88, slope=-0.20):
    im = D.grain(D.diagonal_fade(plate(src, shift, brighten, saturate, vshift), a, b, slope), 7)
    d = ImageDraw.Draw(im)
    f = D.F("Oswald", 104)
    top = 190 - dy
    d.line((L, top + 40, RULE_W, top + 40), fill=RULE, width=1)
    y = top + 64
    for line in lines:
        D.tracked(d, (L, y), line, f, (255, 255, 255), 1); y += 96
    y += 54
    d.line((L, y, RULE_W, y), fill=RULE, width=1)
    y += 24
    B.draw_badge(im, L, y, 58)
    if bar: spectral_bar(im, 98, top, (y + 58) - top)
    im.save(out); print("wrote", out)

if __name__ == "__main__":
    CINEMA = "/sessions/zen-adoring-goldberg/mnt/uploads/felix-mooneeram-evlkOfkQ5rE-unsplash.jpg"
    # the cinema shot is very dark and its subject is centred, so lift it and
    # bias the crop right so the seats land in the exposed part of the frame
    for name, bar in (("bar", True), ("plain", False)):
        build(CINEMA, ("JUST", "RELEASED"), f"justreleased-{name}.png",
              bar=bar, shift=0.72, vshift=1.0, brighten=1.34, saturate=1.14)
