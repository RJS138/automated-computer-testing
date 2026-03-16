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
from src.models.test_result import TestResult, TestStatus
from src.ui.widgets.dashboard_card import DashboardCard
from src.ui.widgets.header_bar import HeaderBar
from src.ui.widgets.report_options_panel import ReportOptionsPanel
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

        # ── Run-all state ─────────────────────────────────────────────────────
        self._running_all: bool = False
        self._active_workers: list[TestWorker] = []
        self._parallel_done_count: int = 0
        self._parallel_total: int = 0
        self._sequential_queue: list[dict] = []

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
        self._right_layout = QVBoxLayout(right_col)
        self._right_layout.setContentsMargins(0, 0, 0, 0)
        self._right_layout.setSpacing(8)
        right_layout = self._right_layout  # local alias for readability below

        # Report options panel (Advanced mode only — hidden by default)
        self._report_options = ReportOptionsPanel(self)
        self._report_options.hide()
        right_layout.addWidget(self._report_options)

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
        self._header.generate_report_clicked.connect(self._on_generate_report)
        self._header.new_job_clicked.connect(self._on_new_job)

        # Keep report worker alive while it runs
        self._report_worker: object | None = None

        # ── Start system info ─────────────────────────────────────────────────
        self._start_system_info()

    # ── Mode switching ────────────────────────────────────────────────────────

    def _on_mode_changed(self, mode: str) -> None:
        """Show/hide advanced-only cards and report options panel based on selected mode."""
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
        self._report_options.setVisible(is_advanced)

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
        """Calculate overall status from all completed results and update panel + header."""
        statuses = [r.status.value for r in self._results.values()]
        if not statuses:
            self._info_panel.set_overall("waiting")
            return

        # Priority: fail/error > warn > skip > pass > running > waiting
        priority = ["fail", "error", "warn", "skip", "pass", "running", "waiting"]
        overall = "waiting"
        for p in priority:
            if p in statuses:
                overall = p
                break

        self._info_panel.set_overall(overall)

        # Check if all checked tests are done (no WAITING or RUNNING)
        incomplete = {"waiting", "running"}
        all_done = all(
            r.status.value not in incomplete
            for name, r in self._results.items()
            if self._cards.get(name) and self._cards[name].is_checked()
        )
        if all_done and not self._running_all:
            self._header.set_action_state("generate_report")

    # ── Run All ───────────────────────────────────────────────────────────────

    def _on_run_all(self) -> None:
        """Construct JobInfo, launch all checked automated tests."""
        from src.models.job import JobInfo, ReportType

        # Build JobInfo from header fields
        report_type = ReportType.AFTER if self._header.report_type() == "after" else ReportType.BEFORE
        self._window.job_info = JobInfo(
            customer_name=self._header.customer(),
            device_description=self._header.device(),
            job_number=self._header.job_number(),
            report_type=report_type,
        )

        self._running_all = True
        for card in self._cards.values():
            card.set_running_all(True)

        # Separate checked automated tests into parallel and sequential groups
        parallel_entries = []
        self._sequential_queue = []
        for entry in self._TEST_REGISTRY:
            if entry["kind"] != "automated":
                continue
            card = self._cards.get(entry["name"])
            if card is None or not card.is_checked():
                continue
            if entry["advanced_only"] and self._header.mode() != "advanced":
                continue
            if entry["group"] == "parallel":
                parallel_entries.append(entry)
            else:
                self._sequential_queue.append(entry)

        self._parallel_total = len(parallel_entries)
        self._parallel_done_count = 0

        if parallel_entries:
            for entry in parallel_entries:
                self._launch_test(entry)
        else:
            # No parallel tests — go straight to sequential
            self._next_sequential()

    def _on_run_requested(self, name: str) -> None:
        """Individual card Run/Re-run button clicked."""
        if self._running_all:
            return  # ignore individual runs during Run All
        entry = next((e for e in self._TEST_REGISTRY if e["name"] == name), None)
        if entry is None:
            return
        if entry["kind"] == "manual":
            self._run_single_manual(entry)
            return
        result = self._results.get(name)
        if result is None:
            return
        # Reset result and card to RUNNING
        result.status = TestStatus.WAITING
        result.summary = ""
        result.error_message = ""
        result.data = {}
        card = self._cards[name]
        card.set_status("running")
        worker = self._make_worker(entry, result, on_done=lambda n: self._on_single_test_done(n))
        self._active_workers.append(worker)
        worker.start()

    # ── Worker helpers ────────────────────────────────────────────────────────

    def _launch_test(self, entry: dict) -> None:
        """Launch a test worker for an automated registry entry."""
        name = entry["name"]
        result = self._results[name]
        result.status = TestStatus.WAITING
        result.summary = ""
        result.error_message = ""
        result.data = {}
        card = self._cards[name]
        card.set_status("running")
        on_done = self._on_parallel_test_done if entry["group"] == "parallel" else self._on_sequential_test_done
        worker = self._make_worker(entry, result, on_done=on_done)
        self._active_workers.append(worker)
        worker.start()

    def _make_worker(self, entry: dict, result: TestResult, on_done) -> TestWorker:
        """Create and wire a TestWorker for the given registry entry."""
        cls = entry["cls"]
        module_name = cls.__module__.split(".")[-1]
        cls_name = cls.__name__
        worker = TestWorker(
            name=entry["name"],
            module=module_name,
            cls_name=cls_name,
            result=result,
            mode=TestMode.QUICK,
            parent=self,
        )
        worker.finished.connect(on_done)
        return worker

    # ── Result callbacks ──────────────────────────────────────────────────────

    def _on_parallel_test_done(self, name: str) -> None:
        self._apply_result(name)
        self._parallel_done_count += 1
        if self._parallel_done_count >= self._parallel_total:
            # All parallel done → start sequential
            self._next_sequential()

    def _on_sequential_test_done(self, name: str) -> None:
        self._apply_result(name)
        self._next_sequential()

    def _on_single_test_done(self, name: str) -> None:
        self._apply_result(name)
        self._recalculate_overall()

    def _next_sequential(self) -> None:
        if self._sequential_queue:
            entry = self._sequential_queue.pop(0)
            self._launch_test(entry)
        else:
            self._on_automated_done()

    def _on_automated_done(self) -> None:
        """Called when all automated tests finish during Run All. Starts manual queue."""
        self._run_manual_queue()

    def _run_manual_queue(self) -> None:
        """Build and execute the ordered queue of checked manual tests."""
        self._manual_queue: list[dict] = [
            entry for entry in self._TEST_REGISTRY
            if entry["kind"] == "manual"
            and self._cards.get(entry["name"]) is not None
            and self._cards[entry["name"]].is_checked()
        ]
        self._run_next_manual()

    def _run_next_manual(self) -> None:
        """Pop next manual test from queue and run its dialog."""
        if not self._manual_queue:
            self._on_all_tests_done()
            return

        entry = self._manual_queue.pop(0)
        name = entry["name"]
        dialog_cls = entry["dialog_cls"]
        dialog_kwargs = entry["dialog_kwargs"]

        card = self._cards.get(name)
        if card:
            card.set_status("running")

        dialog = dialog_cls(parent=self, **dialog_kwargs)
        dialog.run()
        result_str = dialog.result_str  # "pass" / "fail" / "skip"

        result = self._results.get(name)
        if result:
            if result_str == "pass":
                result.mark_pass(f"{entry['display_name']} passed")
            elif result_str == "fail":
                result.mark_fail(f"{entry['display_name']} failed")
            else:
                result.mark_skip(f"{entry['display_name']} skipped")

        if card:
            card.set_status(result.status.value if result else result_str, "")

        if result and result not in self._window.test_results:
            self._window.test_results.append(result)
            self._window.manual_items.append(result)

        self._recalculate_overall()
        self._run_next_manual()

    def _on_all_tests_done(self) -> None:
        """Called when all tests (automated + manual) complete during Run All."""
        self._running_all = False
        for card in self._cards.values():
            card.set_running_all(False)
        self._recalculate_overall()

    def _run_single_manual(self, entry: dict) -> None:
        """Run a single manual test outside of Run All queue."""
        name = entry["name"]
        dialog_cls = entry["dialog_cls"]
        dialog_kwargs = entry["dialog_kwargs"]

        card = self._cards.get(name)
        if card:
            card.set_status("running")

        dialog = dialog_cls(parent=self, **dialog_kwargs)
        dialog.run()
        result_str = dialog.result_str

        result = self._results.get(name)
        if result:
            if result_str == "pass":
                result.mark_pass(f"{entry['display_name']} passed")
            elif result_str == "fail":
                result.mark_fail(f"{entry['display_name']} failed")
            else:
                result.mark_skip(f"{entry['display_name']} skipped")

        if card and result:
            card.set_status(result.status.value, "")

        if result and result not in self._window.test_results:
            self._window.test_results.append(result)
            self._window.manual_items.append(result)

        self._recalculate_overall()

    def _apply_result(self, name: str) -> None:
        """Update the card for a completed test and clean up the worker."""
        result = self._results.get(name)
        card = self._cards.get(name)
        if result and card:
            card.set_status(result.status.value, result.summary or "", result.error_message or "")
        # Clean up finished workers
        self._active_workers = [w for w in self._active_workers if w.isRunning()]
        self._recalculate_overall()

    # ── Report generation ─────────────────────────────────────────────────────

    def _on_generate_report(self) -> None:
        """Immediately switch button to New Job state, then generate report in background."""
        self._header.set_action_state("new_job")

        from src.ui.workers import ReportWorker
        job = self._window.job_info
        results = self._window.test_results

        self._report_worker = ReportWorker(job=job, results=results, parent=self)
        self._report_worker.status.connect(self._on_report_status)
        self._report_worker.done.connect(self._on_report_done)
        self._report_worker.error.connect(self._on_report_error)
        self._report_worker.start()

    def _on_report_status(self, msg: str) -> None:
        self._header.show_status_message(msg)

    def _on_report_done(self, html_path: str, pdf_path: str) -> None:  # noqa: ARG002
        import webbrowser
        webbrowser.open(html_path)
        self._header.show_status_message(f"Saved: {html_path}")

    def _on_report_error(self, msg: str) -> None:
        self._header.show_status_message(f"Error: {msg}")

    # ── New Job reset ─────────────────────────────────────────────────────────

    def _on_new_job(self) -> None:
        """Reset everything for a new job."""
        # Reset cards
        for name, card in self._cards.items():  # noqa: B007
            card.set_status("waiting")

        # Reset results
        from src.models.test_result import TestStatus
        for result in self._results.values():
            result.status = TestStatus.WAITING
            result.summary = ""
            result.error_message = ""
            result.data = {}

        # Reset window state
        self._window.job_info = None
        self._window.test_results = []
        self._window.manual_items = []

        # Reset header
        self._header.set_action_state("run_all_disabled")

        # Re-run system info
        self._start_system_info()

    # ── Dev helper ────────────────────────────────────────────────────────────

    def dev_trigger_display(self) -> None:
        """Trigger display dialog — used by --dev-manual flag."""
        card = self._cards.get("display")
        if card:
            card.run_requested.emit("display")
