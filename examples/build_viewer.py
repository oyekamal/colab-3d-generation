"""Bake the viewer: embeds each .glb, sprite and Blender render sheet as data so the page is one self-contained file.
  python build_viewer.py <examples_dir> <out.html>
"""
import base64
import io
import json
import pathlib
import sys

from PIL import Image

ex, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])

# order = how the strip reads; grade drives colour; notes are what the renders actually showed
ASSETS = [
    ("army_jeep", "Army jeep", "Good", "good",
     "Reads as a real vehicle: wheels, doors, grille, roof. The sprite shows only the side, so the front and top are the model's guess, and they hold up."),
    ("ranger", "Ranger", "Good", "good",
     "A proper 3D figure with beret, boots and backpack. The face and the front view are invented from a side-on drawing."),
    ("biryani_box", "Biryani box", "Decent", "ok",
     "The open lid and the rice are there. The surface is crumpled, because the pixel-art noise turned into bumps."),
    ("police_cone", "Police cone", "OK", "ok",
     "Right silhouette and a base ring. The base is lumpy and the sides are faceted. No orange or white bands, because the shape model has no paint."),
    ("biker", "Biker", "Weak", "weak",
     "A thick cut-out of the bike and rider, not a bike. One flat side-view gives the model no depth to work from."),
    ("teargas_can", "Tear-gas can", "Weakest", "weak",
     "Boxy instead of round, with a noisy surface. The sprite is a flat grey rectangle, so there was little to read."),
]


def data_uri(img: Image.Image, fmt: str, **kw) -> str:
    buf = io.BytesIO(); img.save(buf, fmt, **kw)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


assets = []
for id_, label, verdict, grade, note in ASSETS:
    spr = Image.open(ex / "inputs" / f"{id_}.png").convert("RGBA").resize((256, 256), Image.NEAREST)
    sheet = Image.open(ex / "renders" / f"{id_}.png").convert("RGB")
    sheet = sheet.resize((sheet.width * 2 // 3, sheet.height * 2 // 3), Image.LANCZOS)
    glb = (ex / "glb" / f"{id_}.glb").read_bytes()
    assets.append({
        "id": id_, "label": label, "verdict": verdict, "grade": grade, "note": note,
        "sprite": data_uri(spr, "PNG", optimize=True),
        "angles": data_uri(sheet, "JPEG", quality=84),
        "glb": base64.b64encode(glb).decode(),
        "stats": [["Faces", "30,000"], ["File", f"{len(glb) / 1e6:.1f} MB"], ["Format", "glTF binary (.glb)"]],
    })

html = (ex / "viewer_template.html").read_text().replace("/*ASSETS*/", json.dumps(assets))
out.write_text(html)
print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
