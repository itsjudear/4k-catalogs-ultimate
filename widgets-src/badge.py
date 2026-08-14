from PIL import Image, ImageDraw, ImageFont

BOLD = "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"

def fit_font(path, text, target_h, d):
    """Font whose CAP height is ~target_h."""
    s = int(target_h * 1.35)
    for _ in range(40):
        f = ImageFont.truetype(path, s)
        box = d.textbbox((0, 0), text, font=f)
        h = box[3] - box[1]
        if abs(h - target_h) <= 1:
            break
        s += 1 if h < target_h else -1
    return ImageFont.truetype(path, max(s, 8))

def draw_badge(im, x, y, h, fg=(255, 255, 255)):
    """White-on-dark 4K ULTRA HD badge. (x,y)=top-left. Returns width."""
    w = int(h * 1.11)
    d = ImageDraw.Draw(im)
    t = max(2, int(h * 0.055))          # frame thickness
    band_h = int(h * 0.26)              # 'ULTRA HD' band
    frame_h = h - band_h

    # outer frame around the 4K area
    d.rectangle((x, y, x + w, y + frame_h), outline=fg, width=t)

    # '4K' filling the frame
    inner_h = frame_h - 2 * t
    f4 = fit_font(BOLD, "4K", int(inner_h * 0.74), d)
    box = d.textbbox((0, 0), "4K", font=f4)
    tw, th = box[2] - box[0], box[3] - box[1]
    d.text((x + (w - tw) / 2 - box[0], y + (frame_h - th) / 2 - box[1]),
           "4K", font=f4, fill=fg)

    # solid band with knocked-out 'ULTRA HD'
    by = y + frame_h + int(h * 0.04)
    d.rectangle((x, by, x + w, by + band_h), fill=fg)
    fu = fit_font(BOLD, "ULTRA HD", int(band_h * 0.52), d)
    box = d.textbbox((0, 0), "ULTRA HD", font=fu)
    tw, th = box[2] - box[0], box[3] - box[1]
    d.text((x + (w - tw) / 2 - box[0], by + (band_h - th) / 2 - box[1]),
           "ULTRA HD", font=fu, fill=(0, 0, 0))
    return w
