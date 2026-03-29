#!/usr/bin/env bash
# Touchstone — Live ISO Build Script
#
# Builds a bootable Debian-based live ISO that auto-launches Touchstone via X11.
#
# Prerequisites:
#   Docker installed and running
#
# Output:
#   dist/iso/touchstone-live.iso
#
# Usage:
#   ./scripts/build-iso.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS_DIR="$REPO_ROOT/scripts"
ISO_CONFIG_DIR="$SCRIPTS_DIR/iso-config"
DIST_LINUX_DIR="$REPO_ROOT/dist/linux"
DIST_ISO_DIR="$REPO_ROOT/dist/iso"
BINARY_SRC="$DIST_LINUX_DIR/touchstone_linux_x86_64"
BINARY_STAGE="$ISO_CONFIG_DIR/config/includes.chroot/usr/local/bin/touchstone"

# On Apple Silicon and other non-x86_64 hosts, force Docker to run an
# x86_64 (linux/amd64) image so live-build produces a proper amd64 ISO.
HOST_ARCH="$(uname -m)"
DOCKER_PLATFORM_FLAG=""
if [ "$HOST_ARCH" != "x86_64" ] && [ "$HOST_ARCH" != "amd64" ]; then
    DOCKER_PLATFORM_FLAG="--platform=linux/amd64"
fi

echo "=== Touchstone — Live ISO Build ==="
echo "Repo root : $REPO_ROOT"
echo "Output    : $DIST_ISO_DIR/touchstone-live.iso"

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

if [ -f "$BINARY_SRC" ]; then
    echo "  Found pre-built binary: $BINARY_SRC"
else
    echo "  Binary not found — building inside Docker (debian:bookworm + UV + PyInstaller)..."
    mkdir -p "$DIST_LINUX_DIR"

    # Mount the workspace READ-ONLY to prevent Docker (running as root) from
    # touching the host .venv or any other host-owned files.
    # The output binary is written directly to the separately mounted $DIST_LINUX_DIR.
    docker run --rm $DOCKER_PLATFORM_FLAG \
        -v "$REPO_ROOT:/workspace:ro" \
        -v "$DIST_LINUX_DIR:/output" \
        debian:bookworm bash -c "
            set -euo pipefail
            apt-get update -qq
            apt-get install -y -qq curl ca-certificates rsync binutils

            # Debian bookworm ships patchelf 0.14 which lacks --clear-execstack
            # (added in 0.17). Install upstream 0.18 binary.
            mkdir -p /tmp/patchelf_install
            curl -L -o /tmp/patchelf.tar.gz \
                https://github.com/NixOS/patchelf/releases/download/0.18.0/patchelf-0.18.0-x86_64.tar.gz
            tar xzf /tmp/patchelf.tar.gz -C /tmp/patchelf_install
            install /tmp/patchelf_install/bin/patchelf /usr/local/bin/patchelf
            patchelf --version

            curl -LsSf https://astral.sh/uv/install.sh | sh
            export PATH=\"\$HOME/.local/bin:\$PATH\"

            # Copy workspace to a fully writable build dir (excludes .venv, dist, etc.)
            rsync -a \
                --exclude '.venv' \
                --exclude '__pycache__' \
                --exclude '*.pyc' \
                --exclude 'dist' \
                /workspace/ /build/

            cd /build
            chmod +x build/linux/build.sh
            bash build/linux/build.sh

            cp /build/dist/linux/touchstone_linux_x86_64 /output/touchstone_linux_x86_64
            echo 'Binary built and copied to output.'
        "
    echo "  Binary built: $BINARY_SRC"
fi

echo ""
echo "[2/4] Staging binary into iso-config..."
mkdir -p "$(dirname "$BINARY_STAGE")"
cp "$BINARY_SRC" "$BINARY_STAGE"
chmod +x "$BINARY_STAGE"
echo "  Staged to: $BINARY_STAGE"

echo ""
echo "[3/4] Building live ISO (Docker --privileged, debian:bookworm + live-build)..."
mkdir -p "$DIST_ISO_DIR"

docker run --rm --privileged $DOCKER_PLATFORM_FLAG \
    -v "$REPO_ROOT:/workspace" \
    debian:bookworm bash -c "
        set -euo pipefail
        apt-get update -qq
        apt-get install -y -qq live-build

        # Work in a temp dir — live-build writes many build artefacts
        mkdir -p /tmp/lb-build
        cp -r /workspace/scripts/iso-config/. /tmp/lb-build/

        cd /tmp/lb-build
        lb config
        lb build

        ISO_FILE=\$(ls /tmp/lb-build/*.iso 2>/dev/null | head -n1)
        if [ -z \"\$ISO_FILE\" ]; then
            echo 'ERROR: No ISO produced by lb build.'
            exit 1
        fi
        cp \"\$ISO_FILE\" /workspace/dist/iso/touchstone-live.iso
        echo \"ISO copied: \$ISO_FILE -> dist/iso/touchstone-live.iso\"
    "

echo ""
echo "[4/4] Done."
echo "Output : $DIST_ISO_DIR/touchstone-live.iso"
echo ""
echo "Next steps:"
echo "  • Test in VirtualBox / UTM: boot from the ISO"
echo "  • Copy ISO to Ventoy USB: cp $DIST_ISO_DIR/touchstone-live.iso /Volumes/Ventoy/iso/"
echo "  • Populate full USB:       ./scripts/create_usb.sh"
