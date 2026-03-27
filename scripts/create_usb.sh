#!/usr/bin/env bash
# Touchstone — USB Setup Script (macOS / Linux)
#
# Installs Ventoy on a USB drive, then downloads the latest PC Tester
# executables from GitHub Releases and copies them onto the drive.
#
# Usage:
#   sudo ./scripts/create_usb.sh              # Full setup — installs Ventoy + downloads
#   sudo ./scripts/create_usb.sh --update     # Skip Ventoy, just refresh executables
#
# Requirements: bash 4+, curl
# Supported OS: macOS, Linux

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
# Auto-detect the GitHub repo from the git remote; falls back to the value below.
GITHUB_REPO=$(git -C "$(dirname "${BASH_SOURCE[0]}")/.." \
    remote get-url origin 2>/dev/null \
    | sed 's|.*github\.com[:/]||; s|\.git$||' \
    | tr -d '[:space:]') 2>/dev/null || true
GITHUB_REPO="${GITHUB_REPO:-RJS138/touchstone}"

USB_MARKER="touchstone_usb.marker"
REPORTS_DIR="reports"

# ── Colour helpers ────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    RED='\033[0;31m' YEL='\033[1;33m' GRN='\033[0;32m'
    CYN='\033[0;36m' BOLD='\033[1m' NC='\033[0m'
else
    RED='' YEL='' GRN='' CYN='' BOLD='' NC=''
fi

die()  { echo -e "\n${RED}✗  ERROR: $*${NC}\n" >&2; exit 1; }
info() { echo -e "${CYN}   → $*${NC}"; }
ok()   { echo -e "${GRN}   ✓ $*${NC}"; }
warn() { echo -e "${YEL}   ⚠ $*${NC}"; }
step() { echo -e "\n${BOLD}$*${NC}"; }

# ── Argument parsing ──────────────────────────────────────────────────────────
SKIP_VENTOY=false
for arg in "$@"; do
    case "$arg" in
        --update|--no-ventoy) SKIP_VENTOY=true ;;
        -h|--help)
            echo "Usage: sudo $0 [--update]"
            echo "  --update   Refresh executables only — skip Ventoy install"
            exit 0 ;;
    esac
done

# ── Elevation ─────────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "Root access required for disk operations. Re-running with sudo..."
    exec sudo bash "$0" "$@"
fi

# ── OS / dependency check ────────────────────────────────────────────────────
OS=$(uname -s)
[[ "$OS" == "Darwin" || "$OS" == "Linux" ]] \
    || die "Unsupported OS: $OS. Use scripts/create_usb.ps1 on Windows."
command -v curl &>/dev/null || die "curl is required but not installed."

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo ""
echo -e "${BOLD}Touchstone — USB Setup${NC}"
echo "  Repo : $GITHUB_REPO"
echo "  OS   : $OS"

# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — Select USB drive
# ═════════════════════════════════════════════════════════════════════════════
step "[1/5] Select USB drive"
echo ""

if [[ "$OS" == "Darwin" ]]; then
    echo "  External drives:"
    diskutil list external physical 2>/dev/null | grep "^/dev/" | \
    while read -r dev _; do
        SIZE=$(diskutil info "$dev" 2>/dev/null \
            | grep "Disk Size" | sed 's/.*Disk Size: *//; s/ (.*//')
        NAME=$(diskutil info "$dev" 2>/dev/null \
            | grep "Media Name" | sed 's/.*Media Name: *//')
        printf "    %-12s  %s  —  %s\n" "$dev" "$SIZE" "$NAME"
    done
    echo ""
    echo "  Tip: 'diskutil list external physical' for full details."
else
    echo "  USB block devices:"
    lsblk -d -o NAME,SIZE,MODEL,TRAN 2>/dev/null \
        | awk 'NR==1 {printf "    %s\n", $0} NR>1 && $4=="usb" {printf "    %s\n", $0}' \
        || lsblk -d -o NAME,SIZE,MODEL 2>/dev/null | awk 'NR<=6 {print "    "$0}'
    echo ""
    echo "  Tip: 'lsblk -d -o NAME,SIZE,MODEL,TRAN' to see all drives."
fi

echo ""
read -rp "  Enter device path (e.g. /dev/disk2 or /dev/sdb): " DRIVE
DRIVE="${DRIVE%/}"
[[ -b "$DRIVE" ]] || die "$DRIVE is not a block device."

# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — Confirm (if full install)
# ═════════════════════════════════════════════════════════════════════════════
if [[ "$SKIP_VENTOY" == false ]]; then
    echo ""
    echo -e "  ${RED}${BOLD}⚠  WARNING: ALL data on $DRIVE will be permanently erased!${NC}"
    echo ""
    if [[ "$OS" == "Darwin" ]]; then
        diskutil info "$DRIVE" 2>/dev/null \
            | grep -E "Media Name|Disk Size|Volume Name" | sed 's/^/    /'
    else
        lsblk -o NAME,SIZE,MODEL "$DRIVE" 2>/dev/null | sed 's/^/    /'
    fi
    echo ""
    read -rp "  Type YES (all caps) to continue: " CONFIRM
    [[ "$CONFIRM" == "YES" ]] || { echo "  Aborted."; exit 0; }
fi

# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — Ventoy install (or locate existing)
# ═════════════════════════════════════════════════════════════════════════════
MOUNT_POINT=""

if [[ "$SKIP_VENTOY" == false ]]; then
    step "[2/5] Installing Ventoy"

    info "Fetching latest Ventoy version..."
    VENTOY_VER=$(curl -fsSL "https://api.github.com/repos/ventoy/ventoy/releases/latest" \
        | grep '"tag_name"' | head -1 | sed 's/.*"v\([^"]*\)".*/\1/')
    [[ -n "$VENTOY_VER" ]] || die "Could not determine latest Ventoy version (check network connection)."
    info "Latest Ventoy: v$VENTOY_VER"

    VENTOY_URL="https://github.com/ventoy/ventoy/releases/download/v${VENTOY_VER}/ventoy-${VENTOY_VER}-linux.tar.gz"
    info "Downloading Ventoy..."
    curl -fsSL --progress-bar "$VENTOY_URL" -o "$TMP/ventoy.tar.gz" \
        || die "Failed to download Ventoy from $VENTOY_URL"

    # Verify Ventoy archive integrity against its published SHA-256
    info "Verifying Ventoy checksum..."
    VENTOY_SHA256_URL="https://github.com/ventoy/ventoy/releases/download/v${VENTOY_VER}/ventoy-${VENTOY_VER}-linux.tar.gz.sha256"
    if curl -fsSL "$VENTOY_SHA256_URL" -o "$TMP/ventoy.tar.gz.sha256" 2>/dev/null; then
        VENTOY_EXPECTED=$(awk '{print $1}' "$TMP/ventoy.tar.gz.sha256")
        if command -v sha256sum &>/dev/null; then
            VENTOY_ACTUAL=$(sha256sum "$TMP/ventoy.tar.gz" | awk '{print $1}')
        elif command -v shasum &>/dev/null; then
            VENTOY_ACTUAL=$(shasum -a 256 "$TMP/ventoy.tar.gz" | awk '{print $1}')
        else
            VENTOY_ACTUAL=""
        fi
        if [[ -n "$VENTOY_ACTUAL" && "$VENTOY_ACTUAL" != "$VENTOY_EXPECTED" ]]; then
            die "Ventoy checksum MISMATCH — download may be corrupted or tampered with.
  Expected: $VENTOY_EXPECTED
  Got:      $VENTOY_ACTUAL"
        elif [[ -n "$VENTOY_ACTUAL" ]]; then
            ok "Ventoy checksum verified."
        else
            warn "No sha256sum/shasum available — Ventoy checksum skipped."
        fi
    else
        warn "Ventoy checksum file not available for v${VENTOY_VER} — skipping verification."
    fi

    tar -xzf "$TMP/ventoy.tar.gz" -C "$TMP"

    VENTOY_SH="$TMP/ventoy-${VENTOY_VER}/Ventoy2Disk.sh"
    [[ -f "$VENTOY_SH" ]] || die "Ventoy archive structure unexpected. File not found: $VENTOY_SH"

    if [[ "$OS" == "Darwin" ]]; then
        info "Unmounting $DRIVE partitions..."
        diskutil unmountDisk "$DRIVE" &>/dev/null || true
    fi

    info "Writing Ventoy to $DRIVE (may take 20–60 seconds)..."
    # Pipe two 'y' responses to satisfy Ventoy's two confirmation prompts.
    printf 'y\ny\n' | bash "$VENTOY_SH" -i "$DRIVE" \
        || die "Ventoy installation failed. Make sure no partitions on $DRIVE are mounted."
    ok "Ventoy installed."

    # Mount the Ventoy data partition (partition 1 — the large exFAT partition)
    if [[ "$OS" == "Darwin" ]]; then
        info "Waiting for VENTOY partition to mount..."
        for i in {1..10}; do
            [[ -d "/Volumes/VENTOY" ]] && break
            sleep 1
        done
        # macOS doesn't always automount after a write — force it
        if [[ ! -d "/Volumes/VENTOY" ]]; then
            info "Automount didn't fire — mounting ${DRIVE}s1 manually..."
            diskutil mount "${DRIVE}s1" &>/dev/null || true
            sleep 3
        fi
        [[ -d "/Volumes/VENTOY" ]] \
            || die "Could not mount VENTOY partition. Try manually: diskutil mount ${DRIVE}s1"
        MOUNT_POINT="/Volumes/VENTOY"
    else
        # nvme/mmcblk use p1 suffix; everything else uses 1
        if [[ "$DRIVE" =~ nvme|mmcblk ]]; then
            PART="${DRIVE}p1"
        else
            PART="${DRIVE}1"
        fi
        MOUNT_POINT="$TMP/ventoy_data"
        mkdir -p "$MOUNT_POINT"
        sleep 2  # let kernel settle partition table
        mount "$PART" "$MOUNT_POINT" \
            || die "Could not mount $PART. Try manually: sudo mount $PART /mnt"
    fi

else
    # --update: find the already-mounted VENTOY partition
    step "[2/5] Locating VENTOY partition"

    if [[ "$OS" == "Darwin" ]]; then
        [[ -d "/Volumes/VENTOY" ]] \
            || die "No VENTOY drive at /Volumes/VENTOY. Insert the USB drive first."
        MOUNT_POINT="/Volumes/VENTOY"
    else
        MOUNT_POINT=$(findmnt -rn -o TARGET -S LABEL=VENTOY 2>/dev/null | head -1 || true)
        if [[ -z "$MOUNT_POINT" ]]; then
            read -rp "  Enter VENTOY mount path (e.g. /media/user/VENTOY): " MOUNT_POINT
        fi
        [[ -d "$MOUNT_POINT" ]] || die "Mount point '$MOUNT_POINT' not found."
    fi
fi

ok "VENTOY partition at: $MOUNT_POINT"

# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — Download latest executables
# ═════════════════════════════════════════════════════════════════════════════
step "[3/5] Downloading latest PC Tester release"
info "Source: https://github.com/$GITHUB_REPO/releases/latest"

BASE_URL="https://github.com/$GITHUB_REPO/releases/latest/download"

mkdir -p \
    "$MOUNT_POINT/windows" \
    "$MOUNT_POINT/linux" \
    "$MOUNT_POINT/macos" \
    "$MOUNT_POINT/$REPORTS_DIR"

# Download the checksum manifest first — all binary downloads are verified against it.
info "Downloading SHA256SUMS..."
curl -fsSL "$BASE_URL/SHA256SUMS" -o "$TMP/SHA256SUMS" \
    || die "Could not download SHA256SUMS from release. Cannot verify file integrity."
ok "SHA256SUMS downloaded."

_verify_file() {
    local file="$1" name="$2"
    [[ -f "$file" ]] || return 0  # file was skipped — nothing to verify
    local expected
    expected=$(grep "[[:space:]]${name}$" "$TMP/SHA256SUMS" 2>/dev/null | awk '{print $1}')
    if [[ -z "$expected" ]]; then
        warn "No checksum entry for $name — skipping verification."
        return 0
    fi
    local actual
    if command -v sha256sum &>/dev/null; then
        actual=$(sha256sum "$file" | awk '{print $1}')
    elif command -v shasum &>/dev/null; then
        actual=$(shasum -a 256 "$file" | awk '{print $1}')
    else
        warn "sha256sum/shasum not available — skipping checksum for $name."
        return 0
    fi
    if [[ "$actual" == "$expected" ]]; then
        ok "Checksum OK: $name"
    else
        rm -f "$file"
        die "Checksum MISMATCH for $name — file removed. Possible tampering detected.
  Expected: $expected
  Got:      $actual"
    fi
}

_dl() {
    local name="$1" dest="$2"
    info "Downloading $name..."
    if curl -fsSL --progress-bar -L "$BASE_URL/$name" -o "$dest" 2>&1; then
        _verify_file "$dest" "$name"
    else
        warn "$name not found in latest release (skipped)."
        rm -f "$dest"
    fi
}

_dl "touchstone_linux_x86_64"       "$MOUNT_POINT/linux/touchstone_linux_x86_64"
_dl "touchstone_linux_arm64"        "$MOUNT_POINT/linux/touchstone_linux_arm64"
_dl "touchstone_windows_x64.exe"    "$MOUNT_POINT/windows/touchstone_windows_x64.exe"
_dl "touchstone_windows_arm64.exe"  "$MOUNT_POINT/windows/touchstone_windows_arm64.exe"

_dl "touchstone_macos_arm64.dmg"    "$MOUNT_POINT/macos/touchstone_macos_arm64.dmg"

# Make Linux binaries executable (DMG handles macOS permissions internally)
chmod +x \
    "$MOUNT_POINT/linux/touchstone_linux_x86_64" \
    "$MOUNT_POINT/linux/touchstone_linux_arm64" \
    2>/dev/null || true

# ═════════════════════════════════════════════════════════════════════════════
# STEP 5 — Marker file and README
# ═════════════════════════════════════════════════════════════════════════════
step "[4/5] Writing marker and README"

touch "$MOUNT_POINT/$USB_MARKER"

cat > "$MOUNT_POINT/README.txt" << 'EOF'
Touchstone USB Drive
===================

WINDOWS (x64)
  Run: windows\touchstone_windows_x64.exe
  Right-click → "Run as Administrator"

WINDOWS (ARM)
  Run: windows\touchstone_windows_arm64.exe
  Right-click → "Run as Administrator"

MACOS (Apple Silicon / M-series)
  Double-click: macos/touchstone_macos_arm64.dmg
  Right-click Touchstone → Open on first launch to bypass Gatekeeper.

MACOS (Intel)
  Use macos/touchstone_macos_arm64.dmg — runs via Rosetta 2 automatically.

LINUX (x86)
  Run: linux/touchstone_linux_x86_64  (requires sudo)

LINUX (ARM)
  Run: linux/touchstone_linux_arm64  (requires sudo)

Reports are saved automatically to the reports/ folder on this drive.
To update the executables, re-run: sudo scripts/create_usb.sh --update
EOF

ok "Marker and README written."

# ═════════════════════════════════════════════════════════════════════════════
# STEP 6 — Eject
# ═════════════════════════════════════════════════════════════════════════════
step "[5/5] Ejecting"

if [[ "$OS" == "Darwin" ]]; then
    diskutil eject "$DRIVE" &>/dev/null \
        && ok "Drive ejected — safe to unplug." \
        || warn "Could not auto-eject. Use Finder to eject before unplugging."
else
    if [[ "$SKIP_VENTOY" == false ]]; then
        umount "$MOUNT_POINT" 2>/dev/null && ok "Drive unmounted." || true
    else
        info "Drive not unmounted automatically when using --update (you mounted it)."
    fi
fi

echo ""
echo -e "${GRN}${BOLD}✓  USB drive is ready.${NC}"
echo "   Plug it into the PC under test and run the appropriate executable."
echo ""
