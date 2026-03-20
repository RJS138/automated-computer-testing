"""TouchstoneWindow — application main window."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from src.models.job import JobInfo, ReportType
from src.models.settings import Settings
from src.models.test_result import TestResult
from src.ui.pages.job_setup_page import JobSetupPage
from src.ui.pages.test_dashboard_page import TestDashboardPage
from src.ui.stylesheet import QSS_DARK, QSS_LIGHT, refresh_style
from src.utils.theme_prefs import load_theme, save_theme


class TouchstoneWindow(QMainWindow):
    """Application main window with two-page QStackedWidget flow."""

    def __init__(self, dev_manual: bool = False) -> None:
        super().__init__()

        # Shared state
        self.job_info: JobInfo | None = None
        self.test_results: list[TestResult] = []
        self.manual_items: list[TestResult] = []
        self.settings: Settings = Settings()

        # Theme
        theme = load_theme()
        self._apply_theme(theme)

        self.setWindowTitle("Touchstone")
        self.setMinimumSize(900, 640)

        # Stack: index 0 = JobSetupPage, index 1 = TestDashboardPage
        self._stack = QStackedWidget()
        self._setup_page = JobSetupPage(self)
        self._dashboard = TestDashboardPage(self, self)
        self._stack.addWidget(self._setup_page)
        self._stack.addWidget(self._dashboard)
        self.setCentralWidget(self._stack)

        # Navigation signals
        self._setup_page.start_testing.connect(self._on_start_testing)
        self._dashboard.new_job_requested.connect(self._on_new_job_requested)

        # Elevation warning
        if not self._is_admin():
            self._dashboard._header.show_elevation_warning()

        # Load recent jobs for setup page
        self._setup_page.reload_recent_jobs()

        if dev_manual:
            self._start_dev_manual()
        else:
            self._stack.setCurrentIndex(0)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_start_testing(self, job_info: JobInfo) -> None:
        self.job_info = job_info
        self.test_results = []
        self.manual_items = []
        self._stack.setCurrentIndex(1)
        self._dashboard.on_page_entered(job_info)

    def _on_new_job_requested(self) -> None:
        self._stack.setCurrentIndex(0)
        self._setup_page.reload_recent_jobs()

    # ── Dev manual ────────────────────────────────────────────────────────────

    def _start_dev_manual(self) -> None:
        """Bypass JobSetupPage and go straight to test dashboard with a dummy job."""
        self.job_info = JobInfo(
            customer_name="Dev",
            device_description="Test Device",
            job_number="DEV-001",
            report_type=ReportType.BEFORE,
        )
        self.test_results = []
        self.manual_items = []
        self._stack.setCurrentIndex(1)
        self._dashboard.on_page_entered(self.job_info)
        QTimer.singleShot(500, self._dashboard.dev_trigger_display)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self, theme: str) -> None:
        app = QApplication.instance()
        if app is None:
            return
        if theme == "light":
            app.setStyleSheet(QSS_LIGHT)
            app.setPalette(self._light_palette())
        else:
            app.setStyleSheet(QSS_DARK)
            app.setPalette(self._dark_palette())

    def set_theme(self, theme: str) -> None:
        save_theme(theme)
        self._apply_theme(theme)
        refresh_style(self)

    @staticmethod
    def _dark_palette() -> QPalette:
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window,          QColor("#09090b"))
        pal.setColor(QPalette.ColorRole.WindowText,      QColor("#fafafa"))
        pal.setColor(QPalette.ColorRole.Base,            QColor("#18181b"))
        pal.setColor(QPalette.ColorRole.AlternateBase,   QColor("#27272a"))
        pal.setColor(QPalette.ColorRole.Text,            QColor("#fafafa"))
        pal.setColor(QPalette.ColorRole.Button,          QColor("#27272a"))
        pal.setColor(QPalette.ColorRole.ButtonText,      QColor("#fafafa"))
        pal.setColor(QPalette.ColorRole.Highlight,       QColor("#3b82f6"))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.BrightText,      QColor("#ffffff"))
        return pal

    @staticmethod
    def _light_palette() -> QPalette:
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window,          QColor("#f9fafb"))
        pal.setColor(QPalette.ColorRole.WindowText,      QColor("#111827"))
        pal.setColor(QPalette.ColorRole.Base,            QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.AlternateBase,   QColor("#f3f4f6"))
        pal.setColor(QPalette.ColorRole.Text,            QColor("#111827"))
        pal.setColor(QPalette.ColorRole.Button,          QColor("#e5e7eb"))
        pal.setColor(QPalette.ColorRole.ButtonText,      QColor("#111827"))
        pal.setColor(QPalette.ColorRole.Highlight,       QColor("#3b82f6"))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.BrightText,      QColor("#ffffff"))
        return pal

    # ── Admin check ───────────────────────────────────────────────────────────

    @staticmethod
    def _is_admin() -> bool:
        try:
            if sys.platform == "win32":
                import ctypes
                return bool(ctypes.windll.shell32.IsUserAnAdmin())
            else:
                import os
                return os.geteuid() == 0
        except Exception:
            return True
