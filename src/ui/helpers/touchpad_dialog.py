"""Full-screen QDialog touchpad / trackpad test.

Port of the tkinter _touchpad_helper.py to PySide6 QDialog.
Tests drawing coverage, left click, right click, and scroll detection.
"""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ._utils import make_dialog_btn, show_fullscreen

# ── Visual constants ─────────────────────────────────────────────────────

_BG = "#1a1a1a"
_FG = "#cccccc"
_GRID_COLS = 20
_GRID_ROWS = 12
_COVERAGE_THRESHOLD = 25


# ── Drawing canvas ───────────────────────────────────────────────────────


class _DrawCanvas(QWidget):
    """Custom widget that tracks mouse drawing and paints trails."""

    def __init__(self, dialog: "TouchpadDialog") -> None:
        super().__init__()
        self._dialog = dialog
        self._lines: list[tuple[QPointF, QPointF]] = []
        self._last_pos: QPointF | None = None
        self.setMouseTracking(False)
        self.setStyleSheet("background: #0d0d0d;")
        self.setCursor(Qt.CrossCursor)

    def clear(self) -> None:
        self._lines.clear()
        self._last_pos = None
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor("#2a5ab8"), 2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        for p1, p2 in self._lines:
            painter.drawLine(p1, p2)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._last_pos = event.position()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.LeftButton:
            pos = event.position()
            if self._last_pos is not None:
                self._lines.append((self._last_pos, pos))
                self.update()
            self._last_pos = pos
            self._dialog._update_coverage(int(pos.x()), int(pos.y()), self.width(), self.height())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._last_pos = None

    def leaveEvent(self, event) -> None:
        self._last_pos = None


# ── Zone widget ──────────────────────────────────────────────────────────


class _ZoneWidget(QFrame):
    """A zone panel for left click, right click, or scroll detection."""

    def __init__(self, title: str, zone_type: str, dialog: "TouchpadDialog") -> None:
        super().__init__()
        self._dialog = dialog
        self._zone_type = zone_type
        self.setStyleSheet("QFrame { background: #111111; border: none; }")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignCenter)
        self._title_label.setStyleSheet(
            "color: #888; font-family: Courier; font-size: 10px; font-weight: bold; border: none;"
        )
        layout.addWidget(self._title_label)

        self._count_label = QLabel("0")
        self._count_label.setAlignment(Qt.AlignCenter)
        self._count_label.setStyleSheet(
            "color: #555; font-family: Courier; font-size: 28px; font-weight: bold; border: none;"
        )
        layout.addWidget(self._count_label)

        self._status_label = QLabel("waiting...")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            "color: #555; font-family: Courier; font-size: 10px; border: none;"
        )
        layout.addWidget(self._status_label)

        if zone_type == "left":
            self.setCursor(Qt.PointingHandCursor)
        elif zone_type == "right":
            self.setCursor(Qt.PointingHandCursor)
        elif zone_type == "scroll":
            self.setCursor(Qt.SizeVerCursor)

    def _activate(self, count: int) -> None:
        self.setStyleSheet("QFrame { background: #0d1f0d; border: none; }")
        self._count_label.setText(str(count))
        self._count_label.setStyleSheet(
            "color: #2a8a2a; font-family: Courier; font-size: 28px; font-weight: bold; border: none;"
        )
        self._status_label.setText("detected")
        self._status_label.setStyleSheet(
            "color: #2a8a2a; font-family: Courier; font-size: 10px; border: none;"
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._zone_type == "left" and event.button() == Qt.LeftButton:
            self._dialog._on_left_click()
        elif self._zone_type == "right" and event.button() == Qt.RightButton:
            self._dialog._on_right_click()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._zone_type == "scroll":
            self._dialog._on_scroll()


# ── Main dialog ──────────────────────────────────────────────────────────


class TouchpadDialog(QDialog):
    """Full-screen touchpad / trackpad test dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result_str: str = "fail"
        self.setWindowTitle("Touchpad / Trackpad Test")
        self.setStyleSheet(f"QDialog {{ background: {_BG}; }}")

        self._left_clicks = 0
        self._right_clicks = 0
        self._scroll_total = 0
        self._coverage_pct = 0
        self._visited_cells: set[tuple[int, int]] = set()
        self._pass_unlocked = False

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 18)

        # Top bar
        top_bar = QHBoxLayout()
        title = QLabel("Touchpad / Trackpad Test")
        title.setStyleSheet(
            f"color: #4a9eff; background: {_BG}; font-family: Courier; font-size: 16px; font-weight: bold;"
        )
        top_bar.addWidget(title)

        self._coverage_label = QLabel("Coverage: 0%")
        self._coverage_label.setStyleSheet(
            f"color: #555; background: {_BG}; font-family: Courier; font-size: 13px; font-weight: bold;"
        )
        top_bar.addStretch()
        top_bar.addWidget(self._coverage_label)
        root.addLayout(top_bar)

        # Instruction
        instr = QLabel(
            "Draw across the pad surface. Left-click, right-click, and scroll in the zones."
        )
        instr.setStyleSheet(
            f"color: #888; background: {_BG}; font-family: Courier; font-size: 11px;"
        )
        root.addWidget(instr)

        # Content area
        content = QHBoxLayout()

        # Drawing canvas
        self._canvas = _DrawCanvas(self)
        content.addWidget(self._canvas, 1)

        # Right column: zones
        right_col = QVBoxLayout()
        self._lc_zone = _ZoneWidget("LEFT CLICK\nclick here", "left", self)
        right_col.addWidget(self._lc_zone)
        self._rc_zone = _ZoneWidget("RIGHT CLICK\nright-click here", "right", self)
        right_col.addWidget(self._rc_zone)
        self._sc_zone = _ZoneWidget("SCROLL\nscroll here", "scroll", self)
        right_col.addWidget(self._sc_zone)
        right_col.addStretch()

        right_widget = QWidget()
        right_widget.setFixedWidth(220)
        right_widget.setLayout(right_col)
        content.addWidget(right_widget)

        root.addLayout(content, 1)

        # Bottom hint
        hint = QLabel("Complete all zones and reach 25% coverage to enable Pass.")
        hint.setStyleSheet(
            f"color: #555; background: {_BG}; font-family: Courier; font-size: 10px;"
        )
        hint.setAlignment(Qt.AlignCenter)
        root.addWidget(hint)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)

        clear_btn = make_dialog_btn("Clear", "#2a2a2a", "#3a3a3a", fg="#888")
        clear_btn.clicked.connect(self._do_clear)
        btn_row.addWidget(clear_btn)

        fail_btn = make_dialog_btn("Fail", "#8b1a1a", "#a02020")
        fail_btn.clicked.connect(lambda: self._finish("fail"))
        btn_row.addWidget(fail_btn)

        self._pass_btn = QPushButton("Pass")
        self._pass_btn.setEnabled(False)
        self._pass_btn.setStyleSheet(
            "QPushButton { background: #2a2a2a; color: #555; border: none; "
            "padding: 8px 28px; font-family: Courier; font-size: 13px; font-weight: bold; }"
            "QPushButton:enabled { background: #1a6b1a; color: white; }"
            "QPushButton:enabled:hover { background: #228822; }"
        )
        self._pass_btn.setCursor(Qt.ArrowCursor)
        self._pass_btn.clicked.connect(lambda: self._finish("pass"))
        btn_row.addWidget(self._pass_btn)

        skip_btn = make_dialog_btn("Skip", "#3a3a3a", "#4a4a4a", fg="#aaa")
        skip_btn.clicked.connect(lambda: self._finish("skip"))
        btn_row.addWidget(skip_btn)

        root.addLayout(btn_row)

    # ── helpers ────────────────────────────────────────────────────────

    def _finish(self, result: str) -> None:
        if result == "pass" and not self._pass_unlocked:
            return
        self.result_str = result
        self.accept()

    def _check_pass_unlock(self) -> None:
        ok = (
            self._left_clicks >= 1
            and self._right_clicks >= 1
            and self._scroll_total >= 1
            and self._coverage_pct >= _COVERAGE_THRESHOLD
        )
        self._pass_unlocked = ok
        self._pass_btn.setEnabled(ok)
        self._pass_btn.setCursor(Qt.PointingHandCursor if ok else Qt.ArrowCursor)

    def _update_coverage(self, x: int, y: int, cw: int, ch: int) -> None:
        if cw <= 0 or ch <= 0:
            return
        col = int(x / cw * _GRID_COLS)
        row = int(y / ch * _GRID_ROWS)
        col = max(0, min(_GRID_COLS - 1, col))
        row = max(0, min(_GRID_ROWS - 1, row))
        cell = (col, row)
        if cell not in self._visited_cells:
            self._visited_cells.add(cell)
            total_cells = _GRID_COLS * _GRID_ROWS
            pct = int(len(self._visited_cells) / total_cells * 100)
            self._coverage_pct = pct
            color = "#1a6b1a" if pct >= _COVERAGE_THRESHOLD else "#555"
            self._coverage_label.setText(f"Coverage: {pct}%")
            self._coverage_label.setStyleSheet(
                f"color: {color}; background: {_BG}; font-family: Courier; font-size: 13px; font-weight: bold;"
            )
            self._check_pass_unlock()

    def _on_left_click(self) -> None:
        self._left_clicks += 1
        self._lc_zone._activate(self._left_clicks)
        self._check_pass_unlock()

    def _on_right_click(self) -> None:
        self._right_clicks += 1
        self._rc_zone._activate(self._right_clicks)
        self._check_pass_unlock()

    def _on_scroll(self) -> None:
        self._scroll_total += 1
        self._sc_zone._activate(self._scroll_total)
        self._check_pass_unlock()

    def _do_clear(self) -> None:
        self._canvas.clear()
        self._visited_cells.clear()
        self._coverage_pct = 0
        self._coverage_label.setText("Coverage: 0%")
        self._coverage_label.setStyleSheet(
            f"color: #555; background: {_BG}; font-family: Courier; font-size: 13px; font-weight: bold;"
        )
        self._check_pass_unlock()

    # ── events ────────────────────────────────────────────────────────

    def run(self) -> int:
        """Show full-screen and run the dialog. Use instead of QDialog.exec()."""
        show_fullscreen(self)
        return super().exec()

    def keyPressEvent(self, event) -> None:
        key = event.text().lower()
        if key == "p" and self._pass_unlocked:
            self._finish("pass")
        elif key == "f":
            self._finish("fail")
        elif key == "s":
            self._finish("skip")
        elif event.key() == Qt.Key_Escape:
            return

    def closeEvent(self, event) -> None:
        if self.result() != QDialog.DialogCode.Accepted:
            self.result_str = "fail"
        event.accept()
