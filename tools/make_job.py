"""Build a daemon job that sends the cut-out sprites to Colab, runs Hunyuan3D-2mini on each, and returns a zip of .glb files.
  python make_job.py <inputs_dir> <job_file.py> [name1,name2,...]
"""
import base64
import pathlib
import sys

inputs_dir, job_file = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
inputs = {p.stem: base64.b64encode(p.read_bytes()).decode() for p in sorted(inputs_dir.glob("*.png")) if not only or p.stem in only}

GEN = '''
import time, os, glob, gc, torch, trimesh
from PIL import Image
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
t = time.time()
pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained("tencent/Hunyuan3D-2mini", subfolder="hunyuan3d-dit-v2-mini-turbo", use_safetensors=True, device="cuda")
print("model loaded in", round(time.time() - t, 1), "s; vram", round(torch.cuda.memory_allocated() / 1e9, 2), "GB", flush=True)
os.makedirs("/content/out", exist_ok=True)
for f in sorted(glob.glob("/content/in/*.png")):
    name = os.path.basename(f)[:-4]
    try:
        t = time.time()
        mesh = pipe(image=Image.open(f).convert("RGBA"), num_inference_steps=5, octree_resolution=320, num_chunks=20000,
                    generator=torch.manual_seed(12345), output_type="trimesh")[0]
        raw = len(mesh.faces)
        try:
            mesh = mesh.simplify_quadric_decimation(face_count=30000)
        except Exception as e:
            print("  simplify skipped:", type(e).__name__, e)
        out = f"/content/out/{name}.glb"
        mesh.export(out)
        print(f"{name}: {time.time() - t:.1f}s faces {raw} -> {len(mesh.faces)} watertight={mesh.is_watertight} {os.path.getsize(out) / 1e6:.1f}MB peakVRAM={torch.cuda.max_memory_allocated() / 1e9:.1f}GB", flush=True)
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"{name}: FAILED {type(e).__name__}: {e}", flush=True)
    gc.collect(); torch.cuda.empty_cache()
'''

code = f'''
import base64, os, subprocess, zipfile
os.makedirs("/content/in", exist_ok=True)
for n, b in {inputs!r}.items():
    open(f"/content/in/{{n}}.png", "wb").write(base64.b64decode(b))
def sh(c, n=2500):
    r = subprocess.run(c, shell=True, capture_output=True, text=True); return (r.stdout + r.stderr)[-n:]
open("/content/gen.py", "w").write({GEN!r})
print(sh("cd /content && python3 gen.py 2>&1 | grep -v -i warning | tail -80", 9000), flush=True)
os.makedirs("/content/out", exist_ok=True)
with zipfile.ZipFile("/content/out.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(os.listdir("/content/out")):
        z.write("/content/out/" + f, f)
print("zip bytes", os.path.getsize("/content/out.zip"), flush=True)
print("ARTIFACT_BASE64_START")
print(base64.b64encode(open("/content/out.zip", "rb").read()).decode("ascii"))
print("ARTIFACT_BASE64_END")
'''
job_file.write_text(code)
print("job written:", job_file, "inputs:", list(inputs))
