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
            tag.setStyleSheet("color: #60a5fa; font-size: 9px; font-weight: 600;")
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
        self._status_lbl.setStyleSheet("color: #7d8590; font-size: 10px; font-weight: 600;")
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
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 600;")

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
