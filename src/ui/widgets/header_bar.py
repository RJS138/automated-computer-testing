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

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.ui.stylesheet import refresh_style
from src.ui.widgets.toggle_switch import ToggleSwitch
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
    if os_name == "windows":
        import ctypes as _ctypes

        params = " ".join(sys.argv)
        _ctypes.windll.shell32.ShellExecuteW(  # type: ignore[attr-defined]
            None, "runas", sys.executable, params, None, 1
        )
    else:
        # macOS/Linux: launch elevated process without blocking the GUI thread
        subprocess.Popen(["sudo", sys.executable, *sys.argv])
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
    settings_clicked = Signal()
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
        root.setSpacing(4)

        # ── Row 1: all controls ──────────────────────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        _V = Qt.AlignmentFlag.AlignVCenter
        _LBL = "color: #7d8590; font-size: 13px;"
        _TOGGLE_LBL_ON = "color: #e6edf3; font-weight: 600; font-size: 13px;"
        _TOGGLE_LBL_OFF = "color: #7d8590; font-size: 13px;"
        _TOGGLE_LBL_ACT = "color: #60a5fa; font-weight: 600; font-size: 13px;"

        # Customer field — editable combo showing known jobs
        cust_lbl = QLabel("Customer:")
        cust_lbl.setStyleSheet(_LBL)
        row1.addWidget(cust_lbl, alignment=_V)

        self._customer_combo = QComboBox()
        self._customer_combo.setEditable(True)
        self._customer_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        _le = self._customer_combo.lineEdit()
        if _le is not None:
            _le.setPlaceholderText("Name")
        self._customer_combo.setFixedWidth(160)
        row1.addWidget(self._customer_combo, alignment=_V)

        # Job # field
        job_lbl = QLabel("Job #:")
        job_lbl.setStyleSheet(_LBL)
        row1.addWidget(job_lbl, alignment=_V)

        self._job_field = QLineEdit()
        self._job_field.setPlaceholderText("12345")
        self._job_field.setFixedWidth(90)
        row1.addWidget(self._job_field, alignment=_V)

        # Device field
        dev_lbl = QLabel("Device:")
        dev_lbl.setStyleSheet(_LBL)
        row1.addWidget(dev_lbl, alignment=_V)

        self._device_field = QLineEdit()
        self._device_field.setPlaceholderText("Model")
        self._device_field.setFixedWidth(140)
        row1.addWidget(self._device_field, alignment=_V)

        # Flexible spacer
        row1.addStretch()

        # ── Helper: build a labelled toggle container ─────────────────────────
        def _toggle_group(left: str, right: str) -> tuple[QWidget, QHBoxLayout]:
            w = QWidget()
            lay = QHBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(7)
            return w, lay

        # ── Mode toggle: Simple —●— Advanced ─────────────────────────────────
        mode_row, mode_lay = _toggle_group("Simple", "Advanced")

        self._simple_lbl = QLabel("Simple")
        self._simple_lbl.setStyleSheet(_TOGGLE_LBL_ON)
        mode_lay.addWidget(self._simple_lbl, alignment=_V)

        self._mode_toggle = ToggleSwitch(checked=False)
        mode_lay.addWidget(self._mode_toggle, alignment=_V)

        self._advanced_lbl = QLabel("Advanced")
        self._advanced_lbl.setStyleSheet(_TOGGLE_LBL_OFF)
        mode_lay.addWidget(self._advanced_lbl, alignment=_V)

        row1.addWidget(mode_row, alignment=_V)
        row1.addSpacing(16)

        # ── Report toggle: Before —●— After ──────────────────────────────────
        report_row, report_lay = _toggle_group("Before", "After")

        self._before_lbl = QLabel("Before")
        self._before_lbl.setStyleSheet(_TOGGLE_LBL_ON)
        report_lay.addWidget(self._before_lbl, alignment=_V)

        self._report_toggle = ToggleSwitch(checked=False)
        report_lay.addWidget(self._report_toggle, alignment=_V)

        self._after_lbl = QLabel("After")
        self._after_lbl.setStyleSheet(_TOGGLE_LBL_OFF)
        report_lay.addWidget(self._after_lbl, alignment=_V)

        row1.addWidget(report_row, alignment=_V)
        row1.addSpacing(12)

        # ── Action button ────────────────────────────────────────────────────
        self._action_btn = QPushButton("\u25b6 Run All")
        self._action_btn.setProperty("class", "primary")
        self._action_btn.setFixedHeight(32)
        self._action_btn.setEnabled(False)
        refresh_style(self._action_btn)
        row1.addWidget(self._action_btn, alignment=_V)

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFixedSize(32, 32)
        self._settings_btn.setToolTip("Settings")
        row1.addWidget(self._settings_btn, alignment=_V)

        root.addLayout(row1)

        # store style strings for reuse in _select_*
        self._toggle_lbl_on = _TOGGLE_LBL_ON
        self._toggle_lbl_off = _TOGGLE_LBL_OFF
        self._toggle_lbl_act = _TOGGLE_LBL_ACT

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
        # Mode toggle
        self._mode_toggle.toggled.connect(
            lambda checked: self._select_mode("advanced" if checked else "simple")
        )

        # Report type toggle
        self._report_toggle.toggled.connect(
            lambda checked: self._select_report_type("after" if checked else "before")
        )

        # Action button
        self._action_btn.clicked.connect(self._on_action_clicked)

        # Customer selection → auto-fill
        self._customer_combo.activated.connect(self._on_customer_activated)

        # Job # validation
        self._job_field.textChanged.connect(self._update_action_button)
        self._customer_combo.editTextChanged.connect(self._update_action_button)

        # Restart button
        self._restart_btn.clicked.connect(_restart_as_admin)

        # Settings button
        self._settings_btn.clicked.connect(self.settings_clicked)

        # Load existing jobs into customer combo
        self._refresh_customers()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def job_number(self) -> str:
        """Return current job number text."""
        return self._job_field.text()

    def customer(self) -> str:
        """Return current customer text."""
        return self._customer_combo.currentText()

    def device(self) -> str:
        """Return current device text."""
        return self._device_field.text()

    def mode(self) -> str:
        """Return current mode: 'simple' | 'advanced'."""
        return "advanced" if self._mode_toggle.isChecked() else "simple"

    def report_type(self) -> str:
        """Return current report type: 'before' | 'after'."""
        return "after" if self._report_toggle.isChecked() else "before"

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
        """Update label styles and emit mode_changed signal."""
        is_advanced = mode == "advanced"
        self._simple_lbl.setStyleSheet(self._toggle_lbl_off if is_advanced else self._toggle_lbl_on)
        self._advanced_lbl.setStyleSheet(
            self._toggle_lbl_act if is_advanced else self._toggle_lbl_off
        )
        self.mode_changed.emit(mode)

    def _select_report_type(self, report_type: str) -> None:
        """Update label styles and emit report_type_changed signal."""
        is_after = report_type == "after"
        self._before_lbl.setStyleSheet(self._toggle_lbl_off if is_after else self._toggle_lbl_on)
        self._after_lbl.setStyleSheet(self._toggle_lbl_act if is_after else self._toggle_lbl_off)
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

    def _refresh_customers(self) -> None:
        """Populate the customer combo with jobs found in the reports directory."""
        from src.utils.file_manager import scan_existing_jobs

        self._known_jobs: list[dict] = scan_existing_jobs()

        self._customer_combo.blockSignals(True)
        self._customer_combo.clear()
        for job in self._known_jobs:
            label = job["customer_name"]
            if job["job_number"]:
                label += f"  —  Job #{job['job_number']}"
            self._customer_combo.addItem(label)
        # Restore blank state so placeholder shows
        self._customer_combo.setCurrentIndex(-1)
        self._customer_combo.blockSignals(False)

    def _on_customer_activated(self, index: int) -> None:
        """Auto-fill fields and set report type when an existing job is selected."""
        if index < 0 or index >= len(self._known_jobs):
            return
        job = self._known_jobs[index]

        # Fill text fields
        self._customer_combo.setEditText(job["customer_name"])
        if job["job_number"]:
            self._job_field.setText(job["job_number"])
        if job["device_description"]:
            self._device_field.setText(job["device_description"])

        # If a before report exists, default to after
        if job["has_before"] and not self._report_toggle.isChecked():
            self._report_toggle.setChecked(True)
            self._select_report_type("after")
        elif not job["has_before"] and self._report_toggle.isChecked():
            self._report_toggle.setChecked(False)
            self._select_report_type("before")
