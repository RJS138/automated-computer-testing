#!/usr/bin/env bash
# PC Tester — macOS Build Script
#
# Prerequisites:
#   Install UV:        curl -LsSf https://astral.sh/uv/install.sh | sh
#   Install Homebrew:  https://brew.sh
#
# UV handles Python and all Python dependencies automatically.
# PDF generation uses ReportLab (pure Python — no system libraries needed).
# Produces a native binary for the current architecture (x86_64 or arm64).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist/macos"
ARCH="$(uname -m)"
APP_NAME="pctester_${ARCH}"

echo "=== PC Tester — macOS Build ==="
echo "Repo root : $REPO_ROOT"
echo "Arch      : $ARCH"
echo "Output    : $DIST_DIR/$APP_NAME"

# Build in a temporary workspace to avoid touching any existing .venv or
# PyInstaller artefacts in the repo (which may have different permissions).
BUILD_ROOT="$(mktemp -d /tmp/pctester-macos-XXXXXX)"
echo ""
echo "Using temporary build directory: $BUILD_ROOT"

echo ""
echo "[1/3] Syncing dependencies (uv sync --group build)..."
rsync -a --delete --exclude ".venv" "$REPO_ROOT"/ "$BUILD_ROOT"/
cd "$BUILD_ROOT"

uv sync --group build

echo ""
echo "[2/3] Running PyInstaller..."
rm -rf .pyinstaller
uv run pyinstaller \
  --onefile \
  --name "$APP_NAME" \
  --distpath "dist/macos" \
  --workpath ".pyinstaller/work" \
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

mkdir -p "$DIST_DIR"
cp "dist/macos/$APP_NAME" "$DIST_DIR/$APP_NAME"

echo ""
echo "[3/3] Done."
echo "Output : $DIST_DIR/$APP_NAME"
echo ""
echo "NOTE: The macOS binary is not codesigned. To run it on another Mac:"
echo "  chmod +x $DIST_DIR/$APP_NAME"
echo "  xattr -d com.apple.quarantine $DIST_DIR/$APP_NAME  # if blocked by Gatekeeper"
echo "  $DIST_DIR/$APP_NAME"
