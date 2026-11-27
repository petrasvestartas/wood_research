"""setup_harness.py <repo copy> <runner binary>: add the session_cpp kernel to a copy of brep-bench's kernels.json.

The copy is ours to change (never the clone itself); no `source` pattern, so every case is asked of the runner,
which builds it, refuses it with a reason, or (an id it does not know) exits non-zero."""
import json
import os
import sys

repo, binary = sys.argv[1], os.path.abspath(sys.argv[2])
path = os.path.join(repo, "kernels.json")
with open(path) as f:
    data = json.load(f)
data["kernels"] = [k for k in data["kernels"] if k["name"] != "session_cpp"]
data["kernels"].append({
    "name": "session_cpp",
    "kernel": "https://github.com/petrasvestartas/session",
    "license": "MIT",
    "backend": "C++",
    "frontend": "C++",
    "build": ["true"],
    "command": [binary],
    "version": [binary, "--version"],
    "step": True,
    "binary": [binary],
})
with open(path, "w") as f:
    json.dump(data, f, indent=2)
print("session_cpp added to", path)
