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
if [ "$ARCH" = "x86_64" ]; then
    BIN_NAME="touchstone_linux_x86_64"
elif [ "$ARCH" = "aarch64" ]; then
    BIN_NAME="touchstone_linux_arm64"
else
    BIN_NAME="touchstone_linux_${ARCH}"
fi

echo "=== Touchstone — Linux Build ==="
echo "Repo root : $REPO_ROOT"
echo "Arch      : $ARCH"
echo "Output    : $DIST_DIR/$BIN_NAME"

cd "$REPO_ROOT"

# Install Python + all deps + PyInstaller into the project venv
echo ""
echo "[1/3] Syncing dependencies (uv sync --group build)..."
uv sync --group build

echo ""
echo "[2/3] Running PyInstaller..."
uv run pyinstaller \
  --onefile \
  --name "$BIN_NAME" \
  --icon "$REPO_ROOT/assets/icon.png" \
  --distpath "$DIST_DIR" \
  --workpath "build/_pyinstaller_work" \
  --specpath "build/_pyinstaller_spec" \
  --add-data "$REPO_ROOT/src/report/templates:src/report/templates" \
  --add-data "$REPO_ROOT/src/ui/keyboards:src/ui/keyboards" \
  --hidden-import psutil \
  --hidden-import cpuinfo \
  --hidden-import pySMART \
  --hidden-import pynvml \
  --hidden-import GPUtil \
  --hidden-import jinja2 \
  --collect-all PySide6 \
  --collect-all reportlab \
  --collect-all cv2 \
  main.py

echo ""
echo "[3/3] Done."
echo "Output : $DIST_DIR/$BIN_NAME"
