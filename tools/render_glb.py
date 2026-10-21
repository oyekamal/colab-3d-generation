"""Blender headless: render a clay turntable sheet (front / 3-4 / side / top) of one .glb.
Run: blender -b -P render_glb.py -- model.glb out_basename   (writes out_basename.png)
"""
import math
import sys

import bpy
from mathutils import Vector

glb, out = sys.argv[sys.argv.index("--") + 1:][:2]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]

# one clay material, flat-shaded smooth enough to read form
mat = bpy.data.materials.new("clay")
mat.use_nodes = True
bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
bsdf.inputs["Base Color"].default_value = (0.52, 0.47, 0.41, 1)
bsdf.inputs["Roughness"].default_value = 0.65
for o in meshes:
    o.data.materials.clear()
    o.data.materials.append(mat)

# centre + scale to a unit-ish box
lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
centre = (lo + hi) / 2
size = max(hi - lo)
for o in meshes:
    o.location -= centre
    o.scale *= 2.0 / size
bpy.context.view_layer.update()

scn = bpy.context.scene
scn.render.engine = "CYCLES"
scn.cycles.samples = 24
scn.cycles.device = "CPU"
scn.render.resolution_x = scn.render.resolution_y = 480
scn.render.film_transparent = False
world = bpy.data.worlds.new("w"); scn.world = world; world.use_nodes = True
scn.view_settings.view_transform = "Standard"  # Blender 5 defaults to AgX, which washes out clay
world.node_tree.nodes["Background"].inputs[0].default_value = (0.20, 0.23, 0.30, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9

sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 3.0; sun.angle = math.radians(8)
so = bpy.data.objects.new("sun", sun); scn.collection.objects.link(so)
so.rotation_euler = (math.radians(55), math.radians(10), math.radians(40))
fill = bpy.data.lights.new("fill", "SUN"); fill.energy = 1.2
fo = bpy.data.objects.new("fill", fill); scn.collection.objects.link(fo)
fo.rotation_euler = (math.radians(70), 0, math.radians(-120))
# ground plane gives contact shadow + a horizon
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -1.02))
ground = bpy.context.active_object
gm = bpy.data.materials.new("ground"); gm.use_nodes = True
next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.32, 0.34, 0.38, 1)
ground.data.materials.append(gm)

cam_d = bpy.data.cameras.new("cam"); cam_d.lens = 55
cam = bpy.data.objects.new("cam", cam_d); scn.collection.objects.link(cam); scn.camera = cam

views = {"front": (0, -4.6, 0.3), "three_quarter": (3.3, -3.3, 1.7), "side": (4.6, 0, 0.3), "top": (0.01, -2.2, 4.4)}
frames = []
for name, pos in views.items():
    cam.location = pos
    d = Vector((0, 0, 0)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scn.render.filepath = f"/tmp/_view_{name}.png"
    bpy.ops.render.render(write_still=True)
    frames.append(scn.render.filepath)

# stitch the four views into one sheet
imgs = [bpy.data.images.load(f) for f in frames]
w, h = imgs[0].size
sheet = bpy.data.images.new("sheet", w * len(imgs), h)
buf = [0.0] * (w * len(imgs) * h * 4)
for i, im in enumerate(imgs):
    px = list(im.pixels)
    for y in range(h):
        s = y * w * 4
        d = (y * w * len(imgs) + i * w) * 4
        buf[d:d + w * 4] = px[s:s + w * 4]
sheet.pixels = buf
sheet.filepath_raw = out + ".png"
sheet.file_format = "PNG"
sheet.save()
print("wrote", out + ".png")
