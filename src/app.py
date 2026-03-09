"""Main Textual application class."""

import os

from textual.app import App, ComposeResult

from .models.job import JobInfo
from .models.test_result import TestResult
from .ui.screens.readiness import ReadinessScreen

# Applied on top of each screen's DEFAULT_CSS when running on limited terminals.
# Goal: eliminate coloured borders (which bleed on terminals that don't handle
# RGB/256-colour resets correctly) and rely only on text styling for focus indication.
_SIMPLE_CSS = """
Screen { background: $background; }

/* Remove coloured status borders — use a neutral panel border instead */
TestCard               { border: solid $panel; }
TestCard.status-pass   { border: solid $panel; }
TestCard.status-warn   { border: solid $panel; }
TestCard.status-fail   { border: solid $panel; }
TestCard.status-error  { border: solid $panel; }
TestCard.status-running { border: solid $panel; }
TestCard.status-skip   { border: solid $panel; }

/* Replace highlight border on focused inputs/buttons with reverse-video —
   universally supported and doesn't require colour escape sequences */
Input:focus    { border: solid $panel; text-style: bold; }
Button:focus   { text-style: bold reverse; border: none; }
TextArea:focus { border: solid $panel; }
"""

_FANCY_CSS = """
Screen { background: $background; }
"""


class PCTesterApp(App):
    """PC Diagnostic Testing Application."""

    TITLE = "PC Tester"
    SIMPLE_UI: bool = os.environ.get("PCTESTER_SIMPLE_UI") == "1"
    CSS = _SIMPLE_CSS if SIMPLE_UI else _FANCY_CSS

    def __init__(self, dev_manual_item: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._dev_manual_item = dev_manual_item
        # Shared state across screens
        self.job_info: JobInfo | None = None
        self.test_results: list[TestResult] = []
        self.manual_items: list[TestResult] = []

    def on_mount(self) -> None:
        if self._dev_manual_item is not None:
            # Dev mode: skip straight to the manual tests screen.
            # Populate a stub job_info so ReportDoneScreen doesn't crash if
            # the technician happens to complete the flow.
            self.job_info = JobInfo(
                customer_name="DEV",
                device_description="dev-mode",
                job_number="0000",
            )
            from .ui.screens.manual_tests import ManualTestsScreen
            # Empty string means "start from first item"; any other string
            # means "seek to that item id".
            start = self._dev_manual_item or None
            self.push_screen(ManualTestsScreen(start_item=start))
        else:
            self.push_screen(ReadinessScreen())
