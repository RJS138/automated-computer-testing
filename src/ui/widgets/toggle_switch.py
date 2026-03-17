"""ToggleSwitch — an iOS-style sliding toggle widget."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

_COLOR_ON = QColor("#3b82f6")  # accent blue — "advanced"
_COLOR_OFF = QColor("#30363d")  # dark border  — "simple"
_COLOR_THUMB = QColor("#ffffff")


class ToggleSwitch(QWidget):
    """Pill-shaped toggle: dot slides left (off/simple) ↔ right (on/advanced).

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

        # Interpolate track colour: grey → blue
        off_r, off_g, off_b = _COLOR_OFF.red(), _COLOR_OFF.green(), _COLOR_OFF.blue()
        on_r, on_g, on_b = _COLOR_ON.red(), _COLOR_ON.green(), _COLOR_ON.blue()
        t = self._pos
        track = QColor(
            int(off_r + (on_r - off_r) * t),
            int(off_g + (on_g - off_g) * t),
            int(off_b + (on_b - off_b) * t),
        )

        p.setBrush(track)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, r, r)

        # Thumb
        margin = 3
        thumb_d = h - 2 * margin
        travel = w - thumb_d - 2 * margin
        thumb_x = int(margin + self._pos * travel)

        p.setBrush(_COLOR_THUMB)
        p.drawEllipse(thumb_x, margin, thumb_d, thumb_d)

        p.end()
