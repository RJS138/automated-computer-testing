"""MainDashboard — single persistent dashboard page.

Layout:
    HeaderBar
    ── body (horizontal) ──────────────────────────────────
    SystemInfoPanel (fixed 180 px)  |  right column
                                    |    AUTOMATED TESTS
                                    |    scroll grid (3 cols)
                                    |    MANUAL TESTS
                                    |    scroll grid (4 cols)
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.models.job import TestMode
from src.models.test_result import TestResult
from src.ui.widgets.dashboard_card import DashboardCard
from src.ui.widgets.header_bar import HeaderBar
from src.ui.widgets.system_info_panel import SystemInfoPanel
from src.ui.workers import TestWorker

# ── Test imports ──────────────────────────────────────────────────────────────
from src.tests.cpu import CpuTest
from src.tests.ram import RamTest
from src.tests.storage import StorageTest
from src.tests.battery import BatteryTest
from src.tests.gpu import GpuTest
from src.tests.network import NetworkTest
from src.tests.smart_deep import SmartDeepTest
from src.tests.ram_extended import RamExtendedTest
from src.tests.fan import FanTest

# ── Dialog imports ────────────────────────────────────────────────────────────
from src.ui.helpers.display_dialog import DisplayDialog
from src.ui.helpers.keyboard_dialog import KeyboardDialog
from src.ui.helpers.touchpad_dialog import TouchpadDialog
from src.ui.helpers.speakers_dialog import SpeakersDialog
from src.ui.helpers.usb_dialog import UsbDialog
from src.ui.helpers.hdmi_dialog import HdmiDialog
from src.ui.helpers.webcam_dialog import WebcamDialog


class MainDashboard(QWidget):
    """Single-page dashboard: header bar + system info panel + test grid."""

    # ── Registry ──────────────────────────────────────────────────────────────

    _TEST_REGISTRY: list[dict] = [
        # ── Automated — parallel group ───────────────────────────────────────
        {"name": "cpu",     "display_name": "CPU Stress",  "cls": CpuTest,     "group": "parallel",   "kind": "automated", "advanced_only": False, "dialog_cls": None, "dialog_kwargs": {}},
        {"name": "ram",     "display_name": "RAM Scan",    "cls": RamTest,     "group": "sequential", "kind": "automated", "advanced_only": False, "dialog_cls": None, "dialog_kwargs": {}},
        {"name": "storage", "display_name": "Storage",     "cls": StorageTest, "group": "sequential", "kind": "automated", "advanced_only": False, "dialog_cls": None, "dialog_kwargs": {}},
        {"name": "battery", "display_name": "Battery",     "cls": BatteryTest, "group": "parallel",   "kind": "automated", "advanced_only": False, "dialog_cls": None, "dialog_kwargs": {}},
        {"name": "gpu",     "display_name": "GPU",         "cls": GpuTest,     "group": "parallel",   "kind": "automated", "advanced_only": False, "dialog_cls": None, "dialog_kwargs": {}},
        {"name": "network", "display_name": "Network",     "cls": NetworkTest, "group": "parallel",   "kind": "automated", "advanced_only": False, "dialog_cls": None, "dialog_kwargs": {}},
        # ── Automated — advanced only ────────────────────────────────────────
        {"name": "smart_deep",   "display_name": "SMART Deep",   "cls": SmartDeepTest,   "group": "sequential", "kind": "automated", "advanced_only": True, "dialog_cls": None, "dialog_kwargs": {}},
        {"name": "ram_extended", "display_name": "RAM Extended",  "cls": RamExtendedTest, "group": "sequential", "kind": "automated", "advanced_only": True, "dialog_cls": None, "dialog_kwargs": {}},
        {"name": "fan",          "display_name": "Fan Test",      "cls": FanTest,         "group": "parallel",   "kind": "automated", "advanced_only": True, "dialog_cls": None, "dialog_kwargs": {}},
        # ── Manual tests ─────────────────────────────────────────────────────
        {"name": "display",  "display_name": "Display",  "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": DisplayDialog,  "dialog_kwargs": {}},
        {"name": "keyboard", "display_name": "Keyboard", "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": KeyboardDialog, "dialog_kwargs": {}},
        {"name": "touchpad", "display_name": "Touchpad", "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": TouchpadDialog, "dialog_kwargs": {}},
        {"name": "speakers", "display_name": "Speakers", "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": SpeakersDialog, "dialog_kwargs": {}},
        {"name": "usb_a",   "display_name": "USB-A",    "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": UsbDialog,     "dialog_kwargs": {"port_type": "USB-A"}},
        {"name": "usb_c",   "display_name": "USB-C",    "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": UsbDialog,     "dialog_kwargs": {"port_type": "USB-C"}},
        {"name": "hdmi",    "display_name": "HDMI",     "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": HdmiDialog,    "dialog_kwargs": {}},
        {"name": "webcam",  "display_name": "Webcam",   "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": WebcamDialog,  "dialog_kwargs": {}},
    ]

    # ── Constructor ───────────────────────────────────────────────────────────

    def __init__(self, window, parent=None) -> None:
        super().__init__(parent)
        self._window = window

        # ── Cards and results dicts ───────────────────────────────────────────
        self._cards: dict[str, DashboardCard] = {}
        self._results: dict[str, TestResult] = {}
        self._si_result: TestResult | None = None

        # ── Layout ────────────────────────────────────────────────────────────
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        self._header = HeaderBar(self)
        main_layout.addWidget(self._header)

        # Body
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(8)

        # Left column — system info panel (fixed 180 px)
        self._info_panel = SystemInfoPanel(self)
        body_layout.addWidget(self._info_panel)

        # Right column
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # Automated section title
        auto_title = QLabel("AUTOMATED TESTS")
        auto_title.setProperty("class", "section-title")
        right_layout.addWidget(auto_title)

        # Automated grid (3 columns) inside a scroll area
        auto_scroll = QScrollArea()
        auto_scroll.setWidgetResizable(True)
        auto_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        auto_container = QWidget()
        auto_grid = QGridLayout(auto_container)
        auto_grid.setContentsMargins(0, 0, 0, 0)
        auto_grid.setSpacing(6)

        auto_scroll.setWidget(auto_container)
        right_layout.addWidget(auto_scroll)

        # Manual section title
        manual_title = QLabel("MANUAL TESTS")
        manual_title.setProperty("class", "section-title")
        right_layout.addWidget(manual_title)

        # Manual grid (4 columns) inside a scroll area
        manual_scroll = QScrollArea()
        manual_scroll.setWidgetResizable(True)
        manual_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        manual_container = QWidget()
        manual_grid = QGridLayout(manual_container)
        manual_grid.setContentsMargins(0, 0, 0, 0)
        manual_grid.setSpacing(6)

        manual_scroll.setWidget(manual_container)
        right_layout.addWidget(manual_scroll)

        body_layout.addWidget(right_col)
        main_layout.addLayout(body_layout)

        # ── Populate cards from registry ──────────────────────────────────────
        auto_col = 0
        auto_row = 0
        manual_col = 0
        manual_row = 0
        auto_cols = 3
        manual_cols = 4

        for entry in self._TEST_REGISTRY:
            name = entry["name"]
            display_name = entry["display_name"]
            kind = entry["kind"]
            advanced_only = entry["advanced_only"]

            card = DashboardCard(name, display_name, parent=auto_container if kind == "automated" else manual_container)
            card.run_requested.connect(self._on_run_requested)
            self._cards[name] = card

            # Create a TestResult for each test (excluding system_info which is silent)
            self._results[name] = TestResult(name=name, display_name=display_name)

            if kind == "automated":
                auto_grid.addWidget(card, auto_row, auto_col)
                auto_col += 1
                if auto_col >= auto_cols:
                    auto_col = 0
                    auto_row += 1
            else:
                manual_grid.addWidget(card, manual_row, manual_col)
                manual_col += 1
                if manual_col >= manual_cols:
                    manual_col = 0
                    manual_row += 1

            # Hide advanced-only cards initially
            if advanced_only:
                card.hide()

        # ── Signal connections ────────────────────────────────────────────────
        self._header.mode_changed.connect(self._on_mode_changed)
        self._header.run_all_clicked.connect(self._on_run_all)

        # ── Start system info ─────────────────────────────────────────────────
        self._start_system_info()

    # ── Mode switching ────────────────────────────────────────────────────────

    def _on_mode_changed(self, mode: str) -> None:
        """Show/hide advanced-only cards based on selected mode."""
        is_advanced = mode == "advanced"
        for entry in self._TEST_REGISTRY:
            if entry["advanced_only"]:
                card = self._cards.get(entry["name"])
                if card is not None:
                    if is_advanced:
                        card.show()
                    else:
                        card.hide()
            card = self._cards.get(entry["name"])
            if card is not None:
                card.set_advanced(is_advanced)

    # ── System info ───────────────────────────────────────────────────────────

    def _start_system_info(self) -> None:
        """Launch system_info test silently in background."""
        self._info_panel.set_loading()

        self._si_result = TestResult(name="system_info", display_name="System Info")

        worker = TestWorker(
            name="system_info",
            module="system_info",
            cls_name="SystemInfoTest",
            result=self._si_result,
            mode=TestMode.QUICK,
            parent=self,
        )
        worker.finished.connect(self._on_system_info_done)
        worker.start()

    def _on_system_info_done(self, name: str) -> None:  # noqa: ARG002
        """Populate the info panel once system_info completes."""
        if self._si_result is not None:
            self._info_panel.populate(self._si_result.data)
        self._recalculate_overall()

    def _recalculate_overall(self) -> None:
        """Placeholder — will be properly implemented in Task 7."""
        self._info_panel.set_overall("waiting")

    # ── Stubs for later tasks ─────────────────────────────────────────────────

    def _on_run_all(self) -> None:
        pass

    def _on_run_requested(self, name: str) -> None:
        pass

    # ── Dev helper ────────────────────────────────────────────────────────────

    def dev_trigger_display(self) -> None:
        """Trigger display dialog — used by --dev-manual flag."""
        card = self._cards.get("display")
        if card:
            card.run_requested.emit("display")
