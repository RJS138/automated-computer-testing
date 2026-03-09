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
    #btn-run-test {
        width: 1fr;
        margin: 0 0 1 0;
    }
    #post-test-note {
        text-align: center;
        color: $success;
        margin: 0 0 1 0;
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

    def __init__(self, start_item: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._runner = ManualTestRunner()
        if start_item:
            self._runner.seek_to(start_item)
        self._interactive_done = False  # tracks whether current item's test was run

    def compose(self) -> ComposeResult:
        with Static(id="manual-panel"):
            yield Label("Manual Hardware Checks", id="manual-title")
            yield Label("", id="progress-line")
            yield Label("", id="item-label")
            yield Static("", id="instructions")
            # "Start Display Test" (or similar) — only shown for interactive items
            yield Button("▶  Start Display Test", variant="primary", id="btn-run-test")
            # Shown after an interactive test completes
            yield Label("", id="post-test-note")
            yield Label("Notes (optional):", id="notes-label")
            yield TextArea(id="notes-input")
            with Static(id="btn-row"):
                yield Button("P — Pass", variant="success", id="btn-pass")
                yield Button("F — Fail", variant="error", id="btn-fail")
                yield Button("S — Skip", variant="default", id="btn-skip")

    def on_mount(self) -> None:
        self._refresh_item()

    # ------------------------------------------------------------------
    # Item display
    # ------------------------------------------------------------------

    def _refresh_item(self) -> None:
        if self._runner.is_complete:
            self._finish()
            return

        item = self._runner.current_item
        total = len(self._runner.items)
        idx = self._runner._index

        self.query_one("#progress-line", Label).update(f"Item {idx + 1} of {total}")
        self.query_one("#item-label", Label).update(f"[bold]{item['label']}[/bold]")
        self.query_one("#instructions", Static).update(item["instructions"])
        self.query_one("#notes-input", TextArea).clear()
        self.query_one("#post-test-note", Label).update("")

        has_interactive = bool(item.get("test_type"))

        # Run-test button label
        test_type = item.get("test_type", "")
        run_btn = self.query_one("#btn-run-test", Button)
        if test_type == "display_color":
            run_btn.label = "▶  Start Display Test"
        else:
            run_btn.label = "▶  Run Test"

        self._interactive_done = not has_interactive
        self._apply_interactive_state()

    def _apply_interactive_state(self) -> None:
        """Enable/disable widgets based on whether the interactive test still needs to run."""
        run_btn = self.query_one("#btn-run-test", Button)

        item = self._runner.current_item
        has_interactive_type = bool(item and item.get("test_type"))
        waiting = has_interactive_type and not self._interactive_done

        # Run-test button: visible only while waiting for interactive test
        run_btn.display = waiting

        # Pass/fail blocked until interactive test runs; skip is always allowed
        self.query_one("#btn-pass", Button).disabled = waiting
        self.query_one("#btn-fail", Button).disabled = waiting

    # ------------------------------------------------------------------
    # Interactive test launcher
    # ------------------------------------------------------------------

    def _launch_interactive(self) -> None:
        item = self._runner.current_item
        if not item:
            return
        test_type = item.get("test_type")
        if test_type == "display_color":
            from .display_test import DisplayTestScreen
            self.app.push_screen(DisplayTestScreen(), self._on_interactive_done)

    def _on_interactive_done(self, completed: bool) -> None:
        """Called when the interactive test screen is dismissed."""
        self._interactive_done = True
        note = self.query_one("#post-test-note", Label)
        if completed:
            note.update("[green]✓ Colour cycle complete.[/green]  "
                        "Did the display pass all checks?")
        else:
            note.update("[yellow]⚠ Cycle ended early.[/yellow]  "
                        "Review what you observed and mark accordingly.")
        self._apply_interactive_state()

    # ------------------------------------------------------------------
    # Button and keyboard handling
    # ------------------------------------------------------------------

    def _get_notes(self) -> str:
        return self.query_one("#notes-input", TextArea).text.strip()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id
        if btn == "btn-run-test":
            self._launch_interactive()
            return
        notes = self._get_notes()
        if btn == "btn-skip":
            self._runner.skip_current(notes)
            self._refresh_item()
            return
        if not self._interactive_done:
            return  # block pass/fail until interactive test is run
        if btn == "btn-pass":
            self._runner.pass_current(notes)
        elif btn == "btn-fail":
            self._runner.fail_current(notes)
        self._refresh_item()

    def on_key(self, event) -> None:
        notes = self._get_notes()
        key = event.key.lower()
        if key == "s":
            self._runner.skip_current(notes)
            self._refresh_item()
            return
        if not self._interactive_done:
            return  # block p/f shortcuts until interactive test is run
        if key == "p":
            self._runner.pass_current(notes)
            self._refresh_item()
        elif key == "f":
            self._runner.fail_current(notes)
            self._refresh_item()

    # ------------------------------------------------------------------
    # Finish
    # ------------------------------------------------------------------

    def _finish(self) -> None:
        manual_result = self._runner.summary_result()
        manual_items = self._runner.to_test_results()

        existing = getattr(self.app, "test_results", [])  # type: ignore[attr-defined]
        existing.append(manual_result)
        self.app.test_results = existing  # type: ignore[attr-defined]
        self.app.manual_items = manual_items  # type: ignore[attr-defined]

        from .report_done import ReportDoneScreen
        self.app.push_screen(ReportDoneScreen())
