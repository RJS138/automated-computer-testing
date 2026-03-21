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
TouchstoneWindow (QMainWindow)
  └─ QStackedWidget
       ├─ index 0: JobSetupPage     (startup — fill job info, then Start Testing)
       └─ index 1: TestDashboardPage (test execution — categories, Run All, Generate Report)
```

`app_window.py` owns the `QStackedWidget`. Navigating between pages is done by calling `setCurrentIndex()`. Shared state lives on the window instance: `window.job_info`, `window.test_results`, `window.manual_items`.

- **"▶ Start Testing"** (JobSetupPage) → validates Customer Name + Job #, emits `start_testing(job_info)`, app_window switches to index 1 and calls `TestDashboardPage.on_page_entered(job_info)`.
- **"← New Job"** (TestDashboardPage header) → confirms if tests running, resets state, emits `new_job_requested`, app_window switches to index 0 and calls `JobSetupPage.reload_recent_jobs()`.

### Main Window (`src/ui/app_window.py`)

- `TouchstoneWindow(QMainWindow)` — `QStackedWidget` as central widget, dark theme applied at QApplication level
- Shared state: `job_info`, `test_results`, `manual_items`
- `--dev-manual` flag: pre-populates a dummy `JobInfo`, switches to index 1, fires `dev_trigger_display()` after 500 ms

### Automated Tests (`src/tests/`)

- All tests are `async`, subclass `BaseTest`, and populate a `TestResult` in-place via `mark_pass()` / `mark_warn()` / `mark_fail()`.
- `TestDashboardPage` runs each test in a **`TestWorker(QThread)`** whose `run()` calls `asyncio.run(test.safe_run())`. Three groups:
  - **system_info**: launched independently on page entry; result populates `DeviceBanner` and enables Generate Report
  - **Parallel** (on Run All): `network`, `battery`, `gpu` (+ `fan` in Advanced mode)
  - **Sequential** (after parallel): `cpu` → `ram` → `storage` (+ `smart_deep`, `ram_extended` in Advanced mode)
- Test durations are controlled by constants in `src/config.py` (`CPU_STRESS_QUICK`, etc.).
- Advanced-only tests (`smart_deep`, `ram_extended`, `fan`) are hidden/skipped in Simple mode.

### Manual Tests

- Manual tests (display, keyboard, touchpad, speakers, USB-A, USB-C, HDMI, webcam) are defined in `_TEST_REGISTRY` in `TestDashboardPage`.
- `TestDashboardPage._run_manual_queue()` runs all enabled manual tests in sequence after automated tests complete (Run All path only). Individual cards can also be triggered manually via `run_requested` signal.
- Each manual test launches a `QDialog` helper from `src/ui/helpers/`.
- Helpers run in-process via `dialog.run()` (blocks until closed). Result is read from `dialog.result_str`.

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
- Background `#09090b`, Surface `#18181b`, Elevated `#27272a`, Border `#3f3f46`
- Accent `#3b82f6`, Text `#fafafa`, Muted `#71717a`
- Pass `#22c55e`, Warn `#f59e0b`, Fail `#ef4444`

**Design rules (do not break these):**
- No `border: 1px solid` anywhere — use background color differences to distinguish elements. Inputs use `#27272a` bg, surfaces use `#18181b`, page bg is `#09090b`.
- No borders on containers (panels, cards, form sections) — background tint only.

**QSS property selectors are unreliable — do not use them for toggled state.**
`setProperty("class", "seg-left")` + `[checked="true"]` selectors silently fail when set in `__init__` before the widget is shown. `refresh_style` (unpolish/polish) is also a no-op before first show. **Always use direct `setStyleSheet()` for any state that changes.** Define ON/OFF style constants at module level and swap them explicitly:
```python
# Good — reliable
btn.setStyleSheet(_SEG_L_ON if selected else _SEG_L_OFF)

# Bad — silently fails before widget is shown
btn.setProperty("checked", "true")
refresh_style(btn)
```

**Vertical centering in QHBoxLayout:** use per-widget alignment, not layout-level:
```python
# Good
row.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

# Bad — does not reliably center fixed-height items
row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
row.addWidget(btn)
```

### Dashboard UI Structure (`src/ui/widgets/`)

- `DashboardCard` — flat row (52px tall, `#18181b` bg, 8px radius) showing one test. Layout: `[name] → [detail/elapsed] → [STATUS text] → [Run btn]`. All items added with `AlignVCenter`. Status shown as coloured text, no background pill.
- `CategorySection` — collapsible section header + `QVBoxLayout` of `DashboardCard` rows (5px spacing). No grid, no mini-badges. Header is plain uppercase label + collapse arrow.
- Segmented buttons (Simple/Advanced, Before/After, format picker) all use direct `_SEG_L_ON/OFF` / `_SEG_R_ON/OFF` style constants — see `src/ui/widgets/header_bar.py` for the pattern.

### PyInstaller Notes

- Templates bundled via `--add-data "src/report/templates:src/report/templates"`
- Keyboard XML layouts bundled via `--add-data "src/ui/keyboards:src/ui/keyboards"`
- PySide6 bundled via `--collect-all PySide6`
- `is_frozen()` checks `sys._MEIPASS`; use `get_exe_dir()` when locating bundled assets
- `wmi` is Windows-only (platform-conditional in `pyproject.toml`) — no manual exclusion needed
- No subprocess helper dispatch — all helpers run in-process as QDialogs

### Manual Test Dialog Flow

`TestDashboardPage._run_manual_queue()` iterates enabled manual tests in registry order and calls `_run_single_manual(entry)` for each. The dialog is created, `dialog.run()` is called (blocks), result is read from `dialog.result_str`, `TestResult` is updated, and the card is refreshed. After all manual tests complete, `_on_all_tests_done()` clears the running-all state. Individual manual tests can also be triggered by clicking a card's Run button.
