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

if [ "$ARCH" = "arm64" ]; then
    APP_NAME="PC Tester (Apple Silicon)"
else
    APP_NAME="PC Tester (Intel)"
fi

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

# Bundle smartctl — auto-install via Homebrew if not already present
SMARTCTL_PATH="$(command -v smartctl 2>/dev/null || true)"
if [ -z "$SMARTCTL_PATH" ]; then
    echo "  smartctl not found — installing via Homebrew..."
    brew install smartmontools
    SMARTCTL_PATH="$(command -v smartctl 2>/dev/null || true)"
fi

SMARTCTL_FLAG=""
if [ -n "$SMARTCTL_PATH" ]; then
    echo "  Bundling smartctl: $SMARTCTL_PATH"
    SMARTCTL_FLAG="--add-binary ${SMARTCTL_PATH}:."
else
    echo "  WARNING: smartctl unavailable — SMART data will not be bundled"
fi

# shellcheck disable=SC2086
.venv/bin/pyinstaller \
  --onefile \
  --name "$APP_NAME" \
  --distpath "dist/macos" \
  --workpath ".pyinstaller/work" \
  --add-data "src/report/templates:src/report/templates" \
  $SMARTCTL_FLAG \
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
  --collect-submodules src.tests \
  --collect-submodules src.ui \
  --collect-submodules src.report \
  --collect-submodules src.models \
  --collect-submodules src.utils \
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
