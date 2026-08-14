"""A-layout + the original familiar 4K ULTRA HD badge."""
import design as D, badge as B
from PIL import Image, ImageDraw

W, H = 1280, 720
L, GOLD, DIM, RULE = 150, (222, 199, 154), (150, 150, 150), (78, 78, 78)

def spectral_bar(im, x, y, h, w=5):
    stops = [(0,(255,60,80)),(0.28,(255,190,60)),(0.52,(80,240,180)),
             (0.76,(70,150,255)),(1,(190,90,255))]
    bar = Image.new("RGB", (w, h)); px = bar.load()
    for yy in range(h):
        t = yy/(h-1)
        for i in range(len(stops)-1):
            (p0,c0),(p1,c1) = stops[i], stops[i+1]
            if p0 <= t <= p1:
                k=(t-p0)/(p1-p0)
                col=tuple(int(c0[j]+(c1[j]-c0[j])*k) for j in range(3)); break
        for xx in range(w): px[xx,yy]=col
    im.paste(bar,(x,y))

def build(out, eyebrow=None, bar=False):
    im = D.grain(D.diagonal_fade(D.plate(), a=0.40, b=0.88, slope=-0.20), 7)
    d = ImageDraw.Draw(im)
    f_eye, f_dis, f_met = D.F("SpaceMono",16), D.F("Oswald",104), D.F("SpaceMono",15)

    top = 190
    if eyebrow:
        D.tracked(d,(L,top),eyebrow,f_eye,GOLD,3.4)
    d.line((L, top+40, 566, top+40), fill=RULE, width=1)

    y = top + 64
    for line in ("RECENTLY","UPGRADED"):
        D.tracked(d,(L,y),line,f_dis,(255,255,255),1); y += 96
    y += 54
    d.line((L, y, 566, y), fill=RULE, width=1)
    y += 24
    bw = B.draw_badge(im, L, y, 58)          # the original badge
    d = ImageDraw.Draw(im)
    D.tracked(d,(L+bw+22, y+20),"3840 × 2160   ·   DOLBY VISION",f_met,DIM,1.6)

    if bar:
        spectral_bar(im, 98, top, (y+58) - top)
    im.save(out); print("wrote", out)

build("final-V1-bar.png", eyebrow=None, bar=True)
build("final-V2-eyebrow.png", eyebrow="APPLE TV  ·  UNITED STATES", bar=False)
