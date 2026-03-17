# Settings Modal & Advanced Mode Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inline ReportOptionsPanel with a gear-icon settings modal, and replace the Advanced mode card grid with a sectioned row list.

**Architecture:** Two independent UI layers share a new `Settings` dataclass on `TouchstoneWindow`. `SettingsDialog` replaces `ReportOptionsPanel` entirely. `TestSectionList` is added to `MainDashboard` alongside the existing card grid and toggled visible/hidden based on mode.

**Tech Stack:** PySide6, Python 3.12+, uv, existing QSS dark theme in `src/ui/stylesheet.py`

**No automated tests exist in this project.** Verification steps use `uv run touchstone` and visual inspection.

---

## Chunk 1: Settings Modal Side

### Task 1: `Settings` dataclass

**Files:**
- Create: `src/models/settings.py`
- Modify: `src/models/__init__.py`

- [ ] **Step 1: Create `src/models/settings.py`**

```python
"""Settings — ephemeral app-level settings (reset each launch)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Settings:
    """Ephemeral report settings. Not persisted to disk."""

    output_format: str = "html_pdf"  # "html_pdf" | "html_only" | "pdf_only"
    save_path: str = ""
    notes: str = ""
```

- [ ] **Step 2: Export from `src/models/__init__.py`**

Replace the existing content with:

```python
from .job import JobInfo, ReportType, TestMode
from .report import FullReport
from .settings import Settings
from .test_result import TestResult, TestStatus

__all__ = [
    "FullReport",
    "JobInfo",
    "ReportType",
    "Settings",
    "TestMode",
    "TestResult",
    "TestStatus",
]
```

- [ ] **Step 3: Verify app still launches**

```bash
cd "/Users/robertsaunders/Code/Automated PC Testing/pc-tester"
uv run touchstone &
sleep 3 && kill %1
```

Expected: no import errors printed to terminal.

- [ ] **Step 4: Commit**

```bash
git add src/models/settings.py src/models/__init__.py
git commit -m "feat: add Settings dataclass"
```

---

### Task 2: `seg-mid` QSS rule

**Files:**
- Modify: `src/ui/stylesheet.py` (around line 393 — after `seg-right` block)

- [ ] **Step 1: Add `seg-mid` rules to `QSS_DARK`**

In `src/ui/stylesheet.py`, find the block ending with the `seg-right` rules (around line 408). After that closing `}` and before the next comment, insert:

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

- [ ] **Step 2: Commit**

```bash
git add src/ui/stylesheet.py
git commit -m "feat: add seg-mid QSS rule for three-button groups"
```

---

### Task 3: `SettingsDialog`

**Files:**
- Create: `src/ui/widgets/settings_dialog.py`

- [ ] **Step 1: Create `src/ui/widgets/settings_dialog.py`**

```python
"""SettingsDialog — modal for report output settings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.models.settings import Settings
from src.ui.stylesheet import refresh_style


class SettingsDialog(QDialog):
    """Modal dialog for report output settings.

    Usage:
        dlg = SettingsDialog(copy(window.settings), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            window.settings = dlg.result_settings()
    """

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings  # caller passes a copy; no need to copy again
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        # ── Output Format ─────────────────────────────────────────────────────
        root.addWidget(self._section_label("Output Format"))

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(0)

        self._btn_html_pdf = QPushButton("HTML + PDF")
        self._btn_html_pdf.setProperty("class", "seg-left")
        self._btn_html_pdf.setCheckable(False)
        self._btn_html_pdf.clicked.connect(lambda: self._select_format("html_pdf"))

        self._btn_html_only = QPushButton("HTML only")
        self._btn_html_only.setProperty("class", "seg-mid")
        self._btn_html_only.setCheckable(False)
        self._btn_html_only.clicked.connect(lambda: self._select_format("html_only"))

        self._btn_pdf_only = QPushButton("PDF only")
        self._btn_pdf_only.setProperty("class", "seg-right")
        self._btn_pdf_only.setCheckable(False)
        self._btn_pdf_only.clicked.connect(lambda: self._select_format("pdf_only"))

        fmt_row.addWidget(self._btn_html_pdf)
        fmt_row.addWidget(self._btn_html_only)
        fmt_row.addWidget(self._btn_pdf_only)
        fmt_row.addStretch()
        root.addLayout(fmt_row)

        self._select_format(settings.output_format)

        # ── Save Location ─────────────────────────────────────────────────────
        root.addWidget(self._section_label("Save Location"))

        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        self._path_edit = QLineEdit(settings.save_path)
        path_row.addWidget(self._path_edit, stretch=1)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        root.addLayout(path_row)

        # ── Technician Notes ──────────────────────────────────────────────────
        root.addWidget(self._section_label("Technician Notes"))
        self._notes_edit = QPlainTextEdit(settings.notes)
        self._notes_edit.setPlaceholderText("Technician notes…")
        self._notes_edit.setMaximumHeight(80)
        root.addWidget(self._notes_edit)

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("class", "section-title")
        return lbl

    def _select_format(self, fmt: str) -> None:
        self._settings.output_format = fmt
        for btn, key in (
            (self._btn_html_pdf, "html_pdf"),
            (self._btn_html_only, "html_only"),
            (self._btn_pdf_only, "pdf_only"),
        ):
            btn.setProperty("checked", "true" if fmt == key else "false")
            refresh_style(btn)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Save Location", self._path_edit.text()
        )
        if path:
            self._path_edit.setText(path)

    # ── Public API ────────────────────────────────────────────────────────────

    def result_settings(self) -> Settings:
        """Return Settings reflecting current dialog state. Call after exec() → Accepted."""
        return Settings(
            output_format=self._settings.output_format,
            save_path=self._path_edit.text().strip(),
            notes=self._notes_edit.toPlainText(),
        )
```

- [ ] **Step 2: Verify app still launches**

```bash
uv run touchstone &
sleep 3 && kill %1
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/ui/widgets/settings_dialog.py
git commit -m "feat: add SettingsDialog"
```

---

### Task 4: Gear button in `HeaderBar`

**Files:**
- Modify: `src/ui/widgets/header_bar.py`

- [ ] **Step 1: Add `settings_clicked` signal**

At the top of the `HeaderBar` class signals block (around line 92), add after `new_job_clicked`:

```python
settings_clicked = Signal()
```

- [ ] **Step 2: Add gear button to `_build_ui`**

In `_build_ui`, find the line that adds `self._action_btn` to `row1` (around line 216):
```python
row1.addWidget(self._action_btn, alignment=_V)
```

After that line, add:

```python
self._settings_btn = QPushButton("⚙")
self._settings_btn.setFixedSize(32, 32)
self._settings_btn.setToolTip("Settings")
row1.addWidget(self._settings_btn, alignment=_V)
```

- [ ] **Step 3: Wire signal in `_connect_signals`**

At the end of `_connect_signals`, add:

```python
self._settings_btn.clicked.connect(self.settings_clicked)
```

- [ ] **Step 4: Run the app and verify gear button appears**

```bash
uv run touchstone
```

Expected: a `⚙` button appears at the right end of the header bar. Clicking it does nothing yet (signal not wired in dashboard).

- [ ] **Step 5: Commit**

```bash
git add src/ui/widgets/header_bar.py
git commit -m "feat: add gear settings button to HeaderBar"
```

---

### Task 5: Init `window.settings` and wire gear button in dashboard

**Files:**
- Modify: `src/ui/app_window.py`
- Modify: `src/ui/pages/main_dashboard.py`

- [ ] **Step 1: Init `window.settings` in `TouchstoneWindow.__init__`**

In `src/ui/app_window.py`, add this import at the top with other model imports:

```python
from src.models.settings import Settings
from src.utils.file_manager import find_usb_drive
```

In `TouchstoneWindow.__init__`, after the existing state assignments (`self.job_info = None` etc.), add:

```python
# Default save path — detect USB once at startup
_usb = find_usb_drive()
self.settings = Settings(
    save_path=str(_usb) if _usb else str(Path.home() / "touchstone_reports")
)
```

Also add `from pathlib import Path` to `app_window.py` imports if not present.

- [ ] **Step 2: Add type annotation to class body**

In `TouchstoneWindow`, alongside the existing class-level annotations, add:

```python
settings: Settings
```

- [ ] **Step 3: Wire gear button in `MainDashboard`**

In `MainDashboard.__init__`, in the signal connections block (around line 370), add:

```python
self._header.settings_clicked.connect(self._on_settings_clicked)
```

Add this new method to `MainDashboard` (after `_on_new_job`):

```python
def _on_settings_clicked(self) -> None:
    """Open the settings modal."""
    from src.ui.widgets.settings_dialog import SettingsDialog

    from copy import copy

    from PySide6.QtWidgets import QDialog

    dlg = SettingsDialog(copy(self._window.settings), parent=self)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        self._window.settings = dlg.result_settings()
```

- [ ] **Step 4: Run the app and test the settings dialog**

```bash
uv run touchstone
```

Expected:
- Gear button opens the SettingsDialog modal
- Three output format buttons highlight the selected one (HTML+PDF by default)
- Browse button opens a folder picker
- Save updates `window.settings`, Cancel discards

- [ ] **Step 5: Commit**

```bash
git add src/ui/app_window.py src/ui/pages/main_dashboard.py
git commit -m "feat: init window.settings and wire gear button to SettingsDialog"
```

---

### Task 6: Update `ReportWorker` to use `Settings`

**Files:**
- Modify: `src/ui/workers.py`
- Modify: `src/ui/pages/main_dashboard.py`

- [ ] **Step 1: Update `ReportWorker.__init__`**

In `src/ui/workers.py`, change the `ReportWorker.__init__` signature and body:

```python
def __init__(self, job, results: list, settings, parent=None) -> None:
    super().__init__(parent)
    self._job = job
    self._results = results
    self._settings = settings
```

- [ ] **Step 2: Update `ReportWorker.run()` to respect output_format and save_path**

Replace the `run()` method body with:

```python
def run(self) -> None:
    try:
        from pathlib import Path

        from src.config import REPORTS_DIR_NAME
        from src.report.diff import generate_comparison
        from src.report.generator import assemble_report
        from src.report.html_render import render_html
        from src.report.pdf_render import render_pdf

        job = self._job
        results = self._results
        fmt = self._settings.output_format  # "html_pdf" | "html_only" | "pdf_only"
        report_type = job.report_type.value

        # Build report object
        report = assemble_report(job, results)

        # Derive save directory from settings.save_path
        base = Path(self._settings.save_path)
        report_dir = base / REPORTS_DIR_NAME / job.folder_name() / report_type
        job_dir = base / REPORTS_DIR_NAME / job.folder_name()
        report_dir.mkdir(parents=True, exist_ok=True)

        html_path = report_dir / f"{report_type}.html"
        pdf_path = report_dir / f"{report_type}.pdf"

        html_content: str = ""

        if fmt in ("html_pdf", "html_only"):
            self.status.emit("Rendering HTML…")
            html_content = render_html(report)
            html_path.write_text(html_content, encoding="utf-8")

        if fmt in ("html_pdf", "pdf_only"):
            self.status.emit("Rendering PDF…")
            if not html_content:
                # pdf_only: render HTML in-memory to feed to PDF renderer
                html_content = render_html(report)
            render_pdf(html_content, pdf_path)

        # open_path: prefer HTML when available, fall back to PDF
        open_path: Path = html_path if html_path.exists() else pdf_path

        # Comparison report (only when both before and after exist)
        other_type = "after" if report_type == "before" else "before"
        other_html = job_dir / other_type / f"{other_type}.html"
        if other_html.exists() and html_path.exists():
            self.status.emit("Generating comparison report…")
            comparison_html = generate_comparison(job_dir, job)
            if comparison_html:
                comp_html_path = job_dir / "comparison.html"
                comp_html_path.write_text(comparison_html, encoding="utf-8")
                if fmt in ("html_pdf", "pdf_only"):
                    render_pdf(comparison_html, job_dir / "comparison.pdf")
                open_path = comp_html_path

        self.status.emit("Reports saved.")
        self.done.emit(open_path.as_uri(), str(pdf_path) if pdf_path.exists() else "")

    except Exception as exc:
        self.error.emit(str(exc))
```

- [ ] **Step 3: Pass `settings` when constructing `ReportWorker` in `MainDashboard`**

In `src/ui/pages/main_dashboard.py`, in `_on_generate_report`, change:

```python
self._report_worker = ReportWorker(job=job, results=results, parent=self)
```

to:

```python
self._report_worker = ReportWorker(
    job=job, results=results, settings=self._window.settings, parent=self
)
```

- [ ] **Step 4: Run the app and verify report generation**

```bash
uv run touchstone
```

Run a few tests, click Generate Report. Verify:
- Report saves to the path shown in Settings dialog
- With "HTML only" selected in settings, only `.html` file is created
- With "HTML + PDF", both files are created

- [ ] **Step 5: Commit**

```bash
git add src/ui/workers.py src/ui/pages/main_dashboard.py
git commit -m "feat: thread Settings through ReportWorker for save path and output format"
```

---

## Chunk 2: Advanced Mode Test List

### Task 7: `TestSectionList` and `TestRowWidget`

**Files:**
- Create: `src/ui/widgets/test_section_list.py`

The section-to-test mapping uses the exact `name` strings from `MainDashboard._TEST_REGISTRY`:
`cpu`, `ram`, `storage`, `smart_deep`, `ram_extended`, `battery`, `network`, `gpu`, `display`, `keyboard`, `touchpad`, `speakers`, `usb_a`, `usb_c`, `hdmi`, `webcam`, `fan`.

- [ ] **Step 1: Create `src/ui/widgets/test_section_list.py`**

```python
"""TestSectionList — Advanced mode row-based test view."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.models.test_result import TestResult

# ── Section definitions ────────────────────────────────────────────────────────

_SECTIONS: list[tuple[str, list[str]]] = [
    ("⚡  Performance", ["cpu", "ram", "storage", "smart_deep", "ram_extended"]),
    ("🔋  Battery", ["battery"]),
    ("🌐  Connectivity", ["network"]),
    ("🖥  Display & GPU", ["gpu", "display"]),
    ("⌨  Input", ["keyboard", "touchpad"]),
    ("🔌  Ports & Output", ["usb_a", "usb_c", "hdmi"]),
    ("🎧  Audio & Camera", ["speakers", "webcam"]),
    ("🌀  System", ["fan"]),
]

# Static placeholder descriptions shown while WAITING
_PLACEHOLDERS: dict[str, str] = {
    "cpu": "Sustained load · temperature · throttle check",
    "ram": "Capacity · speed · available memory",
    "storage": "Read/write throughput · drive health",
    "smart_deep": "Full SMART attribute scan",
    "ram_extended": "Full memory stress test",
    "battery": "Capacity · cycle count · charge rate",
    "network": "Wi-Fi · Bluetooth · ping · NIC count",
    "gpu": "GPU model · VRAM · driver",
    "display": "Full-screen color grid · dead pixel check",
    "keyboard": "Every key registered",
    "touchpad": "Click · tap · gesture",
    "speakers": "TTS spoken code verification",
    "usb_a": "Device detection",
    "usb_c": "Device detection",
    "hdmi": "External display output",
    "webcam": "Live preview check",
    "fan": "Fan detection · RPM reading",
}

# Tests that are manual (dialog-based)
_MANUAL_TESTS: frozenset[str] = frozenset(
    ["display", "keyboard", "touchpad", "speakers", "usb_a", "usb_c", "hdmi", "webcam"]
)

# Tests that are advanced-only
_ADV_TESTS: frozenset[str] = frozenset(["smart_deep", "ram_extended", "fan"])

# Status colours
_STATUS_COLORS: dict[str, str] = {
    "waiting": "#7d8590",
    "running": "#f59e0b",
    "pass": "#22c55e",
    "warn": "#f59e0b",
    "fail": "#ef4444",
    "error": "#ef4444",
    "skip": "#484f58",
}


# ── TestRowWidget ──────────────────────────────────────────────────────────────


class TestRowWidget(QWidget):
    """A single row representing one test in the Advanced mode list."""

    run_requested = Signal(str)  # emits test name

    def __init__(
        self,
        name: str,
        display_name: str,
        test_enabled: dict[str, bool],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._test_enabled = test_enabled
        self._status = "waiting"

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(10)

        # Checkbox
        self._check = QCheckBox()
        self._check.setChecked(test_enabled.get(name, True))
        self._check.toggled.connect(self._on_check_toggled)
        row.addWidget(self._check)

        # Name + detail
        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        name_col.setContentsMargins(0, 0, 0, 0)

        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_row.setContentsMargins(0, 0, 0, 0)

        self._name_lbl = QLabel(display_name)
        self._name_lbl.setStyleSheet("font-weight: 600; font-size: 13px;")
        name_row.addWidget(self._name_lbl)

        if name in _MANUAL_TESTS:
            tag = QLabel("MANUAL")
            tag.setStyleSheet(
                "color: #60a5fa; font-size: 9px; font-weight: 600;"
            )
            name_row.addWidget(tag)
        elif name in _ADV_TESTS:
            tag = QLabel("ADV")
            tag.setStyleSheet(
                "color: #60a5fa; font-size: 9px; font-weight: 600;"
                "background: #1e3a5f; padding: 1px 5px; border-radius: 3px;"
            )
            name_row.addWidget(tag)

        name_row.addStretch()
        name_col.addLayout(name_row)

        self._detail_lbl = QLabel(_PLACEHOLDERS.get(name, ""))
        self._detail_lbl.setStyleSheet("color: #7d8590; font-size: 11px;")
        name_col.addWidget(self._detail_lbl)

        row.addLayout(name_col, stretch=1)

        # Status label
        self._status_lbl = QLabel("WAITING")
        self._status_lbl.setStyleSheet(f"color: #7d8590; font-size: 10px; font-weight: 600;")
        self._status_lbl.setFixedWidth(60)
        row.addWidget(self._status_lbl)

        # Run / Re-run button
        self._run_btn = QPushButton("Run")
        self._run_btn.setFixedHeight(26)
        self._run_btn.setStyleSheet("font-size: 11px; padding: 2px 10px;")
        self._run_btn.clicked.connect(lambda: self.run_requested.emit(self._name))
        row.addWidget(self._run_btn)

    # ── Checkbox ──────────────────────────────────────────────────────────────

    def _on_check_toggled(self, checked: bool) -> None:
        self._test_enabled[self._name] = checked

    def sync_checkbox(self) -> None:
        """Re-read checked state from _test_enabled (called on mode switch)."""
        self._check.blockSignals(True)
        self._check.setChecked(self._test_enabled.get(self._name, True))
        self._check.blockSignals(False)

    # ── Status update ─────────────────────────────────────────────────────────

    def update_status(self, status: str, summary: str) -> None:
        self._status = status
        label = status.upper()
        if status == "running":
            label = "RUNNING…"
        self._status_lbl.setText(label)
        color = _STATUS_COLORS.get(status, "#7d8590")
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-size: 10px; font-weight: 600;"
        )

        # Update detail line
        if summary and status != "waiting":
            self._detail_lbl.setText(summary)
        elif status == "waiting":
            self._detail_lbl.setText(_PLACEHOLDERS.get(self._name, ""))

        # Update button label
        btn_label = "Run" if status in ("waiting", "skip", "error") else "Re-run"
        self._run_btn.setText(btn_label)


# ── TestSectionList ────────────────────────────────────────────────────────────


class TestSectionList(QWidget):
    """Advanced mode: tests displayed as sectioned rows."""

    run_requested = Signal(str)  # propagated from TestRowWidget

    def __init__(
        self,
        test_enabled: dict[str, bool],
        display_names: dict[str, str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._rows: dict[str, TestRowWidget] = {}

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        for section_label, test_names in _SECTIONS:
            # Filter to tests that actually exist in display_names
            names = [n for n in test_names if n in display_names]
            if not names:
                continue

            # Section header
            lbl = QLabel(section_label)
            lbl.setProperty("class", "section-title")
            layout.addWidget(lbl)

            # Card frame containing rows
            card = QFrame()
            card.setProperty("class", "card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(0)

            for i, name in enumerate(names):
                row = TestRowWidget(
                    name=name,
                    display_name=display_names[name],
                    test_enabled=test_enabled,
                    parent=card,
                )
                row.run_requested.connect(self.run_requested)
                card_layout.addWidget(row)
                self._rows[name] = row

                # Divider between rows (not after last)
                if i < len(names) - 1:
                    divider = QFrame()
                    divider.setFrameShape(QFrame.Shape.HLine)
                    divider.setStyleSheet("color: #21262d; background: #21262d;")
                    divider.setFixedHeight(1)
                    card_layout.addWidget(divider)

            layout.addWidget(card)

        layout.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Public API ────────────────────────────────────────────────────────────

    def update_row(self, name: str, status: str, summary: str) -> None:
        """Update status badge and detail line for the named row."""
        row = self._rows.get(name)
        if row is not None:
            row.update_status(status, summary)

    def init_from_results(self, results: dict[str, TestResult]) -> None:
        """Populate all rows from current result state (called on first show)."""
        for name, result in results.items():
            self.update_row(name, result.status.value, result.summary or "")

    def sync_checkboxes(self) -> None:
        """Re-read all checkbox states from _test_enabled (call on mode switch)."""
        for row in self._rows.values():
            row.sync_checkbox()
```

- [ ] **Step 2: Verify import is clean**

```bash
cd "/Users/robertsaunders/Code/Automated PC Testing/pc-tester"
uv run python -c "from src.ui.widgets.test_section_list import TestSectionList; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ui/widgets/test_section_list.py
git commit -m "feat: add TestSectionList and TestRowWidget for Advanced mode"
```

---

### Task 8: Wire `TestSectionList` into `MainDashboard`

**Files:**
- Modify: `src/ui/pages/main_dashboard.py`

This is the largest single edit. Follow each step carefully.

- [ ] **Step 1: Add imports at top of `main_dashboard.py`**

Add these to the existing imports:

```python
from src.ui.widgets.test_section_list import TestSectionList
```

Remove the existing `ReportOptionsPanel` import:
```python
# DELETE this line:
from src.ui.widgets.report_options_panel import ReportOptionsPanel
```

- [ ] **Step 2: Add `_test_enabled` dict in `__init__`**

After `self._results: dict[str, TestResult] = {}` (around line 245), add:

```python
# Shared checkbox state — read/written by both card grid and TestSectionList
self._test_enabled: dict[str, bool] = {
    entry["name"]: True for entry in self._TEST_REGISTRY
}
```

- [ ] **Step 3: Remove `ReportOptionsPanel` from `__init__`**

Find and delete these lines (around line 282–284):

```python
# DELETE:
self._report_options = ReportOptionsPanel(self)
self._report_options.hide()
right_layout.addWidget(self._report_options)
```

- [ ] **Step 4: Add `TestSectionList` to the right column in `__init__`**

After the `right_scroll = QScrollArea()` block is set up and `right_layout.addWidget(right_scroll, stretch=1)` is called (around line 322), add:

```python
# Advanced mode: sectioned row list (hidden by default — shown when mode="advanced")
_display_names = {e["name"]: e["display_name"] for e in self._TEST_REGISTRY}
self._section_list = TestSectionList(
    test_enabled=self._test_enabled,
    display_names=_display_names,
    parent=right_col,
)
self._section_list.hide()
self._section_list.run_requested.connect(self._on_run_requested)
right_layout.addWidget(self._section_list, stretch=1)
```

- [ ] **Step 5: Update `_on_mode_changed`**

Replace the existing `_on_mode_changed` method:

```python
def _on_mode_changed(self, mode: str) -> None:
    """Switch between Simple (card grid) and Advanced (section list) views."""
    if self._running_all:
        return  # ignore mode changes during a run

    is_advanced = mode == "advanced"

    # Show/hide advanced-only cards in the simple grid
    for entry in self._TEST_REGISTRY:
        if entry["advanced_only"]:
            card = self._cards.get(entry["name"])
            if card is not None:
                card.setVisible(is_advanced)

    # Checkboxes visible on cards in advanced mode
    for entry in self._TEST_REGISTRY:
        card = self._cards.get(entry["name"])
        if card is not None:
            card.set_advanced(is_advanced)

    if is_advanced:
        # Switch to section list
        self._section_list.sync_checkboxes()
        if not any(
            r.status.value != "waiting" for r in self._results.values()
        ):
            pass  # all waiting — no init needed
        else:
            self._section_list.init_from_results(self._results)
        # Find the scroll area holding the card grid and hide it
        self._card_scroll.hide()
        self._section_list.show()
    else:
        self._section_list.hide()
        self._card_scroll.show()
```

Note: this requires storing `right_scroll` as `self._card_scroll` in `__init__`. Go back to where `right_scroll = QScrollArea()` is constructed and change it to:

```python
self._card_scroll = QScrollArea()
self._card_scroll.setWidgetResizable(True)
self._card_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
```

Then replace all subsequent references to `right_scroll` in `__init__` with `self._card_scroll`.

- [ ] **Step 6: Update `_on_run_all` to read from `_test_enabled`**

In `_on_run_all`, replace the card-checking logic (around line 478–486):

```python
# OLD — delete these lines:
card = self._cards.get(entry["name"])
if card is None or not card.is_checked():
    continue
```

With:

```python
if not self._test_enabled.get(entry["name"], True):
    continue
```

- [ ] **Step 7: Update `_run_manual_queue` to read from `_test_enabled`**

Replace the existing list comprehension in `_run_manual_queue`:

```python
# OLD — delete:
self._manual_queue: list[dict] = [
    entry
    for entry in self._TEST_REGISTRY
    if entry["kind"] == "manual"
    and self._cards.get(entry["name"]) is not None
    and self._cards[entry["name"]].is_checked()
]
```

With:

```python
self._manual_queue: list[dict] = [
    entry
    for entry in self._TEST_REGISTRY
    if entry["kind"] == "manual" and self._test_enabled.get(entry["name"], True)
]
```

- [ ] **Step 8: Update `_apply_result` for dual-update**

Replace `_apply_result`:

```python
def _apply_result(self, name: str) -> None:
    """Update card and section list row for a completed test, clean up worker."""
    result = self._results.get(name)
    card = self._cards.get(name)
    if result and card:
        sub = result.data.get("card_sub_detail", "") if result.data else ""
        if not sub and result.error_message:
            sub = result.error_message
        card.set_status(result.status.value, result.summary or "", sub)
    if result:
        self._section_list.update_row(name, result.status.value, result.summary or "")
    self._active_workers = [w for w in self._active_workers if w.isRunning()]
    self._recalculate_overall()
```

- [ ] **Step 9: Update `_recalculate_overall` to use `_test_enabled`**

Replace the `all_done` check in `_recalculate_overall`:

```python
# OLD — delete:
all_done = all(
    r.status.value not in incomplete
    for name, r in self._results.items()
    if self._cards.get(name) and self._cards[name].is_checked()
)
```

With:

```python
all_done = all(
    r.status.value not in incomplete
    for name, r in self._results.items()
    if self._test_enabled.get(name, True)
)
```

- [ ] **Step 10: Reset `_test_enabled` on new job in `_on_new_job`**

At the end of `_on_new_job`, add:

```python
# Reset all checkboxes to enabled
for key in self._test_enabled:
    self._test_enabled[key] = True
self._section_list.sync_checkboxes()
```

- [ ] **Step 11: Run the app and test mode switching**

```bash
uv run touchstone
```

Expected:
- Simple mode: card grid visible, section list hidden — all works as before
- Toggle to Advanced: section list appears with sections, card grid hides
- All rows show correct names, MANUAL/ADV tags, WAITING state
- Checkboxes sync when toggling between modes
- Run All in Advanced mode respects unchecked rows
- Gear button opens settings dialog

- [ ] **Step 12: Commit**

```bash
git add src/ui/pages/main_dashboard.py
git commit -m "feat: wire TestSectionList into MainDashboard with mode switching and _test_enabled"
```

---

### Task 9: Remove `ReportOptionsPanel`

**Files:**
- Delete: `src/ui/widgets/report_options_panel.py`

- [ ] **Step 1: Delete the file**

```bash
git rm src/ui/widgets/report_options_panel.py
```

- [ ] **Step 2: Run app one final time to confirm clean state**

```bash
uv run touchstone
```

Expected: app launches cleanly, no import errors. Both modes work. Settings modal accessible via gear button.

- [ ] **Step 3: Final commit**

```bash
git commit -m "chore: remove ReportOptionsPanel (replaced by SettingsDialog)"
```

---

## Done

All tasks complete. Run lint as a final check:

```bash
uv run --group lint ruff check src/ && uv run --group lint ruff format --check src/
```

Fix any issues with `uv run --group lint ruff check --fix src/ && uv run --group lint ruff format src/`.
