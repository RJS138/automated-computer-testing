"""Manual tests screen — guided one-at-a-time checklist."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Label, Static, TextArea

from ...tests.manual import ManualTestRunner


class ManualTestsScreen(Screen):
    DEFAULT_CSS = """
    ManualTestsScreen {
        align: center middle;
    }
    #manual-panel {
        width: 72;
        height: auto;
        border: solid $primary;
        padding: 1 2;
    }
    #manual-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin: 0 0 1 0;
    }
    #progress-line {
        text-align: center;
        color: $text-muted;
        margin: 0 0 1 0;
    }
    #item-label {
        text-style: bold;
        color: $text;
        margin: 0 0 1 0;
    }
    #instructions {
        background: $surface;
        padding: 1;
        margin: 0 0 1 0;
        color: $text;
    }
    #notes-label {
        color: $text-muted;
        margin: 0 0 0 0;
    }
    #notes-input {
        height: 3;
        margin: 0 0 1 0;
    }
    #btn-row {
        layout: horizontal;
        margin: 0 0 0 0;
    }
    #btn-pass {
        width: 1fr;
        margin: 0 1 0 0;
    }
    #btn-fail {
        width: 1fr;
        margin: 0 1 0 0;
    }
    #btn-skip {
        width: 1fr;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._runner = ManualTestRunner()

    def compose(self) -> ComposeResult:
        with Static(id="manual-panel"):
            yield Label("Manual Hardware Checks", id="manual-title")
            yield Label("", id="progress-line")
            yield Label("", id="item-label")
            yield Static("", id="instructions")
            yield Label("Notes (optional):", id="notes-label")
            yield TextArea(id="notes-input")
            with Static(id="btn-row"):
                yield Button("P — Pass", variant="success", id="btn-pass")
                yield Button("F — Fail", variant="error", id="btn-fail")
                yield Button("S — Skip", variant="default", id="btn-skip")

    def on_mount(self) -> None:
        self._refresh_item()

    def _refresh_item(self) -> None:
        if self._runner.is_complete:
            self._finish()
            return

        item = self._runner.current_item
        total = len(self._runner.items)
        current_idx = self._runner._index  # 0-based index of current item

        self.query_one("#progress-line", Label).update(
            f"Item {current_idx + 1} of {total}"
        )
        self.query_one("#item-label", Label).update(
            f"[bold]{item['label']}[/bold]"
        )
        self.query_one("#instructions", Static).update(item["instructions"])
        self.query_one("#notes-input", TextArea).clear()

    def _get_notes(self) -> str:
        return self.query_one("#notes-input", TextArea).text.strip()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        notes = self._get_notes()
        if event.button.id == "btn-pass":
            self._runner.pass_current(notes)
        elif event.button.id == "btn-fail":
            self._runner.fail_current(notes)
        elif event.button.id == "btn-skip":
            self._runner.skip_current(notes)
        self._refresh_item()

    def on_key(self, event) -> None:
        notes = self._get_notes()
        key = event.key.lower()
        if key == "p":
            self._runner.pass_current(notes)
            self._refresh_item()
        elif key == "f":
            self._runner.fail_current(notes)
            self._refresh_item()
        elif key == "s":
            self._runner.skip_current(notes)
            self._refresh_item()

    def _finish(self) -> None:
        # Store manual results in app
        manual_result = self._runner.summary_result()
        manual_items = self._runner.to_test_results()

        # Add to overall results
        existing = getattr(self.app, "test_results", [])  # type: ignore[attr-defined]
        existing.append(manual_result)
        self.app.test_results = existing  # type: ignore[attr-defined]
        self.app.manual_items = manual_items  # type: ignore[attr-defined]

        from .report_done import ReportDoneScreen
        self.app.push_screen(ReportDoneScreen())
