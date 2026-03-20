"""HeaderBar — compact job info + Simple/Advanced toggle + Run All + New Job + Settings."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.models.job import JobInfo
from src.ui.stylesheet import refresh_style


class HeaderBar(QFrame):
    """Test-dashboard top bar.

    Signals
    -------
    run_all_clicked     Run All button pressed.
    new_job_clicked     ← New Job pressed.
    settings_clicked    Settings gear pressed.
    mode_changed(str)   "simple" or "advanced" when toggle changes.
    """

    run_all_clicked = Signal()
    new_job_clicked = Signal()
    settings_clicked = Signal()
    mode_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("class", "header-bar")
        self._mode = "simple"
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Primary row
        primary = QWidget()
        primary.setStyleSheet(
            "background: #18181b; border-bottom: 1px solid #3f3f46;"
        )
        row = QHBoxLayout(primary)
        row.setContentsMargins(16, 8, 16, 8)
        row.setSpacing(12)

        # Job info (flex-1)
        self._job_info_lbl = QLabel("—")
        self._job_info_lbl.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #fafafa; background: transparent;"
        )
        self._report_badge = QLabel()
        self._report_badge.setStyleSheet(
            "background: #1e3a5f; color: #60a5fa; font-size: 10px; font-weight: 700; "
            "padding: 1px 7px; border-radius: 4px; border: 1px solid #3b82f6;"
        )
        self._report_badge.hide()

        info_row_layout = QHBoxLayout()
        info_row_layout.setSpacing(6)
        info_row_layout.setContentsMargins(0, 0, 0, 0)
        info_row_layout.addWidget(self._job_info_lbl)
        info_row_layout.addWidget(self._report_badge)
        info_row_layout.addStretch()
        info_widget = QWidget()
        info_widget.setStyleSheet("background: transparent;")
        info_widget.setLayout(info_row_layout)
        row.addWidget(info_widget, stretch=1)

        # Simple / Advanced toggle
        self._simple_btn = QPushButton("Simple")
        self._simple_btn.setProperty("class", "seg-left")
        self._simple_btn.setProperty("checked", "true")
        self._simple_btn.clicked.connect(lambda: self._select_mode("simple"))
        row.addWidget(self._simple_btn)

        self._advanced_btn = QPushButton("Advanced")
        self._advanced_btn.setProperty("class", "seg-right")
        self._advanced_btn.setProperty("checked", "false")
        self._advanced_btn.clicked.connect(lambda: self._select_mode("advanced"))
        row.addWidget(self._advanced_btn)

        # Run All
        self._run_all_btn = QPushButton("▶ Run All")
        self._run_all_btn.setProperty("class", "primary")
        self._run_all_btn.clicked.connect(self.run_all_clicked)
        row.addWidget(self._run_all_btn)

        # New Job
        new_job_btn = QPushButton("← New Job")
        new_job_btn.setProperty("class", "ghost")
        new_job_btn.clicked.connect(self.new_job_clicked)
        row.addWidget(new_job_btn)

        # Settings gear
        settings_btn = QPushButton("⚙")
        settings_btn.setProperty("class", "icon-btn")
        settings_btn.clicked.connect(self.settings_clicked)
        row.addWidget(settings_btn)

        outer.addWidget(primary)

        # Elevation warning row (hidden unless not running as admin)
        self._warn_row = QWidget()
        self._warn_row.setStyleSheet(
            "background: #2d1a00; border-bottom: 1px solid #7c3d00;"
        )
        warn_layout = QHBoxLayout(self._warn_row)
        warn_layout.setContentsMargins(16, 4, 16, 4)
        warn_lbl = QLabel(
            "⚠ Not running as administrator — some tests may be limited or fail."
        )
        warn_lbl.setStyleSheet("color: #f59e0b; font-size: 11px;")
        warn_layout.addWidget(warn_lbl)
        self._warn_row.hide()
        outer.addWidget(self._warn_row)

        refresh_style(self._simple_btn)
        refresh_style(self._advanced_btn)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_job_info(self, job_info: JobInfo) -> None:
        """Update job info label and report type badge."""
        self._job_info_lbl.setText(f"{job_info.customer_name}  ·  {job_info.job_number}")
        self._report_badge.setText(job_info.report_type.value.upper())
        self._report_badge.show()

    def clear_job_info(self) -> None:
        self._job_info_lbl.setText("—")
        self._report_badge.hide()

    def show_elevation_warning(self) -> None:
        self._warn_row.show()

    def mode(self) -> str:
        return self._mode

    def reset_mode(self) -> None:
        """Reset to Simple mode without emitting mode_changed."""
        if self._mode != "simple":
            self._mode = "simple"
            self._simple_btn.setProperty("checked", "true")
            self._advanced_btn.setProperty("checked", "false")
            refresh_style(self._simple_btn)
            refresh_style(self._advanced_btn)

    # ── Private ───────────────────────────────────────────────────────────────

    def _select_mode(self, mode: str) -> None:
        if mode == self._mode:
            return
        self._mode = mode
        is_adv = mode == "advanced"
        self._simple_btn.setProperty("checked", "false" if is_adv else "true")
        self._advanced_btn.setProperty("checked", "true" if is_adv else "false")
        refresh_style(self._simple_btn)
        refresh_style(self._advanced_btn)
        self.mode_changed.emit(mode)
