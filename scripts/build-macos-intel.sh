#!/usr/bin/env bash
# PC Tester — macOS Intel Build Script
#
# Builds an x86_64 (Intel) binary for macOS.
#
#   On Intel Macs:      builds natively using the system UV.
#   On Apple Silicon:   downloads the x86_64 UV binary directly from GitHub
#                       (the UV installer always installs arm64 on Apple
#                       Silicon hardware regardless of arch -x86_64), then
#                       uses it to download x86_64 Python and build.
#
# Prerequisites:
#   Install UV:  curl -LsSf https://astral.sh/uv/install.sh | sh
#
# Usage:
#   ./scripts/build-macos-intel.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist/macos"
APP_NAME="PC Tester (Intel)"
HOST_ARCH="$(uname -m)"

echo "=== PC Tester — macOS Intel Build ==="
echo "Repo root : $REPO_ROOT"
echo "Host arch : $HOST_ARCH"
echo "Target    : x86_64 (Intel)"
echo "Output    : $DIST_DIR/$APP_NAME"

# ---------------------------------------------------------------------------
# Determine which UV binary to use
# ---------------------------------------------------------------------------

if [ "$HOST_ARCH" = "arm64" ]; then
    # The UV *installer* (astral.sh/uv/install.sh) checks hw.optional.arm64 at
    # the OS level and always installs the arm64 binary regardless of
    # `arch -x86_64`. Instead, directly download the x86_64 UV release tarball
    # from GitHub using the same version as the currently installed arm64 UV.

    if ! command -v uv &>/dev/null; then
        echo ""
        echo "ERROR: UV is not installed. Install it first:"
        echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi

    UV_VERSION="$(uv --version | awk '{print $2}')"
    echo ""
    echo "Apple Silicon detected — downloading x86_64 UV ${UV_VERSION} directly..."

    X86_HOME="$(mktemp -d /tmp/uv-intel-XXXXXX)"
    curl -fsSL \
        "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-apple-darwin.tar.gz" \
        | tar xz -C "$X86_HOME" --strip-components=1
    UV_BIN="$X86_HOME/uv"

    # Verify the downloaded binary is genuinely x86_64
    UV_ARCH="$(file "$UV_BIN")"
    echo "  UV binary: $UV_ARCH"
    if ! echo "$UV_ARCH" | grep -q "x86_64"; then
        echo ""
        echo "ERROR: Downloaded UV binary is not x86_64 (got: $UV_ARCH)."
        exit 1
    fi

    # Redirect both the package cache AND the Python install directory so the
    # x86_64 UV never picks up the arm64 Python cached under $HOME.
    export UV_CACHE_DIR="$X86_HOME/.uv-cache"
    export UV_PYTHON_INSTALL_DIR="$X86_HOME/.uv-python"

    echo "  UV_PYTHON_INSTALL_DIR : $UV_PYTHON_INSTALL_DIR"

    # Unset any active venv NOW — before any uv command — so UV doesn't try to
    # inspect the original arm64 .venv when looking up the Python interpreter.
    unset VIRTUAL_ENV VIRTUAL_ENV_PROMPT CONDA_DEFAULT_ENV 2>/dev/null || true

    # Explicitly install x86_64 Python into the isolated directory before sync.
    # Without this, UV falls back to any Python on PATH (arm64 on Apple Silicon).
    # We also pass --force so the python3.11 shim in ~/.local/bin doesn't block
    # the install if an arm64 shim already exists there.
    echo "  Installing x86_64 Python (managed)..."
    "$UV_BIN" python install --python-preference only-managed --force
else
    echo ""
    echo "Intel Mac detected — using system UV."
    UV_BIN="uv"
fi

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

BUILD_ROOT="$(mktemp -d /tmp/pctester-intel-XXXXXX)"
echo ""
echo "Using temporary build directory: $BUILD_ROOT"

echo ""
echo "[1/3] Syncing dependencies..."
rsync -a --delete --exclude ".venv" "$REPO_ROOT"/ "$BUILD_ROOT"/
cd "$BUILD_ROOT"

"$UV_BIN" sync --group build --python-preference only-managed

echo ""
echo "[2/3] Running PyInstaller (x86_64)..."
rm -rf .pyinstaller

# Bundle x86_64 smartctl — we always need an x86_64 Mach-O binary regardless of host arch.
# Strategy:
#   1. Check /usr/local/bin/smartctl (Intel Homebrew path, works on Intel Macs natively)
#   2. Download the x86_64 Homebrew bottle and extract smartctl from it
SMARTCTL_X86=""

if [ -f "/usr/local/bin/smartctl" ] && file "/usr/local/bin/smartctl" | grep -q "x86_64"; then
    SMARTCTL_X86="/usr/local/bin/smartctl"
    echo "  Found x86_64 smartctl at /usr/local/bin/smartctl"
fi

if [ -z "$SMARTCTL_X86" ]; then
    echo "  Fetching x86_64 smartmontools Homebrew bottle..."
    BOTTLE_TMP="$(mktemp -d /tmp/smartctl-bottle-XXXXXX)"
    # Try recent macOS Intel bottle tags (newest first; arm64_ prefix = Apple Silicon, skip those)
    for TAG in sequoia sonoma ventura monterey; do
        if HOMEBREW_CACHE="$BOTTLE_TMP" brew fetch --force --bottle-tag="$TAG" smartmontools \
                >/dev/null 2>&1; then
            BOTTLE_TAR="$(find "$BOTTLE_TMP/downloads" -name "*.tar.gz" | head -n1)"
            if [ -n "$BOTTLE_TAR" ]; then
                tar xzf "$BOTTLE_TAR" -C "$BOTTLE_TMP" 2>/dev/null || true
                SC="$(find "$BOTTLE_TMP" -path "*/bin/smartctl" -type f | head -n1)"
                if [ -n "$SC" ] && file "$SC" | grep -q "x86_64"; then
                    chmod +x "$SC"
                    SMARTCTL_X86="$SC"
                    echo "  Extracted x86_64 smartctl from $TAG bottle: $(file "$SC")"
                    break
                fi
            fi
        fi
    done
fi

SMARTCTL_FLAG=""
if [ -n "$SMARTCTL_X86" ]; then
    SMARTCTL_FLAG="--add-binary ${SMARTCTL_X86}:."
else
    echo "  WARNING: Could not obtain x86_64 smartctl — SMART data will not be bundled"
fi

# Call pyinstaller directly from the venv uv sync just built.
# `uv run pyinstaller` would re-evaluate groups and recreate the venv without
# the build group (default-groups = [] in pyproject.toml), losing pyinstaller.
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

# Confirm output binary architecture
OUTPUT_ARCH="$(file "$DIST_DIR/$APP_NAME")"
echo ""
echo "Output binary: $OUTPUT_ARCH"
if ! echo "$OUTPUT_ARCH" | grep -q "x86_64"; then
    echo ""
    echo "WARNING: Output binary is not x86_64 — it may not run on Intel Macs."
fi

echo ""
echo "[3/3] Done."
echo "Output : $DIST_DIR/$APP_NAME"
echo ""
echo "NOTE: The binary is not codesigned. To run it on another Mac:"
echo "  chmod +x \"$DIST_DIR/$APP_NAME\""
echo "  xattr -d com.apple.quarantine \"$DIST_DIR/$APP_NAME\"  # if blocked by Gatekeeper"
echo "  \"$DIST_DIR/$APP_NAME\""
