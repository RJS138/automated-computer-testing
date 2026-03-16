"""DashboardCard widget — QFrame showing one test's status with a run button."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from ..stylesheet import refresh_style

# ── Status → badge colour ─────────────────────────────────────────────────────
_STATUS_COLORS: dict[str, str] = {
    "waiting": "#7d8590",
    "running": "#f59e0b",
    "pass": "#22c55e",
    "warn": "#f59e0b",
    "fail": "#ef4444",
    "error": "#ef4444",
    "skip": "#7d8590",
}


class DashboardCard(QFrame):
    """One card per test in the redesigned dashboard.

    Signals
    -------
    run_requested(str)
        Emitted when the Run / Re-run button is clicked; carries the test name.
    """

    run_requested = Signal(str)

    def __init__(self, name: str, display_name: str, parent=None) -> None:
        super().__init__(parent)
        self._name = name
        self._display_name = display_name

        # Wire QSS test-card rules
        self.setProperty("class", "test-card")
        self.setProperty("status", "waiting")

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(4)

        # ── Top row: name label + checkbox ────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(6)

        self._name_lbl = QLabel(self._display_name)
        self._name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._name_lbl.setStyleSheet("font-weight: 600;")
        header.addWidget(self._name_lbl)

        header.addStretch()

        self._checkbox = QCheckBox()
        self._checkbox.setChecked(True)
        self._checkbox.hide()
        header.addWidget(self._checkbox)

        outer.addLayout(header)

        # ── Status badge ──────────────────────────────────────────────────────
        self._badge_lbl = QLabel("WAITING")
        self._badge_lbl.setStyleSheet(f"color: {_STATUS_COLORS['waiting']}; font-size: 12px;")
        outer.addWidget(self._badge_lbl)

        # ── Detail lines ──────────────────────────────────────────────────────
        self._detail_lbl = QLabel("")
        self._detail_lbl.setStyleSheet("color: #7d8590; font-size: 12px;")
        outer.addWidget(self._detail_lbl)

        self._sub_detail_lbl = QLabel("")
        self._sub_detail_lbl.setStyleSheet("color: #7d8590; font-size: 12px;")
        outer.addWidget(self._sub_detail_lbl)

        # ── Run button (right-aligned) ────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._run_btn = QPushButton("▶ Run")
        self._run_btn.clicked.connect(self._on_run_clicked)
        btn_row.addWidget(self._run_btn)

        outer.addLayout(btn_row)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_status(self, status: str, detail: str = "", sub_detail: str = "") -> None:
        """Update the card's status badge, border colour, detail lines, and button label."""
        status = status.lower()
        color = _STATUS_COLORS.get(status, "#7d8590")

        self._badge_lbl.setText(status.upper())
        self._badge_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")

        self._detail_lbl.setText(detail)
        self._sub_detail_lbl.setText(sub_detail)

        self._run_btn.setText("▶ Run" if status == "waiting" else "↺ Re-run")

        self.setProperty("status", status)
        refresh_style(self)

    def set_advanced(self, enabled: bool) -> None:
        """Show or hide the checkbox (Advanced mode toggle)."""
        if enabled:
            self._checkbox.show()
        else:
            self._checkbox.hide()

    def is_checked(self) -> bool:
        """Return True if this test should be included in a run.

        When advanced mode is off the checkbox is hidden and the card is always
        considered included (returns True).  When advanced mode is on, the
        checkbox's checked state is returned directly.
        """
        if not self._checkbox.isVisible():
            return True
        return self._checkbox.isChecked()

    def set_running_all(self, active: bool) -> None:
        """Disable the run button while a Run All operation is in progress."""
        self._run_btn.setEnabled(not active)

    # ── Private slots ─────────────────────────────────────────────────────────

    def _on_run_clicked(self) -> None:
        self.run_requested.emit(self._name)
