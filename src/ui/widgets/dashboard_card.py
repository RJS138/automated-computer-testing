"""DashboardCard widget — QFrame showing one test's status with a run button."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
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

_PROGRESS_BAR_QSS = """
QProgressBar {
    border: none;
    border-radius: 4px;
    background-color: #21262d;
    max-height: 7px;
    min-height: 7px;
}
QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 4px;
}
"""


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

        # Fixed height — all cards uniform; text wraps within this budget
        self.setFixedHeight(190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Elapsed-time ticker (1 Hz, only active while running)
        self._elapsed_s: int = 0
        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._tick)

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 10)
        outer.setSpacing(4)

        # ── Top row: name label + checkbox ────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(6)

        self._name_lbl = QLabel(self._display_name)
        self._name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._name_lbl.setStyleSheet("font-weight: 700; font-size: 17px;")
        header.addWidget(self._name_lbl)

        header.addStretch()

        self._checkbox = QCheckBox()
        self._checkbox.setChecked(True)
        self._checkbox.hide()
        header.addWidget(self._checkbox)

        outer.addLayout(header)

        # ── Status badge ──────────────────────────────────────────────────────
        self._badge_lbl = QLabel("WAITING")
        self._badge_lbl.setStyleSheet(
            f"color: {_STATUS_COLORS['waiting']}; font-size: 13px; font-weight: 600;"
        )
        outer.addWidget(self._badge_lbl)

        # ── Running state: progress bar + elapsed timer ───────────────────────
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(_PROGRESS_BAR_QSS)
        self._progress_bar.hide()
        outer.addWidget(self._progress_bar)

        self._timer_lbl = QLabel("0s")
        self._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._timer_lbl.setStyleSheet("color: #60a5fa; font-size: 22px; font-weight: 700;")
        self._timer_lbl.hide()
        outer.addWidget(self._timer_lbl)

        # ── Done state: detail lines ───────────────────────────────────────────
        self._detail_lbl = QLabel("")
        self._detail_lbl.setStyleSheet("color: #e6edf3; font-size: 15px; font-weight: 500;")
        self._detail_lbl.setWordWrap(True)
        outer.addWidget(self._detail_lbl)

        self._sub_detail_lbl = QLabel("")
        self._sub_detail_lbl.setStyleSheet("color: #7d8590; font-size: 13px;")
        self._sub_detail_lbl.setWordWrap(True)
        outer.addWidget(self._sub_detail_lbl)

        # Push button to bottom
        outer.addStretch(1)

        # ── Run button (right-aligned) ────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._run_btn = QPushButton("▶ Run")
        self._run_btn.clicked.connect(self._on_run_clicked)
        btn_row.addWidget(self._run_btn)

        outer.addLayout(btn_row)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_status(self, status: str, detail: str = "", sub_detail: str = "") -> None:
        """Update badge, border colour, running/done widgets, and button label."""
        status = status.lower()
        color = _STATUS_COLORS.get(status, "#7d8590")

        self._badge_lbl.setText(status.upper())
        self._badge_lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600;")

        is_running = status == "running"

        if is_running:
            # Reset and start elapsed timer
            self._elapsed_s = 0
            self._timer_lbl.setText("0s")
            if not self._ticker.isActive():
                self._ticker.start()
            # Show running widgets, hide detail lines
            self._progress_bar.show()
            self._timer_lbl.show()
            self._detail_lbl.hide()
            self._sub_detail_lbl.hide()
        else:
            # Stop timer, hide running widgets, show detail lines
            self._ticker.stop()
            self._progress_bar.hide()
            self._timer_lbl.hide()
            self._detail_lbl.setText(detail)
            self._sub_detail_lbl.setText(sub_detail)
            self._detail_lbl.show()
            self._sub_detail_lbl.show()

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

    def _tick(self) -> None:
        """Increment the elapsed timer display by one second."""
        self._elapsed_s += 1
        if self._elapsed_s < 60:
            self._timer_lbl.setText(f"{self._elapsed_s}s")
        else:
            m = self._elapsed_s // 60
            s = self._elapsed_s % 60
            self._timer_lbl.setText(f"{m}:{s:02d}")

    def _on_run_clicked(self) -> None:
        self.run_requested.emit(self._name)
