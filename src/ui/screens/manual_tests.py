"""Manual tests screen — guided one-at-a-time checklist."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Label, Static

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
    #btn-skip {
        width: 1fr;
    }
    """

    def __init__(self, start_item: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._runner = ManualTestRunner()
        if start_item:
            self._runner.seek_to(start_item)

    def compose(self) -> ComposeResult:
        with Static(id="manual-panel"):
            yield Label("Manual Hardware Checks", id="manual-title")
            yield Label("", id="progress-line")
            yield Label("", id="item-label")
            yield Static("", id="instructions")
            yield Button("▶  Start Display Test", variant="primary", id="btn-run-test")
            yield Label("", id="post-test-note")
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
        self.query_one("#post-test-note", Label).update("")

        test_type = item.get("test_type", "")
        run_btn = self.query_one("#btn-run-test", Button)
        _labels = {
            "display_color":  "▶  Start Display Test",
            "keyboard_test":  "▶  Start Keyboard Test",
            "speakers_test":  "▶  Start Speaker Test",
            "touchpad_test":  "▶  Start Touchpad Test",
            "usb_test_a":     "▶  Start USB-A Test",
            "usb_test_c":     "▶  Start USB-C Test",
            "hdmi_test":      "▶  Start HDMI Test",
            "webcam_test":    "▶  Start Webcam Test",
        }
        run_btn.label = _labels.get(test_type, "▶  Run Test")
        run_btn.display = bool(test_type)

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
            self.app.push_screen(DisplayTestScreen(), self._on_test_result)
        elif test_type == "keyboard_test":
            from .keyboard_test import KeyboardTestScreen
            self.app.push_screen(KeyboardTestScreen(), self._on_test_result)
        elif test_type in ("speakers_test", "touchpad_test",
                           "usb_test_a", "usb_test_c", "hdmi_test", "webcam_test"):
            self._launch_helper(test_type)

    def _on_test_result(self, result: str) -> None:
        """Called when any interactive test screen or helper completes."""
        if result == "pass":
            self._runner.pass_current("")
            self._refresh_item()
        elif result == "fail":
            self._runner.fail_current("")
            self._refresh_item()
        elif result == "skip":
            self._runner.skip_current("")
            self._refresh_item()
        else:
            # Unavailable — show message, let user skip manually
            self.query_one("#post-test-note", Label).update(
                "[dim]Helper unavailable — press Skip to continue.[/dim]"
            )

    # ------------------------------------------------------------------
    # Generic helper launcher (speakers, touchpad, USB, HDMI, webcam)
    # ------------------------------------------------------------------

    def _launch_helper(self, test_type: str) -> None:
        """Launch a tkinter helper subprocess for the given test type."""
        import asyncio
        import sys
        from pathlib import Path

        _HELPER_MAP = {
            "speakers_test": "_speakers_helper.py",
            "touchpad_test": "_touchpad_helper.py",
            "usb_test_a":    "_usb_helper.py",
            "usb_test_c":    "_usb_helper.py",
            "hdmi_test":     "_hdmi_helper.py",
            "webcam_test":   "_webcam_helper.py",
        }
        _HELPER_NAME_MAP = {
            "speakers_test": "speakers",
            "touchpad_test": "touchpad",
            "usb_test_a":    "usb_a",
            "usb_test_c":    "usb_c",
            "hdmi_test":     "hdmi",
            "webcam_test":   "webcam",
        }
        helper_name = _HELPER_NAME_MAP[test_type]
        helper_file = _HELPER_MAP[test_type]
        helper_path = Path(__file__).parent.parent / helper_file

        async def _run():
            frozen = hasattr(sys, "_MEIPASS")
            if not frozen and not helper_path.exists():
                self._on_test_result("unavailable")
                return

            if frozen:
                cmd = [sys.executable, "--run-helper", helper_name]
            else:
                cmd = [sys.executable, str(helper_path)]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            rc = await proc.wait()
            if rc == 0:
                result = "pass"
            elif rc == 3:
                result = "skip"
            elif rc == 2:
                result = "unavailable"
            else:
                result = "fail"
            self._on_test_result(result)

        self.run_worker(_run(), exclusive=True)

    # ------------------------------------------------------------------
    # Button and keyboard handling
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id
        if btn == "btn-run-test":
            self._launch_interactive()
        elif btn == "btn-skip":
            self._runner.skip_current("")
            self._refresh_item()

    def on_key(self, event) -> None:
        if event.key.lower() == "s":
            self._runner.skip_current("")
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
