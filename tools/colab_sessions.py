"""List (and optionally release) the Colab runtimes assigned to the cached mcp-colab-gpu login.
Uses the connector's own functions, so it only touches what the connector itself can touch.
  python colab_sessions.py            -> list only (read-only)
  python colab_sessions.py release    -> unassign every listed runtime
Never prints the token.
"""
import sys

from mcp_colab_gpu import colab_runtime as cr

creds = cr.get_credentials()
token = creds.token
headers = cr._colab_headers(token)
r = cr.requests.get(f"{cr.COLAB_API}/tun/m/assignments", params={"authuser": "0"}, headers=headers, timeout=30)
print("HTTP", r.status_code)
data = cr._strip_xssi(r.text) if r.ok else {"error": r.text[:300]}
assigns = data.get("assignments", []) if isinstance(data, dict) else []
print("assignments:", len(assigns))
for a in assigns:
    print({k: a.get(k) for k in ("endpoint", "accelerator", "variant", "machineShape", "idleTimeoutSec") if k in a})
if not assigns:
    print("raw keys:", list(data.keys()) if isinstance(data, dict) else type(data))
if len(sys.argv) > 1 and sys.argv[1] == "release":
    for a in assigns:
        print("release", a.get("endpoint"), "->", cr.unassign_runtime(token, a["endpoint"]))
