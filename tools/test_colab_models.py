"""Test colab_models.get_model against a tiny real Hugging Face repo, with a fake 'Drive' folder and a fake disk_usage.
Cases: (1) drive big enough -> downloads into drive; (2) second call -> reuses, no download; (3) drive too small -> local disk;
(4) partial download interrupted -> resumes; (5) USE_DRIVE False -> local."""
import importlib.util, os, shutil, sys, tempfile, types
spec = importlib.util.spec_from_file_location("cm", os.path.join(os.path.dirname(os.path.abspath(__file__)), "colab_models.py")); cm = importlib.util.module_from_spec(spec); spec.loader.exec_module(cm)

root = tempfile.mkdtemp(prefix="fakecolab_")
fake_drive = os.path.join(root, "drive/MyDrive"); os.makedirs(fake_drive)
cm.DRIVE_ROOT = os.path.join(fake_drive, "colab-models"); cm.LOCAL_ROOT = os.path.join(root, "local")
cm._mount_drive = lambda: cm.USE_DRIVE
real_usage = shutil.disk_usage
def fake_usage(p):
    if str(p).startswith("/content/drive"): return types.SimpleNamespace(total=15e9, used=15e9 - FREE[0], free=FREE[0])
    return real_usage(p)
FREE = [15e9]; shutil.disk_usage = fake_usage

REPO = "hf-internal-testing/tiny-random-bert"; kw = dict(allow_patterns=["*.json", "*.txt", "*.safetensors"], ignore_patterns=None)
ok = True
def check(label, cond):
    global ok; ok &= bool(cond); print(("PASS " if cond else "FAIL ") + label)

print("--- 1. Drive has room")
d1 = cm.get_model(REPO, "tiny", **kw)
check("downloaded into the fake Drive", d1 == os.path.join(cm.DRIVE_ROOT, "tiny") and os.path.exists(os.path.join(d1, cm._MARK)) and os.path.exists(os.path.join(d1, "config.json")))
print("--- 2. second call")
import huggingface_hub
calls = []; orig = huggingface_hub.snapshot_download
huggingface_hub.snapshot_download = lambda *a, **k: calls.append(1) or orig(*a, **k)
d2 = cm.get_model(REPO, "tiny", **kw)
check("reused the saved copy", d2 == d1); check("did not call the downloader again", not calls)
print("--- 3. Drive too small")
FREE[0] = 1000  # bytes
d3 = cm.get_model(REPO, "tiny_small_drive", **kw)
check("fell back to the local disk", d3 == os.path.join(cm.LOCAL_ROOT, "tiny_small_drive") and os.path.exists(os.path.join(d3, "config.json")))
FREE[0] = 15e9
print("--- 4. interrupted download resumes")
d4 = os.path.join(cm.DRIVE_ROOT, "tiny_partial"); os.makedirs(d4)
open(os.path.join(d4, "config.json"), "w").write("{ truncated")      # a damaged file and no marker
d4b = cm.get_model(REPO, "tiny_partial", **kw)
import json
check("no marker -> downloaded again and finished", os.path.exists(os.path.join(d4b, cm._MARK)))
check("damaged file was repaired", json.load(open(os.path.join(d4b, "config.json"))))
print("--- 5. USE_DRIVE = False")
cm.USE_DRIVE = False
d5 = cm.get_model(REPO, "tiny_nodrive", **kw)
check("used the local disk", d5 == os.path.join(cm.LOCAL_ROOT, "tiny_nodrive"))
print("\nALL PASS" if ok else "\nSOME FAILED"); shutil.rmtree(root, ignore_errors=True); sys.exit(0 if ok else 1)
