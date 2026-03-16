"""Shared utilities for manual test helper dialogs."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton


def make_dialog_btn(text: str, bg: str, hover: str, fg: str = "white") -> QPushButton:
    """Create a styled P/F/S button for manual test dialogs."""
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background: {bg}; color: {fg}; border: none; "
        f"padding: 8px 28px; font-family: Courier; font-size: 13px; font-weight: bold; }}"
        f"QPushButton:hover {{ background: {hover}; }}"
    )
    return btn
