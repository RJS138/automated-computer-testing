# Dashboard Redesign — Design Spec

**Date:** 2026-03-15
**Status:** Approved (updated after spec review — 8 issues resolved)

---

## Overview

Replace the current multi-screen linear flow with a single persistent dashboard. The readiness screen is removed entirely. Everything — system info, test results, and report generation — lives on one page. The tech opens the app, fills in job details in the header bar, and works from a single view.

---

## What Changes

### Removed
- `ReadinessPage` — dependency checks before testing (removed entirely)
- `WelcomePage` — dedicated job info form screen
- `ModeSelectPage` — dedicated Quick/Full mode selection screen
- `DashboardPage` — automated tests runner screen
- `ManualTestsPage` — sequential one-at-a-time manual checklist screen
- `ReportDonePage` — dedicated report generation screen

### Replaced by
- `MainDashboard` — a single `QWidget` containing all of the above functionality

---

## Readiness Checks (formerly ReadinessPage)

The `ReadinessPage` performed four checks: elevation (sudo/admin), `smartctl`, `mactop`, and `reportlab`. These move as follows:

- **Elevation / admin rights** — checked silently at startup. If elevation is required (Linux/macOS for SMART data, Windows for WMI access), a non-blocking amber badge appears in the header bar ("⚠ Not elevated — Restart as Admin") with a clickable button that re-launches with elevation. Tests that need elevation degrade gracefully without it (skip the elevation-dependent step, mark WARN rather than blocking the app).
- **smartctl** — if not found, the Storage card shows WARN with "smartctl not found — install smartmontools for SMART data". Speed test still runs.
- **mactop / powermetrics** — if not available, CPU temperature monitoring falls back to psutil or skips temp data. Stress results still shown.
- **reportlab** — if not found, PDF generation is silently skipped. HTML report is always generated. Generate Report button works regardless.

There is no blocking gate. The app always reaches the dashboard.

---

## App Window & State

`TouchstoneWindow` initialises directly to `MainDashboard`, set as the central widget. The `QStackedWidget` is removed — it is no longer needed.

Shared state remains on `TouchstoneWindow`:
- `job_info: JobInfo | None` — constructed from header fields when Run All is clicked
- `test_results: list[TestResult]` — populated by `MainDashboard` as tests complete
- `manual_items: list[TestResult]` — individual manual test results (subset of `test_results`)

**`--dev-manual` flag:** `TouchstoneWindow` detects this flag and, after `MainDashboard` is shown, immediately triggers the Display dialog as if the tech had clicked its Run button. Preserves the fast dev loop.

---

## Layout

### Header Bar (always visible)

A compact bar fixed at the top of the window:

| Element | Detail |
|---------|--------|
| Customer field | Editable text input (optional) |
| Job # field | Editable text input — **required** before Run All is enabled |
| Device field | Editable text input (optional) |
| Mode toggle | Simple \| Advanced (pill buttons) |
| Report type toggle | Before \| After (pill buttons) |
| Primary action button | "▶ Run All" (disabled until Job # is non-empty) → "✓ Generate Report" when all selected tests have a final result |

**Validation:** Run All is disabled until Job # contains at least one non-whitespace character. Clearing Job # after tests are done also disables Generate Report.

**Elevation warning:** If the process lacks required privileges, an amber badge appears in the header with a "Restart as Admin" button.

### Body — Two Columns

**Left column — System Info Panel (fixed width ~180px)**

`system_info` runs automatically and silently when the dashboard loads. It does not appear as a card in the test grid and is not part of Run All. The panel shows a loading indicator until it completes, then populates:
- Model, Serial number
- OS name + version
- Firmware version
- CPU, RAM, Storage, GPU, Display, Battery (from system_info result data)
- Overall status badge — recalculates whenever any test result changes

**Right column — Test Grid (fills remaining space, scrollable)**

Two labelled sections:
1. **Automated Tests** — 3-column grid
2. **Manual Tests** — 4-column grid

---

## Test Cards

Each test is a card showing:
- Test name
- Status badge: WAITING / RUNNING / PASS / WARN / FAIL / SKIP / ERROR
- One-line detail (e.g. "Apple M3 Pro · 12-core")
- One-line sub-detail (e.g. "Max 72°C · Avg load 94%")
- Action button: "▶ Run" (WAITING) or "↺ Re-run" (any completed state)

In **Advanced mode**, each card also shows a checkbox (top-right corner) to include or exclude the test from Run All.

### Re-run Behaviour

Clicking "↺ Re-run":
- Resets that card to RUNNING and re-executes the test
- Updates the card and recalculates the overall status badge when done
- Does **not** reset other cards or remove the Generate Report button — if all other checked tests are still complete, Generate Report stays visible and updates after the re-run finishes
- The Re-run button is hidden on all cards while a Run All sequence is actively in progress

---

## Mode: Simple vs Advanced

### Simple (default)
- One-click Run All
- No checkboxes
- Core test set only (see test catalogue below)
- No report options panel

### Advanced
- Checkboxes on every card — uncheck to exclude from Run All
- Report Options panel appears above the test grid with:
  - Output format (HTML + PDF / HTML only / PDF only)
  - Save path (editable, defaults to USB drive or app dir)
  - Technician notes field
- Additional tests unlocked (marked with an "Advanced" badge):
  - SMART Deep — extended drive diagnostics (reallocated sectors, pending sectors, uncorrectable errors)
  - RAM Extended — full pattern sweep (walking ones, checkerboard, etc.)
  - Fan Test — reads RPM for all connected fans at idle and under load
  - More to be added in future without changing the dashboard structure

---

## Test Catalogue

### Automated (Simple + Advanced)
| Test | What it does |
|------|-------------|
| CPU Stress | Stress test + temperature monitoring |
| RAM Scan | Memory pattern scan |
| Storage | Speed test + SMART health |
| Battery | Health %, cycle count, capacity |
| GPU | Model, VRAM (info only) |
| Network | Ping connectivity check |

### Automated (Advanced only)
| Test | What it does |
|------|-------------|
| SMART Deep | Extended SMART self-test via smartctl |
| RAM Extended | Full pattern sweep (longer, more thorough than RAM Scan) |
| Fan Test | Enumerate connected fans, read RPM at idle and load |

### Manual (Simple + Advanced)
| Test | Interaction |
|------|-------------|
| Display | Full-screen colour cycle dialog |
| Keyboard | Full-screen key registration dialog |
| Touchpad | Full-screen drag test dialog |
| Speakers | Full-screen audio code entry dialog |
| USB-A | Full-screen connector insertion dialog |
| USB-C | Full-screen connector insertion dialog |
| HDMI | Full-screen video output dialog |
| Webcam | Full-screen camera preview dialog |

Manual tests launch the existing `QDialog` helpers full-screen (unchanged from today). Dashboard is hidden while the dialog runs; returns to dashboard on close with result recorded.

---

## Run All Behaviour

### Execution sequence

1. Construct `JobInfo` from current header field values and store on `window.job_info`
2. Run automated tests — parallel group first, sequential group after, same `TestWorker(QThread)` pattern as today
3. Once all automated tests complete, begin the manual test queue

### Manual test queue

`MainDashboard` maintains an internal ordered list of checked manual tests. After automated tests finish:
- The first queued manual dialog is launched via `dialog.run()` — this calls `showFullScreen()` then `QDialog.exec()` internally, which blocks the calling code while running its own event loop. The main window remains visible behind the dialog but is not interactable while the dialog is open.
- On dialog close, `dialog.result_str` ("pass"/"fail"/"skip") is written to the test result and the card updates
- The next queued dialog launches automatically until the queue is exhausted

If the user manually clicks a manual card's Run button while Run All is active, the click is ignored (individual Run buttons are disabled during active Run All).

### Simple vs Advanced

- **Simple:** all automated tests run, all manual tests queue
- **Advanced:** only checked tests run; only checked manual tests queue

---

## Report Generation

The Generate Report button appears (replacing Run All in the header) when every checked test has a final result (PASS, WARN, FAIL, SKIP, or ERROR). WAITING and RUNNING states do not satisfy the condition.

Clicking Generate Report:
1. Assembles `FullReport` from `window.job_info` + `window.test_results`
2. Renders HTML via Jinja2 (unchanged)
3. Renders PDF via ReportLab (unchanged, skipped if not available)
4. Saves to job directory via `FileManager` (unchanged)
5. Generates comparison report if the other report type exists (unchanged)
6. Opens HTML in default browser
7. A status message appears briefly in the header confirming the save path

After generating, a "New Job" button appears in the header. Clicking it resets all fields and card states, re-runs `system_info`, and re-enables Run All.

The Before/After toggle in the header replaces the `ModeSelectPage` report type selection.

---

## Extensibility

New tests are added by:
1. Creating a new test module in `src/tests/` (subclass `BaseTest`)
2. Adding an entry to `MainDashboard._TEST_REGISTRY` — a list of dicts:

```python
{
    "name": "fan",              # matches TestResult.name
    "display_name": "Fan Test", # shown on card
    "cls": FanTest,             # BaseTest subclass
    "group": "parallel",        # "parallel" or "sequential"
    "kind": "automated",        # "automated" or "manual"
    "advanced_only": True,      # True = hidden in Simple mode
    # manual tests only:
    "dialog_cls": None,
    "dialog_kwargs": {},
}
```

No changes to the dashboard layout or scheduling logic are required to add new tests.

---

## Navigation & App Window

`TouchstoneWindow` initialises directly to `MainDashboard` set as the central widget. The `QStackedWidget` is removed. Manual test dialogs are `QDialog` subclasses and run their own event loop — they are not part of any widget stack. Page-to-page navigation is eliminated.

---

## What Is Not Changing

- All 7 manual test `QDialog` helpers — unchanged
- `BaseTest` / `TestResult` / `JobInfo` / `FullReport` data models — unchanged
- Report rendering pipeline (HTML + PDF) — unchanged
- `TestWorker(QThread)` execution pattern — unchanged
- Stylesheet and colour tokens — unchanged
- Platform detection and per-platform test branches — unchanged
- USB drive detection and report directory layout — unchanged
