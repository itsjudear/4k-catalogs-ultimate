"""Composite each transparent logo onto its backdrop to make the final tile.

Same scale factor and left margin for all three, so the type is physically
identical across the set and the words start at the same x on every tab.
"""
from PIL import Image

S, X, H = 0.60, 140, 720
PAIRS = [
    ("backdrop-upgraded.png",     "logo2x-upgraded.png",     "upgraded-4k-wide.png"),
    ("backdrop-justreleased.png", "logo2x-justreleased.png", "just-released-wide.png"),
    ("backdrop-movies.png",       "logo2x-movies.png",       "movies-4k-wide.png"),
]

for bd, lg, out in PAIRS:
    bg = Image.open(bd).convert("RGBA")
    l = Image.open(lg)
    l = l.resize((int(l.width * S), int(l.height * S)), Image.LANCZOS)
    bg.alpha_composite(l, (X, (H - l.height) // 2))
    bg.convert("RGB").save(out)
    print("wrote", out)
