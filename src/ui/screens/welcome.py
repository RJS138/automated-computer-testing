"""Welcome screen — job info form."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static, TextArea

from ...config import APP_NAME, APP_VERSION, BUSINESS_NAME
from ...models.job import JobInfo


class WelcomeScreen(Screen):
    """Collects customer name, device description, job number, and notes."""

    DEFAULT_CSS = """
    WelcomeScreen {
        align: center middle;
    }
    #welcome-panel {
        width: 70;
        height: auto;
        border: solid $primary;
        padding: 1 2;
    }
    #title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin: 0 0 1 0;
    }
    #subtitle {
        text-align: center;
        color: $text-muted;
        margin: 0 0 1 0;
    }
    .field-label {
        margin: 1 0 0 0;
        color: $text;
    }
    Input {
        margin: 0 0 0 0;
    }
    TextArea {
        height: 4;
        margin: 0 0 1 0;
    }
    #btn-start {
        margin: 1 0 0 0;
        width: 100%;
    }
    .error-msg {
        color: $error;
        height: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Static(id="welcome-panel"):
            yield Label(f"[bold]{APP_NAME} v{APP_VERSION}[/bold]", id="title")
            yield Label(BUSINESS_NAME, id="subtitle")
            yield Label("Customer Name *", classes="field-label")
            yield Input(placeholder="e.g. John Smith", id="customer-name")
            yield Label("Device Description *", classes="field-label")
            yield Input(placeholder="e.g. Dell XPS 15, HP Pavilion", id="device-desc")
            yield Label("Job Number *", classes="field-label")
            yield Input(placeholder="e.g. JOB-2024-001", id="job-number")
            yield Label("Notes", classes="field-label")
            yield TextArea(id="notes")
            yield Label("", id="error-msg", classes="error-msg")
            yield Button("Start →", variant="primary", id="btn-start")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        customer = self.query_one("#customer-name", Input).value.strip()
        device = self.query_one("#device-desc", Input).value.strip()
        job_num = self.query_one("#job-number", Input).value.strip()
        notes = self.query_one("#notes", TextArea).text.strip()

        if not customer or not device or not job_num:
            self.query_one("#error-msg", Label).update(
                "Please fill in Customer Name, Device Description, and Job Number."
            )
            return

        job = JobInfo(
            customer_name=customer,
            device_description=device,
            job_number=job_num,
            notes=notes,
        )
        # Pass job info to the next screen via app state
        self.app.job_info = job  # type: ignore[attr-defined]
        from .mode_select import ModeSelectScreen
        self.app.push_screen(ModeSelectScreen())
