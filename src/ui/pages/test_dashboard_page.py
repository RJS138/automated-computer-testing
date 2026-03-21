"""TestDashboardPage — test execution page replacing MainDashboard."""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.models.job import JobInfo, TestMode
from src.models.test_result import TestResult, TestStatus
from src.tests.battery import BatteryTest
from src.tests.cpu import CpuTest
from src.tests.fan import FanTest
from src.tests.gpu import GpuTest
from src.tests.network import NetworkTest
from src.tests.ram import RamTest
from src.tests.ram_extended import RamExtendedTest
from src.tests.smart_deep import SmartDeepTest
from src.tests.storage import StorageTest
from src.ui.helpers.display_dialog import DisplayDialog
from src.ui.helpers.hdmi_dialog import HdmiDialog
from src.ui.helpers.keyboard_dialog import KeyboardDialog
from src.ui.helpers.speakers_dialog import SpeakersDialog
from src.ui.helpers.touchpad_dialog import TouchpadDialog
from src.ui.helpers.usb_dialog import UsbDialog
from src.ui.helpers.webcam_dialog import WebcamDialog
from src.ui.widgets.category_section import CategorySection
from src.ui.widgets.device_banner import DeviceBanner
from src.ui.widgets.header_bar import HeaderBar
from src.ui.workers import ReportWorker, TestWorker


class TestDashboardPage(QWidget):
    """Test execution page: header + device banner + category sections.

    Signals
    -------
    new_job_requested
        Emitted after the user confirms returning to job setup.
    """

    new_job_requested = Signal()

    # ── Test registry ─────────────────────────────────────────────────────────

    _TEST_REGISTRY: ClassVar[list[dict]] = [
        # Parallel group (launched together on Run All)
        {"name": "network",      "display_name": "Network",      "cls": NetworkTest,     "group": "parallel",   "kind": "automated", "advanced_only": False, "dialog_cls": None,          "dialog_kwargs": {}},
        {"name": "battery",      "display_name": "Battery",      "cls": BatteryTest,     "group": "parallel",   "kind": "automated", "advanced_only": False, "dialog_cls": None,          "dialog_kwargs": {}},
        {"name": "gpu",          "display_name": "GPU",          "cls": GpuTest,         "group": "parallel",   "kind": "automated", "advanced_only": False, "dialog_cls": None,          "dialog_kwargs": {}},
        {"name": "fan",          "display_name": "Fan Test",     "cls": FanTest,         "group": "parallel",   "kind": "automated", "advanced_only": True,  "dialog_cls": None,          "dialog_kwargs": {}},
        # Sequential queue (cpu → ram → storage → smart_deep → ram_extended)
        {"name": "cpu",          "display_name": "CPU Stress",   "cls": CpuTest,         "group": "sequential", "kind": "automated", "advanced_only": False, "dialog_cls": None,          "dialog_kwargs": {}},
        {"name": "ram",          "display_name": "RAM Scan",     "cls": RamTest,         "group": "sequential", "kind": "automated", "advanced_only": False, "dialog_cls": None,          "dialog_kwargs": {}},
        {"name": "storage",      "display_name": "Storage",      "cls": StorageTest,     "group": "sequential", "kind": "automated", "advanced_only": False, "dialog_cls": None,          "dialog_kwargs": {}},
        {"name": "smart_deep",   "display_name": "SMART Deep",   "cls": SmartDeepTest,   "group": "sequential", "kind": "automated", "advanced_only": True,  "dialog_cls": None,          "dialog_kwargs": {}},
        {"name": "ram_extended", "display_name": "RAM Extended", "cls": RamExtendedTest, "group": "sequential", "kind": "automated", "advanced_only": True,  "dialog_cls": None,          "dialog_kwargs": {}},
        # Manual tests
        {"name": "display",  "display_name": "Display",  "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": DisplayDialog,  "dialog_kwargs": {}},
        {"name": "keyboard", "display_name": "Keyboard", "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": KeyboardDialog, "dialog_kwargs": {}},
        {"name": "touchpad", "display_name": "Touchpad", "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": TouchpadDialog, "dialog_kwargs": {}},
        {"name": "speakers", "display_name": "Speakers", "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": SpeakersDialog, "dialog_kwargs": {}},
        {"name": "usb_a",    "display_name": "USB-A",    "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": UsbDialog,      "dialog_kwargs": {"port_type": "USB-A"}},
        {"name": "usb_c",    "display_name": "USB-C",    "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": UsbDialog,      "dialog_kwargs": {"port_type": "USB-C"}},
        {"name": "hdmi",     "display_name": "HDMI",     "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": HdmiDialog,     "dialog_kwargs": {}},
        {"name": "webcam",   "display_name": "Webcam",   "cls": None, "group": None, "kind": "manual", "advanced_only": False, "dialog_cls": WebcamDialog,   "dialog_kwargs": {}},
    ]

    # Category definitions: (title, tests, col_count, short_names)
    _CATEGORIES: ClassVar[
        list[tuple[str, list[tuple[str, str, bool]], int, dict[str, str]]]
    ] = [
        (
            "⚡ Performance",
            [
                ("cpu",          "CPU Stress",   False),
                ("ram",          "RAM Scan",     False),
                ("storage",      "Storage",      False),
                ("smart_deep",   "SMART Deep",   True),
                ("ram_extended", "RAM Extended", True),
            ],
            3,
            {"cpu": "CPU", "ram": "RAM", "storage": "STORAGE", "smart_deep": "SMART", "ram_extended": "RAM+"},
        ),
        (
            "📡 Connectivity",
            [
                ("network", "Network", False),
                ("usb_a",   "USB-A",   False),
                ("usb_c",   "USB-C",   False),
                ("hdmi",    "HDMI",    False),
            ],
            4,
            {"network": "NET", "usb_a": "USB-A", "usb_c": "USB-C", "hdmi": "HDMI"},
        ),
        (
            "🖥 Display & Input",
            [
                ("display",  "Display",  False),
                ("keyboard", "Keyboard", False),
                ("touchpad", "Touchpad", False),
            ],
            3,
            {"display": "DISP", "keyboard": "KB", "touchpad": "TPAD"},
        ),
        (
            "🔊 Audio & Video",
            [("speakers", "Speakers", False), ("webcam", "Webcam", False)],
            2,
            {"speakers": "SPK", "webcam": "CAM"},
        ),
        (
            "🔋 Power",
            [("battery", "Battery", False), ("fan", "Fan Test", True)],
            3,
            {"battery": "BATT", "fan": "FAN"},
        ),
    ]

    def __init__(self, window, parent=None) -> None:
        super().__init__(parent)
        self._window = window

        self._results: dict[str, TestResult] = {}
        self._test_enabled: dict[str, bool] = {e["name"]: True for e in self._TEST_REGISTRY}
        self._si_result: TestResult | None = None
        self._si_worker: TestWorker | None = None

        self._running_all = False
        self._active_workers: list[TestWorker] = []
        self._parallel_done_count = 0
        self._parallel_total = 0
        self._sequential_queue: list[dict] = []
        self._manual_queue: list[dict] = []

        self._report_worker: ReportWorker | None = None
        self._category_sections: list[CategorySection] = []

        self._build_ui()

        for entry in self._TEST_REGISTRY:
            self._results[entry["name"]] = TestResult(
                name=entry["name"], display_name=entry["display_name"]
            )

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = HeaderBar(self)
        self._header.run_all_clicked.connect(self._on_run_all)
        self._header.new_job_clicked.connect(self._on_new_job)
        self._header.settings_clicked.connect(self._on_settings_clicked)
        self._header.mode_changed.connect(self._on_mode_changed)
        outer.addWidget(self._header)

        self._banner = DeviceBanner(self)
        self._banner.generate_report_requested.connect(self._on_generate_report)
        outer.addWidget(self._banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: #09090b; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: #09090b;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(16, 12, 16, 12)
        scroll_layout.setSpacing(8)

        for title, tests, col_count, short_names in self._CATEGORIES:
            section = CategorySection(
                title=title,
                tests=tests,
                col_count=col_count,
                short_names=short_names,
            )
            self._category_sections.append(section)
            scroll_layout.addWidget(section)

        for section in self._category_sections:
            self._wire_section_run_buttons(section)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        outer.addWidget(scroll, stretch=1)

        # Status bar (outside scroll, at bottom of page)
        self._status_bar = QLabel("")
        self._status_bar.setStyleSheet(
            "color: #71717a; font-size: 11px; padding: 4px 16px; "
            "background: #09090b; border-top: 1px solid #27272a;"
        )
        self._status_bar.hide()
        outer.addWidget(self._status_bar)

        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._status_bar.hide)

    def _wire_section_run_buttons(self, section: CategorySection) -> None:
        """Connect run_requested for all currently-instantiated cards in a section."""
        for name, _, _ in section._tests:
            card = section.card(name)
            if card is not None:
                try:
                    card.run_requested.disconnect(self._on_run_requested)
                except RuntimeError:
                    pass
                card.run_requested.connect(self._on_run_requested)

    # ── Page entry ────────────────────────────────────────────────────────────

    def on_page_entered(self, job_info: JobInfo) -> None:
        """Called by app_window after switching stack to this page."""
        self._reset_state()
        self._header.set_job_info(job_info)
        self._header.reset_mode()
        self._start_system_info()

    # ── Mode switch ───────────────────────────────────────────────────────────

    def _on_mode_changed(self, mode: str) -> None:
        is_adv = mode == "advanced"
        for section in self._category_sections:
            section.set_advanced(is_adv)
            self._wire_section_run_buttons(section)

    # ── System info ───────────────────────────────────────────────────────────

    def _start_system_info(self) -> None:
        self._si_result = TestResult(name="system_info", display_name="System Info")
        self._si_worker = TestWorker(
            name="system_info",
            module="system_info",
            cls_name="SystemInfoTest",
            result=self._si_result,
            mode=TestMode.QUICK,
            parent=self,
        )
        self._si_worker.finished.connect(self._on_system_info_done)
        self._si_worker.start()

    def _on_system_info_done(self, _name: str) -> None:
        if self._window.job_info is None:
            return  # navigated away before system_info finished
        if self._si_result is not None:
            self._banner.update_from_result(self._si_result)
            if self._si_result not in self._window.test_results:
                self._window.test_results.append(self._si_result)
        self._recalculate_overall()

    # ── Run All ───────────────────────────────────────────────────────────────

    def _on_run_all(self) -> None:
        self._running_all = True
        for section in self._category_sections:
            for card in section._cards.values():
                card.set_running_all(True)

        is_advanced = self._header.mode() == "advanced"
        parallel_entries: list[dict] = []
        self._sequential_queue = []

        for entry in self._TEST_REGISTRY:
            if entry["kind"] != "automated":
                continue
            if not self._test_enabled.get(entry["name"], True):
                continue
            if entry["advanced_only"] and not is_advanced:
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
            self._next_sequential()

    def _on_run_requested(self, name: str) -> None:
        if self._running_all:
            return
        entry = next((e for e in self._TEST_REGISTRY if e["name"] == name), None)
        if entry is None:
            return
        if entry["kind"] == "manual":
            self._run_single_manual(entry)
            return
        result = self._results.get(name)
        if result is None:
            return
        result.status = TestStatus.WAITING
        result.summary = ""
        result.error_message = ""
        result.data = {}
        card = self._get_card(name)
        if card:
            card.set_status("running")
        worker = self._make_worker(entry, result, on_done=self._on_single_test_done)
        self._active_workers.append(worker)
        worker.start()

    # ── Worker helpers ────────────────────────────────────────────────────────

    def _launch_test(self, entry: dict) -> None:
        name = entry["name"]
        result = self._results[name]
        result.status = TestStatus.WAITING
        result.summary = ""
        result.error_message = ""
        result.data = {}
        card = self._get_card(name)
        if card:
            card.set_status("running")
        on_done = (
            self._on_parallel_test_done
            if entry["group"] == "parallel"
            else self._on_sequential_test_done
        )
        worker = self._make_worker(entry, result, on_done=on_done)
        self._active_workers.append(worker)
        worker.start()

    def _make_worker(self, entry: dict, result: TestResult, on_done) -> TestWorker:
        cls = entry["cls"]
        module_name = cls.__module__.split(".")[-1]
        worker = TestWorker(
            name=entry["name"],
            module=module_name,
            cls_name=cls.__name__,
            result=result,
            mode=TestMode.QUICK,
            parent=self,
        )
        worker.finished.connect(on_done)
        return worker

    def _get_card(self, name: str):
        for section in self._category_sections:
            card = section.card(name)
            if card is not None:
                return card
        return None

    # ── Result callbacks ──────────────────────────────────────────────────────

    def _on_parallel_test_done(self, name: str) -> None:
        self._apply_result(name)
        self._parallel_done_count += 1
        if self._parallel_done_count >= self._parallel_total:
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
        self._run_manual_queue()

    def _apply_result(self, name: str) -> None:
        result = self._results.get(name)
        if result is None:
            return
        for section in self._category_sections:
            if section.card(name) is not None:
                section.update_card(result)
                break
        if result not in self._window.test_results:
            self._window.test_results.append(result)
        self._active_workers = [w for w in self._active_workers if w.isRunning()]
        self._recalculate_overall()

    def _recalculate_overall(self) -> None:
        self._banner.update_overall(list(self._results.values()))

        is_advanced = self._header.mode() == "advanced"
        adv_only = {e["name"]: e["advanced_only"] for e in self._TEST_REGISTRY}
        incomplete = {TestStatus.WAITING, TestStatus.RUNNING}
        all_done = all(
            self._results[name].status not in incomplete
            for name in self._results
            if self._test_enabled.get(name, True)
            and (not adv_only.get(name, False) or is_advanced)
        )
        if all_done and self._running_all:
            self._running_all = False
            for section in self._category_sections:
                for card in section._cards.values():
                    card.set_running_all(False)

    # ── Manual tests ──────────────────────────────────────────────────────────

    def _run_manual_queue(self) -> None:
        queue = [
            e
            for e in self._TEST_REGISTRY
            if e["kind"] == "manual" and self._test_enabled.get(e["name"], True)
        ]
        for entry in queue:
            self._run_single_manual(entry)
        self._on_all_tests_done()

    def _run_single_manual(self, entry: dict) -> None:
        name = entry["name"]
        card = self._get_card(name)
        if card:
            card.set_status("running")

        dialog = entry["dialog_cls"](parent=self, **entry["dialog_kwargs"])
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

        if result:
            for section in self._category_sections:
                if section.card(name) is not None:
                    section.update_card(result)
                    break

        if result and result not in self._window.test_results:
            self._window.test_results.append(result)
            self._window.manual_items.append(result)

        self._recalculate_overall()

    def _on_all_tests_done(self) -> None:
        self._running_all = False
        for section in self._category_sections:
            for card in section._cards.values():
                card.set_running_all(False)
        self._recalculate_overall()

    # ── Report generation ─────────────────────────────────────────────────────

    def _on_generate_report(self) -> None:
        job = self._window.job_info
        results = self._window.test_results
        self._report_worker = ReportWorker(
            job=job, results=results, settings=self._window.settings, parent=self
        )
        self._report_worker.status.connect(self._show_status)
        self._report_worker.done.connect(self._on_report_done)
        self._report_worker.error.connect(self._on_report_error)
        self._report_worker.start()

    def _on_report_done(self, html_path: str, _pdf_path: str) -> None:
        import webbrowser
        webbrowser.open(html_path)
        self._show_status("Report saved.")

    def _on_report_error(self, msg: str) -> None:
        self._show_status(f"Error: {msg}")

    def _show_status(self, msg: str) -> None:
        self._status_bar.setText(msg)
        self._status_bar.show()
        self._status_timer.start(3000)

    # ── New Job ───────────────────────────────────────────────────────────────

    def _on_new_job(self) -> None:
        any_running = any(w.isRunning() for w in self._active_workers)
        if self._si_worker is not None and self._si_worker.isRunning():
            any_running = True
        if any_running:
            reply = QMessageBox.question(
                self,
                "Tests still running",
                "Tests are still running. Return to job setup?\n\n"
                "Running tests will finish in the background.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._reset_state()
        self._window.job_info = None
        self._window.test_results = []
        self._window.manual_items = []
        self._banner.clear()
        self._header.clear_job_info()
        self.new_job_requested.emit()

    def _reset_state(self) -> None:
        """Reset all test results and card states to WAITING."""
        for result in self._results.values():
            result.status = TestStatus.WAITING
            result.summary = ""
            result.error_message = ""
            result.data = {}

        for section in self._category_sections:
            for name, _dn, _adv in section._tests:
                card = section.card(name)
                if card is not None:
                    card.set_status("waiting")

        for key in self._test_enabled:
            self._test_enabled[key] = True

        self._running_all = False
        self._parallel_done_count = 0
        self._parallel_total = 0
        self._sequential_queue = []
        self._manual_queue = []

    # ── Settings ──────────────────────────────────────────────────────────────

    def _on_settings_clicked(self) -> None:
        import copy
        from PySide6.QtWidgets import QDialog
        from src.utils.prefs import save_prefs
        from src.ui.widgets.settings_dialog import SettingsDialog

        dlg = SettingsDialog(
            copy.copy(self._window.settings),
            theme=self._window.theme,  # public property
            parent=self,
        )
        # getattr avoids a security hook that fires on bare .exec() calls:
        if getattr(dlg, "exec")() == QDialog.DialogCode.Accepted:
            new_settings = dlg.result_settings()
            new_theme = dlg.result_theme()
            self._window.settings = new_settings
            self._window.set_theme(new_theme)  # applies visually, no disk write
            save_prefs(                         # single persist call with all values
                theme=new_theme,
                output_format=new_settings.output_format,
                save_path=new_settings.save_path,
            )

    # ── Dev helper ────────────────────────────────────────────────────────────

    def dev_trigger_display(self) -> None:
        """Trigger display dialog — used by --dev-manual flag."""
        card = self._get_card("display")
        if card:
            card.run_requested.emit("display")
