# Settings Modal & Advanced Mode Redesign

## Goal

Move report-saving settings out of the inline advanced panel into a persistent gear-icon modal accessible from the header bar, and redesign the Advanced mode test view from a card grid into a sectioned row list with richer per-row detail.

## Architecture

Two independent UI changes that share a new `Settings` dataclass:

1. **`SettingsDialog`** — a `QDialog` launched from a new gear `QPushButton` in `HeaderBar`. Holds output format, save path, and technician notes. Replaces `ReportOptionsPanel`.
2. **`TestSectionList`** — a new widget that replaces the card grid when mode is `"advanced"`. Backed by the same `TestResult` state already on the window.

Simple mode continues to show the `DashboardCard` grid unchanged.

---

## Section 1 — Settings Modal

### Data model: `Settings` dataclass

New file: `src/models/settings.py`

Fields:
- `output_format: str = "html_pdf"` — one of `"html_pdf"`, `"html_only"`, `"pdf_only"`
- `save_path: str = ""` — populated at startup (see below)
- `notes: str = ""`

**Persistence:** ephemeral — `Settings` resets to defaults on every app restart. No disk serialisation. This matches existing `ReportOptionsPanel` behaviour.

**Default save_path:** Set once in `TouchstoneWindow.__init__` after the window is constructed by calling `find_usb_drive()`. If a USB drive is found, `save_path` is set to its string path; otherwise `str(Path.home() / "touchstone_reports")`. `find_usb_drive()` is called exactly once at startup.

### `SettingsDialog(QDialog)`

**Constructor:** `SettingsDialog(settings: Settings, parent=None)`
Receives a copy of the current settings and pre-populates all fields from it.

**Fields:**

| Field | Widget | Notes |
|---|---|---|
| Output Format | Three `QPushButton` radio group: `seg-left` / `seg-mid` / `seg-right` QSS classes | Pre-selected from `settings.output_format` |
| Save Location | `QLineEdit` + `Browse…` button (opens `QFileDialog.getExistingDirectory`) | Pre-filled from `settings.save_path` |
| Technician Notes | `QPlainTextEdit` | Pre-filled from `settings.notes` |

**Public method:** `result_settings() -> Settings`
Returns a `Settings` instance reflecting current field values. Called after `exec()` returns `Accepted`.

**Opener pattern in `MainDashboard._on_settings_clicked`:**
```
dlg = SettingsDialog(copy(window.settings), parent=self)
if dlg.exec() == QDialog.DialogCode.Accepted:
    window.settings = dlg.result_settings()
```

Cancel calls `reject()`. Save calls `accept()`.

### Header bar trigger

`HeaderBar` gains:
- A `⚙` `QPushButton` at the right end of row 1 (after the action button), always visible regardless of mode.
- A new signal: `settings_clicked = Signal()`.
- The button's `clicked` connects to `settings_clicked`.

`MainDashboard` connects `header.settings_clicked` to `_on_settings_clicked`.

The mode toggle no longer controls `ReportOptionsPanel` visibility (widget is deleted). Gear button is always accessible.

### `ReportWorker` integration

`ReportWorker.__init__` is extended to accept `settings: Settings`.

Changes inside `ReportWorker.run()`:
- **save_path:** Use `settings.save_path` as the report root. Full path: `Path(settings.save_path) / REPORTS_DIR_NAME / job.folder_name() / job.report_type.value`
- **output_format:**
  - `"html_pdf"` — render both HTML and PDF (current behaviour)
  - `"html_only"` — render HTML only, skip PDF
  - `"pdf_only"` — render PDF only, skip HTML

`MainDashboard._on_generate_report` passes `window.settings` to `ReportWorker`.

### `seg-mid` stylesheet addition

`stylesheet.py` needs a `seg-mid` rule for three-button groups (same colours as `seg-left`/`seg-right`, zero border-radius on all corners, right border removed):

```css
QPushButton[class="seg-mid"] {
    background-color: #161b22;
    color: #7d8590;
    border: 1px solid #30363d;
    padding: 7px 14px;
    font-weight: 500;
    min-height: 32px;
    border-radius: 0px;
    border-right-width: 0px;
}
QPushButton[class="seg-mid"]:hover {
    background-color: #1c2128;
    color: #e6edf3;
}
QPushButton[class="seg-mid"][checked="true"] {
    background-color: #1e3a5f;
    border-color: #3b82f6;
    color: #60a5fa;
    font-weight: 600;
}
```

---

## Section 2 — Advanced Mode Test List

### Checkbox state: shared `_test_enabled` dict

`MainDashboard` maintains:
```
self._test_enabled: dict[str, bool] = {name: True for name in ALL_TEST_NAMES}
```

Both `DashboardCard` (simple) and `TestRowWidget` (advanced) read their initial checked state from this dict and write back to it on toggle. `_on_run_all` and `_run_manual_queue` read from `_test_enabled` — not from individual widgets.

On mode switch, the newly visible view initialises each checkbox from `_test_enabled`.

### Mode switching safety

`MainDashboard._on_mode_changed` returns early (no-op) while `_running_all` is `True`. The mode switch takes effect after the run completes.

When `TestSectionList` is first shown, it calls `init_from_results(self._results)` to render any already-completed test states correctly.

### Widget: `TestSectionList(QWidget)`

**Constructor:** `TestSectionList(test_enabled: dict[str, bool], parent=None)`
Receives a reference to the shared `_test_enabled` dict.

**Public methods:**
- `update_row(name: str, status: TestStatus, summary: str) -> None` — updates the status badge and detail line for the named row.
- `init_from_results(results: dict[str, TestResult]) -> None` — called once on first show; calls `update_row` for each result.

**Signal:** `run_requested = Signal(str)` — emitted when a row's Run/Re-run button is clicked; propagated from `TestRowWidget.run_requested`.

### Sections and test membership

| Section label | Test names |
|---|---|
| ⚡ Performance | `cpu`, `ram`, `storage`, `smart_deep` (adv), `ram_extended` (adv) |
| 🔋 Battery | `battery` |
| 🌐 Connectivity | `network` |
| 🖥 Display & GPU | `gpu`, `display_color` (manual) |
| ⌨ Input | `keyboard` (manual), `touchpad` (manual) |
| 🔌 Ports & Output | `usb_test_a` (manual), `usb_test_c` (manual), `hdmi_test` (manual) |
| 🎧 Audio & Camera | `speakers_test` (manual), `webcam_test` (manual) |
| 🌀 System | `fan` (adv) |

### Widget: `TestRowWidget(QWidget)`

Row layout (left to right):
- **QCheckBox** — no label. Reads initial state from `test_enabled[name]`; on toggle writes `test_enabled[name] = checked`.
- **Name QLabel** — `font-weight: 600; font-size: 13px`. Appends `MANUAL` tag (blue) or `ADV` pill (blue) as applicable.
- **Detail QLabel** — `font-size: 11px; color: #7d8590`. Shows `TestResult.summary` when available; static placeholder description when `WAITING`.
- **Status QLabel** — coloured by status: WAITING `#7d8590`, RUNNING `#f59e0b` with suffix " …", PASS `#22c55e`, WARN `#f59e0b`, FAIL `#ef4444`, ERROR `#ef4444`, SKIP `#484f58`.
- **Run/Re-run QPushButton** — `height: 26px`. Label is "Run" for `WAITING/SKIP/ERROR`, "Re-run" otherwise. Emits `run_requested = Signal(str)` with test name.

Rows are separated by 1px `#21262d` dividers inside a `QFrame[class="card"]`.

### `_apply_result` dual-update

```python
def _apply_result(self, name: str) -> None:
    result = self._results[name]
    card = self._cards.get(name)
    if card:
        card.set_status(result.status, result.summary, result.data.get("card_sub_detail", ""))
    self._section_list.update_row(name, result.status, result.summary)
```

---

## Files to Create

| File | Purpose |
|---|---|
| `src/models/settings.py` | `Settings` dataclass |
| `src/ui/widgets/settings_dialog.py` | `SettingsDialog(QDialog)` |
| `src/ui/widgets/test_section_list.py` | `TestSectionList(QWidget)` + `TestRowWidget(QWidget)` |

## Files to Modify

| File | Change |
|---|---|
| `src/ui/widgets/header_bar.py` | Add `⚙` button + `settings_clicked` signal |
| `src/ui/pages/main_dashboard.py` | Wire gear; add `TestSectionList`; mode-switch logic; `_apply_result` dual-update; `_test_enabled` dict; remove `ReportOptionsPanel` |
| `src/ui/app_window.py` | Instantiate `window.settings: Settings` at startup |
| `src/ui/workers.py` | Accept `settings: Settings`; apply `output_format` and `save_path` |
| `src/ui/stylesheet.py` | Add `seg-mid` QSS rules |
| `src/models/__init__.py` | Export `Settings` |

## Files to Delete

| File | Reason |
|---|---|
| `src/ui/widgets/report_options_panel.py` | Replaced by `SettingsDialog` |
