"""DashboardCard widget — flat row with expandable detail panel."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..stylesheet import get_colors, refresh_style
from .temp_chart_widget import TempChartWidget

_STATUS_COLORS: dict[str, str] = {
    "waiting": "#52525b",
    "running": "#60a5fa",
    "pass":    "#22c55e",
    "warn":    "#f59e0b",
    "fail":    "#ef4444",
    "error":   "#ef4444",
    "skip":    "#52525b",
    "cancel":  "#fb923c",
}

# Light-mode overrides for statuses whose dark hex doesn't work on light bg.
_STATUS_COLORS_LIGHT: dict[str, str] = {
    "cancel": "#ea580c",
}


class DashboardCard(QFrame):
    """One row per test — flat row with optional expandable detail panel.

    Clicking the row (outside the Run button) toggles the detail panel.

    Signals
    -------
    run_requested(str)
        Emitted when Run / Re-run is clicked; carries the test name.
    """

    run_requested = Signal(str)
    stop_requested = Signal(str)

    def __init__(self, name: str, display_name: str, theme: str = "dark", parent=None) -> None:
        super().__init__(parent)
        self._name = name
        self._display_name = display_name
        self._sub_detail_text = ""
        self._expanded = False
        self._has_chart_data: bool = False
        self._stop_mode: bool = False

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._elapsed_s: int = 0
        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._tick)

        self._build_ui()
        self.apply_theme(theme)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Main row (always visible, fixed height) ───────────────────────────
        self._main_row = QWidget()
        self._main_row.setFixedHeight(52)
        self._main_row.setStyleSheet("background: transparent;")
        self._main_row.setCursor(Qt.CursorShape.PointingHandCursor)
        self._main_row.mousePressEvent = self._on_row_clicked

        row = QHBoxLayout(self._main_row)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(12)

        vc = Qt.AlignmentFlag.AlignVCenter

        # Checkbox (advanced mode, hidden by default)
        self._checkbox = QCheckBox()
        self._checkbox.setChecked(True)
        self._checkbox.hide()
        row.addWidget(self._checkbox, 0, vc)

        # Test name
        self._name_lbl = QLabel(self._display_name)
        self._name_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        row.addWidget(self._name_lbl, 0, vc)

        # Inline summary — expands to fill available space
        self._detail_lbl = QLabel("")
        self._detail_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | vc)
        self._detail_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(self._detail_lbl, 1, vc)

        # Compact sparkline — shown while temp samples are arriving
        self._sparkline = TempChartWidget(compact=True, theme="dark")
        self._sparkline.hide()
        row.addWidget(self._sparkline, 0, vc)

        # Expand arrow — shown only when sub-detail exists
        self._expand_arrow = QLabel("▾")
        self._expand_arrow.setFixedWidth(18)
        self._expand_arrow.hide()
        row.addWidget(self._expand_arrow, 0, vc)

        # Status text
        self._status_lbl = QLabel("WAITING")
        self._status_lbl.setStyleSheet(
            f"color: {_STATUS_COLORS['waiting']}; font-size: 12px; font-weight: 600;"
            " background: transparent;"
        )
        self._status_lbl.setFixedWidth(64)
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | vc)
        row.addWidget(self._status_lbl, 0, vc)

        # Run button
        self._run_btn = QPushButton("Run")
        self._run_btn.setFixedWidth(72)
        self._run_btn.setFixedHeight(28)
        self._run_btn.clicked.connect(self._on_run_clicked)
        row.addWidget(self._run_btn, 0, vc)

        outer.addWidget(self._main_row)

        # ── Expandable detail panel ───────────────────────────────────────────
        self._detail_panel = QLabel("")
        self._detail_panel.setWordWrap(True)
        self._detail_panel.hide()
        outer.addWidget(self._detail_panel)

        # Full area chart panel — shown in expandable area after test completes
        self._chart_panel = TempChartWidget(compact=False, theme="dark")
        self._chart_panel.hide()
        outer.addWidget(self._chart_panel)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_status(self, status: str, detail: str = "", sub_detail: str = "") -> None:
        """Update inline summary, status colour, expandable panel, and button label."""
        status = status.lower()
        c = get_colors(self._theme)

        # Theme-aware status label colour
        light_overrides = _STATUS_COLORS_LIGHT if self._theme == "light" else {}
        color = light_overrides.get(status) or _STATUS_COLORS.get(status, "#52525b")

        self._status_lbl.setText(status.upper())
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: 600; background: transparent;"
        )

        if status == "running":
            self._stop_mode = True
            # Reset chart widgets for a fresh run (handles Re-run button)
            self._sparkline.reset()
            self._chart_panel.reset()
            self._has_chart_data = False
            self._expand_arrow.hide()
            self._elapsed_s = 0
            self._detail_lbl.setText("running…")
            self._detail_lbl.setStyleSheet(
                f"color: {c['badge_accent_text']}; font-size: 13px; background: transparent;"
            )
            if not self._ticker.isActive():
                self._ticker.start()
            self._set_sub_detail("")
            # Morph Run button into ◼ Stop
            self._run_btn.setText("◼ Stop")
            self._run_btn.setStyleSheet(
                f"QPushButton {{ background: {c['danger_bg']}; color: {c['danger_text']};"
                f" border: none; border-radius: 6px; font-size: 12px; font-weight: 600; }}"
                f"QPushButton:hover {{ background: {c['danger_text']}; color: #ffffff; }}"
            )
        else:
            self._stop_mode = False
            self._sparkline.hide()
            self._ticker.stop()
            detail_text = "cancelled" if status == "cancel" else detail
            self._detail_lbl.setText(detail_text)
            self._detail_lbl.setStyleSheet(
                f"color: {c['text_muted']}; font-size: 13px; background: transparent;"
            )
            self._set_sub_detail(sub_detail)
            # Restore normal Run/Re-run button
            self._run_btn.setText("Run" if status == "waiting" else "Re-run")
            self._apply_run_btn_normal_style()

    def push_temp_sample(self, time_s: float, temp_c: float) -> None:
        """Called while test is running. Grows the sparkline and updates the detail label."""
        # Guard against late-arriving queued signals after test completes.
        # _stop_mode is True only while the test is running.
        if not self._stop_mode:
            return
        self._sparkline.push_sample(time_s, temp_c)
        if not self._sparkline.isVisible():
            self._sparkline.show()
            # Stop the plain elapsed ticker — sparkline label takes over
            self._ticker.stop()
        self._detail_lbl.setText(f"{int(time_s)}s · {int(temp_c)}°C")

    def set_chart_data(
        self,
        samples: list[dict],
        warn: float | None = None,
        fail: float | None = None,
    ) -> None:
        """Load completed temp_samples into the full chart panel."""
        self._chart_panel.set_samples(samples)
        self._chart_panel.set_thresholds(warn, fail)
        self._has_chart_data = True
        self._expand_arrow.show()
        if self._expanded:
            self._chart_panel.show()

    def set_advanced(self, enabled: bool) -> None:
        self._checkbox.setVisible(enabled)

    def is_checked(self) -> bool:
        if not self._checkbox.isVisible():
            return True
        return self._checkbox.isChecked()

    def set_running_all(self, active: bool) -> None:
        self._run_btn.setEnabled(not active)

    def apply_theme(self, theme: str) -> None:
        """Re-apply all inline styles using the given theme's color tokens."""
        self._theme = theme
        c = get_colors(theme)
        self.setStyleSheet(
            f"QFrame {{ border: none; background: {c['bg_surface']}; border-radius: 8px; }}"
        )
        self._name_lbl.setStyleSheet(
            f"color: {c['text_primary']}; font-size: 14px; font-weight: 500; background: transparent;"
        )
        self._detail_lbl.setStyleSheet(
            f"color: {c['text_muted']}; font-size: 13px; background: transparent;"
        )
        self._expand_arrow.setStyleSheet(
            f"color: {c['text_secondary']}; font-size: 16px; background: transparent;"
        )
        if self._stop_mode:
            self._run_btn.setText("◼ Stop")
            self._run_btn.setStyleSheet(
                f"QPushButton {{ background: {c['danger_bg']}; color: {c['danger_text']};"
                f" border: none; border-radius: 6px; font-size: 12px; font-weight: 600; }}"
                f"QPushButton:hover {{ background: {c['danger_text']}; color: #ffffff; }}"
            )
        else:
            self._apply_run_btn_normal_style()
        self._detail_panel.setStyleSheet(
            f"color: {c['text_secondary']}; font-size: 12px; background: transparent;"
            f" padding: 2px 10px 10px 10px;"
        )
        self._sparkline.apply_theme(theme)
        self._chart_panel.apply_theme(theme)

    # ── Private ───────────────────────────────────────────────────────────────

    def _apply_run_btn_normal_style(self) -> None:
        c = get_colors(self._theme)
        self._run_btn.setStyleSheet(
            f"QPushButton {{ background: {c['bg_elevated']}; color: {c['text_secondary']};"
            f" border: none; border-radius: 6px; font-size: 12px; font-weight: 500; }}"
            f"QPushButton:hover {{ background: {c['bg_hover']}; color: {c['text_primary']}; }}"
            f"QPushButton:pressed {{ background: {c['text_muted']}; }}"
            f"QPushButton:disabled {{ background: {c['bg_elevated']}; color: {c['text_muted']}; }}"
        )

    def _set_sub_detail(self, text: str) -> None:
        self._sub_detail_text = text.strip()
        has = bool(self._sub_detail_text)
        # Show expand arrow if either sub-detail text OR chart data is present
        self._expand_arrow.setVisible(has or self._has_chart_data)
        self._detail_panel.setText(self._sub_detail_text)
        if not has and self._expanded and not self._has_chart_data:
            self._expanded = False
            self._detail_panel.hide()

    def _on_row_clicked(self, event) -> None:
        if not self._sub_detail_text and not self._has_chart_data:
            return
        self._expanded = not self._expanded
        self._expand_arrow.setText("▴" if self._expanded else "▾")
        if self._expanded:
            if self._sub_detail_text:
                self._detail_panel.show()
            if self._has_chart_data:
                self._chart_panel.show()
        else:
            self._detail_panel.hide()
            self._chart_panel.hide()
        self.adjustSize()
        if self.parent():
            self.parent().adjustSize()  # type: ignore[union-attr]

    def _tick(self) -> None:
        self._elapsed_s += 1
        if self._elapsed_s < 60:
            self._detail_lbl.setText(f"{self._elapsed_s}s")
        else:
            m = self._elapsed_s // 60
            s = self._elapsed_s % 60
            self._detail_lbl.setText(f"{m}:{s:02d}")

    def _on_run_clicked(self) -> None:
        if self._stop_mode:
            self.stop_requested.emit(self._name)
        else:
            self.run_requested.emit(self._name)
