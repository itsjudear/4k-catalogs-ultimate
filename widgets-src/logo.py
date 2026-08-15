"""Standalone transparent title-logo lockups for Nuvio's titleLogoUrl."""
from PIL import Image, ImageDraw, ImageFont
import design as D, badge as B

FONT = "fonts/BebasNeue.ttf"

def make(lines, out, size=132, tr=2, pad=28, badge_h=58, badge_gap=26,
         chroma=True, with_badge=True):
    C = Image.new("RGBA", (1800, 900), (0, 0, 0, 0))
    d = ImageDraw.Draw(C)
    f = ImageFont.truetype(FONT, size)
    x0, y = 60, 60

    for line in lines:
        if chroma:
            # fringes drawn as translucent colour (no black plate to add onto)
            for dx, col in ((-3, (255, 40, 60, 150)), (3, (0, 220, 255, 150))):
                D.tracked(d, (x0 + dx, y), line, f, col, tr)
        D.tracked(d, (x0, y), line, f, (255, 255, 255, 255), tr)
        y += size

    if with_badge:
        B.draw_badge(C, x0, y + badge_gap, badge_h, fg=(255, 255, 255, 255))

    bb = C.getbbox()
    C = C.crop((bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad))
    C.save(out); print("wrote", out, C.size)
    return C

if __name__ == "__main__":
    make(("RECENTLY", "UPGRADED"), "logo-upgraded.png")
    make(("JUST", "RELEASED"), "logo-justreleased.png")
    make(("MOVIES",), "logo-movies.png")

    # in-situ check: logo over its own backdrop
    bg = Image.open("backdrop-upgraded.png").convert("RGBA")
    lg = Image.open("logo-upgraded.png")
    s = 620 / lg.width
    lg = lg.resize((620, int(lg.height * s)), Image.LANCZOS)
    bg.alpha_composite(lg, (140, (720 - lg.height) // 2))
    bg.convert("RGB").save("logo-insitu.png"); print("wrote logo-insitu.png")
