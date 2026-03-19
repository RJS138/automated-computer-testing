# Phase 2 — Main Dashboard Redesign Spec

**Date:** 2026-03-19
**Status:** Draft

## Goal

Replace the current single-layout main dashboard with a two-phase flow: a dedicated Job Setup screen shown at startup, and a Test Dashboard screen the technician works in. Tests are grouped by hardware category rather than automated/manual. The Generate Report button is always available once device info populates — never gated behind test completion.

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Job entry UX | Two-phase (setup screen → test screen) | Clean separation; fields have room to breathe |
| Starting point | New Job form + collapsible Recent Jobs | Fast for new jobs, convenient for returning ones |
| Test grouping | Hardware categories | Maps to what the customer cares about |
| Device info placement | Horizontal banner below top bar | Frees full width for tests |
| Simple/Advanced toggle | Test screen top bar | Belongs to test execution, not job setup |
| Report generation | Always-available button in device banner | Enabled as soon as system_info completes |

---

## 1. Architecture

### 1.1 Screen Stack

`TouchstoneWindow` gains a `QStackedWidget` as its central widget with two pages:

```
QStackedWidget (index 0 = setup, index 1 = dashboard)
  ├─ JobSetupPage       (shown at startup)
  └─ TestDashboardPage  (shown after "Start Testing")
```

`MainDashboard` is **replaced** by `TestDashboardPage`. Its test execution logic (workers, queues, result handling) is preserved — only the layout changes.

### 1.2 Navigation

- **"Start Testing"** on `JobSetupPage` → validates fields, builds `JobInfo`, switches stack to index 1, triggers system_info auto-run
- **"← New Job"** on `TestDashboardPage` → confirms if tests are running, resets state, switches stack to index 0

### 1.3 File Map

| File | Action |
|------|--------|
| `src/ui/pages/job_setup_page.py` | **New** — job form + recent jobs |
| `src/ui/pages/test_dashboard_page.py` | **New** — replaces `main_dashboard.py` layout |
| `src/ui/widgets/device_banner.py` | **New** — horizontal spec strip + overall badge + generate report button |
| `src/ui/widgets/category_section.py` | **New** — collapsible test category with header badges |
| `src/ui/widgets/dashboard_card.py` | **Modify** — minor layout tweaks for category context |
| `src/ui/widgets/header_bar.py` | **Rewrite** — remove job fields, add simple/advanced toggle |
| `src/ui/app_window.py` | **Modify** — switch central widget to QStackedWidget |
| `src/ui/pages/main_dashboard.py` | **Delete** — replaced by test_dashboard_page.py |

---

## 2. Job Setup Page (`src/ui/pages/job_setup_page.py`)

### 2.1 Layout

Vertically centred in the window, max-width 520px:

```
[App header bar — Touchstone title + ⚙ settings icon]
─────────────────────────────────────────────────────
  "New Job"  (display title, 20px/600)
  "Fill in the details below, then start testing."  (subtitle)

  ┌─ Form card (bg-surface, border, border-radius 8px) ──────┐
  │  Customer Name [___________________]  Job # [_________]  │
  │  Device Description [_________________________________]   │
  │  ─────────────────────────────────────────────────────   │
  │  Report Type   [Before] [After]                          │
  └──────────────────────────────────────────────────────────┘

  [▶ Start Testing]  (primary button, full width)

  ┌─ Recent Jobs (collapsible) ──────────────────────────────┐
  │  Recent Jobs                              ▾ show         │
  │  ──────────────────────────────────────────────────────  │
  │  Smith Repair — MacBook Pro    WO#142 · Mar 15           │
  │                                [Before ✓]  [After —]     │
  │  Jones Electronics — Dell XPS  WO#141 · Mar 14           │
  │                                [Before ✓]  [After ✓]     │
  └──────────────────────────────────────────────────────────┘
```

### 2.2 Form Behaviour

- **Customer Name**: `QLineEdit` — plain text entry
- **Job #**: `QLineEdit` — plain text entry
- **Device Description**: `QLineEdit` — plain text entry
- **Before / After toggle**: segmented `QPushButton` pair (`class="seg-left"` / `class="seg-right"`), Before selected by default
- **Start Testing button**: `QPushButton(class="primary")`, enabled only when Customer Name and Job # are non-empty. Displays "▶ Start Testing".

### 2.3 Recent Jobs Panel

- Populated by `scan_existing_jobs()` from `file_manager.py` at page load
- Sorted by most-recently-modified first, capped at 10 entries
- Each row shows: customer + device description, job#, date, Before badge, After badge
  - Badge is `pass`-coloured if that report exists, `muted`-coloured if not
- Clicking a row pre-fills Customer Name, Job #, Device Description from the job metadata. Before/After is set to whichever report **does not yet exist** for that job (i.e., if Before exists → select After). If both exist → leave current selection.
- Panel is collapsed by default. Toggle arrow expands/collapses with a `QPropertyAnimation` on `maximumHeight`.

### 2.4 Validation

"Start Testing" is disabled (opacity 0.4, cursor not-allowed) when either Customer Name or Job # is empty. No other validation — device description is optional.

---

## 3. Test Dashboard Page (`src/ui/pages/test_dashboard_page.py`)

### 3.1 Layout

```
[HeaderBar — compact job info + Simple/Advanced + Run All + ← New Job + ⚙]
[DeviceBanner — spec fields + Overall badge + Generate Report button]
─────────────────────────────────────────────────────────────────────────
[Scrollable test area]
  CategorySection: ⚡ Performance
  CategorySection: 📡 Connectivity
  CategorySection: 🖥 Display & Input
  CategorySection: 🔊 Audio & Video
  CategorySection: 🔋 Power
```

### 3.2 Test Execution Logic

All test execution logic from `main_dashboard.py` is preserved unchanged:
- `TestWorker(QThread)` per automated test
- Parallel group (system_info, network, battery, gpu, display) + sequential queue (cpu → ram → storage)
- Manual test queue via `_run_manual_queue()` / `_on_manual_result()`
- `window.job_info`, `window.test_results`, `window.manual_items` shared state on window

**On entry (after "Start Testing"):**
1. Reset all `TestResult` objects to `WAITING`
2. Auto-run the parallel group immediately (system_info runs first alongside others)
3. Sequential queue starts after parallel group completes

### 3.3 Test Category Mapping

| Category | Tests (in order) |
|---|---|
| ⚡ Performance | cpu, ram, storage |
| 📡 Connectivity | network, usb_a, usb_c, hdmi |
| 🖥 Display & Input | display, keyboard, touchpad |
| 🔊 Audio & Video | speakers, webcam |
| 🔋 Power | battery, fan |

Advanced-only tests (smart_deep, ram_extended) appear in Performance when Advanced mode is active.

---

## 4. Header Bar (rewrite)

`src/ui/widgets/header_bar.py` is rewritten to serve the test dashboard only. Job entry fields are removed.

### 4.1 Layout

Single row:

```
[Customer · WO#142 · BEFORE badge]  [Simple | Advanced]  [▶ Run All]  [← New Job]  [⚙]
```

- **Job info** (left, flex-1): `QLabel` showing `"{customer} · {job_number}"` + `QLabel` with Before/After badge
- **Simple / Advanced toggle**: segmented button pair. Default: Simple. Switching reconfigures `CategorySection` instances to show/hide advanced tests.
- **Run All button**: `QPushButton(class="primary")`. Label: `"▶ Run All"` while idle, `"◼ Stop"` while running (not yet implemented — keep as Run All for Phase 2, stop is Phase 4).
- **← New Job link**: `QPushButton(class="ghost")`, returns to setup screen
- **Settings gear**: `QPushButton(class="icon-btn")`, opens `SettingsDialog`

### 4.2 Elevation Warning

Preserved from current implementation: second row shown only when not running with admin privileges. Hidden otherwise.

---

## 5. Device Banner (`src/ui/widgets/device_banner.py`)

### 5.1 Layout

Horizontal strip, `bg-base` background, `border-subtle` bottom border:

```
[MODEL ___] [SERIAL ___] [OS ___] [CPU ___] [RAM ___] [STORAGE ___]  [Overall PASS]  [Generate Report]
```

- Each field: label (`text-muted`, 10px, uppercase) above value (`text-primary`, 13px, monospace font)
- Fields not available yet show `—` in `text-muted`
- **Overall badge**: colour-coded by worst result across all completed tests (pass/warn/fail). Shows `—` while no tests have completed.
- **Generate Report button**: `QPushButton` styled as a bordered card (not `class="primary"`). Label: "Generate\nReport" (two lines). **Enabled** as soon as `system_info` completes (device fields populate). Disabled (opacity 0.4) before that.

### 5.2 Data Population

`DeviceBanner.update_from_result(result: TestResult)` is called by `TestDashboardPage` whenever `system_info` completes. Maps `result.data` keys:

| Banner field | data key |
|---|---|
| MODEL | `chassis_model` or `board_model` (+ `apple_model_number` on macOS) |
| SERIAL | `board_serial` |
| OS | `os_name` + `os_version` |
| CPU | `processor_marketing` + `cpu_cores` |
| RAM | `ram_total` |
| STORAGE | first item from `storage_list` (model + size) |

### 5.3 Overall Badge

`DeviceBanner.update_overall(results: list[TestResult])` called after each test completes. Worst status wins: fail > warn > pass > running > waiting.

### 5.4 Report Generation

"Generate Report" button emits a `generate_report_requested` signal. `TestDashboardPage` connects this to the existing `ReportWorker` logic (unchanged from current implementation). After generation, a status message is shown in the header bar elevation row (or a toast — same mechanism as current).

---

## 6. Category Section (`src/ui/widgets/category_section.py`)

### 6.1 Layout

```
┌─ Category header ──────────────────────────────────────────────────┐
│  ⚡ PERFORMANCE          [CPU PASS] [RAM PASS] [STORAGE FAIL]  ▾   │
├────────────────────────────────────────────────────────────────────┤
│  [DashboardCard: CPU]  [DashboardCard: RAM]  [DashboardCard: Storage] │
└────────────────────────────────────────────────────────────────────┘
```

- **Header row**: category icon + name (`text-secondary`, 11px, uppercase, 0.08em letter-spacing), mini status badges per test, expand/collapse arrow
- **Mini badges**: `QLabel(class="badge")` per test, showing test short name + status colour. Hidden for tests not yet run (replaced with `—`).
- **Card grid**: `QGridLayout` with 3 columns for Performance/Display&Input/Power (≤3 tests), 4 columns for Connectivity (4 tests), 2 columns for Audio&Video
- **Collapse behaviour**: clicking the header row toggles card grid visibility via `QPropertyAnimation` on `maximumHeight`. All sections expanded by default.

### 6.2 Advanced Mode

`CategorySection.set_advanced(enabled: bool)`:
- In Performance: shows/hides `smart_deep` and `ram_extended` cards; column count adjusts accordingly
- Other categories: no change (no advanced-only tests outside Performance)

### 6.3 Card Updates

`CategorySection.update_card(result: TestResult)` — finds the `DashboardCard` for `result.name`, calls its existing `update(result)` method. Header badges update simultaneously.

---

## 7. Dashboard Card (minor update)

`src/ui/widgets/dashboard_card.py` — layout preserved. One change: the checkbox (used in Advanced mode for selective run) is now always visible when Advanced mode is active, regardless of category. Previously it was controlled by the card's `advanced_only` flag.

---

## 8. Simple vs Advanced Mode

| Mode | Effect |
|---|---|
| Simple | advanced-only tests hidden in Performance category |
| Advanced | all tests visible; checkboxes shown on each card |

Mode is toggled via the segmented button in the header bar. `TestDashboardPage` calls `category_section.set_advanced(enabled)` on all sections when mode changes.

---

## 9. State Reset ("← New Job")

When the technician clicks "← New Job":
1. If any tests are `RUNNING`: show a `QMessageBox` confirmation ("Tests are still running. Return to job setup?")
2. Cancel/interrupt running workers
3. Reset all `TestResult` objects to `WAITING` status
4. Clear `window.job_info`, `window.test_results`, `window.manual_items`
5. Clear `DeviceBanner` fields back to `—`
6. Reset header bar labels
7. Switch stack to index 0 (JobSetupPage)
8. Reload recent jobs list in `JobSetupPage`

---

## 10. Out of Scope

- Report diff (before/after comparison) — Phase 4
- Theme toggle in settings — Phase 3
- Stop/cancel individual running tests — Phase 4
- Notes field on job setup — Phase 3 (settings)
- Advanced per-test checkboxes controlling Run All selection — existing behaviour preserved as-is
