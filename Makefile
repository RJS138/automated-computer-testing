.PHONY: build run dev clean lint

# Build a binary. Optionally specify TARGET to pick a platform/arch:
#   make build                    → macOS native (arm64 on Apple Silicon)
#   make build TARGET=macos       → macOS native
#   make build TARGET=macos-arm   → macOS Apple Silicon (arm64)
#   make build TARGET=macos-intel → macOS Intel (x86_64) via Rosetta — runs on Apple Silicon
#   make build TARGET=linux       → Linux (run on the target machine)
#   make build TARGET=windows     → Windows x64 (run on the target machine)
#   make build TARGET=windows-arm → Windows ARM (run on the target machine)
TARGET ?= macos

build:
	@case "$(TARGET)" in \
	  macos)        bash build/macos/build.sh ;; \
	  macos-arm)    arch -arm64  bash build/macos/build.sh ;; \
	  macos-intel)  arch -x86_64 bash build/macos/build.sh ;; \
	  linux)        bash build/linux/build.sh ;; \
	  windows)      cmd /c build\\windows\\build.bat ;; \
	  windows-arm)  cmd /c build\\windows\\build_arm.bat ;; \
	  *) echo "Unknown TARGET '$(TARGET)'. Valid: macos, macos-arm, macos-intel, linux, windows, windows-arm" && exit 1 ;; \
	esac

# Run the app in dev mode (no build needed)
run:
	uv run touchstone

# Jump straight to the manual tests screen
dev:
	uv run touchstone --dev-manual

# Remove PyInstaller work/spec caches and built binaries
clean:
	rm -rf build/_pyinstaller_work build/_pyinstaller_spec dist/

# Run linter (ruff) and type checker (ty)
lint:
	uv run --group lint ruff check src/
	uv run --group lint ruff format --check src/
	uv run --group lint ty check src/
