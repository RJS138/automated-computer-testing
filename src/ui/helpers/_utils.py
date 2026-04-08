"""Shared utilities for manual test helper dialogs."""

import platform

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QPushButton


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


def show_fullscreen(dialog: QDialog) -> None:
    """Show a dialog fullscreen, covering the taskbar on Windows."""
    if platform.system() == "Windows":
        dialog.setWindowFlags(
            dialog.windowFlags()
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        screen = QApplication.primaryScreen()
        if screen is not None:
            dialog.setGeometry(screen.geometry())
        dialog.show()
    else:
        dialog.showFullScreen()
