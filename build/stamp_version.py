"""
Stamp src/_version.py with the current release version.

Resolution order:
  1. GITHUB_REF matches refs/tags/v<semver>  → use the tag (normal release)
  2. INPUT_VERSION env var is set             → use it (manual workflow_dispatch)
  3. pyproject.toml version field             → use it (dev / branch build)

Called by CI as: python3 build/stamp_version.py
"""
import os
import re

ref = os.environ.get("GITHUB_REF", "")
inp = os.environ.get("INPUT_VERSION", "").strip().lstrip("v")

if re.match(r"^refs/tags/v[0-9]+\.[0-9]+\.[0-9]", ref):
    v = ref[len("refs/tags/v"):]
elif inp and re.match(r"^[0-9]+\.[0-9]+\.[0-9]", inp):
    v = inp
else:
    content = open("pyproject.toml").read()
    m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.M)
    v = m.group(1) if m else "dev"

print(f"Stamping version: {v}", flush=True)
with open("src/_version.py", "w") as f:
    f.write(f'__version__ = "{v}"\n')
