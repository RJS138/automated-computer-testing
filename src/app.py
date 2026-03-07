"""Main Textual application class."""

from textual.app import App, ComposeResult

from .models.job import JobInfo
from .models.test_result import TestResult
from .ui.screens.readiness import ReadinessScreen


class PCTesterApp(App):
    """PC Diagnostic Testing Application."""

    TITLE = "PC Tester"
    CSS = """
    Screen {
        background: $background;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # Shared state across screens
        self.job_info: JobInfo | None = None
        self.test_results: list[TestResult] = []
        self.manual_items: list[TestResult] = []

    def on_mount(self) -> None:
        self.push_screen(ReadinessScreen())
