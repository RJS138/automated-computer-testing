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

case "$ARCH" in
    x86_64|amd64) APP_NAME="PC Tester (Linux x86_64)" ;;
    aarch64|arm64) APP_NAME="PC Tester (Linux ARM64)" ;;
    *) APP_NAME="PC Tester (Linux ${ARCH})" ;;
esac

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

# Bundle smartctl if available (provides SMART disk data without requiring smartmontools on target)
SMARTCTL_FLAG=""
SMARTCTL_PATH="$(command -v smartctl 2>/dev/null || true)"
if [ -n "$SMARTCTL_PATH" ]; then
    echo "  Bundling smartctl: $SMARTCTL_PATH"
    SMARTCTL_FLAG="--add-binary ${SMARTCTL_PATH}:."
else
    echo "  smartctl not found — SMART data unavailable without smartmontools on target"
    echo "  Install with: sudo apt-get install smartmontools  (or equivalent)"
fi

# shellcheck disable=SC2086
.venv/bin/pyinstaller \
  --onefile \
  --name "$APP_NAME" \
  --distpath "$DIST_DIR" \
  --workpath ".pyinstaller/work" \
  --specpath ".pyinstaller/spec" \
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

echo ""
echo "[3/3] Done."
echo "Output : $DIST_DIR/$APP_NAME"
echo "Copy to USB drive at: linux/$APP_NAME"
