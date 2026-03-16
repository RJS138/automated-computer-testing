"""Main application window for Touchstone."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMainWindow

from src.models.job import JobInfo
from src.models.test_result import TestResult
from src.ui.stylesheet import QSS_DARK


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

        # ── Window properties ────────────────────────────────────
        self.setWindowTitle("Touchstone")
        self.setMinimumSize(900, 650)

        # ── Stylesheet ───────────────────────────────────────────
        app = QApplication.instance()
        if app is not None:
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

    def showEvent(self, event) -> None:  # type: ignore[override]
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

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        event.accept()
        sys.exit(0)
