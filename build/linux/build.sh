#!/usr/bin/env bash
# PC Tester — Linux Build Script
#
# Prerequisites:
#   Install UV:  curl -LsSf https://astral.sh/uv/install.sh | sh
#
# UV will:
#   - Download and pin the correct Python version (.python-version)
#   - Create a .venv and install all dependencies + PyInstaller
#   - Build a single self-contained binary
#
# Run on an x86_64 machine for x64 binary, arm64 machine for arm64 binary.
# For maximum glibc compatibility build on the oldest supported distro.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$REPO_ROOT/dist/linux"
ARCH="$(uname -m)"
APP_NAME="touchstone_${ARCH}"

echo "=== Touchstone — Linux Build ==="
echo "Repo root : $REPO_ROOT"
echo "Arch      : $ARCH"
echo "Output    : $DIST_DIR/$APP_NAME"

cd "$REPO_ROOT"

# Install Python + all deps + PyInstaller into the project venv
echo ""
echo "[1/3] Syncing dependencies (uv sync --group build)..."
uv sync --group build

echo ""
echo "[2/3] Running PyInstaller..."
uv run pyinstaller \
  --onefile \
  --name "$APP_NAME" \
  --distpath "$DIST_DIR" \
  --workpath "build/_pyinstaller_work" \
  --specpath "build/_pyinstaller_spec" \
  --add-data "$REPO_ROOT/src/report/templates:src/report/templates" \
  --add-data "$REPO_ROOT/src/ui/keyboards:src/ui/keyboards" \
  --hidden-import textual \
  --hidden-import psutil \
  --hidden-import cpuinfo \
  --hidden-import pySMART \
  --hidden-import pynvml \
  --hidden-import GPUtil \
  --hidden-import jinja2 \
  --hidden-import tkinter \
  --hidden-import PIL \
  --collect-all textual \
  --collect-all reportlab \
  --collect-all cv2 \
  --collect-all PIL \
  main.py

echo ""
echo "[3/3] Done."
echo "Output : $DIST_DIR/$APP_NAME"
