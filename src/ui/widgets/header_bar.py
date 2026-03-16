"""HeaderBar widget — compact top bar for the new dashboard.

Layout (single row):
  [Customer: ___] [Job #: ___] [Device: ___]  [Simple|Advanced]  [Before|After]  [▶ Run All]

A second row below shows elevation warnings and transient status messages.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from src.ui.stylesheet import refresh_style
from src.utils.platform_detect import get_os

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ACTION_STATES = frozenset({"run_all", "run_all_disabled", "generate_report", "new_job"})


def _is_elevated() -> bool:
    """Return True when the process is running with admin/root privileges."""
    try:
        os_name = get_os()
        if os_name == "windows":
            try:
                return ctypes.windll.shell32.IsUserAnAdmin() != 0  # type: ignore[attr-defined]
            except Exception:
                return False
        else:
            # darwin / linux
            return os.getuid() == 0
    except Exception:
        return False


def _restart_as_admin() -> None:
    """Re-launch the current process with elevated privileges and quit."""
    os_name = get_os()
    try:
        if os_name == "windows":
            import ctypes as _ctypes

            params = " ".join(sys.argv)
            _ctypes.windll.shell32.ShellExecuteW(  # type: ignore[attr-defined]
                None, "runas", sys.executable, params, None, 1
            )
        else:
            subprocess.run(["sudo", sys.executable, *sys.argv])
    finally:
        app = QApplication.instance()
        if app is not None:
            app.quit()


# ---------------------------------------------------------------------------
# HeaderBar
# ---------------------------------------------------------------------------


class HeaderBar(QFrame):
    """Compact horizontal bar at the top of the dashboard.

    Signals
    -------
    run_all_clicked          Emitted when the action button is clicked in "run_all" state.
    generate_report_clicked  Emitted when the action button is clicked in "generate_report" state.
    new_job_clicked          Emitted when the action button is clicked in "new_job" state.
    mode_changed(str)        "simple" | "advanced"
    report_type_changed(str) "before" | "after"
    """

    run_all_clicked = Signal()
    generate_report_clicked = Signal()
    new_job_clicked = Signal()
    mode_changed = Signal(str)
    report_type_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("class", "panel")

        # Internal state
        self._action_state: str = "run_all_disabled"

        self._build_ui()
        self._connect_signals()

        # Elevation check — warn if not elevated
        if not _is_elevated():
            self.show_elevation_warning(True)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        # ── Row 1: all controls ──────────────────────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        # Customer field
        cust_lbl = QLabel("Customer:")
        cust_lbl.setStyleSheet("color: #7d8590;")
        row1.addWidget(cust_lbl)

        self._customer_field = QLineEdit()
        self._customer_field.setPlaceholderText("Name")
        self._customer_field.setFixedWidth(130)
        row1.addWidget(self._customer_field)

        # Job # field
        job_lbl = QLabel("Job #:")
        job_lbl.setStyleSheet("color: #7d8590;")
        row1.addWidget(job_lbl)

        self._job_field = QLineEdit()
        self._job_field.setPlaceholderText("12345")
        self._job_field.setFixedWidth(90)
        row1.addWidget(self._job_field)

        # Device field
        dev_lbl = QLabel("Device:")
        dev_lbl.setStyleSheet("color: #7d8590;")
        row1.addWidget(dev_lbl)

        self._device_field = QLineEdit()
        self._device_field.setPlaceholderText("Model")
        self._device_field.setFixedWidth(140)
        row1.addWidget(self._device_field)

        # Flexible spacer
        row1.addStretch()

        # ── Mode toggle: Simple | Advanced ──────────────────────────────────
        self._simple_btn = QPushButton("Simple")
        self._simple_btn.setProperty("class", "toggle")
        self._simple_btn.setProperty("checked", "true")
        self._simple_btn.setFixedHeight(32)
        refresh_style(self._simple_btn)
        row1.addWidget(self._simple_btn)

        self._advanced_btn = QPushButton("Advanced")
        self._advanced_btn.setProperty("class", "toggle")
        self._advanced_btn.setProperty("checked", "false")
        self._advanced_btn.setFixedHeight(32)
        refresh_style(self._advanced_btn)
        row1.addWidget(self._advanced_btn)

        # Separator space
        row1.addSpacing(12)

        # ── Report type toggle: Before | After ───────────────────────────────
        self._before_btn = QPushButton("Before")
        self._before_btn.setProperty("class", "toggle")
        self._before_btn.setProperty("checked", "true")
        self._before_btn.setFixedHeight(32)
        refresh_style(self._before_btn)
        row1.addWidget(self._before_btn)

        self._after_btn = QPushButton("After")
        self._after_btn.setProperty("class", "toggle")
        self._after_btn.setProperty("checked", "false")
        self._after_btn.setFixedHeight(32)
        refresh_style(self._after_btn)
        row1.addWidget(self._after_btn)

        # Separator space
        row1.addSpacing(12)

        # ── Action button ────────────────────────────────────────────────────
        self._action_btn = QPushButton("\u25b6 Run All")
        self._action_btn.setProperty("class", "primary")
        self._action_btn.setFixedHeight(32)
        self._action_btn.setEnabled(False)
        refresh_style(self._action_btn)
        row1.addWidget(self._action_btn)

        root.addLayout(row1)

        # ── Row 2: elevation warning + status message ────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        # Elevation warning label
        self._elev_lbl = QLabel("\u26a0 Not elevated \u2014 Restart as Admin")
        self._elev_lbl.setStyleSheet("color: #f59e0b; font-size: 12px;")
        self._elev_lbl.hide()
        row2.addWidget(self._elev_lbl)

        # Restart button
        self._restart_btn = QPushButton("Restart as Admin")
        self._restart_btn.setProperty("class", "warn")
        self._restart_btn.setFixedHeight(26)
        self._restart_btn.setStyleSheet("font-size: 11px; padding: 3px 10px;")
        self._restart_btn.hide()
        row2.addWidget(self._restart_btn)

        row2.addStretch()

        # Transient status message
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #7d8590; font-size: 12px;")
        self._status_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row2.addWidget(self._status_lbl)

        root.addLayout(row2)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        # Mode toggles
        self._simple_btn.clicked.connect(lambda: self._select_mode("simple"))
        self._advanced_btn.clicked.connect(lambda: self._select_mode("advanced"))

        # Report type toggles
        self._before_btn.clicked.connect(lambda: self._select_report_type("before"))
        self._after_btn.clicked.connect(lambda: self._select_report_type("after"))

        # Action button
        self._action_btn.clicked.connect(self._on_action_clicked)

        # Job # validation
        self._job_field.textChanged.connect(self._update_action_button)

        # Restart button
        self._restart_btn.clicked.connect(_restart_as_admin)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def job_number(self) -> str:
        """Return current job number text."""
        return self._job_field.text()

    def customer(self) -> str:
        """Return current customer text."""
        return self._customer_field.text()

    def device(self) -> str:
        """Return current device text."""
        return self._device_field.text()

    def mode(self) -> str:
        """Return current mode: 'simple' | 'advanced'."""
        if self._simple_btn.property("checked") == "true":
            return "simple"
        return "advanced"

    def report_type(self) -> str:
        """Return current report type: 'before' | 'after'."""
        if self._before_btn.property("checked") == "true":
            return "before"
        return "after"

    def set_action_state(self, state: str) -> None:
        """Transition the action button to the given state.

        Parameters
        ----------
        state:
            "run_all"           — Run All button, enabled.
            "run_all_disabled"  — Run All button, disabled.
            "generate_report"   — Generate Report button, enabled.
            "new_job"           — New Job button, enabled.
        """
        if state not in _ACTION_STATES:
            raise ValueError(f"Invalid action state: {state!r}")

        self._action_state = state

        if state == "run_all_disabled":
            self._action_btn.setText("\u25b6 Run All")
            self._action_btn.setProperty("class", "primary")
            self._action_btn.setEnabled(False)
        elif state == "run_all":
            self._action_btn.setText("\u25b6 Run All")
            self._action_btn.setProperty("class", "primary")
            self._action_btn.setEnabled(True)
        elif state == "generate_report":
            self._action_btn.setText("\u2713 Generate Report")
            self._action_btn.setProperty("class", "success")
            self._action_btn.setEnabled(True)
        elif state == "new_job":
            self._action_btn.setText("+ New Job")
            self._action_btn.setProperty("class", "")
            self._action_btn.setEnabled(True)

        refresh_style(self._action_btn)

    def show_elevation_warning(self, show: bool) -> None:
        """Show or hide the elevation warning row."""
        self._elev_lbl.setVisible(show)
        self._restart_btn.setVisible(show)

    def show_status_message(self, msg: str) -> None:
        """Display *msg* for 3 seconds, then clear it."""
        self._status_lbl.setText(msg)
        QTimer.singleShot(3000, lambda: self._status_lbl.clear())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _select_mode(self, mode: str) -> None:
        """Switch the mode toggle selection and emit signal."""
        is_simple = mode == "simple"
        self._simple_btn.setProperty("checked", "true" if is_simple else "false")
        self._advanced_btn.setProperty("checked", "false" if is_simple else "true")
        refresh_style(self._simple_btn)
        refresh_style(self._advanced_btn)
        self.mode_changed.emit(mode)

    def _select_report_type(self, report_type: str) -> None:
        """Switch the report type toggle selection and emit signal."""
        is_before = report_type == "before"
        self._before_btn.setProperty("checked", "true" if is_before else "false")
        self._after_btn.setProperty("checked", "false" if is_before else "true")
        refresh_style(self._before_btn)
        refresh_style(self._after_btn)
        self.report_type_changed.emit(report_type)

    def _on_action_clicked(self) -> None:
        """Route the action button click to the correct signal."""
        if self._action_state == "run_all":
            self.run_all_clicked.emit()
        elif self._action_state == "generate_report":
            self.generate_report_clicked.emit()
        elif self._action_state == "new_job":
            self.new_job_clicked.emit()

    def _update_action_button(self) -> None:
        """Enable/disable Run All based on whether job # is filled in."""
        if self._action_state not in ("run_all", "run_all_disabled"):
            return
        if self.job_number().strip():
            self.set_action_state("run_all")
        else:
            self.set_action_state("run_all_disabled")
