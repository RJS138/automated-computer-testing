# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Dev Commands

```bash
uv sync                     # install deps + create .venv
uv run touchstone           # launch the app normally
uv run touchstone --dev-manual  # skip to manual tests screen

uv sync --group build       # add PyInstaller
./build/macos/build.sh      # macOS binary → dist/macos/
./build/linux/build.sh      # Linux binary → dist/linux/
build\windows\build.bat     # Windows binary → dist\windows\
```

There are no automated tests. Manual testing is done by running the app.

## Architecture

The app is a **Textual TUI** that walks a technician through PC diagnostics and generates HTML/PDF reports.

### Screen Flow

```
ReadinessScreen → WelcomeScreen → ModeSelectScreen → DashboardScreen → ManualTestsScreen → ReportDoneScreen
```

Screens are pushed onto the Textual screen stack. Shared state lives on the `PCTesterApp` instance: `app.job_info`, `app.test_results`, `app.manual_items`.

### Automated Tests (`src/tests/`)

- All tests are `async`, subclass `BaseTest`, and populate a `TestResult` in-place via `mark_pass()` / `mark_warn()` / `mark_fail()`.
- `DashboardScreen` runs each test in a **Textual Worker** (off UI thread). Two groups run concurrently:
  - **Parallel** (fast/info): `system_info`, `network`, `battery`, `gpu`, `display`
  - **Sequential** (resource-intensive): `cpu` → `ram` → `storage`
- Test durations are controlled by constants in `src/config.py` (`CPU_STRESS_QUICK`, etc.).

### Manual Tests (`src/tests/manual/`)

- Each item (LCD, keyboard, touchpad, speakers, USB-A/C, HDMI, webcam) is a small module.
- `ManualTestRunner` in `runner.py` manages state; `ManualTestsScreen` renders one item at a time.
- Items with a `test_type` field (e.g., `display_color`, `keyboard_test`) launch an interactive sub-screen.

### Thresholds (`src/thresholds.py`)

Hardware-specific pass/warn/fail thresholds for CPU families (Intel, AMD, Apple Silicon), GPU families (NVIDIA, AMD RDNA, Intel Arc, Apple), storage types (NVMe Gen 3/4/5, SATA SSD, HDD), and battery health/cycle counts. Match detected hardware names to threshold families here when adding new hardware support.

### Report Pipeline

1. `report/generator.py` — assembles `FullReport` from `JobInfo` + `list[TestResult]`
2. `report/html_render.py` — Jinja2 → HTML string; embeds raw JSON in `<script id="report-data">` for downstream use
3. `report/pdf_render.py` — parses that JSON, builds PDF via ReportLab Platypus (pure Python, no system libs)
4. `report/diff.py` — generates before/after comparison from two reports in the same job folder

Templates live in `src/report/templates/`.

### Platform Detection

`src/utils/platform_detect.py` exposes `get_os()`, `get_arch()`, `is_frozen()`, and `get_exe_dir()`. Every test module has explicit `if os == "darwin" / "windows" / "linux"` branches — always add all three when writing new platform-specific logic.

### Key Config

- `src/config.py` — test durations, temperature thresholds, `APP_NAME`, report folder naming, USB marker filename
- `src/utils/file_manager.py` — USB drive detection and report directory layout (`reports/{customer_job}/before|after/`)

### Terminal Fallback

Set `TOUCHSTONE_SIMPLE=1` to force simple ASCII/256-color mode. `src/utils/term_detect.py` auto-detects and sets `TOUCHSTONE_SIMPLE_UI`. UI widgets check `app.SIMPLE_UI` and use ASCII fallbacks where needed. Override env vars: `TOUCHSTONE_FANCY=1` (force fancy) / `TOUCHSTONE_SIMPLE=1` (force simple).

### PyInstaller Notes

- Templates must be bundled via `--add-data "src/report/templates:src/report/templates"`
- Keyboard XML layouts bundled via `--add-data "src/ui/keyboards:src/ui/keyboards"`
- `is_frozen()` checks `sys._MEIPASS`; use `get_exe_dir()` when locating bundled assets
- `wmi` is Windows-only (platform-conditional in `pyproject.toml`) — no manual exclusion needed
- tkinter helper windows (`_display_helper.py`, `_keyboard_helper.py`) are invoked via `--run-helper <name>` dispatch in `main.py` so the frozen binary re-invokes itself rather than trying to run a `.py` file
