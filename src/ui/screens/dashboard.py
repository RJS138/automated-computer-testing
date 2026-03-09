"""
Dashboard screen — live test progress with Textual Workers.

Architecture
------------
- Each test runs in a Textual Worker (thread=True), completely off the UI thread.
- `on_worker_state_changed` fires on the UI thread when any worker finishes,
  so card updates are always thread-safe.
- A single screen-level set_interval drives all card animations.
- Parallel group (info-gathering) all start together.
- Sequential group (stress tests) chains: next starts when previous finishes.
"""

import asyncio
from collections import deque
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import ScrollableContainer
from textual.widgets import Button, Label, Static
from textual.worker import WorkerState

from ...models.test_result import TestResult, TestStatus
from ...models.job import TestMode
from ...config import (
    CPU_STRESS_QUICK, CPU_STRESS_FULL,
    RAM_SCAN_QUICK,   RAM_SCAN_FULL,
    STORAGE_SPEED_QUICK, STORAGE_SPEED_FULL,
)
from ..widgets.test_card import TestCard

if TYPE_CHECKING:
    from ...app import PCTesterApp


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# (name, display_name, module, class_name)
TEST_REGISTRY = [
    ("system_info", "System Info", "system_info", "SystemInfoTest"),
    ("cpu",         "CPU",         "cpu",         "CpuTest"),
    ("ram",         "RAM",         "ram",         "RamTest"),
    ("storage",     "Storage",     "storage",     "StorageTest"),
    ("gpu",         "GPU",         "gpu",         "GpuTest"),
    ("display",     "Displays",    "display",     "DisplayTest"),
    ("network",     "Network",     "network",     "NetworkTest"),
    ("battery",     "Battery",     "battery",     "BatteryTest"),
]

_REGISTRY_MAP: dict[str, tuple[str, str]] = {
    name: (mod, cls) for name, _, mod, cls in TEST_REGISTRY
}

_EXPECTED_SECONDS: dict[str, dict[TestMode, float | None]] = {
    "cpu":         {TestMode.QUICK: CPU_STRESS_QUICK,         TestMode.FULL: CPU_STRESS_FULL},
    "ram":         {TestMode.QUICK: RAM_SCAN_QUICK,           TestMode.FULL: RAM_SCAN_FULL},
    "storage":     {TestMode.QUICK: STORAGE_SPEED_QUICK + 5,  TestMode.FULL: STORAGE_SPEED_FULL + 10},
    "system_info": {TestMode.QUICK: None, TestMode.FULL: None},
    "gpu":         {TestMode.QUICK: None, TestMode.FULL: None},
    "display":     {TestMode.QUICK: None, TestMode.FULL: None},
    "network":     {TestMode.QUICK: None, TestMode.FULL: None},
    "battery":     {TestMode.QUICK: None, TestMode.FULL: None},
}

# Tests that run simultaneously (fast, info-gathering)
_PARALLEL = ["system_info", "network", "battery", "gpu", "display"]

# Tests that run one at a time after the parallel group (resource-intensive)
_SEQUENTIAL = ["cpu", "ram", "storage"]


# ---------------------------------------------------------------------------
# Blocking test runner — called inside a Textual Worker thread.
# Gets its own asyncio event loop so it never touches Textual's loop.
# ---------------------------------------------------------------------------

def _run_test_blocking(module_name: str, class_name: str,
                       result: TestResult, mode: TestMode) -> None:
    import asyncio
    import importlib

    mod = importlib.import_module(f"src.tests.{module_name}")
    TestClass = getattr(mod, class_name)
    test = TestClass(result=result, mode=mode)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(test.safe_run())
    except Exception as exc:
        result.mark_error(str(exc))
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Dashboard screen
# ---------------------------------------------------------------------------

class DashboardScreen(Screen):
    DEFAULT_CSS = """
    DashboardScreen { layout: vertical; }

    #dashboard-header {
        height: 5;
        border-bottom: solid $primary;
        padding: 0 2;
        layout: vertical;
    }
    #header-row {
        layout: horizontal;
        height: 1;
        margin: 1 0 0 0;
    }
    #dashboard-title {
        width: 1fr;
        text-style: bold;
        color: $primary;
    }
    #dashboard-status { color: $text-muted; }
    #device-info      { height: 1; color: $text; }

    #cards-container  { padding: 1 2; }

    #btn-next {
        dock: bottom;
        margin: 1 2;
        width: 1fr;
    }
    """

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._results:          dict[str, TestResult] = {}
        self._cards:            dict[str, TestCard]   = {}
        self._parallel_running: set[str]              = set()
        self._sequential_queue: deque[str]            = deque(_SEQUENTIAL)
        self._completed         = 0
        self._total             = len(TEST_REGISTRY)
        self._finished          = False

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        job = self.app.job_info  # type: ignore[attr-defined]
        with Static(id="dashboard-header"):
            with Static(id="header-row"):
                yield Label(
                    f"{job.customer_name}  ·  {job.device_description}  ·  "
                    f"{job.report_type.value.upper()}  ·  {job.test_mode.value.upper()}",
                    id="dashboard-title",
                )
                yield Label("Starting…", id="dashboard-status")
            yield Label("", id="device-info")

        with ScrollableContainer(id="cards-container"):
            pass

        yield Button("Next: Manual Checks →", variant="primary",
                     id="btn-next", disabled=True)

    # ------------------------------------------------------------------
    # Mount — start animation clock, then mount cards and kick off tests
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        # Animation clock lives on the Screen — always fires regardless of
        # what workers are doing.
        self._anim_timer = self.set_interval(1 / 10, self._tick_cards)
        self.call_after_refresh(self._setup)

    def _tick_cards(self) -> None:
        for card in self._cards.values():
            if card.test_active:
                card.tick()

    # ------------------------------------------------------------------
    # Setup: mount all cards, then start the parallel group
    # ------------------------------------------------------------------

    async def _setup(self) -> None:
        container = self.query_one("#cards-container", ScrollableContainer)

        for name, display_name, *_ in TEST_REGISTRY:
            result = TestResult(name=name, display_name=display_name)
            self._results[name] = result
            card = TestCard(result, id=f"card-{name}")
            self._cards[name] = card
            await container.mount(card)
            # Yield after each card so Textual paints it in WAITING state
            # before the next one appears — gives a nice "cards loading" effect.
            await asyncio.sleep(0.04)

        self.app.test_results = list(self._results.values())  # type: ignore[attr-defined]

        # One more cycle to let all cards fully render before any go RUNNING.
        await asyncio.sleep(0.1)

        # Launch the parallel group with a small visual stagger.
        for name in _PARALLEL:
            if name in _REGISTRY_MAP:
                self._launch(name)
                self._parallel_running.add(name)
                await asyncio.sleep(0.07)   # user sees each card light up in turn

    # ------------------------------------------------------------------
    # Launch one test as a Textual Worker (thread)
    # ------------------------------------------------------------------

    def _launch(self, name: str) -> None:
        result   = self._results[name]
        card     = self._cards[name]
        job      = self.app.job_info  # type: ignore[attr-defined]
        expected = (_EXPECTED_SECONDS.get(name) or {}).get(job.test_mode)
        module, cls_name = _REGISTRY_MAP[name]

        # Transition card to RUNNING on the UI thread.
        result.mark_running()
        card.start_running(expected)
        self._status(f"{self._completed}/{self._total}  ·  {result.display_name}: running…")

        # The worker function runs in a background thread.
        # Capture locals explicitly so the closure is correct in a loop.
        def _worker(mod=module, cls=cls_name, res=result, mode=job.test_mode) -> None:
            _run_test_blocking(mod, cls, res, mode)

        self.run_worker(_worker, name=f"test__{name}", thread=True, exclusive=False)

    # ------------------------------------------------------------------
    # React to worker completion — fires on the UI thread
    # ------------------------------------------------------------------

    def on_worker_state_changed(self, event) -> None:
        # Filter: only our test workers, only terminal states.
        wname = event.worker.name or ""
        if not wname.startswith("test__"):
            return
        if event.state not in (WorkerState.SUCCESS, WorkerState.ERROR):
            return

        name = wname[len("test__"):]
        self._on_complete(name)

    def _on_complete(self, name: str) -> None:
        result = self._results[name]
        card   = self._cards[name]

        card.update_result(result)
        self._completed += 1
        self._status(f"{self._completed}/{self._total} complete")

        if name == "system_info":
            self._show_device_info(result)

        # Decide what to do next.
        if name in _PARALLEL:
            self._parallel_running.discard(name)
            if not self._parallel_running:
                # All parallel tests done → start the sequential queue.
                self._next_sequential()
        else:
            # A sequential test finished → start the next one (if any).
            self._next_sequential()

    # ------------------------------------------------------------------
    # Sequential chain
    # ------------------------------------------------------------------

    def _next_sequential(self) -> None:
        if self._sequential_queue:
            self._launch(self._sequential_queue.popleft())
        else:
            self._all_done()

    def _all_done(self) -> None:
        self._finished = True
        self._anim_timer.stop()
        self._status(f"All {self._total} tests complete ✓")
        self.query_one("#btn-next", Button).disabled = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _status(self, text: str) -> None:
        self.query_one("#dashboard-status", Label).update(text)

    def _show_device_info(self, si_result: TestResult) -> None:
        d      = si_result.data
        model  = d.get("chassis_model") or d.get("board_model") or "Unknown"
        serial = d.get("board_serial") or "—"
        a_num  = d.get("apple_model_number", "")
        model_str = f"{model} ({a_num})" if a_num else model
        self.query_one("#device-info", Label).update(
            f"[dim]Device:[/dim] {model_str}   [dim]Serial:[/dim] {serial}"
        )
        if a_num:
            job = self.app.job_info  # type: ignore[attr-defined]
            self.query_one("#dashboard-title", Label).update(
                f"{job.customer_name}  ·  {job.device_description}  ·  "
                f"{a_num}  ·  {job.report_type.value.upper()}  ·  {job.test_mode.value.upper()}"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-next" and self._finished:
            from .manual_tests import ManualTestsScreen
            self.app.push_screen(ManualTestsScreen())
