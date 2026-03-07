"""Mode selection screen — Quick vs Full, Before vs After."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Label, RadioButton, RadioSet, Static

from ...models.job import ReportType, TestMode


class ModeSelectScreen(Screen):
    """
    User selects:
      - Test mode: Quick (~5 min) or Full (~30 min)
      - Report type: Before repair or After repair
    """

    DEFAULT_CSS = """
    ModeSelectScreen {
        align: center middle;
    }
    #mode-panel {
        width: 60;
        height: auto;
        border: solid $primary;
        padding: 1 2;
    }
    #panel-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin: 0 0 1 0;
    }
    .section-label {
        text-style: bold;
        margin: 1 0 0 0;
    }
    RadioSet {
        margin: 0 0 1 0;
    }
    #btn-run {
        width: 100%;
        margin: 1 0 0 0;
    }
    #btn-back {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Static(id="mode-panel"):
            yield Label("Configure Test Run", id="panel-title")

            yield Label("Test Mode", classes="section-label")
            with RadioSet(id="test-mode"):
                yield RadioButton("Quick  (~5 min) — essential checks only", value=True, id="quick")
                yield RadioButton("Full  (~30 min) — thorough stress + deep scan", id="full")

            yield Label("Report Type", classes="section-label")
            with RadioSet(id="report-type"):
                yield RadioButton("Before repair", value=True, id="before")
                yield RadioButton("After repair", id="after")

            yield Button("Run Tests →", variant="primary", id="btn-run")
            yield Button("← Back", variant="default", id="btn-back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-run":
            self._start()
        elif event.button.id == "btn-back":
            self.app.pop_screen()

    def _start(self) -> None:
        mode_set = self.query_one("#test-mode", RadioSet)
        report_set = self.query_one("#report-type", RadioSet)

        mode = TestMode.QUICK
        if mode_set.pressed_index == 1:
            mode = TestMode.FULL

        report_type = ReportType.BEFORE
        if report_set.pressed_index == 1:
            report_type = ReportType.AFTER

        self.app.job_info.test_mode = mode  # type: ignore[attr-defined]
        self.app.job_info.report_type = report_type  # type: ignore[attr-defined]

        from .dashboard import DashboardScreen
        self.app.push_screen(DashboardScreen())
