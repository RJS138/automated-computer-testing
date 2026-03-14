.PHONY: build run dev clean

# Build a local binary for the current machine (macOS arm64 on an M-series Mac).
# Output: dist/macos/touchstone_arm64
build:
	bash build/macos/build.sh

# Run the app in dev mode (no build needed)
run:
	uv run touchstone

# Jump straight to the manual tests screen
dev:
	uv run touchstone --dev-manual

# Remove PyInstaller work/spec caches and built binaries
clean:
	rm -rf build/_pyinstaller_work build/_pyinstaller_spec dist/
