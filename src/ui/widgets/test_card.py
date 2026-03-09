"""Test status card widget with animated progress bar."""

import os
import time

from textual.app import ComposeResult
from textual.widgets import Label, Static

from ...models.test_result import TestResult, TestStatus

_SIMPLE = os.environ.get("PCTESTER_SIMPLE_UI") == "1"

# Unicode icons for capable terminals; ASCII fallbacks for limited ones
if _SIMPLE:
    STATUS_ICONS = {
        TestStatus.WAITING: ".",
        TestStatus.PASS:    "*",
        TestStatus.WARN:    "!",
        TestStatus.FAIL:    "X",
        TestStatus.SKIP:    "-",
        TestStatus.ERROR:   "!",
        TestStatus.RUNNING: ">",
    }
    _SPINNERS = r"-\|/"
else:
    STATUS_ICONS = {
        TestStatus.WAITING: "○",
        TestStatus.PASS:    "✓",
        TestStatus.WARN:    "⚠",
        TestStatus.FAIL:    "✗",
        TestStatus.SKIP:    "—",
        TestStatus.ERROR:   "!",
        TestStatus.RUNNING: "◐",
    }
    _SPINNERS = "◐◓◑◒"

STATUS_CLASSES = {
    TestStatus.WAITING: "status-waiting",
    TestStatus.RUNNING: "status-running",
    TestStatus.PASS:    "status-pass",
    TestStatus.WARN:    "status-warn",
    TestStatus.FAIL:    "status-fail",
    TestStatus.SKIP:    "status-skip",
    TestStatus.ERROR:   "status-error",
}

_BAR_WIDTH = 34


class TestCard(Static):
    """
    One card per test.  The DashboardScreen calls:
        card.start_running(expected_seconds)   — when test begins
        card.tick()                            — every ~100 ms while running (driven by screen)
        card.update_result(result)             — when test finishes
    """

    DEFAULT_CSS = """
    TestCard {
        border: solid $surface;
        padding: 0 1;
        margin: 0 0 1 0;
        height: 4;
        layout: vertical;
    }
    TestCard .card-header {
        layout: horizontal;
        height: 1;
    }
    TestCard .card-icon {
        width: 3;
        text-align: center;
    }
    TestCard .card-name {
        width: 1fr;
        text-style: bold;
    }
    TestCard .card-elapsed {
        width: 14;
        text-align: right;
        color: $text-muted;
    }
    TestCard .card-bar {
        padding: 0 3;
        color: $warning;
        height: 1;
    }
    TestCard .card-summary {
        color: $text-muted;
        padding: 0 3;
        height: 1;
    }

    TestCard.status-waiting { border: solid $surface; }
    TestCard.status-running { border: solid $warning;  }
    TestCard.status-pass    { border: solid $success;  }
    TestCard.status-warn    { border: solid $warning;  }
    TestCard.status-fail    { border: solid $error;    }
    TestCard.status-skip    { border: solid $surface;  }
    TestCard.status-error   { border: solid $error;    }

    .status-waiting { color: $text-muted; }
    .status-running { color: $warning;    }
    .status-pass    { color: $success;    }
    .status-warn    { color: $warning;    }
    .status-fail    { color: $error;      }
    .status-skip    { color: $text-muted; }
    .status-error   { color: $error;      }
    """

    def __init__(self, result: TestResult, **kwargs) -> None:
        super().__init__(**kwargs)
        self._result = result
        self._start_time: float | None = None
        self._expected: float | None = None
        self.test_active = False   # read by DashboardScreen to decide whether to tick

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        status = self._result.status
        with Static(classes="card-header"):
            yield Label(
                STATUS_ICONS[status],
                id=f"icon-{self._result.name}",
                classes=f"card-icon {STATUS_CLASSES[status]}",
            )
            yield Label(self._result.display_name, classes="card-name")
            yield Label("", id=f"elapsed-{self._result.name}", classes="card-elapsed")
        yield Label("", id=f"bar-{self._result.name}", classes="card-bar")
        yield Label(
            status.value.upper(),
            id=f"summary-{self._result.name}",
            classes="card-summary",
        )

    def on_mount(self) -> None:
        self._bar_label    = self.query_one(f"#bar-{self._result.name}",     Label)
        self._icon_label   = self.query_one(f"#icon-{self._result.name}",    Label)
        self._elapsed_label= self.query_one(f"#elapsed-{self._result.name}", Label)
        self._summary_label= self.query_one(f"#summary-{self._result.name}", Label)
        self._bar_label.display     = False
        self._elapsed_label.display = False

    # ------------------------------------------------------------------
    # Public API — called from DashboardScreen (UI thread only)
    # ------------------------------------------------------------------

    def start_running(self, expected_seconds: float | None = None) -> None:
        """Transition card to RUNNING state and enable animation."""
        self._start_time = time.monotonic()
        self._expected   = expected_seconds
        self.test_active  = True

        self._apply_status_class(TestStatus.RUNNING)
        self._icon_label.update(_SPINNERS[0])

        self._bar_label.display     = True
        self._elapsed_label.display = True
        self._bar_label.update(_render_bar(0, expected_seconds))
        self._summary_label.update("Gathering info…")
        self.styles.height = 6
        self.refresh(layout=True)

    def tick(self) -> None:
        """
        Called by DashboardScreen.set_interval every ~100 ms while running.
        Keeps the spinner and progress bar animated.
        """
        if not self.test_active or self._start_time is None:
            return
        elapsed = time.monotonic() - self._start_time
        self._icon_label.update(_SPINNERS[int(elapsed * 5) % len(_SPINNERS)])
        self._elapsed_label.update(_format_elapsed(elapsed))
        self._bar_label.update(_render_bar(elapsed, self._expected))

    def update_result(self, result: TestResult) -> None:
        """Apply final result and stop animation."""
        self.test_active = False
        self._result    = result
        status          = result.status

        self.styles.height = 4
        self._bar_label.display     = False
        self._elapsed_label.display = False

        self._apply_status_class(status)
        self._icon_label.update(STATUS_ICONS[status])
        self._icon_label.remove_class(*STATUS_CLASSES.values())
        self._icon_label.add_class(STATUS_CLASSES[status])

        text = result.summary or result.error_message or status.value.upper()
        self._summary_label.update(text)
        self.refresh(layout=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_status_class(self, status: TestStatus) -> None:
        self.remove_class(*STATUS_CLASSES.values())
        self.add_class(STATUS_CLASSES[status])


# ------------------------------------------------------------------
# Bar / elapsed helpers
# ------------------------------------------------------------------

def _render_bar(elapsed: float, expected: float | None) -> str:
    if expected and expected > 0:
        ratio = min(elapsed / expected, 0.97)
    else:
        ratio = elapsed / (elapsed + 6)          # asymptotic, never reaches 1
    filled = round(ratio * _BAR_WIDTH)
    if _SIMPLE:
        return "#" * filled + "." * (_BAR_WIDTH - filled)
    return "▓" * filled + "░" * (_BAR_WIDTH - filled)


def _format_elapsed(elapsed: float) -> str:
    if elapsed < 60:
        return f"{elapsed:.1f}s"
    return f"{int(elapsed)//60}m {int(elapsed)%60:02d}s"
