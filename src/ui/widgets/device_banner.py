"""DeviceBanner — horizontal device-info strip with overall badge and Generate Report button."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.models.test_result import TestResult
from src.ui.stylesheet import get_colors

_OVERALL_STYLES: dict[str, tuple[str, str]] = {
    # status: (bg, text)  — dark mode
    "pass":    ("#1a2e20", "#22c55e"),
    "warn":    ("#2d2006", "#f59e0b"),
    "fail":    ("#2e1414", "#ef4444"),
    "error":   ("#2e1414", "#ef4444"),
    "running": ("#1e3a5f", "#60a5fa"),
    "waiting": ("#27272a", "#71717a"),
    "skip":    ("#27272a", "#71717a"),
}

_OVERALL_STYLES_LIGHT: dict[str, tuple[str, str]] = {
    # status: (bg, text)  — light mode
    "pass":    ("#d6f0dc", "#16a34a"),
    "warn":    ("#fef3c7", "#d97706"),
    "fail":    ("#fee2e2", "#dc2626"),
    "error":   ("#fee2e2", "#dc2626"),
    "running": ("#dbeafe", "#2563eb"),
    "waiting": ("#e7e5e4", "#78716c"),
    "skip":    ("#e7e5e4", "#78716c"),
}

_STATUS_PRIORITY = ["fail", "error", "warn", "skip", "pass", "running", "waiting"]


class _SpecField(QWidget):
    """Label + value column in the banner."""

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        self._has_value = False
        self._theme = "dark"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._lbl = QLabel(label.upper())
        layout.addWidget(self._lbl)

        self._val = QLabel("—")
        layout.addWidget(self._val)

        self.apply_theme("dark")  # initial styles

    def set_value(self, text: str) -> None:
        self._has_value = True
        self._val.setText(text)
        c = get_colors(self._theme)
        self._val.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {c['text_primary']};"
            f" font-family: monospace; background: transparent;"
        )

    def clear(self) -> None:
        self._has_value = False
        self._val.setText("—")
        c = get_colors(self._theme)
        self._val.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {c['text_muted']};"
            f" font-family: monospace; background: transparent;"
        )

    def apply_theme(self, theme: str) -> None:
        self._theme = theme
        c = get_colors(theme)
        self._lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {c['text_muted']};"
            f" letter-spacing: 0.05em; background: transparent;"
        )
        val_color = c["text_primary"] if self._has_value else c["text_muted"]
        self._val.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {val_color};"
            f" font-family: monospace; background: transparent;"
        )


class DeviceBanner(QFrame):
    """Horizontal strip: spec fields, overall badge, Generate Report button.

    Signals
    -------
    generate_report_requested
        Emitted when the Generate Report button is clicked.
    """

    generate_report_requested = Signal()

    def __init__(self, theme: str = "dark", parent=None) -> None:
        super().__init__(parent)
        self._fields: dict[str, _SpecField] = {}
        self._build_ui()       # must run first — creates _report_btn and _fields
        self.apply_theme(theme)

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 10, 16, 10)
        outer.setSpacing(0)

        # Spec fields
        fields_row = QHBoxLayout()
        fields_row.setSpacing(24)
        fields_row.setContentsMargins(0, 0, 0, 0)
        for label in ("MODEL", "SERIAL", "OS", "CPU", "RAM", "STORAGE"):
            f = _SpecField(label)
            self._fields[label] = f
            fields_row.addWidget(f)
        fields_row.addStretch()
        outer.addLayout(fields_row, stretch=1)

        outer.addSpacing(16)

        # Overall badge
        self._overall = QFrame()
        self._overall.setFixedSize(76, 48)
        ov_layout = QVBoxLayout(self._overall)
        ov_layout.setContentsMargins(8, 4, 8, 4)
        ov_layout.setSpacing(2)

        self._ov_title = QLabel("Overall")
        self._ov_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ov_title.setStyleSheet(
            "font-size: 10px; font-weight: 700; background: transparent;"
        )
        ov_layout.addWidget(self._ov_title)

        self._ov_value = QLabel("—")
        self._ov_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ov_value.setStyleSheet(
            "font-size: 13px; font-weight: 700; background: transparent;"
        )
        ov_layout.addWidget(self._ov_value)
        self._ov_status = "waiting"
        self._apply_overall_style("waiting")
        outer.addWidget(self._overall)

        outer.addSpacing(8)

        # Generate Report button
        self._report_btn = QPushButton("Generate\nReport")
        self._report_btn.setFixedSize(82, 48)
        self._report_btn.setEnabled(False)
        self._report_btn.clicked.connect(self.generate_report_requested)
        outer.addWidget(self._report_btn)

    # ── Public API ────────────────────────────────────────────────────────────

    def apply_theme(self, theme: str) -> None:
        """Re-apply all inline styles for the given theme."""
        self._theme = theme
        c = get_colors(theme)
        self.setStyleSheet(
            f"QFrame {{ background-color: {c['bg_surface']}; border: none; }}"
        )
        for field in self._fields.values():
            field.apply_theme(theme)
        self._report_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {c['bg_elevated']}; color: {c['text_muted']};"
            f"  border: none; border-radius: 6px;"
            f"  font-size: 11px; font-weight: 700;"
            f"}}"
            f"QPushButton:enabled {{ color: {c['text_primary']}; }}"
            f"QPushButton:enabled:hover {{"
            f"  background: {c['bg_hover']}; color: {c['text_primary']};"
            f"}}"
            f"QPushButton:disabled {{ color: {c['text_muted']}; }}"
        )
        self._apply_overall_style(self._ov_status)

    def update_from_result(self, result: TestResult) -> None:
        """Populate fields from system_info result.data and enable Generate Report."""
        d = result.data

        model = d.get("chassis_model") or d.get("board_model") or "—"
        if d.get("apple_model_number"):
            model = f"{model}  {d['apple_model_number']}"
        self._fields["MODEL"].set_value(model)

        self._fields["SERIAL"].set_value(d.get("board_serial") or "—")

        os_val = " ".join(filter(None, [d.get("os_name"), d.get("os_version")])) or "—"
        self._fields["OS"].set_value(os_val)

        cpu_name = d.get("processor_marketing") or d.get("processor") or ""
        cores = d.get("cpu_cores") or ""
        cpu_val = f"{cpu_name} · {cores}" if cpu_name and cores else cpu_name or "—"
        self._fields["CPU"].set_value(cpu_val)

        self._fields["RAM"].set_value(d.get("ram_total") or "—")

        storage_list = d.get("storage_list") or []
        self._fields["STORAGE"].set_value(storage_list[0] if storage_list else "—")

        self._report_btn.setEnabled(True)

    def update_overall(self, results: list[TestResult]) -> None:
        """Recalculate worst-status badge from all results."""
        statuses = {r.status.value for r in results}
        if not statuses:
            self._update_overall_text("—", "waiting")
            return
        overall = next((p for p in _STATUS_PRIORITY if p in statuses), "waiting")
        self._update_overall_text(overall.upper(), overall)

    def clear(self) -> None:
        """Reset all fields to — and disable Generate Report."""
        for f in self._fields.values():
            f.clear()
        self._update_overall_text("—", "waiting")
        self._report_btn.setEnabled(False)

    # ── Private ───────────────────────────────────────────────────────────────

    def _update_overall_text(self, text: str, status: str) -> None:
        self._ov_value.setText(text)
        self._apply_overall_style(status)

    def _apply_overall_style(self, status: str) -> None:
        self._ov_status = status
        styles = _OVERALL_STYLES_LIGHT if getattr(self, "_theme", "dark") == "light" else _OVERALL_STYLES
        bg, text_color = styles.get(status, styles["waiting"])
        self._overall.setStyleSheet(
            f"QFrame {{ background: {bg}; border: none; border-radius: 6px; }}"
        )
        self._ov_title.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {text_color}; background: transparent;"
        )
        self._ov_value.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {text_color}; background: transparent;"
        )
