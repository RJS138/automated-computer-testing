#!/usr/bin/env bash
# PC Tester — Linux Build Script
#
# Prerequisites:
#   Install UV:  curl -LsSf https://astral.sh/uv/install.sh | sh
#
# UV handles Python and all Python dependencies automatically.
# Run on an x86_64 machine for the x64 binary, arm64 machine for the arm64 binary.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist/linux"
ARCH="$(uname -m)"
APP_NAME="pctester_${ARCH}"

echo "=== PC Tester — Linux Build ==="
echo "Repo root : $REPO_ROOT"
echo "Arch      : $ARCH"
echo "Output    : $DIST_DIR/$APP_NAME"

cd "$REPO_ROOT"

echo ""
echo "[1/3] Syncing dependencies (uv sync --group build)..."
uv sync --group build

echo ""
echo "[2/3] Running PyInstaller..."
uv run pyinstaller \
  --onefile \
  --name "$APP_NAME" \
  --distpath "$DIST_DIR" \
  --workpath ".pyinstaller/work" \
  --specpath ".pyinstaller/spec" \
  --add-data "src/report/templates:src/report/templates" \
  --hidden-import textual \
  --hidden-import psutil \
  --hidden-import cpuinfo \
  --hidden-import pySMART \
  --hidden-import pynvml \
  --hidden-import GPUtil \
  --hidden-import jinja2 \
  --hidden-import reportlab \
  --collect-all textual \
  --collect-all reportlab \
  main.py

echo ""
echo "[3/3] Done."
echo "Output : $DIST_DIR/$APP_NAME"
echo "Copy to USB drive at: linux/$APP_NAME"
