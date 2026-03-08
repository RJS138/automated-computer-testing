#!/usr/bin/env bash
# PC Tester — USB Population Script (macOS)
#
# Populates a Ventoy-formatted USB drive with all platform binaries and the live ISO.
# Missing files produce warnings only — the USB can be populated incrementally.
#
# Prerequisites:
#   Ventoy installed on the target USB drive (https://www.ventoy.net)
#   The USB drive must be mounted at /Volumes/Ventoy
#
# Usage:
#   ./scripts/create-usb.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENTOY_MOUNT="/Volumes/Ventoy"

echo "=== PC Tester — USB Population (macOS) ==="
echo "Repo root : $REPO_ROOT"
echo "Target    : $VENTOY_MOUNT"

# --- Check Ventoy USB is mounted ---
if [ ! -d "$VENTOY_MOUNT" ]; then
    echo ""
    echo "ERROR: Ventoy USB not found at $VENTOY_MOUNT."
    echo ""
    echo "To set up a Ventoy USB drive:"
    echo "  1. Download Ventoy from https://www.ventoy.net/en/download.html"
    echo "  2. Run VentoyGUI (macOS) and select your USB drive"
    echo "  3. Click 'Install' — this will format and set up the drive"
    echo "  4. The USB will appear as /Volumes/Ventoy once ready"
    echo "  5. Re-run this script"
    exit 1
fi

# --- Ensure required build artefacts exist (best-effort) ---
echo ""
echo "Preflight: ensuring build artefacts exist..."

ISO_PATH="$REPO_ROOT/dist/iso/pctester-live.iso"
if [ ! -f "$ISO_PATH" ]; then
    echo "  Live ISO missing — running scripts/build-iso.sh (this may take several minutes)..."
    bash "$REPO_ROOT/scripts/build-iso.sh"
else
    echo "  Live ISO present: $ISO_PATH"
fi

MACOS_DIR="$REPO_ROOT/dist/macos"
MACOS_ARCH="$(uname -m)"
MACOS_BIN="$MACOS_DIR/pctester_${MACOS_ARCH}"
if [ ! -f "$MACOS_BIN" ]; then
    echo "  macOS binary for arch ${MACOS_ARCH} missing — running scripts/build-macos.sh..."
    bash "$REPO_ROOT/scripts/build-macos.sh"
else
    echo "  macOS binary present: $MACOS_BIN"
fi

WARN_COUNT=0

warn() {
    echo "  WARNING: $1"
    WARN_COUNT=$((WARN_COUNT + 1))
}

echo ""
echo "[1/7] Creating folder structure on USB..."
mkdir -p \
    "$VENTOY_MOUNT/win" \
    "$VENTOY_MOUNT/linux" \
    "$VENTOY_MOUNT/macos" \
    "$VENTOY_MOUNT/iso" \
    "$VENTOY_MOUNT/reports"
echo "  Folders: win/ linux/ macos/ iso/ reports/"

echo ""
echo "[2/7] Copying Windows binaries..."
WIN_SRC="$REPO_ROOT/dist/windows"
if [ -d "$WIN_SRC" ] && ls "$WIN_SRC"/*.exe &>/dev/null 2>&1; then
    cp "$WIN_SRC"/*.exe "$VENTOY_MOUNT/win/"
    for f in "$WIN_SRC"/*.exe; do
        echo "  Copied: win/$(basename "$f")"
    done
else
    warn "No Windows binaries found in dist/windows/. Run scripts/build-windows.bat on a Windows machine."
fi

echo ""
echo "[3/7] Copying Linux binaries..."
LINUX_SRC="$REPO_ROOT/dist/linux"
if [ -d "$LINUX_SRC" ] && ls "$LINUX_SRC"/pctester_* &>/dev/null 2>&1; then
    for f in "$LINUX_SRC"/pctester_*; do
        cp "$f" "$VENTOY_MOUNT/linux/"
        chmod +x "$VENTOY_MOUNT/linux/$(basename "$f")"
        echo "  Copied: linux/$(basename "$f")"
    done
else
    warn "No Linux binaries found in dist/linux/. Run scripts/build-linux.sh on a Linux machine."
fi

echo ""
echo "[4/7] Copying macOS binaries..."
MAC_SRC="$REPO_ROOT/dist/macos"
if [ -d "$MAC_SRC" ] && ls "$MAC_SRC"/pctester_* &>/dev/null 2>&1; then
    for f in "$MAC_SRC"/pctester_*; do
        cp "$f" "$VENTOY_MOUNT/macos/"
        chmod +x "$VENTOY_MOUNT/macos/$(basename "$f")"
        echo "  Copied: macos/$(basename "$f")"
    done
else
    warn "No macOS binaries found in dist/macos/. Run scripts/build-macos.sh on each Mac architecture you care about."
fi

echo ""
echo "[5/7] Copying live ISO..."
ISO_SRC="$REPO_ROOT/dist/iso/pctester-live.iso"
if [ -f "$ISO_SRC" ]; then
    cp "$ISO_SRC" "$VENTOY_MOUNT/iso/pctester-live.iso"
    echo "  Copied: iso/pctester-live.iso"
    echo "  (The ISO will appear in the Ventoy boot menu automatically)"
else
    warn "Live ISO not found at dist/iso/pctester-live.iso. Run scripts/build-iso.sh to build it."
fi

echo ""
echo "[6/7] Writing marker file and README..."

# Marker file used by the app to detect it is running from USB
touch "$VENTOY_MOUNT/pctester_usb.marker"

cat > "$VENTOY_MOUNT/README.txt" << 'EOF'
PC Tester — USB Drive
=====================

This USB drive contains diagnostic tools for PC repair technicians.

CONTENTS
--------
win/         Windows executables (x64, arm64)
linux/       Linux binaries (x86_64)
macos/       macOS binaries (x86_64, arm64)
iso/         Bootable live ISO (boot via Ventoy menu)
reports/     Saved diagnostic reports

HOW TO USE
----------
Windows:
  1. Plug in the USB drive.
  2. Open win\ and run the appropriate .exe for your architecture.
  3. Reports are saved automatically to the reports\ folder on this drive.

Linux (installed OS):
  1. Plug in the USB drive.
  2. Open a terminal and run: chmod +x /path/to/linux/pctester_x86_64
  3. Run: /path/to/linux/pctester_x86_64

macOS:
  1. Plug in the USB drive.
  2. Open macos/ and run the binary that matches your architecture (x86_64 or arm64).
  3. If macOS blocks it, you may need to remove the quarantine attribute:
       xattr -d com.apple.quarantine /path/to/macos/pctester_*

Bootable (for machines that can't boot their own OS):
  1. Plug in the USB drive and boot from it (F12 / Del / F2 for boot menu).
  2. The Ventoy boot menu will appear — select pctester-live.iso.
  3. The PC Tester app launches automatically. No login required.
  4. Reports are saved to the reports\ folder on this USB drive.

VENTOY
------
This drive uses Ventoy for bootable ISO support.
To add more ISOs, simply copy them to the iso\ folder.
Learn more at https://www.ventoy.net
EOF

echo "  Written: pctester_usb.marker"
echo "  Written: README.txt"

echo ""
echo "[7/7] Summary"
echo "  USB path     : $VENTOY_MOUNT"
echo "  Warnings     : $WARN_COUNT"

if [ "$WARN_COUNT" -gt 0 ]; then
    echo ""
    echo "  Some files are missing (see warnings above)."
    echo "  The USB can be used now and updated incrementally as builds are added."
else
    echo ""
    echo "  All files copied successfully. USB is ready."
fi

echo ""
echo "Eject the USB drive before unplugging:"
echo "  diskutil eject $VENTOY_MOUNT"
