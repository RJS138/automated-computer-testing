#!/usr/bin/env bash
# Touchstone — macOS Build Script
#
# Prerequisites:
#   1. Install UV:  curl -LsSf https://astral.sh/uv/install.sh | sh
#
# Produces a .dmg containing a proper .app bundle backed by a --onefile
# PyInstaller binary (the combination proven to work on macOS).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$REPO_ROOT/dist/macos"
ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then
    DMG_NAME="touchstone_macos_arm64"
else
    DMG_NAME="touchstone_macos_x86_64"
fi

echo "=== Touchstone — macOS Build ==="
echo "Repo root : $REPO_ROOT"
echo "Arch      : $ARCH"
echo "Output    : $DIST_DIR/$DMG_NAME.dmg"

cd "$REPO_ROOT"

echo ""
echo "[1/4] Syncing dependencies (uv sync --group build)..."
uv sync --group build

echo ""
echo "[2/4] Running PyInstaller (--onefile)..."
uv run pyinstaller \
  --onefile \
  --name "Touchstone" \
  --icon "$REPO_ROOT/assets/icon.icns" \
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
echo "[3/4] Wrapping binary in .app bundle..."
APP_DIR="$DIST_DIR/Touchstone.app"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"

cp "$DIST_DIR/Touchstone" "$APP_DIR/Contents/MacOS/Touchstone"
chmod +x "$APP_DIR/Contents/MacOS/Touchstone"

# Copy icon into the bundle
mkdir -p "$APP_DIR/Contents/Resources"
cp "$REPO_ROOT/assets/icon.icns" "$APP_DIR/Contents/Resources/icon.icns"

cat > "$APP_DIR/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>      <string>Touchstone</string>
    <key>CFBundleIdentifier</key>      <string>com.touchstone.app</string>
    <key>CFBundleName</key>            <string>Touchstone</string>
    <key>CFBundleDisplayName</key>     <string>Touchstone</string>
    <key>CFBundleVersion</key>         <string>1.0</string>
    <key>CFBundleShortVersionString</key> <string>1.0</string>
    <key>CFBundlePackageType</key>     <string>APPL</string>
    <key>CFBundleIconFile</key>        <string>icon</string>
    <key>NSHighResolutionCapable</key> <true/>
    <key>LSUIElement</key>             <false/>
</dict>
</plist>
PLIST

echo ""
echo "[4/4] Creating DMG..."
# hdiutil can transiently fail with "Resource busy" on CI runners (Spotlight
# or Finder touching the output path).  Retry up to 5 times.
for attempt in 1 2 3 4 5; do
  if hdiutil create \
       -volname "Touchstone" \
       -srcfolder "$APP_DIR" \
       -ov \
       -format UDZO \
       "$DIST_DIR/$DMG_NAME.dmg"; then
    break
  fi
  echo "hdiutil attempt $attempt failed — retrying in 5 s..."
  sleep 5
  if [ "$attempt" -eq 5 ]; then
    echo "hdiutil failed after 5 attempts" >&2
    exit 1
  fi
done

echo ""
echo "Output : $DIST_DIR/$DMG_NAME.dmg"
echo ""
echo "NOTE: App is not codesigned. On first launch:"
echo "  Right-click Touchstone.app → Open"
