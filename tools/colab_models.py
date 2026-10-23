"""Model cache for Colab: reuse a model saved in Google Drive, download it if it is missing, fall back to the local disk if Drive is too small.

Paste this cell near the top of a notebook. Then:

    MODEL_DIR = get_model("black-forest-labs/FLUX.2-klein-4B", "flux2-klein-4b",
                          allow_patterns=[...], ignore_patterns=[...])

What it does, in order:
  1. Mounts Google Drive (skipped if USE_DRIVE = False or the mount is refused) and uses  MyDrive/colab-models/<name>.
  2. If that folder already holds a COMPLETE copy (a marker file written after a finished download), it is used as it is: no download.
  3. Otherwise it asks Hugging Face how big the download is and compares that with the free space in Drive:
       - it fits (with 5% spare): download straight into Drive, so the next session skips the download;
       - it does not fit: download to Colab's local disk (/content/models/<name>) and say so. Free Drive is only 15 GB in total.
  4. A download that was cut off is resumed, not restarted (huggingface_hub keeps partial files).
Nothing is deleted. Returns the folder to pass to from_pretrained().
"""
import os, shutil, json, time

USE_DRIVE = True                                     # set False to always use the local disk
DRIVE_ROOT = "/content/drive/MyDrive/colab-models"   # where models are kept in your Drive
LOCAL_ROOT = "/content/models"                       # used when Drive is off or too small
_MARK = ".download_complete.json"


def _mount_drive():
    if not USE_DRIVE:
        return False
    if os.path.isdir("/content/drive/MyDrive"):
        return True
    try:
        from google.colab import drive
        drive.mount("/content/drive")
        return os.path.isdir("/content/drive/MyDrive")
    except Exception as e:                           # not in Colab, or the user said no
        print("Google Drive not available (" + type(e).__name__ + "): using the local disk")
        return False


def _remote_size(repo, allow_patterns, ignore_patterns):
    from huggingface_hub import HfApi
    import fnmatch
    total = 0
    for f in HfApi().list_repo_tree(repo, recursive=True):
        size = getattr(f, "size", None)
        if size is None:
            continue
        p = f.path
        if allow_patterns and not any(fnmatch.fnmatch(p, a) for a in allow_patterns):
            continue
        if ignore_patterns and any(fnmatch.fnmatch(p, i) for i in ignore_patterns):
            continue
        total += size
    return total


def get_model(repo, name, allow_patterns=None, ignore_patterns=None, revision=None):
    """Return a local folder holding `repo`, using Drive as a cache when it can."""
    from huggingface_hub import snapshot_download
    ignore_patterns = list(ignore_patterns or []) + [_MARK]
    drive_ok = _mount_drive()
    drive_dir = os.path.join(DRIVE_ROOT, name)
    local_dir = os.path.join(LOCAL_ROOT, name)

    for d, where in ((drive_dir, "Google Drive"), (local_dir, "this session's disk")):
        if os.path.exists(os.path.join(d, _MARK)):
            print(f"Using the saved copy in {where}: {d}  (no download)")
            return d

    need = _remote_size(repo, allow_patterns, ignore_patterns)
    print(f"{repo}: about {need / 1e9:.1f} GB to download")
    target = local_dir
    if drive_ok:
        os.makedirs(DRIVE_ROOT, exist_ok=True)
        used_by_us = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(drive_dir) for f in fs) if os.path.isdir(drive_dir) else 0
        free = shutil.disk_usage("/content/drive/MyDrive").free + used_by_us
        if need * 1.05 < free:
            target = drive_dir
            print(f"It fits in Google Drive ({free / 1e9:.1f} GB free): saving to {drive_dir} so the next session skips the download.")
        else:
            print(f"It does NOT fit in Google Drive ({free / 1e9:.1f} GB free, free accounts get 15 GB): using this session's disk, "
                  "so the next session downloads it again. Free up Drive space or use Google One to keep it.")
    os.makedirs(target, exist_ok=True)
    t = time.time()
    snapshot_download(repo, local_dir=target, allow_patterns=allow_patterns, ignore_patterns=ignore_patterns, revision=revision)
    json.dump({"repo": repo, "revision": revision, "bytes": need, "seconds": round(time.time() - t)}, open(os.path.join(target, _MARK), "w"))
    print(f"Done in {time.time() - t:.0f}s: {target}")
    return target
