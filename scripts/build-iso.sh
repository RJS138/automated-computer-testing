#!/usr/bin/env bash
# PC Tester — Live ISO Build Script
#
# Builds a bootable Debian-based live ISO that auto-launches the PC Tester TUI.
#
# Prerequisites:
#   Docker installed and running
#
# Output:
#   dist/iso/pctester-live.iso
#
# Usage:
#   ./scripts/build-iso.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS_DIR="$REPO_ROOT/scripts"
ISO_CONFIG_DIR="$SCRIPTS_DIR/iso-config"
DIST_LINUX_DIR="$REPO_ROOT/dist/linux"
DIST_ISO_DIR="$REPO_ROOT/dist/iso"
BINARY_STAGE_PATH="$ISO_CONFIG_DIR/config/includes.chroot/usr/local/bin/pctester"

# Accept either the user-facing name or the legacy internal name
if [ -f "$DIST_LINUX_DIR/PC Tester (Linux x86_64)" ]; then
    LINUX_BINARY="$DIST_LINUX_DIR/PC Tester (Linux x86_64)"
elif [ -f "$DIST_LINUX_DIR/pctester_x86_64" ]; then
    LINUX_BINARY="$DIST_LINUX_DIR/pctester_x86_64"
else
    LINUX_BINARY=""
fi

# On Apple Silicon and other non-x86_64 hosts, force Docker to run an
# x86_64 (linux/amd64) Debian image so live-build produces a proper amd64 ISO.
HOST_ARCH="$(uname -m)"
DOCKER_PLATFORM_FLAG=""
if [ "$HOST_ARCH" != "x86_64" ] && [ "$HOST_ARCH" != "amd64" ]; then
    DOCKER_PLATFORM_FLAG="--platform=linux/amd64"
fi

echo "=== PC Tester — Live ISO Build ==="
echo "Repo root : $REPO_ROOT"
echo "Output    : $DIST_ISO_DIR/pctester-live.iso"

# --- Prerequisite check ---
if ! command -v docker &>/dev/null; then
    echo ""
    echo "ERROR: Docker not found. Install Docker Desktop and ensure it is running."
    exit 1
fi

if ! docker info &>/dev/null; then
    echo ""
    echo "ERROR: Docker daemon is not running. Start Docker Desktop and try again."
    exit 1
fi

echo ""
echo "[1/4] Checking for Linux x86_64 binary..."

if [ -z "$LINUX_BINARY" ]; then
    echo "  Binary not found — building inside Docker (debian:bookworm + UV + PyInstaller)..."
    mkdir -p "$DIST_LINUX_DIR"

    # Mount the workspace READ-ONLY to prevent Docker (running as root) from
    # ever touching the host .venv or any other host-owned files.
    # The output binary is written directly to the separately mounted $DIST_LINUX_DIR.
    docker run --rm $DOCKER_PLATFORM_FLAG \
        -v "$REPO_ROOT:/workspace:ro" \
        -v "$DIST_LINUX_DIR:/output" \
        debian:bookworm bash -c "
            set -euo pipefail
            apt-get update -qq
            apt-get install -y -qq curl ca-certificates rsync binutils smartmontools

            curl -LsSf https://astral.sh/uv/install.sh | sh
            export PATH=\"\$HOME/.local/bin:\$PATH\"

            # Copy workspace to a fully writable build dir (excludes .venv, __pycache__)
            rsync -a \
                --exclude '.venv' \
                --exclude '__pycache__' \
                --exclude '*.pyc' \
                --exclude '.pyinstaller' \
                --exclude 'dist' \
                /workspace/ /build/

            cd /build
            uv sync --group build

            .venv/bin/pyinstaller \\
                --onefile \\
                --name pctester_x86_64 \\
                --distpath /output \\
                --workpath /tmp/pyinstaller-work \\
                --add-data 'src/report/templates:src/report/templates' \\
                --add-binary \"\$(which smartctl):.\" \\
                --hidden-import textual \\
                --hidden-import psutil \\
                --hidden-import cpuinfo \\
                --hidden-import pySMART \\
                --hidden-import pynvml \\
                --hidden-import GPUtil \\
                --hidden-import jinja2 \\
                --hidden-import reportlab \\
                --collect-all textual \\
                --collect-all reportlab \\
                --collect-submodules src.tests \\
                --collect-submodules src.ui \\
                --collect-submodules src.report \\
                --collect-submodules src.models \\
                --collect-submodules src.utils \\
                main.py
        "
    # Point LINUX_BINARY at the freshly built output
    LINUX_BINARY="$DIST_LINUX_DIR/pctester_x86_64"
    echo "  Binary built: $LINUX_BINARY"
else
    echo "  Found: $LINUX_BINARY"
fi

echo ""
echo "[2/4] Staging binary into iso-config..."
mkdir -p "$(dirname "$BINARY_STAGE_PATH")"
cp "$LINUX_BINARY" "$BINARY_STAGE_PATH"
chmod +x "$BINARY_STAGE_PATH"
echo "  Staged to: $BINARY_STAGE_PATH"

echo ""
echo "[3/4] Building live ISO (Docker --privileged, debian:bookworm + live-build)..."
mkdir -p "$DIST_ISO_DIR"

    docker run --rm --privileged $DOCKER_PLATFORM_FLAG \
    -v "$REPO_ROOT:/workspace" \
    debian:bookworm bash -c "
        set -euo pipefail
        apt-get update -qq
        # Use Debian's live-build defaults; it will pull in the necessary
        # bootloader tooling as dependencies on a full Debian system.
        apt-get install -y -qq live-build

        # Work in a temp dir — live-build writes a lot of build artefacts
        mkdir -p /tmp/lb-build
        cp -r /workspace/scripts/iso-config/. /tmp/lb-build/

        cd /tmp/lb-build
        lb config
        lb build

        # Copy the resulting ISO back to the workspace
        ISO_FILE=\$(ls /tmp/lb-build/*.iso 2>/dev/null | head -n1)
        if [ -z \"\$ISO_FILE\" ]; then
            echo 'ERROR: No ISO produced by lb build.'
            exit 1
        fi
        cp \"\$ISO_FILE\" /workspace/dist/iso/pctester-live.iso
        echo \"ISO copied: \$ISO_FILE -> dist/iso/pctester-live.iso\"
    "

echo ""
echo "[4/4] Done."
echo "Output : $DIST_ISO_DIR/pctester-live.iso"
echo ""
echo "Next steps:"
echo "  • Test in VirtualBox / UTM: boot from the ISO"
echo "  • Copy ISO to Ventoy USB: cp $DIST_ISO_DIR/pctester-live.iso /Volumes/Ventoy/iso/"
echo "  • Populate full USB:       ./scripts/create-usb.sh"
