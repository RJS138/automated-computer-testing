#!/usr/bin/env bash
# PC Tester — macOS Build Script
#
# Prerequisites:
#   1. Install UV:        curl -LsSf https://astral.sh/uv/install.sh | sh
#   2. Install Homebrew:  https://brew.sh
#   3. Install Pango:     brew install pango
#      (Required by WeasyPrint for PDF generation)
#
# UV handles Python and all Python dependencies automatically.
# Produces a native binary for the current architecture (x86_64 or arm64).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$REPO_ROOT/dist/macos"
ARCH="$(uname -m)"
APP_NAME="pctester_${ARCH}"

echo "=== PC Tester — macOS Build ==="
echo "Repo root : $REPO_ROOT"
echo "Arch      : $ARCH"
echo "Output    : $DIST_DIR/$APP_NAME"

# Check Pango is available (needed by WeasyPrint at build time)
if ! brew list pango &>/dev/null 2>&1; then
    echo ""
    echo "WARNING: Pango not found via Homebrew."
    echo "WeasyPrint (PDF generation) requires Pango. Install with:"
    echo "  brew install pango"
    echo ""
    echo "Continuing build — PDF generation may fail at runtime."
fi

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
  --workpath "build/_pyinstaller_work" \
  --specpath "build/_pyinstaller_spec" \
  --add-data "src/report/templates:src/report/templates" \
  --hidden-import textual \
  --hidden-import psutil \
  --hidden-import cpuinfo \
  --hidden-import pySMART \
  --hidden-import pynvml \
  --hidden-import GPUtil \
  --hidden-import jinja2 \
  --hidden-import weasyprint \
  --collect-all textual \
  main.py

echo ""
echo "[3/3] Done."
echo "Output : $DIST_DIR/$APP_NAME"
echo ""
echo "NOTE: The macOS binary is not codesigned. To run it:"
echo "  chmod +x $DIST_DIR/$APP_NAME"
echo "  xattr -d com.apple.quarantine $DIST_DIR/$APP_NAME  (if blocked by Gatekeeper)"
echo "  $DIST_DIR/$APP_NAME"
