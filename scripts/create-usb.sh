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

# Determine expected macOS binary name for this machine
MACOS_DIR="$REPO_ROOT/dist/macos"
MACOS_ARCH="$(uname -m)"
if [ "$MACOS_ARCH" = "arm64" ]; then
    MACOS_BIN="$MACOS_DIR/PC Tester (Apple Silicon)"
else
    MACOS_BIN="$MACOS_DIR/PC Tester (Intel)"
fi
if [ ! -f "$MACOS_BIN" ]; then
    echo "  macOS binary missing — running scripts/build-macos.sh..."
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
WIN_COUNT=0
if [ -d "$WIN_SRC" ]; then
    while IFS= read -r -d '' f; do
        cp "$f" "$VENTOY_MOUNT/win/"
        echo "  Copied: win/$(basename "$f")"
        WIN_COUNT=$((WIN_COUNT + 1))
    done < <(find "$WIN_SRC" -maxdepth 1 -name "PC Tester*.exe" -print0 2>/dev/null)
fi
if [ "$WIN_COUNT" -eq 0 ]; then
    warn "No Windows binaries found in dist/windows/. Run scripts/build-windows.bat on a Windows machine."
fi

echo ""
echo "[3/7] Copying Linux binaries..."
LINUX_SRC="$REPO_ROOT/dist/linux"
LINUX_COUNT=0
if [ -d "$LINUX_SRC" ]; then
    while IFS= read -r -d '' f; do
        cp "$f" "$VENTOY_MOUNT/linux/"
        chmod +x "$VENTOY_MOUNT/linux/$(basename "$f")"
        echo "  Copied: linux/$(basename "$f")"
        LINUX_COUNT=$((LINUX_COUNT + 1))
    done < <(find "$LINUX_SRC" -maxdepth 1 -name "PC Tester (Linux*)" -print0 2>/dev/null)
fi
if [ "$LINUX_COUNT" -eq 0 ]; then
    warn "No Linux binaries found in dist/linux/. Run scripts/build-linux.sh on a Linux machine."
fi

echo ""
echo "[4/7] Copying macOS binaries..."
MAC_SRC="$REPO_ROOT/dist/macos"
MAC_COUNT=0
if [ -d "$MAC_SRC" ]; then
    while IFS= read -r -d '' f; do
        cp "$f" "$VENTOY_MOUNT/macos/"
        chmod +x "$VENTOY_MOUNT/macos/$(basename "$f")"
        echo "  Copied: macos/$(basename "$f")"
        MAC_COUNT=$((MAC_COUNT + 1))
    done < <(find "$MAC_SRC" -maxdepth 1 \( -name "PC Tester (Apple Silicon)" -o -name "PC Tester (Intel)" \) -print0 2>/dev/null)
fi
if [ "$MAC_COUNT" -eq 0 ]; then
    warn "No macOS binaries found in dist/macos/. Run scripts/build-macos.sh (Apple Silicon) and/or scripts/build-macos-intel.sh (Intel)."
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
win/     Windows executables
           PC Tester (Windows x64).exe
           PC Tester (Windows ARM64).exe
linux/   Linux binaries
           PC Tester (Linux x86_64)
           PC Tester (Linux ARM64)
macos/   macOS binaries
           PC Tester (Apple Silicon)
           PC Tester (Intel)
iso/     Bootable live ISO (boot via Ventoy menu)
reports/ Saved diagnostic reports

HOW TO USE
----------
Windows:
  1. Plug in the USB drive.
  2. Open win\ and run "PC Tester (Windows x64).exe" (or ARM64 for ARM devices).
  3. Reports are saved automatically to the reports\ folder on this drive.

Linux (installed OS):
  1. Plug in the USB drive.
  2. Open a terminal, navigate to the linux/ folder on the USB drive.
  3. Run:  chmod +x "PC Tester (Linux x86_64)"
           ./"PC Tester (Linux x86_64)"

macOS:
  1. Plug in the USB drive.
  2. Open macos/ and run "PC Tester (Apple Silicon)" or "PC Tester (Intel)".
  3. If macOS blocks it, right-click → Open, or remove the quarantine attribute:
       xattr -d com.apple.quarantine "/Volumes/Ventoy/macos/PC Tester (Apple Silicon)"

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
