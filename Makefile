.PHONY: build run dev clean icon

# Build a local binary for the current machine.
# Output: dist/macos/Touchstone (Apple Silicon)  or  dist/macos/Touchstone (Intel)
build:
	bash build/macos/build.sh

# Run the app in dev mode (no build needed)
run:
	uv run touchstone

# Jump straight to the manual tests screen
dev:
	uv run touchstone --dev-manual

# Regenerate app icons (assets/icon.png, .ico, .icns)
icon:
	uv run python scripts/generate_icon.py

# Remove PyInstaller work/spec caches and built binaries
clean:
	rm -rf build/_pyinstaller_work build/_pyinstaller_spec dist/
