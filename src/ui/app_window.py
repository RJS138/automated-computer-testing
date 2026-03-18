"""Main application window for Touchstone."""

from __future__ import annotations

import platform
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent, QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow

from src.models.job import JobInfo
from src.models.settings import Settings
from src.models.test_result import TestResult
from src.ui.stylesheet import QSS_DARK
from src.utils.file_manager import find_usb_drive


def _dark_palette() -> QPalette:
    """QPalette matching the app's dark theme tokens.

    Fills in anywhere QSS doesn't reach (focus rings, OS-drawn scrollbars,
    native selection highlights, etc.) so Fusion renders consistently.
    """
    p = QPalette()
    # Window / background
    p.setColor(QPalette.ColorRole.Window,          QColor("#0d1117"))
    p.setColor(QPalette.ColorRole.WindowText,      QColor("#e6edf3"))
    # Input fields
    p.setColor(QPalette.ColorRole.Base,            QColor("#161b22"))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor("#1c2128"))
    p.setColor(QPalette.ColorRole.Text,            QColor("#e6edf3"))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#7d8590"))
    # Buttons
    p.setColor(QPalette.ColorRole.Button,          QColor("#21262d"))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor("#e6edf3"))
    p.setColor(QPalette.ColorRole.BrightText,      QColor("#ffffff"))
    # Selection / highlight
    p.setColor(QPalette.ColorRole.Highlight,       QColor("#1e3a5f"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#e6edf3"))
    # Links
    p.setColor(QPalette.ColorRole.Link,            QColor("#3b82f6"))
    # Tooltips
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#21262d"))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor("#e6edf3"))
    # Disabled state — muted versions
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor("#484f58"))
    return p


class TouchstoneWindow(QMainWindow):
    """QMainWindow with MainDashboard as its central widget.

    Shared state:
        job_info       — populated when Run All is clicked
        test_results   — populated as tests complete
        manual_items   — populated by manual tests
    """

    job_info: JobInfo | None
    test_results: list[TestResult]
    manual_items: list[TestResult]

    def __init__(self, dev_manual: bool = False) -> None:
        super().__init__()

        self.job_info = None
        self.test_results = []
        self.manual_items = []

        # Default save path — detect USB once at startup
        _usb = find_usb_drive()
        self.settings = Settings(
            save_path=str(_usb) if _usb else str(Path.home() / "touchstone_reports")
        )

        # ── Window properties ────────────────────────────────────
        self.setWindowTitle("Touchstone")
        self.setMinimumSize(900, 650)

        # ── Font (set per-platform to avoid alias-lookup cost) ───
        app = QApplication.instance()
        if isinstance(app, QApplication):
            _sys = platform.system()
            if _sys == "Darwin":
                app.setFont(QFont("Helvetica Neue", 13))
            elif _sys == "Windows":
                app.setFont(QFont("Segoe UI", 10))
            else:
                app.setFont(QFont("DejaVu Sans", 10))
            app.setStyle("Fusion")
            app.setPalette(_dark_palette())
            app.setStyleSheet(QSS_DARK)

        # ── Central widget: MainDashboard ────────────────────────
        from src.ui.pages.main_dashboard import MainDashboard

        self._dashboard = MainDashboard(self)
        self.setCentralWidget(self._dashboard)

        # ── Dev-manual trigger ───────────────────────────────────
        if dev_manual:
            self.job_info = JobInfo(
                customer_name="Dev",
                device_description="Dev device",
                job_number="0",
            )
            QTimer.singleShot(500, self._dashboard.dev_trigger_display)

    # ── Show ─────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Centre on screen
        screen = QApplication.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            self.move(
                geom.center().x() - self.width() // 2,
                geom.center().y() - self.height() // 2,
            )

    # ── Close ────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        event.accept()
