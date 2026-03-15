#!/usr/bin/env bash
# PC Tester — macOS Build Script
#
# Prerequisites:
#   1. Install UV:  curl -LsSf https://astral.sh/uv/install.sh | sh
#
# Optional (for tkinter display/keyboard helpers in frozen binary):
#   2. Install Tcl/Tk:  brew install tcl-tk
#      Without this, tkinter windows fall back to terminal mode.
#
# UV handles Python and all Python dependencies automatically.
# Produces a native binary for the current architecture (x86_64 or arm64).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$REPO_ROOT/dist/macos"
ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then
    APP_NAME="Touchstone (Apple Silicon)"
else
    APP_NAME="Touchstone (Intel)"
fi

echo "=== Touchstone — macOS Build ==="
echo "Repo root : $REPO_ROOT"
echo "Arch      : $ARCH"
echo "Output    : $DIST_DIR/$APP_NAME"

cd "$REPO_ROOT"

echo ""
echo "[1/4] Syncing dependencies (uv sync --group build)..."
uv sync --group build

echo ""
echo "[2/4] Generating icons..."
uv run python scripts/generate_icon.py

echo ""
echo "[3/4] Running PyInstaller..."
uv run pyinstaller \
  --onefile \
  --name "$APP_NAME" \
  --icon "$REPO_ROOT/assets/icon.icns" \
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
echo "[4/4] Done."
echo "Output : $DIST_DIR/$APP_NAME"
echo ""
echo "NOTE: The macOS binary is not codesigned. To run it:"
echo "  chmod +x $DIST_DIR/$APP_NAME"
echo "  xattr -d com.apple.quarantine $DIST_DIR/$APP_NAME  (if blocked by Gatekeeper)"
echo "  $DIST_DIR/$APP_NAME"
