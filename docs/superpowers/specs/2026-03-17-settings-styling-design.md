# Settings Icon & Dialog Styling — Design Spec

**Date:** 2026-03-17
**Status:** Approved

## Problem

The settings button in the header bar and the Settings dialog are visually inconsistent with the rest of the app:

1. The settings button uses `QPushButton("⚙")` with no class — it falls back to the default bordered button style and uses a Unicode gear character that renders differently across macOS, Windows, and Linux.
2. The Settings dialog uses `QDialogButtonBox` whose Save/Cancel buttons are unstyled — Save does not read as the primary action.

## Solution

Three targeted changes across three files. No new abstractions, no scope creep.

---

## 1. `src/ui/stylesheet.py` — Add `icon-btn` QSS class

A new square icon button variant appended after the existing button block.

**Behaviour:**
- Transparent background and border at rest — visually subordinate to the primary action button
- Surface background `#21262d` and border `#30363d` appear on hover (uses the default button resting colour as the hover fill, since the button is transparent at rest)
- Pressed state drops to `#161b22`

**QSS to add:**
```css
/* ── Icon buttons (32×32 square, SVG icon, no border at rest) ──── */
QPushButton[class="icon-btn"] {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 0;
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
}

QPushButton[class="icon-btn"]:hover {
    background-color: #21262d;
    border-color: #30363d;
}

QPushButton[class="icon-btn"]:pressed {
    background-color: #161b22;
    border-color: #30363d;
}
```

---

## 2. `src/ui/widgets/header_bar.py` — Replace ⚙ with sliders SVG icon

**Changes:**
- Replace `QPushButton("⚙")` with `QPushButton()`
- Set `class="icon-btn"` property
- Keep `setFixedSize(32, 32)` — QSS `min/max-width/height` alone is not sufficient to guarantee a fixed layout size against Qt layout stretching; `setFixedSize` is the reliable guarantee
- Do **not** call `refresh_style()` on this button — `class` is set before the widget is first shown, so Qt applies QSS on first paint without a manual nudge
- `setProperty("class", "icon-btn")` must be called **before** `row1.addWidget(self._settings_btn, ...)` to ensure the property is present on first paint
- Add a module-level `_settings_icon() -> QIcon` helper (see below)
- Use `setIcon(_settings_icon())` + `setIconSize(QSize(16, 16))`

**`_settings_icon()` implementation:**

Use `QSvgRenderer` + `QPainter` to paint the SVG onto a `QPixmap`. This is the correct approach for this codebase — it uses `QtSvg` as a direct Python import rather than relying on Qt's `svg` image plugin being present at runtime (which `QPixmap.loadFromData()` requires).

```python
def _settings_icon() -> QIcon:
    """Return a crisp SVG sliders icon as a QIcon."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"'
        ' stroke="#7d8590" stroke-width="1.5" stroke-linecap="round"'
        ' stroke-linejoin="round">'
        '<path d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0'
        'M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0'
        'm-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0'
        'm-9.75 0h9.75"/>'
        '</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    px = QPixmap(16, 16)
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    renderer.render(painter)
    painter.end()
    return QIcon(px)
```

Icon stroke colour `#7d8590` (muted token) — reads as secondary at rest.

**New imports required:**
```python
from PySide6.QtCore import QByteArray, QSize, Qt       # add QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap     # new
from PySide6.QtSvg import QSvgRenderer                 # new
```

---

## 3. `src/ui/widgets/settings_dialog.py` — Replace QDialogButtonBox

**Changes:**
- Remove `QDialogButtonBox` from the `from PySide6.QtWidgets import (...)` block
- Add `QFrame` to that same import block — it is not currently imported in this file

**Resulting import block for `settings_dialog.py`:**
```python
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
```
- Add a `QFrame` horizontal separator (`setFrameShape(QFrame.Shape.HLine)`) as a visual divider above the footer
- Add a `QHBoxLayout` footer with:
  - `addStretch()` to push buttons right
  - `Cancel` button — default style, connected to `self.reject`
  - `Save` button — `class="primary"`, connected to `self.accept`

`QHBoxLayout` is already imported — no change needed there.

**Replacement code:**
```python
sep = QFrame()
sep.setFrameShape(QFrame.Shape.HLine)
root.addWidget(sep)

btn_row = QHBoxLayout()
btn_row.addStretch()
cancel_btn = QPushButton("Cancel")
cancel_btn.clicked.connect(self.reject)
save_btn = QPushButton("Save")
save_btn.setProperty("class", "primary")
save_btn.clicked.connect(self.accept)
btn_row.addWidget(cancel_btn)
btn_row.addWidget(save_btn)
root.addLayout(btn_row)
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/ui/stylesheet.py` | Add `icon-btn` QSS block (~12 lines) |
| `src/ui/widgets/header_bar.py` | Replace settings button construction; add `_settings_icon()` helper; add imports |
| `src/ui/widgets/settings_dialog.py` | Replace `QDialogButtonBox` with manual footer; fix imports |

## Out of Scope

- No changes to any other dialogs or buttons
- No changes to the dialog title / window chrome
- No changes to the settings fields themselves
