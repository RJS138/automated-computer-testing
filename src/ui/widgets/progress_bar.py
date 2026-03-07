"""Animated progress bar widget."""

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ProgressBar as TextualProgressBar


class LabeledProgressBar(Widget):
    """
    A simple labeled progress bar: [Label]  [=====>    ]  nn%
    """

    DEFAULT_CSS = """
    LabeledProgressBar {
        layout: horizontal;
        height: 1;
        margin: 0 0 1 0;
    }
    LabeledProgressBar Label {
        width: 20;
        color: $text;
    }
    LabeledProgressBar ProgressBar {
        width: 1fr;
    }
    """

    progress: reactive[float] = reactive(0.0)

    def __init__(self, label: str = "Progress", total: float = 100.0, **kwargs) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._total = total

    def compose(self) -> ComposeResult:
        yield Label(self._label)
        yield TextualProgressBar(total=self._total, show_eta=False, show_percentage=True)

    def advance(self, amount: float = 1.0) -> None:
        bar = self.query_one(TextualProgressBar)
        bar.advance(amount)

    def set_progress(self, value: float) -> None:
        bar = self.query_one(TextualProgressBar)
        bar.update(progress=value)
