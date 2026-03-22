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
from src.ui.stylesheet import build_seg_styles, get_colors


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
    stop_all_clicked = Signal()
    new_job_clicked = Signal()
    settings_clicked = Signal()
    mode_changed = Signal(str)

    def __init__(self, theme: str = "dark", parent=None) -> None:
        super().__init__(parent)
        self._mode = "simple"
        self._theme = theme
        self._running_all: bool = False
        self._build_ui()
        self.apply_theme(theme)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Primary row
        self._primary_row = QWidget()
        row = QHBoxLayout(self._primary_row)
        row.setContentsMargins(16, 8, 16, 8)
        row.setSpacing(12)

        # Job info (flex-1)
        self._job_info_lbl = QLabel("—")
        self._report_badge = QLabel()
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

        # Simple / Advanced toggle — styled directly, no property selectors
        self._simple_btn = QPushButton("Simple")
        self._simple_btn.clicked.connect(lambda: self._select_mode("simple"))
        row.addWidget(self._simple_btn)

        self._advanced_btn = QPushButton("Advanced")
        self._advanced_btn.clicked.connect(lambda: self._select_mode("advanced"))
        row.addWidget(self._advanced_btn)

        # Run All
        self._run_all_btn = QPushButton("▶ Run All")
        self._run_all_btn.clicked.connect(self.run_all_clicked)
        row.addWidget(self._run_all_btn)

        # New Job
        self._new_job_btn = QPushButton("← New Job")
        self._new_job_btn.clicked.connect(self.new_job_clicked)
        row.addWidget(self._new_job_btn)

        # Settings gear — distinct resting background so it reads as a button
        self._settings_btn = QPushButton("⚙")
        self._settings_btn.clicked.connect(self.settings_clicked)
        row.addWidget(self._settings_btn)

        outer.addWidget(self._primary_row)

        # Elevation warning row (hidden unless not running as admin)
        self._warn_row = QWidget()
        warn_layout = QHBoxLayout(self._warn_row)
        warn_layout.setContentsMargins(16, 4, 16, 4)
        self._warn_lbl = QLabel(
            "⚠ Not running as administrator — some tests may be limited or fail."
        )
        warn_layout.addWidget(self._warn_lbl)
        self._warn_row.hide()
        outer.addWidget(self._warn_row)

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
            seg = build_seg_styles(self._theme)
            self._simple_btn.setStyleSheet(seg["L_ON"])
            self._advanced_btn.setStyleSheet(seg["R_OFF"])

    def set_run_all_enabled(self, enabled: bool) -> None:
        self._run_all_btn.setEnabled(enabled)

    def set_running_all(self, active: bool) -> None:
        """Toggle Run All button between ▶ Run All and ◼ Stop."""
        self._running_all = active
        c = get_colors(self._theme)
        if active:
            self._run_all_btn.setText("◼ Stop")
            self._run_all_btn.clicked.disconnect()
            self._run_all_btn.clicked.connect(self.stop_all_clicked)
            self._run_all_btn.setStyleSheet(
                f"QPushButton {{ background: {c['danger_bg']}; color: {c['danger_text']};"
                f" border: none; border-radius: 6px; padding: 5px 14px; font-size: 12px;"
                f" font-weight: 600; min-height: 30px; }}"
                f"QPushButton:hover {{ background: {c['danger_text']}; color: #ffffff; }}"
            )
        else:
            self._run_all_btn.setText("▶ Run All")
            self._run_all_btn.clicked.disconnect()
            self._run_all_btn.clicked.connect(self.run_all_clicked)
            self._apply_run_all_normal_style()

    def apply_theme(self, theme: str) -> None:
        """Re-apply all inline styles for the given theme."""
        self._theme = theme
        c = get_colors(theme)
        seg = build_seg_styles(theme)

        self._primary_row.setStyleSheet(f"background: {c['bg_surface']};")
        self._job_info_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {c['text_primary']}; background: transparent;"
        )
        self._report_badge.setStyleSheet(
            f"background: {c['badge_accent_bg']}; color: {c['badge_accent_text']};"
            f" font-size: 10px; font-weight: 700; padding: 1px 7px; border-radius: 4px; border: none;"
        )
        # Segmented mode buttons (preserve current selected state)
        if self._mode == "advanced":
            self._simple_btn.setStyleSheet(seg["L_OFF"])
            self._advanced_btn.setStyleSheet(seg["R_ON"])
        else:
            self._simple_btn.setStyleSheet(seg["L_ON"])
            self._advanced_btn.setStyleSheet(seg["R_OFF"])
        # Run All / Stop button — preserve current running state
        if self._running_all:
            self._run_all_btn.setText("◼ Stop")
            self._run_all_btn.setStyleSheet(
                f"QPushButton {{ background: {c['danger_bg']}; color: {c['danger_text']};"
                f" border: none; border-radius: 6px; padding: 5px 14px; font-size: 12px;"
                f" font-weight: 600; min-height: 30px; }}"
                f"QPushButton:hover {{ background: {c['danger_text']}; color: #ffffff; }}"
            )
        else:
            self._apply_run_all_normal_style()
        # New Job button
        self._new_job_btn.setStyleSheet(
            f"QPushButton {{ background: {c['bg_elevated']}; color: {c['text_secondary']};"
            f" border: none; border-radius: 6px; padding: 5px 14px; font-size: 12px;"
            f" font-weight: 500; min-height: 30px; }}"
            f"QPushButton:hover {{ background: {c['bg_hover']}; color: {c['text_primary']}; }}"
            f"QPushButton:pressed {{ background: {c['text_muted']}; }}"
        )
        # Settings gear
        self._settings_btn.setStyleSheet(
            f"QPushButton {{ background: {c['bg_elevated']}; border: none; border-radius: 6px;"
            f" min-width: 36px; min-height: 36px; max-width: 36px; max-height: 36px;"
            f" font-size: 18px; padding: 0; }}"
            f"QPushButton:hover {{ background: {c['bg_hover']}; }}"
            f"QPushButton:pressed {{ background: {c['text_muted']}; }}"
        )
        # Elevation warning row
        self._warn_row.setStyleSheet(f"background: {c['warn_row_bg']};")
        self._warn_lbl.setStyleSheet(f"color: {c['warn_text']}; font-size: 11px;")

    def _apply_run_all_normal_style(self) -> None:
        c = get_colors(self._theme)
        self._run_all_btn.setStyleSheet(
            f"QPushButton {{ background: {c['accent']}; color: #ffffff; border: none;"
            f" border-radius: 6px; padding: 5px 14px; font-size: 12px;"
            f" font-weight: 600; min-height: 30px; }}"
            f"QPushButton:hover {{ background: {c['accent_hover']}; }}"
            f"QPushButton:pressed {{ background: {c['accent_hover']}; }}"
            f"QPushButton:disabled {{ background: {c['accent']}; color: #ffffff; }}"
        )

    # ── Private ───────────────────────────────────────────────────────────────

    def _select_mode(self, mode: str) -> None:
        if mode == self._mode:
            return
        self._mode = mode
        seg = build_seg_styles(self._theme)
        if mode == "advanced":
            self._simple_btn.setStyleSheet(seg["L_OFF"])
            self._advanced_btn.setStyleSheet(seg["R_ON"])
        else:
            self._simple_btn.setStyleSheet(seg["L_ON"])
            self._advanced_btn.setStyleSheet(seg["R_OFF"])
        self.mode_changed.emit(mode)
