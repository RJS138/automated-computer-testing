"""Full-screen QDialog colour-cycle display test.

Port of the tkinter _display_helper.py to PySide6 QDialog.
Launched in-process via dialog.exec(); caller reads dialog.result_str afterward.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPalette
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ._utils import show_fullscreen

_COLORS: list[tuple[str, str]] = [
    ("Black", "#000000"),
    ("White", "#FFFFFF"),
    ("Red", "#FF0000"),
    ("Green", "#00FF00"),
    ("Blue", "#0000FF"),
    ("Cyan", "#00FFFF"),
    ("Magenta", "#FF00FF"),
    ("Gray", "#7F7F7F"),
]
_N = len(_COLORS)

_INSTRUCTIONS = (
    "DISPLAY COLOUR TEST\n\n"
    f"The screen will cycle through {_N} solid colors.\n\n"
    "On each colour, look carefully for:\n\n"
    "  Dead pixels      - dots stuck at the wrong colour\n"
    "  Backlight bleed  - bright patches at screen edges\n"
    "                     (most visible on the black screen)\n"
    "  Colour uniformity- no dark or bright patches across the panel\n"
    "  Screen damage    - cracks or pressure marks\n\n"
    "Press any key or click anywhere to advance.\n"
    "Press ESC to end the cycle early."
)

_BG_DARK = "#0d0d0d"
_BG_BTN_F = "#8b1a1a"
_BG_BTN_P = "#1a6b1a"
_BG_BTN_S = "#3a3a3a"


class DisplayDialog(QDialog):
    """Full-screen colour-cycle dialog for display inspection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result_str: str = "skip"
        self.setWindowTitle("Display Test")
        self._phase: int = -1  # -1 = instruction page
        self._in_judgment: bool = False

        # Main layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # Central area (fills entire dialog)
        self._central = QWidget()
        self._central.setStyleSheet(f"background-color: {_BG_DARK};")
        self._layout.addWidget(self._central, 1)

        # Instruction label
        self._instr_label = QLabel(_INSTRUCTIONS, self._central)
        self._instr_label.setStyleSheet(
            f"color: #e0e0e0; background: {_BG_DARK}; font-family: Courier; font-size: 14px;"
        )
        self._instr_label.setAlignment(Qt.AlignCenter)

        # Hint bar
        self._hint_label = QLabel("  Press any key or click to begin   |   ESC to end cycle  ")
        self._hint_label.setStyleSheet(
            "color: #cccccc; background: #1a1a1a; font-family: Courier; font-size: 11px; padding: 6px;"
        )
        self._layout.addWidget(self._hint_label)

        # Judgment widgets (created but hidden)
        self._judgment_widget = QWidget()
        self._judgment_widget.setVisible(False)
        self._judgment_widget.setAutoFillBackground(True)
        self._set_bg(self._judgment_widget, _BG_DARK)

        jl = QVBoxLayout(self._judgment_widget)
        jl.setAlignment(Qt.AlignCenter)

        self._judgment_msg = QLabel()
        self._judgment_msg.setStyleSheet(
            f"color: #cccccc; background: {_BG_DARK}; font-family: Courier; font-size: 14px;"
        )
        self._judgment_msg.setAlignment(Qt.AlignCenter)
        jl.addWidget(self._judgment_msg)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)

        for text, bg, hover, action in [
            ("Fail", _BG_BTN_F, "#a02020", "fail"),
            ("Pass", _BG_BTN_P, "#228822", "pass"),
            ("Skip", _BG_BTN_S, "#4a4a4a", "skip"),
        ]:
            btn = QPushButton(text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: {bg}; color: white; border: none; "
                f"padding: 10px 28px; font-family: Courier; font-size: 13px; font-weight: bold; }}"
                f"QPushButton:hover {{ background: {hover}; }}"
            )
            btn.clicked.connect(lambda checked=False, a=action: self._finish(a))
            btn_row.addWidget(btn)

        jl.addLayout(btn_row)
        self._layout.insertWidget(1, self._judgment_widget, 1)

        self.setCursor(Qt.BlankCursor)

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _set_bg(widget: QWidget, color: str) -> None:
        pal = widget.palette()
        pal.setColor(QPalette.Window, QColor(color))
        widget.setPalette(pal)

    def _finish(self, result: str) -> None:
        self.result_str = result
        self.accept()

    def _advance(self) -> None:
        self._phase += 1
        if self._phase >= _N:
            self._show_judgment(cycle_complete=True)
            return
        name, bg = _COLORS[self._phase]
        self._instr_label.setVisible(False)
        # Use stylesheet instead of palette — app-level QSS overrides palette colors
        self._central.setStyleSheet(f"background-color: {bg};")
        self._hint_label.setStyleSheet(
            "color: #cccccc; background: #1a1a1a; font-family: Courier; font-size: 11px; padding: 6px;"
        )
        self._hint_label.setText(
            f"  {name}   {self._phase + 1} / {_N}   |   any key / click to advance   |   ESC to end  "
        )

    def _show_judgment(self, cycle_complete: bool) -> None:
        self._in_judgment = True
        self.setCursor(Qt.ArrowCursor)
        self._central.setVisible(False)
        self._judgment_widget.setVisible(True)
        msg = (
            "Colour cycle complete.\nDid the display pass all checks?"
            if cycle_complete
            else "Cycle ended early.\nReview what you observed and mark below."
        )
        self._judgment_msg.setText(msg)
        self._hint_label.setText("  Mark the result above  ")

    # ── events ─────────────────────────────────────────────────────────

    def run(self) -> int:
        """Show full-screen and run the dialog. Use instead of QDialog.exec()."""
        show_fullscreen(self)
        return super().exec()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._in_judgment:
            key = event.text().lower()
            if key == "p":
                self._finish("pass")
            elif key == "f":
                self._finish("fail")
            elif key == "s":
                self._finish("skip")
            return

        if event.key() == Qt.Key_Escape:
            self._show_judgment(cycle_complete=False)
        else:
            self._advance()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self._in_judgment:
            self._advance()

    def closeEvent(self, event) -> None:
        if self.result() != QDialog.DialogCode.Accepted:
            self.result_str = "fail"
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Centre instruction label
        if self._instr_label.isVisible():
            self._instr_label.setGeometry(self._central.rect())
