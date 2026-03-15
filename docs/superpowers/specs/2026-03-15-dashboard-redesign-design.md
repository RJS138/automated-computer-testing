# Dashboard Redesign — Design Spec

**Date:** 2026-03-15
**Status:** Approved

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

## Layout

### Header Bar (always visible)

A compact bar fixed at the top of the window containing:

| Element | Detail |
|---------|--------|
| Customer field | Editable text input |
| Job # field | Editable text input |
| Device field | Editable text input |
| Mode toggle | Simple \| Advanced (pill buttons) |
| Report type toggle | Before \| After (pill buttons) |
| Primary action button | "▶ Run All" → becomes "✓ Generate Report" when all selected tests are done |

The Generate Report button only appears (replaces Run All) when every checked test has a final result (pass/warn/fail/skip). Clicking it generates HTML + PDF and opens the HTML in the default browser, same as today.

### Body — Two Columns

**Left column — System Info Panel (fixed width ~180px)**

Populated automatically when `system_info` test completes. Shows:
- Model, Serial number
- OS name + version
- Firmware version
- CPU, RAM, Storage, GPU, Display, Battery (hardware summary)
- Overall status badge at the bottom (PASS / WARN / FAIL / Waiting)

**Right column — Test Grid (fills remaining space, scrollable)**

Divided into two labelled sections:
1. **Automated Tests** — 3-column grid
2. **Manual Tests** — 4-column grid

---

## Test Cards

Each test is a card showing:
- Test name
- Status badge: WAITING / RUNNING / PASS / WARN / FAIL / SKIP / ERROR
- One-line detail (e.g. "Apple M3 Pro · 12-core")
- One-line sub-detail (e.g. "Max 72°C · Avg load 94%")
- Action button: "▶ Run" or "↺ Re-run" depending on state

In **Advanced mode**, each card also shows a checkbox (top-right corner) to include or exclude the test from Run All.

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

### Simple
- Runs all automated tests (parallel group first, sequential group after — same execution strategy as today)
- Then prompts for manual tests one at a time (each launches its full-screen dialog in sequence)
- Generate Report button appears when last test is done

### Advanced
- Runs only checked tests
- Same parallel/sequential execution strategy for automated tests
- Manual tests that are checked are queued and prompted in order after automated tests finish
- Generate Report button appears when all checked tests have a result

---

## Report Generation

Unchanged from today — `FullReport` assembled from `JobInfo` + `list[TestResult]`, rendered to HTML via Jinja2 and PDF via ReportLab. Opens HTML in browser after saving. Before/After comparison report generated automatically if both exist in the job folder.

The Before/After toggle in the header bar replaces the current `ModeSelectPage` report type selection.

---

## Extensibility

New tests are added by:
1. Creating a new test module in `src/tests/` (subclass `BaseTest`)
2. Adding an entry to the test registry in the dashboard (name, display name, mode availability, group — parallel or sequential)
3. For Advanced-only tests, marking them with `advanced_only=True` in the registry

No changes to the dashboard layout or logic are required to add new tests.

---

## Navigation & App Window

`TouchstoneWindow` will initialise directly to `MainDashboard` instead of `ReadinessPage`. The `QStackedWidget` approach is retained but only used for the full-screen manual test dialogs (which are `QDialog` subclasses, not stacked pages). Page-to-page navigation is eliminated.

---

## What Is Not Changing

- All 7 manual test `QDialog` helpers — unchanged
- `BaseTest` / `TestResult` / `JobInfo` / `FullReport` data models — unchanged
- Report rendering pipeline (HTML + PDF) — unchanged
- `TestWorker(QThread)` execution pattern — unchanged
- Stylesheet and colour tokens — unchanged
- Platform detection and per-platform test branches — unchanged
- USB drive detection and report directory layout — unchanged
