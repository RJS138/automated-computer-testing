"""ToggleSwitch — an iOS-style sliding toggle widget."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QApplication, QWidget


class ToggleSwitch(QWidget):
    """Pill-shaped toggle: dot slides left (off/simple) ↔ right (on/advanced).

    Reads the active QPalette at paint time so it responds immediately to
    runtime theme switches without a restart.

    Signals
    -------
    toggled(bool)   True = checked/right (advanced), False = left (simple).
    """

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._checked: bool = checked
        self._pos: float = 1.0 if checked else 0.0

        self._anim = QPropertyAnimation(self, b"thumbPos", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── Qt property for animation ──────────────────────────────────────────

    def _get_pos(self) -> float:
        return self._pos

    def _set_pos(self, v: float) -> None:
        self._pos = v
        self.update()

    thumbPos = Property(float, _get_pos, _set_pos)

    # ── Public API ────────────────────────────────────────────────────────

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = True) -> None:
        if self._checked == checked:
            return
        self._checked = checked
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(1.0 if checked else 0.0)
            self._anim.start()
        else:
            self._pos = 1.0 if checked else 0.0
            self.update()

    # ── Events ────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        self.setChecked(not self._checked)
        self.toggled.emit(self._checked)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        r = h / 2.0

        # Read palette at paint time — responds to runtime theme switches.
        # Button role = off-track colour (bg-elevated token in both themes).
        # Highlight role = on-track colour (accent token in both themes).
        palette = QApplication.palette()
        color_off = palette.color(QPalette.ColorRole.Button)
        color_on  = palette.color(QPalette.ColorRole.Highlight)
        color_thumb = palette.color(QPalette.ColorRole.BrightText)

        # Interpolate track colour between off and on
        t = self._pos
        track = QColor(
            int(color_off.red()   + (color_on.red()   - color_off.red())   * t),
            int(color_off.green() + (color_on.green() - color_off.green()) * t),
            int(color_off.blue()  + (color_on.blue()  - color_off.blue())  * t),
        )

        p.setBrush(track)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, r, r)

        # Thumb
        margin = 3
        thumb_d = h - 2 * margin
        travel = w - thumb_d - 2 * margin
        thumb_x = int(margin + self._pos * travel)

        p.setBrush(color_thumb)
        p.drawEllipse(thumb_x, margin, thumb_d, thumb_d)

        p.end()
