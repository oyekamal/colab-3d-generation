"""Turn Islamabad Runner sprites (checkerboard painted into opaque pixels) into clean RGBA cut-outs
that image-to-3D models can use. Flood-fills the checkerboard from the image border; dark outlines stop it."""
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

# name -> (file, crop box (x0, y0, x1, y1) or None)
JOBS = {
    "police_cone": ("police_cone.png", None),
    "biryani_box": ("biryani_box.png", None),
    "army_jeep": ("army_jeep.png", None),
    "biker": ("bike_ride.png", (60, 40, 560, 440), (8, 135)),      # first of three frames, darker checker
    "ranger": ("ranger_walk.png", (140, 30, 620, 700)),  # first of the two frames
    "teargas_can": ("teargas_can.png", (285, 380, 540, 900)),  # can only; gas cloud painted out below
}
# regions (in cropped coordinates) painted white before cutting, e.g. a gas cloud that is not part of the object
ERASE = {"teargas_can": (163, 0, 255, 115)}


def cut_background(im: Image.Image, max_sat: int = 28, min_bright: int = 150) -> Image.Image:
    a = np.array(im.convert("RGB")).astype(int)
    h, w, _ = a.shape
    sat = a.max(axis=2) - a.min(axis=2)
    bright = a.max(axis=2)
    bg_like = (sat < max_sat) & (bright > min_bright)  # grey / white checker squares
    seen = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if bg_like[y, x]:
                q.append((y, x)); seen[y, x] = True
    for y in range(h):
        for x in (0, w - 1):
            if bg_like[y, x] and not seen[y, x]:
                q.append((y, x)); seen[y, x] = True
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and bg_like[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    alpha = np.where(seen, 0, 255).astype(np.uint8)
    out = Image.fromarray(np.dstack([a.astype(np.uint8), alpha]), "RGBA")
    return out


for name, (fn, box, *tol) in JOBS.items():
    im = Image.open(SRC / fn).convert("RGB")
    if box:
        im = im.crop(box)
    if name in ERASE:
        im.paste((255, 255, 255), ERASE[name])
    rgba = cut_background(im, *(tol[0] if tol else ()))
    bbox = rgba.getchannel("A").getbbox()
    rgba = rgba.crop(bbox)
    side = int(max(rgba.size) * 1.16)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(rgba, ((side - rgba.width) // 2, (side - rgba.height) // 2), rgba)
    canvas = canvas.resize((512, 512), Image.LANCZOS)
    canvas.save(OUT / f"{name}.png")
    kept = np.array(canvas.getchannel("A")).mean() / 255
    print(f"{name}: bbox {bbox}, opaque share {kept:.0%}")
