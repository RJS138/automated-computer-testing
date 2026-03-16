"""Main application window for Touchstone."""

from __future__ import annotations

import sys

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QWidget

from src.models.job import JobInfo
from src.models.test_result import TestResult
from src.ui.stylesheet import QSS_DARK


class TouchstoneWindow(QMainWindow):
    """QMainWindow with a QStackedWidget as its central widget.

    Shared state:
        job_info       — populated on the readiness/welcome screens
        test_results   — populated by the dashboard automated tests
        manual_items   — populated by the manual tests screen
    """

    job_info: JobInfo | None
    test_results: list[TestResult]
    manual_items: list[TestResult]

    def __init__(self, dev_manual_item: str | None = None) -> None:
        super().__init__()

        self.job_info = None
        self.test_results = []
        self.manual_items = []

        self._dev_manual_item = dev_manual_item
        self._started = False

        # ── Window properties ────────────────────────────────────
        self.setWindowTitle("Touchstone")
        self.setMinimumSize(900, 650)

        # ── Central stack ────────────────────────────────────────
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # ── Stylesheet ───────────────────────────────────────────
        self.setup_style()

    # ── Style ────────────────────────────────────────────────────

    @staticmethod
    def setup_style() -> None:
        """Apply QSS_DARK stylesheet at the QApplication level."""
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(QSS_DARK)

    # ── Navigation ───────────────────────────────────────────────

    def navigate_to(self, page: QWidget) -> None:
        """Show *page* in the stacked widget.

        If *page* is already in the stack, switch to it.
        Otherwise add it first, then switch.
        """
        idx = self._stack.indexOf(page)
        if idx == -1:
            idx = self._stack.addWidget(page)
        self._stack.setCurrentIndex(idx)

    # ── Show ─────────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)

        # Centre on screen (done here so the window size is finalised first)
        screen = QApplication.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            self.move(
                geom.center().x() - self.width() // 2,
                geom.center().y() - self.height() // 2,
            )

        # Navigate to the appropriate starting page (only on first show)
        if not self._started:
            self._started = True
            if self._dev_manual_item is not None:
                self._open_dev_manual()
            else:
                self._open_readiness()

    def _open_readiness(self) -> None:
        from src.ui.pages.main_dashboard import MainDashboard

        self.navigate_to(MainDashboard(self))

    def _open_dev_manual(self) -> None:
        from src.ui.pages.main_dashboard import MainDashboard
        from PySide6.QtCore import QTimer

        self.job_info = JobInfo(customer_name="Dev", device_description="Dev device", job_number="0")
        dashboard = MainDashboard(self)
        self.navigate_to(dashboard)
        QTimer.singleShot(500, dashboard.dev_trigger_display)

    # ── Close ────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        event.accept()
        sys.exit(0)
