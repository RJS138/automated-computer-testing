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
from src.ui.stylesheet import QSS_DARK, QSS_LIGHT
from src.utils.file_manager import find_usb_drive
from src.utils.theme_prefs import load_theme, save_theme


def _dark_palette() -> QPalette:
    """QPalette matching the dark theme tokens."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor("#09090b"))
    p.setColor(QPalette.ColorRole.WindowText,      QColor("#fafafa"))
    p.setColor(QPalette.ColorRole.Base,            QColor("#18181b"))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor("#27272a"))
    p.setColor(QPalette.ColorRole.Text,            QColor("#fafafa"))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#71717a"))
    p.setColor(QPalette.ColorRole.Button,          QColor("#27272a"))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor("#fafafa"))
    p.setColor(QPalette.ColorRole.BrightText,      QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.Highlight,       QColor("#3b82f6"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#fafafa"))
    p.setColor(QPalette.ColorRole.Link,            QColor("#3b82f6"))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#27272a"))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor("#fafafa"))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor("#52525b"))
    return p


def _light_palette() -> QPalette:
    """QPalette matching the light theme tokens."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor("#f5f4f1"))
    p.setColor(QPalette.ColorRole.WindowText,      QColor("#1c1917"))
    p.setColor(QPalette.ColorRole.Base,            QColor("#fafaf9"))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor("#e7e5e4"))
    p.setColor(QPalette.ColorRole.Text,            QColor("#1c1917"))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#a8a29e"))
    p.setColor(QPalette.ColorRole.Button,          QColor("#e7e5e4"))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor("#1c1917"))
    p.setColor(QPalette.ColorRole.BrightText,      QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.Highlight,       QColor("#2563eb"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#fafafa"))
    p.setColor(QPalette.ColorRole.Link,            QColor("#2563eb"))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#e7e5e4"))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor("#1c1917"))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor("#a8a29e"))
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

        # ── Apply Fusion style + theme ───────────────────────────
        self._current_theme = "dark"  # default; overwritten below if app is available
        app = QApplication.instance()
        if isinstance(app, QApplication):
            _sys = platform.system()
            if _sys == "Darwin":
                app.setFont(QFont("Helvetica Neue", 13))
            elif _sys == "Windows":
                app.setFont(QFont("Segoe UI", 11))   # spec: 11px (was 10 in old code)
            else:
                app.setFont(QFont("DejaVu Sans", 11))  # spec: 11px (was 10 in old code)
            app.setStyle("Fusion")
            self._current_theme = load_theme()
            if self._current_theme == "light":
                app.setPalette(_light_palette())
                app.setStyleSheet(QSS_LIGHT)
            else:
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

    # ── Theme ─────────────────────────────────────────────────────

    def set_theme(self, theme: str) -> None:
        """Switch between "dark" and "light" themes at runtime. No restart needed."""
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        if theme == "light":
            app.setPalette(_light_palette())
            app.setStyleSheet(QSS_LIGHT)
        else:
            app.setPalette(_dark_palette())
            app.setStyleSheet(QSS_DARK)
        save_theme(theme)
        self._current_theme = theme

    @property
    def current_theme(self) -> str:
        return self._current_theme

    # ── Show ─────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
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
