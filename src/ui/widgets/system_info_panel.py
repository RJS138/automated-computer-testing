"""System hardware info panel widget — left-column summary for dashboard."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..stylesheet import refresh_style


def _list_field(key: str) -> Callable[[dict], str | None]:
    """Return a lambda that joins a list field with newlines, or None if absent."""
    return lambda d: "\n".join(d[key]) if d.get(key) else None


class SystemInfoPanel(QFrame):
    """
    Fixed-width left-column panel showing hardware summary.

    Usage:
        panel = SystemInfoPanel(parent)
        panel.set_loading()  # show "Loading…"
        # ... when system_info result arrives ...
        panel.populate(result_data)
        panel.set_overall("pass")  # update overall badge
    """

    # Maps display labels to callables that extract values from result.data.
    # Return None to skip the row entirely.
    _FIELD_MAP: ClassVar[list[tuple[str, Callable[[dict], str | None]]]] = [
        (
            "Model",
            lambda d: (
                (d.get("chassis_model") or d.get("board_model") or "—")
                + (f"  {d['apple_model_number']}" if d.get("apple_model_number") else "")
            ),
        ),
        ("Serial", lambda d: d.get("board_serial") or None),
        (
            "OS",
            lambda d: " ".join(filter(None, [d.get("os_name"), d.get("os_version")])) or None,
        ),
        ("Firmware", lambda d: d.get("bios_version") or None),
        (
            "CPU",
            lambda d: (
                (d.get("processor_marketing") or d.get("processor") or None)
                and (
                    (d.get("processor_marketing") or d.get("processor", ""))
                    + (f"\n{d['cpu_cores']}" if d.get("cpu_cores") else "")
                )
            ),
        ),
        ("Arch", lambda d: d.get("machine_arch") or None),
        ("RAM", lambda d: d.get("ram_total") or None),
        ("GPU", _list_field("gpu_list")),
        ("Storage", _list_field("storage_list")),
        ("Fans", _list_field("fan_list")),
    ]

    # Badge colours by status
    _BADGE_COLORS: ClassVar[dict[str, dict[str, str]]] = {
        "pass": {"bg": "#22c55e", "text": "#ffffff"},
        "warn": {"bg": "#f59e0b", "text": "#000000"},
        "fail": {"bg": "#ef4444", "text": "#ffffff"},
        "error": {"bg": "#ef4444", "text": "#ffffff"},
        "skip": {"bg": "#30363d", "text": "#7d8590"},
        "waiting": {"bg": "#30363d", "text": "#7d8590"},
        "running": {"bg": "#1e3a5f", "text": "#60a5fa"},
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setProperty("class", "panel")

        self._loading_label: QLabel | None = None
        self._scroll_area: QScrollArea | None = None
        self._rows_widget: QWidget | None = None
        self._rows_layout: QVBoxLayout | None = None
        self._separator: QFrame | None = None
        self._overall_label: QLabel | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the main layout with loading label, scroll area, and overall badge."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        # ── Loading label (visible until populate() called) ──────────────────────
        self._loading_label = QLabel("Loading…")
        self._loading_label.setProperty("class", "muted")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        refresh_style(self._loading_label)
        outer.addWidget(self._loading_label)

        # ── Scroll area for rows (hidden until populate() called) ──────────────────
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.hide()

        # Container widget for rows
        self._rows_widget = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(4)

        self._scroll_area.setWidget(self._rows_widget)
        outer.addWidget(self._scroll_area, stretch=1)

        # ── Separator line ────────────────────────────────────────────────────────
        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.Shape.HLine)
        self._separator.setStyleSheet("color: #30363d;")
        self._separator.hide()
        outer.addWidget(self._separator)

        # ── Overall badge at bottom ───────────────────────────────────────────────
        self._overall_label = QLabel("waiting")
        self._overall_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overall_label.setFixedHeight(28)
        self._overall_label.hide()
        self._apply_overall_style("waiting")
        outer.addWidget(self._overall_label)

    def set_loading(self) -> None:
        """Show 'Loading…' state; hide scroll area and overall badge."""
        if self._loading_label:
            self._loading_label.show()
        if self._scroll_area:
            self._scroll_area.hide()
        if self._separator:
            self._separator.hide()
        if self._overall_label:
            self._overall_label.hide()

    def populate(self, data: dict) -> None:
        """Populate rows from system_info result. Rows returning None are skipped."""
        if not self._rows_layout or not self._scroll_area or not self._loading_label:
            return

        # Clear previous rows
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        # Add rows for each field — skip if extractor returns None
        for label, extractor in self._FIELD_MAP:
            value = extractor(data)
            if value is None:
                continue

            # Section separator above each group of key+value
            key_lbl = QLabel(label.upper())
            key_lbl.setProperty("class", "muted")
            key_lbl.setStyleSheet("font-size: 9px; letter-spacing: 0.5px; margin-top: 6px;")
            refresh_style(key_lbl)

            value_lbl = QLabel(str(value))
            value_lbl.setStyleSheet("font-size: 11px;")
            value_lbl.setWordWrap(True)
            value_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            self._rows_layout.addWidget(key_lbl)
            self._rows_layout.addWidget(value_lbl)

        self._rows_layout.addStretch()

        # Hide loading label; show scroll area, separator, and overall badge
        self._loading_label.hide()
        self._scroll_area.show()
        if self._separator:
            self._separator.show()
        if self._overall_label:
            self._overall_label.show()

    def set_overall(self, status: str) -> None:
        """Update overall status badge colour and text."""
        if not self._overall_label:
            return

        self._overall_label.setText(status.upper())
        self._apply_overall_style(status)

    def _apply_overall_style(self, status: str) -> None:
        """Apply background and text colour to overall badge."""
        if not self._overall_label:
            return

        colors = self._BADGE_COLORS.get(status, self._BADGE_COLORS["waiting"])
        bg = colors["bg"]
        text = colors["text"]

        self._overall_label.setStyleSheet(
            f"background-color: {bg}; color: {text}; "
            f"border-radius: 4px; font-weight: 600; font-size: 12px;"
        )
