"""Full-screen QDialog keyboard test.

Port of the tkinter _keyboard_helper.py to PySide6 QDialog.
Loads XML layout files from src/ui/keyboards/ and draws an interactive keyboard
diagram.  Keys disappear (match background) when pressed.
"""

import platform
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ._utils import make_dialog_btn, show_fullscreen

_KEYBOARDS_DIR = Path(__file__).resolve().parent.parent / "keyboards"
_LAYOUT_ORDER = ["macbook_us", "tkl_us", "full_us"]

# ── Key mapping (identical to tkinter version) ────────────────────────────

_K = Qt.Key
_KEYSYM_MAP: dict[Qt.Key, str] = {
    _K.Key_Escape: "escape",
    _K.Key_F1: "f1",
    _K.Key_F2: "f2",
    _K.Key_F3: "f3",
    _K.Key_F4: "f4",
    _K.Key_F5: "f5",
    _K.Key_F6: "f6",
    _K.Key_F7: "f7",
    _K.Key_F8: "f8",
    _K.Key_F9: "f9",
    _K.Key_F10: "f10",
    _K.Key_F11: "f11",
    _K.Key_F12: "f12",
    _K.Key_Backspace: "backspace",
    _K.Key_Delete: "delete",
    _K.Key_Tab: "tab",
    _K.Key_Backtab: "tab",
    _K.Key_CapsLock: "caps_lock",
    _K.Key_Return: "enter",
    _K.Key_Enter: "enter",
    _K.Key_Shift: "shift",
    _K.Key_Control: "ctrl",
    _K.Key_Alt: "alt",
    _K.Key_Meta: "meta",
    _K.Key_Space: "space",
    _K.Key_Left: "left",
    _K.Key_Right: "right",
    _K.Key_Up: "up",
    _K.Key_Down: "down",
    _K.Key_Insert: "insert",
    _K.Key_Home: "home",
    _K.Key_End: "end",
    _K.Key_PageUp: "page_up",
    _K.Key_PageDown: "page_down",
    _K.Key_Print: "print_screen",
    _K.Key_ScrollLock: "scroll_lock",
    _K.Key_Pause: "pause",
    _K.Key_NumLock: "num_lock",
}

_CHAR_TO_NAME: dict[str, str] = {
    ".": "period",
    ">": "greater_than_sign",
    ",": "comma",
    "<": "less_than_sign",
    ";": "semicolon",
    ":": "colon",
    "'": "apostrophe",
    '"': "double_quote",
    "[": "left_bracket",
    "{": "left_brace",
    "]": "right_bracket",
    "}": "right_brace",
    "-": "minus",
    "_": "underscore",
    "=": "equal",
    "+": "plus",
    "\\": "backslash",
    "|": "pipe",
    "`": "grave_accent",
    "~": "tilde",
    "/": "slash",
    "?": "question_mark",
    "!": "exclamation_mark",
    "@": "at",
    "#": "hash",
    "$": "dollar_sign",
    "%": "percent_sign",
    "^": "caret",
    "&": "ampersand",
    "*": "asterisk",
    "(": "left_parenthesis",
    ")": "right_parenthesis",
    " ": "space",
}


def _normalize_key(qt_key: Qt.Key) -> str | None:
    return _KEYSYM_MAP.get(qt_key)


def _normalize_char(char: str) -> str | None:
    if not char:
        return None
    if char in _CHAR_TO_NAME:
        return _CHAR_TO_NAME[char]
    if len(char) == 1 and char.isalnum():
        return char.lower()
    return None


# ── Layout data model ─────────────────────────────────────────────────────


@dataclass
class _Key:
    id: str
    label: str
    width: float
    names: set[str]
    capturable: bool = True


@dataclass
class _Row:
    items: list  # _Key | float


@dataclass
class _Layout:
    id: str
    name: str
    rows: list[_Row]
    key_map: dict[str, "_Key"]
    capturable_ids: set[str]
    name_map: dict[str, set[str]]
    max_units: float = 0.0  # cached: max row width in key-units


def _load_layout(path: Path) -> _Layout:
    root = ET.parse(path).getroot()
    lid = root.get("id", path.stem)
    lname = root.get("name", lid)
    rows: list[_Row] = []
    key_map: dict[str, _Key] = {}
    name_map: dict[str, set[str]] = {}
    capturable_ids: set[str] = set()

    for row_el in root.findall("row"):
        items: list = []
        for child in row_el:
            if child.tag == "gap":
                items.append(float(child.get("width", "1.0")))
            elif child.tag == "key":
                key_id = child.get("id", "")
                label = child.get("label", "")
                primary = child.get("key", "")
                width = float(child.get("width", "1.0"))
                cap = child.get("capturable", "true").lower() != "false"
                also_raw = child.get("also", "")

                names: set[str] = set()
                if primary:
                    names.add(primary)
                for k in (x.strip() for x in also_raw.split(",") if x.strip()):
                    names.add(k)

                key = _Key(id=key_id, label=label, width=width, names=names, capturable=cap)
                items.append(key)
                key_map[key_id] = key
                if cap:
                    capturable_ids.add(key_id)
                    for n in names:
                        name_map.setdefault(n, set()).add(key_id)
        rows.append(_Row(items=items))

    def _row_units(row: _Row) -> float:
        return sum(k.width if isinstance(k, _Key) else k for k in row.items)

    max_units = max((_row_units(r) for r in rows), default=0.0)
    return _Layout(
        id=lid,
        name=lname,
        rows=rows,
        key_map=key_map,
        capturable_ids=capturable_ids,
        name_map=name_map,
        max_units=max_units,
    )


def _list_layouts() -> list[tuple[str, Path]]:
    result = []
    for lid in _LAYOUT_ORDER:
        p = _KEYBOARDS_DIR / f"{lid}.xml"
        if p.exists():
            result.append((lid, p))
    return result


# ── Visual constants ──────────────────────────────────────────────────────

_BG = "#1a1a1a"
_KEY_UP = "#2a5ab8"
_KEY_DOWN = "#1a1a1a"
_KEY_NOCAP = "#333333"
_OUTLINE = "#444444"
_TXT_KEY = "#ffffff"
_TXT_DIM = "#555555"
_KEY_GAP = 4
_ROW_GAP = 5
_PAD_X = 28
_PAD_Y = 12


# ── Canvas widget ─────────────────────────────────────────────────────────


class _KeyboardCanvas(QWidget):
    """Custom widget that draws the keyboard layout via QPainter."""

    def __init__(self, parent: "KeyboardDialog") -> None:
        super().__init__(parent)
        self._dialog = parent
        self.setMinimumSize(400, 200)
        # Stored rectangles for hit-testing right-clicks: (key_id, QRectF)
        self._key_rects: list[tuple[str, QRectF]] = []

    def paintEvent(self, event) -> None:
        dlg = self._dialog
        layout = dlg._layouts.get(dlg._active_id)
        if layout is None:
            return
        ps = dlg._pressed.get(dlg._active_id, set())

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        cw = self.width()
        ch = self.height()

        max_units = layout.max_units  # cached at load time
        n_rows = len(layout.rows)

        unit_w = min(62.0, (cw - 2 * _PAD_X) / (max_units + 0.4))
        key_h = min(52.0, (ch - 2 * _PAD_Y) / (n_rows + 0.2))
        kb_w = max_units * unit_w
        kb_h = n_rows * key_h
        x0 = (cw - kb_w) / 2
        fsize = max(7, min(12, int(key_h * 0.27)))

        font = QFont("Courier", fsize)
        font.setBold(True)
        painter.setFont(font)

        self._key_rects.clear()

        y = (ch - kb_h) / 2
        for row in layout.rows:
            x = x0
            for item in row.items:
                if isinstance(item, float):
                    x += item * unit_w
                else:
                    kw = item.width * unit_w - _KEY_GAP
                    kh = key_h - _ROW_GAP

                    if not item.capturable:
                        fill, outline, tc = _KEY_NOCAP, _OUTLINE, _TXT_DIM
                    elif item.id in ps:
                        fill, outline, tc = _BG, _BG, _BG
                    else:
                        fill, outline, tc = _KEY_UP, _OUTLINE, _TXT_KEY

                    rect = QRectF(x, y, kw, kh)
                    painter.setPen(QPen(QColor(outline), 1))
                    painter.setBrush(QColor(fill))
                    painter.drawRect(rect)

                    painter.setPen(QColor(tc))
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, item.label)

                    if item.capturable:
                        self._key_rects.append((item.id, rect))

                    x += item.width * unit_w
            y += key_h

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            pos = event.position()
            for key_id, rect in self._key_rects:
                if rect.contains(pos):
                    dlg = self._dialog
                    ps = dlg._pressed.setdefault(dlg._active_id, set())
                    if key_id not in ps:
                        ps.add(key_id)
                        self.update()
                        dlg._update_title()
                    break
        super().mousePressEvent(event)


# ── Main dialog ───────────────────────────────────────────────────────────


class KeyboardDialog(QDialog):
    """Full-screen keyboard test dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result_str: str = "fail"
        self.setWindowTitle("Keyboard Test")
        self.setStyleSheet(f"QDialog {{ background: {_BG}; }}")

        # Load layouts
        layout_list = _list_layouts()
        self._layouts: dict[str, _Layout] = {}
        for lid, path in layout_list:
            try:
                self._layouts[lid] = _load_layout(path)
            except Exception:
                pass

        default_id = {"Darwin": "macbook_us", "Windows": "full_us"}.get(platform.system(), "tkl_us")
        if default_id not in self._layouts:
            default_id = layout_list[0][0] if layout_list else ""
        self._active_id: str = default_id
        self._pressed: dict[str, set[str]] = {lid: set() for lid in self._layouts}

        # ── Top bar ──────────────────────────────────────────────────
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 12, 16, 18)

        top_bar = QHBoxLayout()
        self._title_label = QLabel()
        self._title_label.setStyleSheet(
            f"color: #4a9eff; background: {_BG}; font-family: Courier; font-size: 16px; font-weight: bold;"
        )
        top_bar.addWidget(self._title_label)
        top_bar.addStretch()
        root_layout.addLayout(top_bar)

        # Layout selector
        selector_bar = QHBoxLayout()
        lbl = QLabel("Layout:")
        lbl.setStyleSheet(f"color: #888; background: {_BG}; font-family: Courier; font-size: 11px;")
        selector_bar.addWidget(lbl)

        self._layout_combo = QComboBox()
        self._layout_combo.setStyleSheet(
            "QComboBox { background: #2e2e2e; color: #cccccc; border: none; "
            "padding: 4px 14px; font-family: Courier; font-size: 11px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #252525; color: #cccccc; "
            "selection-background-color: #2a5ab8; }"
        )
        for lid in self._layouts:
            self._layout_combo.addItem(self._layouts[lid].name, lid)
        idx = self._layout_combo.findData(self._active_id)
        if idx >= 0:
            self._layout_combo.setCurrentIndex(idx)
        self._layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        selector_bar.addWidget(self._layout_combo)
        selector_bar.addStretch()
        root_layout.addLayout(selector_bar)

        # ── Keyboard canvas ──────────────────────────────────────────
        self._canvas = _KeyboardCanvas(self)
        self._canvas.setStyleSheet(f"background: {_BG};")
        root_layout.addWidget(self._canvas, 1)

        # ── Hint ─────────────────────────────────────────────────────
        hint_text = "Press every key -- each disappears when registered.  Right-click any key to mark it manually."
        if platform.system() == "Darwin":
            hint_text += "  (F11: if macOS intercepts it, right-click to mark.)"
        hint = QLabel(hint_text)
        hint.setStyleSheet(
            f"color: #555; background: {_BG}; font-family: Courier; font-size: 10px;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(hint)

        # ── Bottom buttons ───────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._fail_btn = make_dialog_btn("Fail", "#8b1a1a", "#a02020")
        self._fail_btn.clicked.connect(lambda: self._finish("fail"))
        btn_row.addWidget(self._fail_btn)

        self._pass_btn = QPushButton("Pass")
        self._pass_btn.setEnabled(False)
        self._pass_btn.setStyleSheet(
            "QPushButton { background: #2a2a2a; color: #555; border: none; "
            "padding: 8px 28px; font-family: Courier; font-size: 13px; font-weight: bold; }"
            "QPushButton:enabled { background: #1a6b1a; color: white; }"
            "QPushButton:enabled:hover { background: #228822; }"
        )
        self._pass_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self._pass_btn.clicked.connect(lambda: self._finish("pass"))
        btn_row.addWidget(self._pass_btn)

        self._skip_btn = make_dialog_btn("Skip", "#3a3a3a", "#4a4a4a", fg="#aaa")
        self._skip_btn.clicked.connect(lambda: self._finish("skip"))
        btn_row.addWidget(self._skip_btn)

        root_layout.addLayout(btn_row)

        self._update_title()

    # ── helpers ─────────────────────────────────────────────────────────

    def _finish(self, result: str) -> None:
        if result == "pass" and not self._pass_btn.isEnabled():
            return
        self.result_str = result
        self.accept()

    def _update_title(self) -> None:
        layout = self._layouts.get(self._active_id)
        if layout is None:
            return
        ps = self._pressed.get(self._active_id, set())
        total = len(layout.capturable_ids)
        count = len(ps)
        self._title_label.setText(f"Keyboard Test  --  {count} / {total} keys")
        all_done = count >= total
        self._pass_btn.setEnabled(all_done)
        if all_done:
            self._pass_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._pass_btn.setCursor(Qt.CursorShape.ArrowCursor)

    def _on_layout_changed(self, index: int) -> None:
        lid = self._layout_combo.itemData(index)
        if lid and lid in self._layouts:
            self._active_id = lid
            self._canvas.update()
            self._update_title()

    def _register_name(self, name: str) -> None:
        layout = self._layouts.get(self._active_id)
        if layout is None:
            return
        key_ids = layout.name_map.get(name, set())
        ps = self._pressed.setdefault(self._active_id, set())
        if key_ids - ps:
            ps.update(key_ids)
            self._canvas.update()
            self._update_title()

    # ── events ─────────────────────────────────────────────────────────

    def run(self) -> int:
        """Show full-screen and run the dialog."""
        show_fullscreen(self)
        return super().exec()  # Qt dialog event loop, not shell

    def showEvent(self, event) -> None:
        super().showEvent(event)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        """Intercept all key events so child widgets can't steal keyboard focus."""
        t = event.type()
        if t == QEvent.Type.KeyPress:
            self.keyPressEvent(event)
            return True
        if t == QEvent.Type.KeyRelease:
            self.keyReleaseEvent(event)
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Try Qt key code first
        name = _normalize_key(event.key())
        # Fallback: character
        if name is None:
            name = _normalize_char(event.text())
        if name is not None:
            self._register_name(name)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        # Caps Lock on macOS: also register on release
        if event.key() == Qt.Key.Key_CapsLock:
            self._register_name("caps_lock")

    def closeEvent(self, event) -> None:
        if self.result() != QDialog.DialogCode.Accepted:
            self.result_str = "fail"
        event.accept()
