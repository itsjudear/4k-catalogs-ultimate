"""Two designed directions for the Nuvio 'Recently Upgraded' tile."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720
SRC = "/sessions/zen-adoring-goldberg/mnt/uploads/tyson-moultrie-BQTHOGNHo08-unsplash.jpg"
F = lambda n, s: ImageFont.truetype(f"fonts/{n}.ttf", s)

def plate(shift=0.62):
    im = Image.open(SRC).convert("RGB")
    ar, (sw, sh) = W / H, Image.open(SRC).size
    nw = int(sh * ar); left = int((sw - nw) * shift)
    return im.crop((left, 0, left + nw, sh)).resize((W, H), Image.LANCZOS)

def diagonal_fade(im, a=0.30, b=0.78, slope=-0.22):
    """Reveal artwork on the right along a slightly raked edge."""
    x = np.arange(W)[None, :].repeat(H, 0)
    y = np.arange(H)[:, None].repeat(W, 1)
    u = (x + slope * (y - H / 2)) / W
    t = np.clip((u - a) / (b - a), 0, 1)
    m = t * t * (3 - 2 * t)
    return Image.composite(im, Image.new("RGB", (W, H), (0, 0, 0)),
                           Image.fromarray((m * 255).astype("uint8")))

def grain(im, amount=9, seed=7):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amount, (H, W, 1)).repeat(3, 2)
    a = np.clip(np.asarray(im).astype(np.int16) + n, 0, 255).astype("uint8")
    return Image.fromarray(a)

def tracked(d, xy, s, font, fill, tr=0):
    x, y = xy
    for ch in s:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + tr
    return x

def badge(im, x, y, h, fg=(255, 255, 255), band=True):
    d = ImageDraw.Draw(im)
    w = int(h * 1.30); t = max(2, int(h * 0.085))
    fh = int(h * 0.70) if band else h
    d.rectangle((x, y, x + w, y + fh), outline=fg, width=t)
    f4 = F("Archivo", int(fh * 0.80))
    bb = d.textbbox((0, 0), "4K", font=f4)
    d.text((x + (w - (bb[2]-bb[0]))/2 - bb[0], y + (fh - (bb[3]-bb[1]))/2 - bb[1]),
           "4K", font=f4, fill=fg)
    if band:
        by = y + fh + int(h * 0.06); bh = h - fh - int(h * 0.06)
        d.rectangle((x, by, x + w, by + bh), fill=fg)
        fu = F("Archivo", int(bh * 0.70))
        bb = d.textbbox((0, 0), "ULTRA HD", font=fu)
        d.text((x + (w - (bb[2]-bb[0]))/2 - bb[0], by + (bh - (bb[3]-bb[1]))/2 - bb[1]),
               "ULTRA HD", font=fu, fill=(0, 0, 0))
    return w

# ---------------------------------------------------------------- direction A
def archive(out):
    """'Archive Print' — condensed display, hairline rules, mono metadata."""
    im = grain(diagonal_fade(plate()), 7)
    d = ImageDraw.Draw(im)
    L, GOLD, DIM = 150, (222, 199, 154), (150, 150, 150)

    f_eye = F("SpaceMono", 17)
    f_dis = F("Oswald", 118)
    f_met = F("SpaceMono", 16)

    top = 196
    tracked(d, (L, top), "APPLE TV  ·  UNITED STATES", f_eye, GOLD, 3.4)

    d.line((L, top + 42, 560, top + 42), fill=(80, 80, 80), width=1)

    y = top + 68
    for line in ("RECENTLY", "UPGRADED"):
        tracked(d, (L, y), line, f_dis, (255, 255, 255), 1)
        y += 108

    y += 26
    d.line((L, y, 560, y), fill=(80, 80, 80), width=1)
    y += 22
    bw = badge(im, L, y, 62)
    tracked(d, (L + bw + 22, y + 20), "3840 × 2160   ·   DOLBY VISION",
            f_met, DIM, 1.6)
    im.save(out); print("wrote", out)

# ---------------------------------------------------------------- direction B
def spectrum(out):
    """'Spectrum' — tall Bebas stack, HDR gamut rule, chromatic edge."""
    im = diagonal_fade(plate(), a=0.34, b=0.80, slope=-0.16)

    # spectral hairline down the left margin = the widened HDR gamut
    bar = Image.new("RGB", (6, H))
    stops = [(0,(255,60,80)),(0.28,(255,190,60)),(0.52,(80,240,180)),
             (0.76,(70,150,255)),(1,(190,90,255))]
    px = bar.load()
    for yy in range(H):
        t = yy / (H - 1)
        for i in range(len(stops) - 1):
            (p0, c0), (p1, c1) = stops[i], stops[i + 1]
            if p0 <= t <= p1:
                k = (t - p0) / (p1 - p0)
                col = tuple(int(c0[j] + (c1[j] - c0[j]) * k) for j in range(3))
                break
        for xx in range(6):
            px[xx, yy] = col
    im.paste(bar, (96, 150))

    d = ImageDraw.Draw(im)
    L = 150
    f_eye = F("SpaceMono", 16)
    f_dis = F("BebasNeue", 132)

    tracked(d, (L, 158), "REMASTERED IN", f_eye, (170, 170, 170), 4.2)

    # chromatic split: faint red/cyan offsets behind white type
    y = 196
    for line in ("RECENTLY", "UPGRADED"):
        for dx, col in ((-3, (255, 40, 60)), (3, (0, 220, 255))):
            g = Image.new("RGB", (W, H), (0, 0, 0))
            gd = ImageDraw.Draw(g)
            tracked(gd, (L + dx, y), line, f_dis, col, 2)
            im = Image.fromarray(np.clip(
                np.asarray(im).astype(np.int16) +
                (np.asarray(g).astype(np.int16) * 0.30).astype(np.int16), 0, 255
            ).astype("uint8"))
            d = ImageDraw.Draw(im)
        tracked(d, (L, y), line, f_dis, (255, 255, 255), 2)
        y += 132

    badge(im, L, y + 16, 74, band=False)
    d = ImageDraw.Draw(im)
    d.text((L + 118, y + 46), "ULTRA HD", font=F("SpaceMono", 18), fill=(190, 190, 190))
    im = grain(im, 8, seed=3)
    im.save(out); print("wrote", out)

if __name__ == "__main__":
    archive("design-A-archive.png")
    spectrum("design-B-spectrum.png")
