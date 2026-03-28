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
  --collect-submodules src.tests \
  --collect-submodules src.ui \
  --collect-submodules src.report \
  --collect-submodules src.models \
  --collect-submodules src.utils \
  main.py

echo ""
echo "[3/3] Clearing executable stack flag (execstack fix)..."
# Modern Linux kernels reject shared libraries/binaries that request an
# executable stack (GNU_STACK ELF note). PyInstaller's bootloader and some
# bundled Qt/PySide6 .so files can have this flag set. Clearing it prevents
# the "cannot enable executable stack" error at runtime.
if command -v patchelf &>/dev/null; then
    patchelf --clear-execstack "$DIST_DIR/$BIN_NAME"
    echo "  patchelf: execstack cleared from binary."
    # Also clear from any loose .so files in the PyInstaller work dir that
    # will be embedded — belt-and-suspenders for the inner archive.
    find "build/_pyinstaller_work" -name "*.so*" -type f 2>/dev/null \
        | xargs -r patchelf --clear-execstack 2>/dev/null || true
else
    echo "  WARNING: patchelf not found — skipping execstack patch."
    echo "  Install with: sudo apt-get install patchelf"
fi

echo ""
echo "Done."
echo "Output : $DIST_DIR/$BIN_NAME"
