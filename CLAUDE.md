# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Dev Commands

```bash
uv sync                     # install deps + create .venv
uv run touchstone           # launch the app normally
uv run touchstone --dev-manual  # skip to manual tests screen

make build                  # build local macOS binary → dist/macos/Touchstone (Apple Silicon) or Touchstone (Intel)
make run                    # same as uv run touchstone
make dev                    # same as uv run touchstone --dev-manual
make clean                  # remove PyInstaller caches and dist/

# Other platforms (run on the target machine):
uv sync --group build && ./build/linux/build.sh   # Linux binary
uv sync --group build && build\windows\build.bat  # Windows binary
```

There are no automated tests. Manual testing is done by running the app.

## Architecture

The app is a **PySide6 desktop GUI** that walks a technician through PC diagnostics and generates HTML/PDF reports.

### Page Flow

```
TouchstoneWindow → MainDashboard (single page)
Manual tests launch full-screen QDialog helpers; no page-to-page navigation.
```

`MainDashboard` is set as the central widget of `TouchstoneWindow` at startup and never replaced. All test execution, manual dialogs, and report generation happen within it. Shared state lives on the window instance: `window.job_info`, `window.test_results`, `window.manual_items`.

### Main Window (`src/ui/app_window.py`)

- `TouchstoneWindow(QMainWindow)` — `MainDashboard` as central widget, dark theme applied at QApplication level
- Shared state: `job_info`, `test_results`, `manual_items`

### Automated Tests (`src/tests/`)

- All tests are `async`, subclass `BaseTest`, and populate a `TestResult` in-place via `mark_pass()` / `mark_warn()` / `mark_fail()`.
- `MainDashboard` runs each test in a **`TestWorker(QThread)`** whose `run()` calls `asyncio.run(test.safe_run())`. Two groups:
  - **Parallel** (fast/info): `system_info`, `network`, `battery`, `gpu`, `display`
  - **Sequential** (resource-intensive): `cpu` → `ram` → `storage`
- Test durations are controlled by constants in `src/config.py` (`CPU_STRESS_QUICK`, etc.).

### Manual Tests

- Manual tests (LCD, keyboard, touchpad, speakers, USB-A/C, HDMI, webcam) are defined in `_TEST_REGISTRY` in `MainDashboard`.
- `MainDashboard._run_manual_queue()` executes checked manual tests in sequence after automated tests complete.
- Each manual test launches a `QDialog` helper from `src/ui/helpers/`.
- Helpers run in-process via `dialog.exec()` (blocks until closed). Result is read from `dialog.result_str`.

### Helper Dialogs (`src/ui/helpers/`)

All 7 helper dialogs are `QDialog` subclasses:

| File | Class | test_type |
|------|-------|-----------|
| `display_dialog.py` | `DisplayDialog` | `display_color` |
| `keyboard_dialog.py` | `KeyboardDialog` | `keyboard_test` |
| `speakers_dialog.py` | `SpeakersDialog` | `speakers_test` |
| `touchpad_dialog.py` | `TouchpadDialog` | `touchpad_test` |
| `usb_dialog.py` | `UsbDialog(port_type)` | `usb_test_a` / `usb_test_c` |
| `hdmi_dialog.py` | `HdmiDialog` | `hdmi_test` |
| `webcam_dialog.py` | `WebcamDialog` | `webcam_test` |

**Pattern:** `dialog = SomeDialog(parent); dialog.run(); result = dialog.result_str`
**result_str:** always `"pass"` / `"fail"` / `"skip"`

**P/F/S keyboard shortcuts:** Override `keyPressEvent`. `P` = pass (when unlocked), `F` = fail, `S` = skip. Skip shortcuts when code entry has focus (speakers dialog).

**Locked pass pattern** (speakers, touchpad, keyboard): Pass is disabled until the user completes required steps. `self._pass_unlocked` controls enable/disable state.

**Speakers spoken code:**
- TTS spoken code: `"The code is " + ", ".join(digits)` — e.g. `"The code is 2, 7, 4, 1"`.
- If TTS fails: show `"TTS unavailable — mark Fail or Skip"`. **Never reveal the code on screen.**
- Wrong code: show `"try again or replay"` only — do not hint at the correct code.

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

### Stylesheet (`src/ui/stylesheet.py`)

Single `QSS_DARK` string applied at app level. Key color tokens:
- Background `#0d1117`, Surface `#161b22`, Border `#30363d`
- Accent `#3b82f6`, Text `#e6edf3`, Muted `#7d8590`
- Pass `#22c55e`, Warn `#f59e0b`, Fail `#ef4444`

Dynamic QSS properties (set via `setProperty` + `unpolish`/`polish`):
- `QFrame[class="test-card"][status="running/pass/warn/fail/error/skip"]` — border color
- `QPushButton[class="primary"]` — accent fill
- `QPushButton[class="toggle"][checked="true"]` — selected state

### PyInstaller Notes

- Templates bundled via `--add-data "src/report/templates:src/report/templates"`
- Keyboard XML layouts bundled via `--add-data "src/ui/keyboards:src/ui/keyboards"`
- PySide6 bundled via `--collect-all PySide6`
- `is_frozen()` checks `sys._MEIPASS`; use `get_exe_dir()` when locating bundled assets
- `wmi` is Windows-only (platform-conditional in `pyproject.toml`) — no manual exclusion needed
- No subprocess helper dispatch — all helpers run in-process as QDialogs

### Manual Test Dialog Flow

`MainDashboard._run_next_manual()` pops the next manual item from the queue and launches its dialog. After the dialog closes, `_on_manual_result(result: str)` handles `"pass"` / `"fail"` / `"skip"`. On any result the queue advances to the next item; when empty, report generation is triggered.
