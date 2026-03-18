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
- Border (`#30363d`) and surface background (`#21262d`) appear on hover
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
- Add a module-level `_settings_icon() -> QIcon` helper that renders the Heroicons `adjustments-horizontal` SVG path into a `QPixmap` and returns a `QIcon`
- Icon stroke colour: `#7d8590` (muted token) — reads as secondary at rest
- Use `setIcon()` + `setIconSize(QSize(16, 16))`
- Remove the `setFixedSize(32, 32)` call — the QSS class enforces the size

**SVG path (Heroicons `adjustments-horizontal`, 24×24 viewBox, stroke-based):**
```
M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0
M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0
m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0
m-9.75 0h9.75
```

**New imports required:** `QIcon`, `QPixmap` from `PySide6.QtGui`; `QSize` from `PySide6.QtCore`.

---

## 3. `src/ui/widgets/settings_dialog.py` — Replace QDialogButtonBox

**Changes:**
- Remove `QDialogButtonBox` and its import
- Add a `QFrame` horizontal separator (`setFrameShape(QFrame.Shape.HLine)`) as a visual divider above the footer
- Add a `QHBoxLayout` footer with:
  - `addStretch()` to push buttons right
  - `Cancel` button — default style, connected to `self.reject`
  - `Save` button — `class="primary"`, connected to `self.accept`

**No new imports needed** — `QFrame` and `QHBoxLayout` are already imported from `PySide6.QtWidgets`.

---

## Files Changed

| File | Change |
|------|--------|
| `src/ui/stylesheet.py` | Add `icon-btn` QSS block (~12 lines) |
| `src/ui/widgets/header_bar.py` | Replace settings button construction, add `_settings_icon()` helper |
| `src/ui/widgets/settings_dialog.py` | Replace `QDialogButtonBox` with manual footer |

## Out of Scope

- No changes to any other dialogs or buttons
- No changes to the dialog title / window chrome
- No changes to the settings fields themselves
