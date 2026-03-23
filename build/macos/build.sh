#!/usr/bin/env bash
# Touchstone — macOS Build Script
#
# Prerequisites:
#   1. Install UV:  curl -LsSf https://astral.sh/uv/install.sh | sh
#
# UV handles Python and all Python dependencies automatically.
# Produces a .app bundle wrapped in a .dmg for the current architecture.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$REPO_ROOT/dist/macos"
ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then
    DMG_NAME="touchstone_macos_arm64"
else
    DMG_NAME="touchstone_macos_x86_64"
fi

echo "=== Touchstone — macOS Build ==="
echo "Repo root : $REPO_ROOT"
echo "Arch      : $ARCH"
echo "Output    : $DIST_DIR/$DMG_NAME.dmg"

cd "$REPO_ROOT"

echo ""
echo "[1/4] Syncing dependencies (uv sync --group build)..."
uv sync --group build

echo ""
echo "[2/4] Running PyInstaller..."
uv run pyinstaller \
  --windowed \
  --name "Touchstone" \
  --icon "$REPO_ROOT/assets/icon.icns" \
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
echo "[3/4] Creating DMG..."
hdiutil create \
  -volname "Touchstone" \
  -srcfolder "$DIST_DIR/Touchstone.app" \
  -ov \
  -format UDZO \
  "$DIST_DIR/$DMG_NAME.dmg"

echo ""
echo "[4/4] Done."
echo "Output : $DIST_DIR/$DMG_NAME.dmg"
echo ""
echo "NOTE: The app is not codesigned. To run after downloading:"
echo "  Right-click Touchstone.app → Open  (bypasses Gatekeeper on first launch)"
