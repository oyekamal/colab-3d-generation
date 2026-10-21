"""Hold ONE Colab T4 runtime open and run code files dropped into a jobs folder, so fixes cost seconds, not a new
12-minute runtime grant each time.

  python colab_daemon.py <jobs_dir>
Drop <n>.py into <jobs_dir>; the result appears as <n>.out (stdout, stderr, exit code). If the code prints
ARTIFACT_BASE64_START / ARTIFACT_BASE64_END around a base64 zip, it is extracted to <jobs_dir>/<n>_artifact/.
Create <jobs_dir>/STOP to release the runtime. Idle timeout: 40 minutes.
"""
import base64
import io
import pathlib
import sys
import time
import types
import zipfile

import requests as _real_requests
from mcp_colab_gpu import colab_runtime as cr
from mcp_colab_gpu import server as srv

jobs = pathlib.Path(sys.argv[1])
jobs.mkdir(parents=True, exist_ok=True)


def _long(fn):
    def wrapped(*a, **k):
        k["timeout"] = max(k.get("timeout") or 0, 180)
        return fn(*a, **k)
    return wrapped


cr.requests = types.SimpleNamespace(**{n: getattr(_real_requests, n) for n in dir(_real_requests) if not n.startswith("__")})
cr.requests.get = _long(_real_requests.get)
cr.requests.post = _long(_real_requests.post)

token = cr.get_credentials().token
assignment = None
for attempt in range(1, 80):
    try:
        assignment = cr.allocate_runtime(token, "T4", False)
        break
    except _real_requests.HTTPError as e:
        if e.response is None or e.response.status_code != 412:
            raise
        print(f"assign refused (412), attempt {attempt}; retry in 45 s", flush=True)
        time.sleep(45)
if not assignment:
    sys.exit("never granted")

stop_keepalive = cr.start_keepalive(token, assignment["endpoint"])
try:
    kernel = cr.create_session(assignment["proxy_url"], assignment["proxy_token"])
    (jobs / "READY").write_text(assignment["endpoint"])
    print("READY", assignment["endpoint"], flush=True)
    last = time.time()
    done = set()
    while not (jobs / "STOP").exists() and time.time() - last < 2400:
        for f in sorted(jobs.glob("*.py")):
            if f.stem in done:
                continue
            done.add(f.stem)
            last = time.time()
            print("running", f.name, flush=True)
            try:
                out, err, rc = cr.execute_code(
                    assignment["proxy_url"], assignment["proxy_token"], kernel, f.read_text(),
                    timeout=2400, access_token=token, endpoint=assignment["endpoint"])
            except Exception as e:  # keep the runtime alive across a failed job
                out, err, rc = "", f"{type(e).__name__}: {e}", 1
            b64 = srv._extract_artifact_b64(out)
            shown = srv._strip_artifact_b64(out)
            (jobs / f"{f.stem}.out").write_text(f"{shown}\n--- STDERR ---\n{err[-3000:]}\n--- exit {rc} ---\n")
            if b64:
                d = jobs / f"{f.stem}_artifact"
                zipfile.ZipFile(io.BytesIO(base64.b64decode(b64))).extractall(d)
        time.sleep(2)
finally:
    stop_keepalive.set()
    cr.unassign_runtime(token, assignment["endpoint"])
    (jobs / "READY").unlink(missing_ok=True)
    print("released", flush=True)
