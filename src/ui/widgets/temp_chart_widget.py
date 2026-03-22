"""TempChartWidget — compact sparkline or full area chart for CPU temperature."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from ..stylesheet import get_colors


class TempChartWidget(QWidget):
    """Renders CPU temperature samples as an area chart.

    compact=True  — 80×22 px sparkline for the dashboard card main row.
    compact=False — 100 px tall full chart for the expandable detail panel.
    """

    def __init__(self, compact: bool = False, theme: str = "dark", parent=None) -> None:
        super().__init__(parent)
        self._compact = compact
        self._theme = theme
        self._samples: list[tuple[float, float]] = []  # (time_s, temp_c)
        self._warn: float | None = None
        self._fail: float | None = None
        self.setStyleSheet("background: transparent;")
        if compact:
            self.setFixedSize(80, 22)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.setFixedHeight(100)
            self.setMouseTracking(True)

    def push_sample(self, time_s: float, temp_c: float) -> None:
        """Append one sample and repaint."""
        self._samples.append((time_s, temp_c))
        self.update()

    def set_samples(self, samples: list[dict]) -> None:
        """Bulk-load samples from result.data['temp_samples']."""
        self._samples = [(s["t"], s["c"]) for s in samples]
        self.update()

    def set_thresholds(self, warn: float | None, fail: float | None) -> None:
        self._warn = warn
        self._fail = fail
        self.update()

    def apply_theme(self, theme: str) -> None:
        self._theme = theme
        self.update()

    def reset(self) -> None:
        """Clear all samples — call before a fresh test run."""
        self._samples.clear()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if len(self._samples) < 2:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        c = get_colors(self._theme)
        temps = [s[1] for s in self._samples]
        times = [s[0] for s in self._samples]

        # Y range — scale to data; threshold lines are drawn only if they fall
        # within the visible range (bounds-checked below), so no need to force
        # y_max up to the fail threshold (which would crush the data into a flat line).
        y_max = max(temps) + 8
        y_min = min(temps) - 5
        y_range = max(y_max - y_min, 1.0)

        # X range
        x_min, x_max = times[0], max(times[-1], 1.0)
        x_range = max(x_max - x_min, 1.0)

        # Padding
        if self._compact:
            pad_l, pad_r, pad_t, pad_b = 0, 0, 2, 2
        else:
            pad_l, pad_r, pad_t, pad_b = 32, 8, 14, 18

        cw = w - pad_l - pad_r
        ch = h - pad_t - pad_b

        def to_x(t: float) -> float:
            return pad_l + (t - x_min) / x_range * cw

        def to_y(temp: float) -> float:
            return pad_t + ch - (temp - y_min) / y_range * ch

        pts = [(to_x(t), to_y(temp)) for t, temp in self._samples]

        accent = QColor(c["accent"])

        # Threshold lines (full mode only)
        if not self._compact:
            if self._warn is not None:
                wy = to_y(self._warn)
                if pad_t <= wy <= pad_t + ch:
                    pen = QPen(QColor(c["warn_text"]))
                    pen.setStyle(Qt.PenStyle.DashLine)
                    pen.setWidthF(1.0)
                    painter.setPen(pen)
                    painter.drawLine(int(pad_l), int(wy), int(w - pad_r), int(wy))
            if self._fail is not None:
                fy = to_y(self._fail)
                if pad_t <= fy <= pad_t + ch:
                    pen = QPen(QColor(c["danger_text"]))
                    pen.setStyle(Qt.PenStyle.DashLine)
                    pen.setWidthF(1.0)
                    painter.setPen(pen)
                    painter.drawLine(int(pad_l), int(fy), int(w - pad_r), int(fy))

        # Area fill
        area = QPainterPath()
        bottom_y = float(pad_t + ch)
        area.moveTo(pts[0][0], bottom_y)
        area.lineTo(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            area.lineTo(x, y)
        area.lineTo(pts[-1][0], bottom_y)
        area.closeSubpath()
        fill = QColor(accent)
        fill.setAlphaF(0.15)
        painter.fillPath(area, fill)

        # Line
        line_pen = QPen(accent)
        line_pen.setWidthF(1.5 if self._compact else 2.0)
        line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(line_pen)
        path = QPainterPath()
        path.moveTo(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            path.lineTo(x, y)
        painter.drawPath(path)

        # Markers (full mode only)
        if not self._compact:
            # Idle dot — first sample, grey
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(c["text_muted"]))
            x0, y0 = pts[0]
            painter.drawEllipse(int(x0) - 3, int(y0) - 3, 6, 6)

            # Peak dot — amber
            peak_i = temps.index(max(temps))
            xp, yp = pts[peak_i]
            painter.setBrush(QColor(c["warn_text"]))
            painter.drawEllipse(int(xp) - 4, int(yp) - 4, 8, 8)

        painter.end()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._compact or len(self._samples) < 2:
            return
        pad_l, pad_r = 32, 8
        cw = self.width() - pad_l - pad_r
        mx = event.position().x()
        if not (pad_l <= mx <= self.width() - pad_r):
            QToolTip.hideText()
            return
        times = [s[0] for s in self._samples]
        x_min = times[0]
        x_max = max(times[-1], 1.0)
        x_range = max(x_max - x_min, 1.0)
        t = (mx - pad_l) / cw * x_range + x_min
        nearest = min(self._samples, key=lambda s: abs(s[0] - t))
        QToolTip.showText(
            event.globalPosition().toPoint(),
            f"{nearest[1]:.1f}°C  ·  {nearest[0]:.0f}s",
            self,
        )
