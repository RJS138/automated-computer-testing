# Theming — Color Token System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix light mode by replacing hardcoded dark hex colors in all inline `setStyleSheet()` calls with theme-aware `apply_theme(theme)` methods, and add live-preview when the theme toggle is clicked.

**Architecture:** Add `DARK`/`LIGHT` color dicts + `build_seg_styles(theme)` to `stylesheet.py` as a single source of truth. Each widget gains `apply_theme(theme)` that rebuilds its inline styles from these dicts. `TouchstoneWindow.set_theme()` propagates down the hierarchy: window → pages → header/banner/sections → cards. `SettingsDialog` gets a `window` param and calls `window.set_theme()` immediately on each click; overriding `reject()` reverts the preview on cancel.

**Tech Stack:** PySide6, Python f-strings, existing `src/ui/stylesheet.py`

---

## File Map

| File | Action | What Changes |
|------|--------|-------------|
| `src/ui/stylesheet.py` | Modify | Add `DARK`, `LIGHT` dicts, `get_colors()`, `build_seg_styles()` |
| `src/ui/widgets/dashboard_card.py` | Modify | `theme` param, `apply_theme()`, import `get_colors` |
| `src/ui/widgets/category_section.py` | Modify | `theme` param, `apply_theme()`, propagate to cards |
| `src/ui/widgets/header_bar.py` | Modify | `theme` param, `apply_theme()`, remove `_SEG_*` constants |
| `src/ui/widgets/device_banner.py` | Modify | `_SpecField.apply_theme()`, `DeviceBanner.apply_theme()` |
| `src/ui/pages/job_setup_page.py` | Modify | `theme` param, `apply_theme()`, remove `_SEG_*` constants, store widget refs |
| `src/ui/widgets/settings_dialog.py` | Modify | `window` param, `apply_theme()`, override `reject()`, live preview, remove `_SEG_*` constants |
| `src/ui/pages/test_dashboard_page.py` | Modify | `theme` param, `apply_theme()`, store scroll refs, update `_on_settings_clicked` |
| `src/ui/app_window.py` | Modify | Pass `theme=self._theme` to pages, update `set_theme()` to propagate |

---

## Task 1: Add color token dicts and helpers to stylesheet.py

**Files:**
- Modify: `src/ui/stylesheet.py`

This is a pure addition — no existing code changes. Adds the three things every other task depends on.

- [ ] **Step 1: Add DARK and LIGHT color token dicts after the module docstring (after line 45, before line 47 `# ------`)**

Add the following block immediately after the closing `"""` of the module docstring and before the `# ---------------------------------------------------------------------------` separator:

```python
# ---------------------------------------------------------------------------
# Color token dicts (programmatic access alongside QSS strings above)
# ---------------------------------------------------------------------------

DARK: dict[str, str] = {
    "bg_base":        "#09090b",
    "bg_surface":     "#18181b",
    "bg_elevated":    "#27272a",
    "bg_hover":       "#3f3f46",
    "text_primary":   "#fafafa",
    "text_secondary": "#a1a1aa",
    "text_muted":     "#71717a",
    "accent":         "#3b82f6",
    "accent_hover":   "#2563eb",
    "border_subtle":  "#27272a",
    "seg_off_bg":     "#3f3f46",
    "seg_off_text":   "#a1a1aa",
    "seg_on_bg":      "#3b82f6",
    "seg_on_text":    "#ffffff",
    "warn_row_bg":    "#2d1a00",
    "warn_text":      "#f59e0b",
    "badge_accent_bg":   "#1e3a5f",
    "badge_accent_text": "#60a5fa",
    "danger_bg":      "#7f1d1d",
    "danger_text":    "#fca5a5",
}

LIGHT: dict[str, str] = {
    "bg_base":        "#f5f4f1",
    "bg_surface":     "#fafaf9",
    "bg_elevated":    "#e7e5e4",
    "bg_hover":       "#d6d3d1",
    "text_primary":   "#1c1917",
    "text_secondary": "#78716c",
    "text_muted":     "#a8a29e",
    "accent":         "#2563eb",
    "accent_hover":   "#1d4ed8",
    "border_subtle":  "#e7e5e4",
    "seg_off_bg":     "#e7e5e4",
    "seg_off_text":   "#78716c",
    "seg_on_bg":      "#2563eb",
    "seg_on_text":    "#ffffff",
    "warn_row_bg":    "#fef3c7",
    "warn_text":      "#d97706",
    "badge_accent_bg":   "#dbeafe",
    "badge_accent_text": "#2563eb",
    "danger_bg":      "#fee2e2",
    "danger_text":    "#dc2626",
}


def get_colors(theme: str) -> dict[str, str]:
    """Return the color token dict for the given theme ("dark" or "light")."""
    return LIGHT if theme == "light" else DARK


def build_seg_styles(theme: str) -> dict[str, str]:
    """Return ON/OFF style strings for left, mid, right segmented buttons.

    Keys: L_ON, L_OFF, M_ON, M_OFF, R_ON, R_OFF

    Note: M_ON / M_OFF are only needed by settings_dialog.py (3-button Output
    Format group). header_bar.py and job_setup_page.py only consume L_* and
    R_* — M variants are generated but intentionally ignored in those files.
    """
    c = get_colors(theme)
    radius = {
        "L": (
            "border-top-left-radius: 6px; border-bottom-left-radius: 6px;"
            " border-top-right-radius: 0; border-bottom-right-radius: 0;"
        ),
        "M": "border-radius: 0;",
        "R": (
            "border-top-left-radius: 0; border-bottom-left-radius: 0;"
            " border-top-right-radius: 6px; border-bottom-right-radius: 6px;"
        ),
    }
    margin = {"L": "", "M": " margin-left: 2px; margin-right: 2px;", "R": ""}
    result: dict[str, str] = {}
    for pos in ("L", "M", "R"):
        r = radius[pos]
        m = margin[pos]
        result[f"{pos}_ON"] = (
            f"QPushButton {{ background: {c['seg_on_bg']}; color: {c['seg_on_text']};"
            f" border: none; {r}{m} font-weight: 600; min-height: 30px;"
            f" padding: 5px 14px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {c['accent_hover']};"
            f" color: {c['seg_on_text']}; }}"
        )
        result[f"{pos}_OFF"] = (
            f"QPushButton {{ background: {c['seg_off_bg']}; color: {c['seg_off_text']};"
            f" border: none; {r}{m} font-weight: 500; min-height: 30px;"
            f" padding: 5px 14px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {c['bg_hover']};"
            f" color: {c['text_primary']}; }}"
        )
    return result
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/robertsaunders/Code/Automated PC Testing/pc-tester"
git add src/ui/stylesheet.py
git commit -m "feat: add DARK/LIGHT color dicts, get_colors(), build_seg_styles() to stylesheet"
```

---

## Task 2: Theme DashboardCard

**Files:**
- Modify: `src/ui/widgets/dashboard_card.py`

**Context:** `DashboardCard` is the leaf widget. It has hardcoded dark hex colors in `_build_ui()`. We add a `theme` param and `apply_theme(theme)` method. `_build_ui()` calls `apply_theme(theme)` at the end instead of setting styles inline. `set_status()` continues to set `_detail_lbl` color inline (status-specific colors are semantic and left unchanged).

- [ ] **Step 1: Add import at top of file**

Add to the imports block (after line 17 `from ..stylesheet import refresh_style`). Use a **relative import** to match the existing style in this file:

```python
from ..stylesheet import get_colors
```

- [ ] **Step 2: Update `__init__` signature and add `apply_theme` call**

Current line 43:
```python
def __init__(self, name: str, display_name: str, parent=None) -> None:
```

Replace with:
```python
def __init__(self, name: str, display_name: str, theme: str = "dark", parent=None) -> None:
```

At the end of `__init__`, replace the `self._build_ui()` call (line 60) with:
```python
self._build_ui()
self.apply_theme(theme)
```

- [ ] **Step 3: Remove all `setStyleSheet` calls from `_build_ui()` for themed widgets**

In `_build_ui()`, remove or clear the inline style arguments for:
- Line 51–52: Frame background — **delete these two lines** (`self.setStyleSheet(...)`)
- Line 88–90: `_name_lbl` style — **delete these three lines** (`self._name_lbl.setStyleSheet(...)`)
- Line 96–98: `_detail_lbl` style — **delete these three lines** (`self._detail_lbl.setStyleSheet(...)`)
- Lines 105–107: `_expand_arrow` style — **delete these three lines** (`self._expand_arrow.setStyleSheet(...)`)
- Lines 126–132: `_run_btn` style — **delete these seven lines** (`self._run_btn.setStyleSheet(...)`)
- Lines 140–143: `_detail_panel` style — **delete these four lines** (`self._detail_panel.setStyleSheet(...)`)

Keep all other lines in `_build_ui()` intact (layout, size policies, signals, etc.).

- [ ] **Step 4: Add `apply_theme()` method**

Add the following method to the `# ── Public API` section (after `set_running_all`, before the `# ── Private` comment):

```python
def apply_theme(self, theme: str) -> None:
    """Re-apply all inline styles using the given theme's color tokens."""
    c = get_colors(theme)
    self.setStyleSheet(
        f"QFrame {{ border: none; background: {c['bg_surface']}; border-radius: 8px; }}"
    )
    self._name_lbl.setStyleSheet(
        f"color: {c['text_primary']}; font-size: 14px; font-weight: 500; background: transparent;"
    )
    self._detail_lbl.setStyleSheet(
        f"color: {c['text_muted']}; font-size: 13px; background: transparent;"
    )
    self._expand_arrow.setStyleSheet(
        f"color: {c['text_secondary']}; font-size: 16px; background: transparent;"
    )
    self._run_btn.setStyleSheet(
        f"QPushButton {{ background: {c['bg_elevated']}; color: {c['text_secondary']};"
        f" border: none; border-radius: 6px; font-size: 12px; font-weight: 500; }}"
        f"QPushButton:hover {{ background: {c['bg_hover']}; color: {c['text_primary']}; }}"
        f"QPushButton:pressed {{ background: {c['text_muted']}; }}"
        f"QPushButton:disabled {{ opacity: 0.4; }}"
    )
    self._detail_panel.setStyleSheet(
        f"color: {c['text_secondary']}; font-size: 12px; background: transparent;"
        f" padding: 2px 10px 10px 10px;"
    )
```

- [ ] **Step 5: Verify app still launches correctly in dark mode**

```bash
uv run touchstone --dev-manual
```

Expected: App opens, test dashboard shows correctly. Cards render with dark surface backgrounds, correct text colors. No visual regressions vs before this task.

- [ ] **Step 6: Commit**

```bash
git add src/ui/widgets/dashboard_card.py
git commit -m "feat: add apply_theme() to DashboardCard; replace hardcoded dark colors"
```

---

## Task 3: Theme CategorySection

**Files:**
- Modify: `src/ui/widgets/category_section.py`

**Context:** `CategorySection` owns `DashboardCard` instances. It adds a `theme` param, stores it as `self._theme`, and propagates to cards in both `_rebuild_rows()` (construction-time) and `apply_theme()` (live update).

- [ ] **Step 1: Add import**

Add to the imports block (after `from src.ui.widgets.dashboard_card import DashboardCard`). Both existing imports in this file are absolute (`from src.models...`, `from src.ui.widgets...`), so use an absolute import here too:

```python
from src.ui.stylesheet import get_colors
```

- [ ] **Step 2: Update `__init__` signature and store theme**

Current line 33–40:
```python
def __init__(
    self,
    title: str,
    tests: list[tuple[str, str, bool]],
    col_count: int,
    short_names: dict[str, str] | None = None,
    parent=None,
) -> None:
    super().__init__(parent)
```

Replace with:
```python
def __init__(
    self,
    title: str,
    tests: list[tuple[str, str, bool]],
    col_count: int,
    short_names: dict[str, str] | None = None,
    theme: str = "dark",
    parent=None,
) -> None:
    super().__init__(parent)
    self._theme = theme
```

- [ ] **Step 2b: Store `self._title_lbl` in `_build_ui()`**

In `_build_ui()`, find this line (currently around line 68):
```python
title_lbl = QLabel(self._title.upper())
title_lbl.setStyleSheet(
    "font-size: 11px; font-weight: 600; color: #71717a; "
    "letter-spacing: 0.06em; background: transparent;"
)
h_layout.addWidget(title_lbl)
```

Change `title_lbl` to `self._title_lbl` (keep the existing inline style for now — it will be overwritten by `apply_theme()` at the end of `__init__`):
```python
self._title_lbl = QLabel(self._title.upper())
self._title_lbl.setStyleSheet(
    "font-size: 11px; font-weight: 600; color: #71717a; "
    "letter-spacing: 0.06em; background: transparent;"
)
h_layout.addWidget(self._title_lbl)
```

Also add `self.apply_theme(theme)` at the end of `__init__`, after `self._build_ui()`:
```python
self._build_ui()
self.apply_theme(theme)
```

- [ ] **Step 3: Pass theme when creating DashboardCards in `_rebuild_rows()`**

In `_rebuild_rows()`, find this line (currently around line 123):
```python
card = DashboardCard(name, display_name)
```

Replace with:
```python
card = DashboardCard(name, display_name, theme=self._theme)
```

- [ ] **Step 4: Add `apply_theme()` method**

Add to the `# ── Public API` section (after `card()` method):

```python
def apply_theme(self, theme: str) -> None:
    """Re-apply all inline styles and propagate to child cards."""
    self._theme = theme
    c = get_colors(theme)
    # Section separator
    for i in range(self.layout().count()):
        item = self.layout().itemAt(i)
        if item and item.widget():
            w = item.widget()
            if isinstance(w, __import__("PySide6.QtWidgets", fromlist=["QFrame"]).QFrame) and w is not self:
                w.setStyleSheet(
                    f"background: {c['border_subtle']}; border: none;"
                    f" max-height: 1px; min-height: 1px;"
                )
    # Header arrow and title
    self._arrow_lbl.setStyleSheet(
        f"color: {c['text_muted']}; font-size: 11px; background: transparent;"
    )
    # Propagate to all cards
    for card in self._cards.values():
        card.apply_theme(theme)
```

**Note:** The separator `QFrame` is found by iterating the outer layout. This is safe because the outer layout contains exactly: `_header_widget` (QWidget), `sep` (QFrame), `_collapsible` (QWidget), and a spacer `QWidget`. The only `QFrame` that is not `self` is the separator.

Actually, to avoid the fragile layout-iteration approach, store a reference to the separator instead. Update `_build_ui()` to store the separator:

Find in `_build_ui()` (currently around line 83):
```python
sep = QFrame()
sep.setFrameShape(QFrame.Shape.HLine)
sep.setStyleSheet("background: #27272a; border: none; max-height: 1px; min-height: 1px;")
outer.addWidget(sep)
```

Change to:
```python
self._sep = QFrame()
self._sep.setFrameShape(QFrame.Shape.HLine)
self._sep.setStyleSheet("background: #27272a; border: none; max-height: 1px; min-height: 1px;")
outer.addWidget(self._sep)
```

Then simplify `apply_theme()` to:

```python
def apply_theme(self, theme: str) -> None:
    """Re-apply all inline styles and propagate to child cards."""
    self._theme = theme
    c = get_colors(theme)
    self._title_lbl.setStyleSheet(
        f"font-size: 11px; font-weight: 600; color: {c['text_muted']};"
        f" letter-spacing: 0.06em; background: transparent;"
    )
    self._sep.setStyleSheet(
        f"background: {c['border_subtle']}; border: none; max-height: 1px; min-height: 1px;"
    )
    self._arrow_lbl.setStyleSheet(
        f"color: {c['text_muted']}; font-size: 11px; background: transparent;"
    )
    for card in self._cards.values():
        card.apply_theme(theme)
```

- [ ] **Step 5: Commit**

```bash
git add src/ui/widgets/category_section.py
git commit -m "feat: add apply_theme() to CategorySection; propagate to DashboardCards"
```

---

## Task 4: Theme HeaderBar

**Files:**
- Modify: `src/ui/widgets/header_bar.py`

**Context:** `HeaderBar` has module-level `_SEG_L/R_ON/OFF` string constants that are duplicates of the same hardcoded strings in other files. These are removed and replaced by `build_seg_styles()`. The widget stores `self._theme` and has `apply_theme(theme)` for all button/background styles. `_select_mode()` calls `build_seg_styles(self._theme)` to get the current theme's styles.

- [ ] **Step 1: Replace imports and remove `_SEG_*` module-level constants**

Current imports (lines 1–13) + constants (lines 17–46). Keep only:
- All `from PySide6.QtCore import Signal`
- All `from PySide6.QtWidgets import ...`
- `from src.models.job import JobInfo`

Add new import:
```python
from src.ui.stylesheet import build_seg_styles, get_colors
```

Delete the entire `_SEG_L_OFF`, `_SEG_L_ON`, `_SEG_R_OFF`, `_SEG_R_ON` constant blocks (lines 19–46).

- [ ] **Step 2: Update `__init__` to accept and store theme**

Current line 65:
```python
def __init__(self, parent=None) -> None:
    super().__init__(parent)
    self._mode = "simple"
    self._build_ui()
```

Replace with:
```python
def __init__(self, theme: str = "dark", parent=None) -> None:
    super().__init__(parent)
    self._mode = "simple"
    self._theme = theme
    self._build_ui()
    self.apply_theme(theme)
```

- [ ] **Step 3: Strip hardcoded styles from `_build_ui()`**

In `_build_ui()`, remove these inline `setStyleSheet` calls (they will be handled by `apply_theme()`):
- `primary.setStyleSheet("background: #18181b;")` — remove
- `self._job_info_lbl.setStyleSheet(...)` — remove
- `self._report_badge.setStyleSheet(...)` — remove
- `self._simple_btn.setStyleSheet(_SEG_L_ON)` — remove the `setStyleSheet` call (keep `clicked.connect`)
- `self._advanced_btn.setStyleSheet(_SEG_R_OFF)` — remove the `setStyleSheet` call (keep `clicked.connect`)
- `self._run_all_btn.setStyleSheet(...)` — remove
- `new_job_btn.setStyleSheet(...)` — remove
- `settings_btn.setStyleSheet(...)` — remove
- `self._warn_row.setStyleSheet("background: #2d1a00;")` — remove
- `warn_lbl.setStyleSheet(...)` — remove

Store refs for widgets that need styling:
- Already stored: `self._job_info_lbl`, `self._report_badge`, `self._simple_btn`, `self._advanced_btn`, `self._run_all_btn`, `self._warn_row`
- Add: `self._new_job_btn = new_job_btn` (currently a local var, make it an instance attr)
- Add: `self._settings_btn = settings_btn` (currently a local var, make it an instance attr)
- Add: `self._warn_lbl = warn_lbl` (currently a local var, make it an instance attr)
- Add: `self._primary_row = primary` (currently a local var, make it an instance attr)

- [ ] **Step 4: Update `_select_mode()` to use `build_seg_styles()`**

Current `_select_mode()` (lines 198–208):
```python
def _select_mode(self, mode: str) -> None:
    if mode == self._mode:
        return
    self._mode = mode
    if mode == "advanced":
        self._simple_btn.setStyleSheet(_SEG_L_OFF)
        self._advanced_btn.setStyleSheet(_SEG_R_ON)
    else:
        self._simple_btn.setStyleSheet(_SEG_L_ON)
        self._advanced_btn.setStyleSheet(_SEG_R_OFF)
    self.mode_changed.emit(mode)
```

Replace with:
```python
def _select_mode(self, mode: str) -> None:
    if mode == self._mode:
        return
    self._mode = mode
    seg = build_seg_styles(self._theme)
    if mode == "advanced":
        self._simple_btn.setStyleSheet(seg["L_OFF"])
        self._advanced_btn.setStyleSheet(seg["R_ON"])
    else:
        self._simple_btn.setStyleSheet(seg["L_ON"])
        self._advanced_btn.setStyleSheet(seg["R_OFF"])
    self.mode_changed.emit(mode)
```

Also update `reset_mode()`:
```python
def reset_mode(self) -> None:
    """Reset to Simple mode without emitting mode_changed."""
    if self._mode != "simple":
        self._mode = "simple"
        seg = build_seg_styles(self._theme)
        self._simple_btn.setStyleSheet(seg["L_ON"])
        self._advanced_btn.setStyleSheet(seg["R_OFF"])
```

- [ ] **Step 5: Add `apply_theme()` method**

Add to the `# ── Public API` section:

```python
def apply_theme(self, theme: str) -> None:
    """Re-apply all inline styles for the given theme."""
    self._theme = theme
    c = get_colors(theme)
    seg = build_seg_styles(theme)

    self._primary_row.setStyleSheet(f"background: {c['bg_surface']};")
    self._job_info_lbl.setStyleSheet(
        f"font-size: 12px; font-weight: 600; color: {c['text_primary']}; background: transparent;"
    )
    self._report_badge.setStyleSheet(
        f"background: {c['badge_accent_bg']}; color: {c['badge_accent_text']};"
        f" font-size: 10px; font-weight: 700; padding: 1px 7px; border-radius: 4px; border: none;"
    )
    # Segmented mode buttons (preserve current selected state)
    if self._mode == "advanced":
        self._simple_btn.setStyleSheet(seg["L_OFF"])
        self._advanced_btn.setStyleSheet(seg["R_ON"])
    else:
        self._simple_btn.setStyleSheet(seg["L_ON"])
        self._advanced_btn.setStyleSheet(seg["R_OFF"])
    # Run All button (always accent — same in both themes)
    self._run_all_btn.setStyleSheet(
        f"QPushButton {{ background: {c['accent']}; color: #ffffff; border: none;"
        f" border-radius: 6px; padding: 5px 14px; font-size: 12px;"
        f" font-weight: 600; min-height: 30px; }}"
        f"QPushButton:hover {{ background: {c['accent_hover']}; }}"
        f"QPushButton:pressed {{ background: {c['accent_hover']}; }}"
        f"QPushButton:disabled {{ background: {c['accent']}; color: #ffffff; opacity: 0.4; }}"
    )
    # New Job button
    self._new_job_btn.setStyleSheet(
        f"QPushButton {{ background: {c['bg_elevated']}; color: {c['text_secondary']};"
        f" border: none; border-radius: 6px; padding: 5px 14px; font-size: 12px;"
        f" font-weight: 500; min-height: 30px; }}"
        f"QPushButton:hover {{ background: {c['bg_hover']}; color: {c['text_primary']}; }}"
        f"QPushButton:pressed {{ background: {c['text_muted']}; }}"
    )
    # Settings gear
    self._settings_btn.setStyleSheet(
        f"QPushButton {{ background: {c['bg_elevated']}; border: none; border-radius: 6px;"
        f" min-width: 36px; min-height: 36px; max-width: 36px; max-height: 36px;"
        f" font-size: 18px; padding: 0; }}"
        f"QPushButton:hover {{ background: {c['bg_hover']}; }}"
        f"QPushButton:pressed {{ background: {c['text_muted']}; }}"
    )
    # Elevation warning row
    self._warn_row.setStyleSheet(f"background: {c['warn_row_bg']};")
    self._warn_lbl.setStyleSheet(f"color: {c['warn_text']}; font-size: 11px;")
```

- [ ] **Step 6: Commit**

```bash
git add src/ui/widgets/header_bar.py
git commit -m "feat: add apply_theme() to HeaderBar; remove _SEG_* constants; use build_seg_styles()"
```

---

## Task 5: Theme DeviceBanner

**Files:**
- Modify: `src/ui/widgets/device_banner.py`

**Context:** `DeviceBanner` contains a private `_SpecField` inner class. `_SpecField` tracks whether it has a value (`_has_value` flag) so `apply_theme()` can set the correct color. `DeviceBanner.apply_theme()` updates the frame background, calls `apply_theme()` on each field, and updates the Generate Report button.

Note: `_OVERALL_STYLES` (status badge colors for the overall indicator) is **not changed** — these are semantic status colors, deferred per spec.

- [ ] **Step 1: Add import**

Add to imports:
```python
from src.ui.stylesheet import get_colors
```

- [ ] **Step 2: Update `_SpecField` to track value state and support theming**

Replace the entire `_SpecField` class (lines 31–66) with:

```python
class _SpecField(QWidget):
    """Label + value column in the banner."""

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        self._has_value = False
        self._theme = "dark"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._lbl = QLabel(label.upper())
        layout.addWidget(self._lbl)

        self._val = QLabel("—")
        layout.addWidget(self._val)

        self.apply_theme("dark")  # initial styles

    def set_value(self, text: str) -> None:
        self._has_value = True
        self._val.setText(text)
        c = get_colors(self._theme)
        self._val.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {c['text_primary']};"
            f" font-family: monospace; background: transparent;"
        )

    def clear(self) -> None:
        self._has_value = False
        self._val.setText("—")
        c = get_colors(self._theme)
        self._val.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {c['text_muted']};"
            f" font-family: monospace; background: transparent;"
        )

    def apply_theme(self, theme: str) -> None:
        self._theme = theme
        c = get_colors(theme)
        self._lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {c['text_muted']};"
            f" letter-spacing: 0.05em; background: transparent;"
        )
        val_color = c["text_primary"] if self._has_value else c["text_muted"]
        self._val.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {val_color};"
            f" font-family: monospace; background: transparent;"
        )
```

- [ ] **Step 3: Update `DeviceBanner.__init__` to remove hardcoded frame style**

Current `__init__` body (lines 80–86) in the actual source:
```python
def __init__(self, parent=None) -> None:
    super().__init__(parent)
    self.setStyleSheet(
        "QFrame { background-color: #18181b; border: none; }"
    )
    self._fields: dict[str, _SpecField] = {}
    self._build_ui()
```

Remove the `setStyleSheet(...)` block. Add `apply_theme("dark")` **after** `self._build_ui()` (not before — `_build_ui()` creates `self._report_btn` and populates `self._fields`, both of which `apply_theme()` needs):
```python
def __init__(self, theme: str = "dark", parent=None) -> None:
    super().__init__(parent)
    self._fields: dict[str, _SpecField] = {}
    self._build_ui()       # must run first — creates _report_btn and _fields
    self.apply_theme(theme)
```

- [ ] **Step 4: Add `apply_theme()` to `DeviceBanner`**

Add to the `# ── Public API` section:

```python
def apply_theme(self, theme: str) -> None:
    """Re-apply all inline styles for the given theme."""
    c = get_colors(theme)
    self.setStyleSheet(
        f"QFrame {{ background-color: {c['bg_surface']}; border: none; }}"
    )
    for field in self._fields.values():
        field.apply_theme(theme)
    self._report_btn.setStyleSheet(
        f"QPushButton {{"
        f"  background: {c['bg_elevated']}; color: {c['text_muted']};"
        f"  border: none; border-radius: 6px;"
        f"  font-size: 11px; font-weight: 700;"
        f"}}"
        f"QPushButton:enabled {{ color: {c['text_primary']}; }}"
        f"QPushButton:enabled:hover {{"
        f"  background: {c['bg_hover']}; color: {c['text_primary']};"
        f"}}"
        f"QPushButton:disabled {{ color: {c['text_muted']}; }}"
    )
```

- [ ] **Step 5: Commit**

```bash
git add src/ui/widgets/device_banner.py
git commit -m "feat: add apply_theme() to DeviceBanner and _SpecField; track value state for correct color"
```

---

## Task 6: Theme JobSetupPage

**Files:**
- Modify: `src/ui/pages/job_setup_page.py`

**Context:** `JobSetupPage` has module-level `_SEG_L/R_ON/OFF` constants (lines 22–49) that are removed. The page stores `self._theme` and refs to all themed widgets. `apply_theme(theme)` rebuilds all styles. Since `_make_recent_row()` creates labels with hardcoded colors, it reads `self._theme` instead. `apply_theme()` calls `reload_recent_jobs()` to regenerate rows with the new theme (fast, infrequent operation).

- [ ] **Step 1: Replace imports and remove `_SEG_*` constants**

Remove lines 22–49 (all four `_SEG_*` string constant definitions).

Add to the imports block:
```python
from src.ui.stylesheet import build_seg_styles, get_colors
```

- [ ] **Step 2: Update `__init__` to accept theme**

Current line 64:
```python
def __init__(self, parent=None) -> None:
    super().__init__(parent)
    self._report_type = ReportType.BEFORE
    self._recent_expanded = False
    self._build_ui()
```

Replace with:
```python
def __init__(self, theme: str = "dark", parent=None) -> None:
    super().__init__(parent)
    self._theme = theme
    self._report_type = ReportType.BEFORE
    self._recent_expanded = False
    self._build_ui()
    self.apply_theme(theme)
```

- [ ] **Step 3: Store refs to all themed widgets in `_build_ui()`**

In `_build_ui()`, change local variables to instance attributes for all widgets whose styles will be managed by `apply_theme()`. Also remove inline `setStyleSheet` calls for those widgets (they'll be set by `apply_theme()`):

**title_lbl (line 91–93):** Change to `self._title_lbl` and remove `.setStyleSheet(...)`:
```python
self._title_lbl = QLabel("New Job")
inner_layout.addWidget(self._title_lbl)
```

**sub_lbl (lines 95–97):** Change to `self._sub_lbl` and remove `.setStyleSheet(...)`:
```python
self._sub_lbl = QLabel("Fill in the details below, then start testing.")
inner_layout.addWidget(self._sub_lbl)
```

**form_card (lines 100–105):** Change to `self._form_card` and remove `.setStyleSheet(...)`:
```python
self._form_card = QFrame()
form_layout = QVBoxLayout(self._form_card)
form_layout.setContentsMargins(20, 20, 20, 20)
form_layout.setSpacing(12)
```

**cust_lbl (lines 114–118):** Change to `self._cust_lbl` and remove `.setStyleSheet(...)`:
```python
self._cust_lbl = QLabel("CUSTOMER NAME")
cust_col.addWidget(self._cust_lbl)
```

**job_lbl (lines 127–131):** Change to `self._job_lbl` and remove `.setStyleSheet(...)`:
```python
self._job_lbl = QLabel("JOB #")
job_col.addWidget(self._job_lbl)
```

**dev_lbl (lines 143–147):** Change to `self._dev_lbl` and remove `.setStyleSheet(...)`:
```python
self._dev_lbl = QLabel("DEVICE DESCRIPTION")
dev_col.addWidget(self._dev_lbl)
```

**sep (lines 154–157):** Change to `self._form_sep` and remove `.setStyleSheet(...)`:
```python
self._form_sep = QFrame()
self._form_sep.setFrameShape(QFrame.Shape.HLine)
form_layout.addWidget(self._form_sep)
```

**type_lbl (lines 161–165):** Change to `self._type_lbl` and remove `.setStyleSheet(...)`:
```python
self._type_lbl = QLabel("REPORT TYPE")
type_col.addWidget(self._type_lbl)
```

**Before/After buttons (lines 170–179):** Remove `.setStyleSheet(...)` calls from both buttons (styles will be set by `apply_theme()` → `_set_report_type()`).

**`self._start_btn` (lines 187–194):** Remove `.setStyleSheet(...)` call.

- [ ] **Step 4: Store refs to themed widgets in `_build_recent_panel()`**

In `_build_recent_panel()`:

**panel (line 215–218):** Change to `self._recent_panel` and remove `.setStyleSheet(...)`:
```python
self._recent_panel = QFrame()
panel_layout = QVBoxLayout(self._recent_panel)
panel_layout.setContentsMargins(0, 0, 0, 0)
panel_layout.setSpacing(0)
```

**title_lbl (lines 229–233):** Change to `self._recent_title_lbl` and remove `.setStyleSheet(...)`:
```python
self._recent_title_lbl = QLabel("Recent Jobs")
h_layout.addWidget(self._recent_title_lbl)
```

At the end of `_build_recent_panel()`, update to use `self._recent_panel`:
```python
parent_layout.addWidget(self._recent_panel)
```

- [ ] **Step 5: Update `_make_recent_row()` to use `self._theme`**

Replace all hardcoded hex colors in `_make_recent_row()` with `get_colors(self._theme)` lookups:

```python
def _make_recent_row(self, job: dict) -> QWidget:
    c = get_colors(self._theme)
    row = QWidget()
    row.setCursor(Qt.CursorShape.PointingHandCursor)
    row.setStyleSheet(
        f"QWidget {{ background: transparent; }}"
        f"QWidget:hover {{ background: {c['bg_elevated']}; }}"
    )
    layout = QGridLayout(row)
    layout.setContentsMargins(12, 8, 12, 8)
    layout.setSpacing(8)
    layout.setColumnStretch(0, 1)

    desc = job.get("device_description") or ""
    name_text = f"{job['customer_name']} — {desc}" if desc else job["customer_name"]
    name_lbl = QLabel(name_text)
    name_lbl.setStyleSheet(
        f"font-size: 12px; color: {c['text_primary']}; font-weight: 500; background: transparent;"
    )
    layout.addWidget(name_lbl, 0, 0)

    mtime = job.get("_mtime", 0.0)
    dt = datetime.fromtimestamp(mtime)
    date_str = f"{dt.strftime('%b')} {dt.day}"
    meta_lbl = QLabel(f"{job['job_number']}  ·  {date_str}")
    meta_lbl.setStyleSheet(f"font-size: 11px; color: {c['text_muted']}; background: transparent;")
    layout.addWidget(meta_lbl, 1, 0)

    for col, (has_it, label) in enumerate(
        [(job["has_before"], "Before"), (job["has_after"], "After")], start=1
    ):
        color = "#22c55e" if has_it else "#52525b"
        mark = "✓" if has_it else "—"
        badge = QLabel(f"{label} {mark}")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: 600; background: transparent;"
        )
        layout.addWidget(badge, 0, col, 2, 1, Qt.AlignmentFlag.AlignVCenter)

    row.mousePressEvent = lambda _e, j=job: self._on_recent_clicked(j)
    return row
```

Also update the divider in `reload_recent_jobs()`:
```python
div = QFrame()
div.setFrameShape(QFrame.Shape.HLine)
c = get_colors(self._theme)
div.setStyleSheet(
    f"background: {c['border_subtle']}; border: none; max-height: 1px; min-height: 1px;"
)
```

- [ ] **Step 6: Update `_set_report_type()` to use `build_seg_styles()`**

Replace:
```python
def _set_report_type(self, rt: ReportType) -> None:
    self._report_type = rt
    self._before_btn.setStyleSheet(_SEG_L_ON if rt == ReportType.BEFORE else _SEG_L_OFF)
    self._after_btn.setStyleSheet(_SEG_R_ON if rt == ReportType.AFTER else _SEG_R_OFF)
```

With:
```python
def _set_report_type(self, rt: ReportType) -> None:
    self._report_type = rt
    seg = build_seg_styles(self._theme)
    self._before_btn.setStyleSheet(seg["L_ON"] if rt == ReportType.BEFORE else seg["L_OFF"])
    self._after_btn.setStyleSheet(seg["R_ON"] if rt == ReportType.AFTER else seg["R_OFF"])
```

- [ ] **Step 7: Add `apply_theme()` method**

Add as a public method:

```python
def apply_theme(self, theme: str) -> None:
    """Re-apply all inline styles for the given theme and regenerate dynamic rows."""
    self._theme = theme
    c = get_colors(theme)
    field_lbl_style = (
        f"font-size: 10px; font-weight: 700; color: {c['text_muted']};"
        f" letter-spacing: 0.05em;"
    )
    self._title_lbl.setStyleSheet(
        f"font-size: 20px; font-weight: 600; color: {c['text_primary']};"
    )
    self._sub_lbl.setStyleSheet(
        f"font-size: 13px; color: {c['text_muted']}; margin-bottom: 4px;"
    )
    self._form_card.setStyleSheet(
        f"QFrame {{ background: {c['bg_surface']}; border: none; border-radius: 8px; }}"
    )
    self._cust_lbl.setStyleSheet(field_lbl_style)
    self._job_lbl.setStyleSheet(field_lbl_style)
    self._dev_lbl.setStyleSheet(field_lbl_style)
    self._type_lbl.setStyleSheet(field_lbl_style)
    self._form_sep.setStyleSheet(
        f"background: {c['border_subtle']}; border: none; max-height: 1px;"
    )
    # Report type buttons (preserve current selection)
    self._set_report_type(self._report_type)
    # Start Testing button
    self._start_btn.setStyleSheet(
        f"QPushButton {{ background: {c['accent']}; color: #ffffff; border: none;"
        f" border-radius: 6px; padding: 5px 14px; font-size: 13px; font-weight: 600; }}"
        f"QPushButton:hover {{ background: {c['accent_hover']}; }}"
        f"QPushButton:pressed {{ background: {c['accent_hover']}; }}"
        f"QPushButton:disabled {{ background: {c['accent']}; color: #ffffff; opacity: 0.4; }}"
    )
    # Recent Jobs panel
    self._recent_panel.setStyleSheet(
        f"QFrame {{ background: {c['bg_surface']}; border: none; border-radius: 8px; }}"
    )
    self._recent_title_lbl.setStyleSheet(
        f"font-size: 11px; font-weight: 600; color: {c['text_secondary']}; background: transparent;"
    )
    self._recent_toggle_lbl.setStyleSheet(
        f"font-size: 10px; color: {c['accent']}; background: transparent;"
    )
    # Regenerate recent rows with updated theme colors
    self.reload_recent_jobs()
```

- [ ] **Step 8: Commit**

```bash
git add src/ui/pages/job_setup_page.py
git commit -m "feat: add apply_theme() to JobSetupPage; remove _SEG_* constants; use build_seg_styles()"
```

---

## Task 7: Theme SettingsDialog

**Files:**
- Modify: `src/ui/widgets/settings_dialog.py`

**Context:** `SettingsDialog` gains a `window=None` param for live preview. `_select_theme()` calls `window.set_theme()` immediately. `reject()` is overridden to revert the preview when dismissed via Cancel button or X button. All `_SEG_*` module constants are removed; `apply_theme()` handles button styles.

- [ ] **Step 1: Replace imports and remove `_SEG_*` module constants**

Remove lines 20–59 (all six `_SEG_*` string constant definitions).

Add to imports:
```python
from src.ui.stylesheet import build_seg_styles, get_colors
```

- [ ] **Step 2: Update `__init__` signature**

Current line 72:
```python
def __init__(self, settings: Settings, theme: str = "dark", parent: QWidget | None = None) -> None:
```

Replace with:
```python
def __init__(
    self,
    settings: Settings,
    theme: str = "dark",
    window=None,
    parent: QWidget | None = None,
) -> None:
```

At the start of `__init__` body (after `super().__init__(parent)`), add:
```python
self._original_theme = theme
self._window = window
```

The existing `self._selected_theme: str = theme` line remains as-is.

- [ ] **Step 3: Update docstring usage example**

Replace the class docstring usage example:
```python
"""Modal dialog for report output settings.

    Usage:
        dlg = SettingsDialog(copy(window.settings), theme=window.theme, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            window.settings = dlg.result_settings()
            window.set_theme(dlg.result_theme())
    """
```

With:
```python
"""Modal dialog for report output settings.

    Usage:
        dlg = SettingsDialog(
            copy(window.settings), theme=window.theme, window=window, parent=self
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_settings = dlg.result_settings()
            window.settings = new_settings
            save_prefs(
                theme=window.theme,
                output_format=new_settings.output_format,
                save_path=new_settings.save_path,
            )
    """
```

- [ ] **Step 4: Remove hardcoded styles from `__init__` body**

In `__init__`, remove these inline `setStyleSheet` calls (they'll be set by `apply_theme()`):
- `cancel_btn.setStyleSheet(...)` — remove (7 lines)
- `save_btn.setStyleSheet(...)` — remove (7 lines)

Store refs:
- `self._cancel_btn = cancel_btn`
- `self._save_btn = save_btn`

Call `apply_theme(theme)` at the very end of `__init__` (after the button row layout).

- [ ] **Step 5: Update `_select_theme()` for live preview**

Replace:
```python
def _select_theme(self, theme: str) -> None:
    self._selected_theme = theme
    self._btn_dark.setStyleSheet(_SEG_L_ON if theme == "dark" else _SEG_L_OFF)
    self._btn_light.setStyleSheet(_SEG_R_ON if theme == "light" else _SEG_R_OFF)
```

With:
```python
def _select_theme(self, theme: str) -> None:
    self._selected_theme = theme
    seg = build_seg_styles(theme)
    self._btn_dark.setStyleSheet(seg["L_ON"] if theme == "dark" else seg["L_OFF"])
    self._btn_light.setStyleSheet(seg["R_ON"] if theme == "light" else seg["R_OFF"])
    if self._window is not None:
        self._window.set_theme(theme)  # live preview
```

Note: `build_seg_styles(theme)` here uses the newly-selected theme for the button highlight. The background app also switches via `window.set_theme(theme)`. This is correct — the selected button shows the accent of the NEW theme.

- [ ] **Step 6: Update `_select_format()` to use `build_seg_styles()`**

Replace:
```python
def _select_format(self, fmt: str) -> None:
    self._settings.output_format = fmt
    self._btn_html_pdf.setStyleSheet(_SEG_L_ON  if fmt == "html_pdf"  else _SEG_L_OFF)
    self._btn_html_only.setStyleSheet(_SEG_M_ON if fmt == "html_only" else _SEG_M_OFF)
    self._btn_pdf_only.setStyleSheet(_SEG_R_ON  if fmt == "pdf_only"  else _SEG_R_OFF)
```

With:
```python
def _select_format(self, fmt: str) -> None:
    self._settings.output_format = fmt
    seg = build_seg_styles(self._selected_theme)
    self._btn_html_pdf.setStyleSheet(seg["L_ON"]  if fmt == "html_pdf"  else seg["L_OFF"])
    self._btn_html_only.setStyleSheet(seg["M_ON"] if fmt == "html_only" else seg["M_OFF"])
    self._btn_pdf_only.setStyleSheet(seg["R_ON"]  if fmt == "pdf_only"  else seg["R_OFF"])
```

**Known limitation (out-of-scope):** When the user clicks [Dark] or [Light] in the open dialog, `window.set_theme()` re-themes the entire app and the dialog's QSS-driven widgets (inputs, etc.) update correctly. However, `window.set_theme()` does **not** call `dlg.apply_theme()` — so the Cancel and Save button backgrounds in the dialog keep the original-theme colors while the rest of the app switches. This is a cosmetic gap that is acceptable for this phase. The dialog closes immediately after any action so the mismatch is brief.

- [ ] **Step 7: Override `reject()` for Cancel revert (covers X button too)**

Add this method to the class:

```python
def reject(self) -> None:
    """Revert live preview theme before dismissing (Cancel or X button)."""
    if self._window is not None and self._selected_theme != self._original_theme:
        self._window.set_theme(self._original_theme)
    super().reject()
```

- [ ] **Step 8: Add `apply_theme()` method**

Add to `# ── Helpers` section:

```python
def apply_theme(self, theme: str) -> None:
    """Re-apply button styles. Called at init and can be called on theme change."""
    c = get_colors(theme)
    seg = build_seg_styles(theme)
    # Appearance (Dark/Light) buttons — preserve current selection
    self._btn_dark.setStyleSheet(
        seg["L_ON"] if self._selected_theme == "dark" else seg["L_OFF"]
    )
    self._btn_light.setStyleSheet(
        seg["R_ON"] if self._selected_theme == "light" else seg["R_OFF"]
    )
    # Output Format buttons — preserve current selection
    fmt = self._settings.output_format
    self._btn_html_pdf.setStyleSheet(seg["L_ON"]  if fmt == "html_pdf"  else seg["L_OFF"])
    self._btn_html_only.setStyleSheet(seg["M_ON"] if fmt == "html_only" else seg["M_OFF"])
    self._btn_pdf_only.setStyleSheet(seg["R_ON"]  if fmt == "pdf_only"  else seg["R_OFF"])
    # Save / Cancel buttons
    self._cancel_btn.setStyleSheet(
        f"QPushButton {{ background: {c['danger_bg']}; color: {c['danger_text']}; border: none;"
        f" border-radius: 6px; padding: 5px 14px; font-size: 12px; font-weight: 500;"
        f" min-height: 30px; }}"
        f"QPushButton:hover {{ background: {c['accent_hover']}; color: #ffffff; }}"
    )
    self._save_btn.setStyleSheet(
        f"QPushButton {{ background: {c['accent']}; color: #ffffff; border: none;"
        f" border-radius: 6px; padding: 5px 14px; font-size: 12px; font-weight: 600;"
        f" min-height: 30px; }}"
        f"QPushButton:hover {{ background: {c['accent_hover']}; }}"
    )
```

`danger_bg` and `danger_text` are included in both `DARK` and `LIGHT` dicts in Task 1. Values:
- `DARK`: `danger_bg="#7f1d1d"`, `danger_text="#fca5a5"` — matches existing dark cancel btn colors
- `LIGHT`: `danger_bg="#fee2e2"`, `danger_text="#dc2626"`

- [ ] **Step 9: Commit**

```bash
git add src/ui/widgets/settings_dialog.py
git commit -m "feat: add apply_theme() to SettingsDialog; live preview; override reject() for Cancel revert; remove _SEG_* constants"
```

---

## Task 8: Theme TestDashboardPage

**Files:**
- Modify: `src/ui/pages/test_dashboard_page.py`

**Context:** `TestDashboardPage` is the coordinator. It stores the scroll area and scroll content as instance attrs (they have hardcoded `#09090b` backgrounds). `apply_theme()` updates those + status bar, then propagates to header, banner, and all sections. `_on_settings_clicked` is updated to pass `window=self._window`.

- [ ] **Step 1: Add import**

Add to imports:
```python
from src.ui.stylesheet import get_colors
```

- [ ] **Step 2: Update `__init__` to accept theme**

Current line 129:
```python
def __init__(self, window, parent=None) -> None:
    super().__init__(parent)
    self._window = window
```

Replace with:
```python
def __init__(self, window, theme: str = "dark", parent=None) -> None:
    super().__init__(parent)
    self._window = window
    self._theme = theme
```

- [ ] **Step 3: Pass theme when creating HeaderBar, DeviceBanner, CategorySection**

In `_build_ui()`, update construction:

Line 160: `self._header = HeaderBar(self)` → `self._header = HeaderBar(theme=self._theme, parent=self)`

Line 167: `self._banner = DeviceBanner(self)` → `self._banner = DeviceBanner(theme=self._theme, parent=self)`

Lines 182–189 (CategorySection construction):
```python
section = CategorySection(
    title=title,
    tests=tests,
    col_count=col_count,
    short_names=short_names,
    theme=self._theme,
)
```

- [ ] **Step 4: Store scroll area and content refs, remove hardcoded backgrounds**

In `_build_ui()`, change:
```python
scroll = QScrollArea()
```
to:
```python
self._scroll = QScrollArea()
scroll = self._scroll  # local alias for rest of _build_ui
```

Change:
```python
scroll_content = QWidget()
scroll_content.setStyleSheet("background: #09090b;")
```
to:
```python
self._scroll_content = QWidget()
scroll_content = self._scroll_content  # local alias
```

Remove the `.setStyleSheet("background: #09090b;")` call on `scroll_content`.

Also remove or make dynamic the scroll area style. Find:
```python
scroll.setStyleSheet("QScrollArea { border: none; background: #09090b; }")
```
Remove this line (will be set by `apply_theme()`).

- [ ] **Step 5: Add `apply_theme()` method**

Add as a public method:

```python
def apply_theme(self, theme: str) -> None:
    """Re-apply all inline styles and propagate to child widgets."""
    self._theme = theme
    c = get_colors(theme)
    self._scroll.setStyleSheet(
        f"QScrollArea {{ border: none; background: {c['bg_base']}; }}"
    )
    self._scroll_content.setStyleSheet(f"background: {c['bg_base']};")
    self._status_bar.setStyleSheet(
        f"color: {c['text_muted']}; font-size: 11px; padding: 4px 16px;"
        f" background: {c['bg_base']}; border-top: 1px solid {c['border_subtle']};"
    )
    self._header.apply_theme(theme)
    self._banner.apply_theme(theme)
    for section in self._category_sections:
        section.apply_theme(theme)
```

- [ ] **Step 6: Update `_on_settings_clicked` to pass `window=self._window`**

Find the current `_on_settings_clicked` (lines 545–566). Update the `SettingsDialog` construction:

```python
dlg = SettingsDialog(
    copy.copy(self._window.settings),
    theme=self._window.theme,
    window=self._window,   # ← new: enables live preview
    parent=self,
)
if getattr(dlg, "exec")() == QDialog.DialogCode.Accepted:
    new_settings = dlg.result_settings()
    self._window.settings = new_settings
    # Theme already applied live; just persist all prefs
    save_prefs(
        theme=self._window.theme,
        output_format=new_settings.output_format,
        save_path=new_settings.save_path,
    )
```

Note: `self._window.set_theme()` is no longer called here — it was called already by `_select_theme()` inside the dialog during live preview.

- [ ] **Step 7: Commit**

```bash
git add src/ui/pages/test_dashboard_page.py
git commit -m "feat: add apply_theme() to TestDashboardPage; propagate to header/banner/sections; live-preview settings"
```

---

## Task 9: Wire app_window.py — pass theme to pages and propagate in set_theme()

**Files:**
- Modify: `src/ui/app_window.py`

**Context:** This is the final wiring task. `TouchstoneWindow` passes `theme=self._theme` to both page constructors and updates `set_theme()` to call `apply_theme()` on both pages after applying the QSS.

- [ ] **Step 1: Pass `theme` to page constructors**

Current lines 44–45:
```python
self._setup_page = JobSetupPage(self)
self._dashboard = TestDashboardPage(self, self)
```

Replace with:
```python
self._setup_page = JobSetupPage(theme=self._theme, parent=self)
self._dashboard = TestDashboardPage(self, theme=self._theme, parent=self)
```

Note: `JobSetupPage.__init__` signature is `(self, theme="dark", parent=None)`. `TestDashboardPage.__init__` signature is `(self, window, theme="dark", parent=None)`.

- [ ] **Step 2: Update `set_theme()` to propagate to pages**

Current `set_theme()` (lines 108–112):
```python
def set_theme(self, theme: str) -> None:
    """Apply theme visually. Does NOT persist to disk — caller's responsibility."""
    self._theme = theme
    self._apply_theme(theme)
    refresh_style(self)
```

Replace with:
```python
def set_theme(self, theme: str) -> None:
    """Apply theme visually. Does NOT persist to disk — caller's responsibility."""
    self._theme = theme
    self._apply_theme(theme)
    refresh_style(self)
    self._setup_page.apply_theme(theme)
    self._dashboard.apply_theme(theme)
```

- [ ] **Step 3: Verify dark mode still works**

```bash
uv run touchstone --dev-manual
```

Expected: App opens in dark mode. All cards, header, banner, sections look identical to before this feature branch. No visual regressions.

- [ ] **Step 4: Verify light mode persists and applies fully**

1. Open Settings (⚙ gear icon)
2. Click `[Light]` — Expected: **entire app goes light immediately** (live preview): white/cream backgrounds, dark text, job setup page changes, category sections change, all cards change
3. Click Save
4. Quit app (`Cmd+Q` or close window)
5. Relaunch: `uv run touchstone --dev-manual`
6. Expected: App opens in light mode — all areas themed correctly

- [ ] **Step 5: Verify cancel reverts (including X button)**

1. Open Settings
2. Click `[Light]` — app goes light
3. Click `[Dark]` — app goes dark
4. Click `[Light]` again
5. Click **Cancel** (or press Escape, or click the X button)
6. Expected: App reverts to dark mode. Nothing persisted.

- [ ] **Step 6: Verify output_format and save_path still persist**

1. Open Settings → select "HTML only" → type a path → click Save
2. Quit and relaunch
3. Open Settings again
4. Expected: "HTML only" is selected, path field shows the typed path

- [ ] **Step 7: Commit**

```bash
git add src/ui/app_window.py
git commit -m "feat: wire theme propagation in TouchstoneWindow; pass theme to pages; set_theme() now calls apply_theme() on all pages"
```

---

## Completion Checklist

- [ ] `stylesheet.py` has `DARK`, `LIGHT` dicts, `get_colors()`, `build_seg_styles()`
- [ ] `DashboardCard.apply_theme()` exists; no hardcoded dark colors in `_build_ui()`
- [ ] `CategorySection.apply_theme()` propagates to all cards
- [ ] `HeaderBar.apply_theme()` updates all buttons; `_SEG_*` module constants removed
- [ ] `DeviceBanner.apply_theme()` updates frame + fields + report button; `_SpecField.apply_theme()` respects `_has_value`
- [ ] `JobSetupPage.apply_theme()` updates all labels + buttons + recent rows; `_SEG_*` removed
- [ ] `SettingsDialog` has `window` param, `reject()` override reverts preview, `apply_theme()` runs at init
- [ ] `TestDashboardPage.apply_theme()` propagates to header, banner, sections; `_on_settings_clicked` passes `window=self._window`
- [ ] `TouchstoneWindow` passes `theme=self._theme` to page constructors; `set_theme()` calls `apply_theme()` on both pages
- [ ] Light mode looks correct: warm-grey backgrounds, dark text throughout entire UI
- [ ] Dark mode still looks correct (no regressions)
- [ ] Live preview works: clicking `[Light]` in open dialog immediately themes entire app
- [ ] Cancel (and X button) reverts live preview
- [ ] Theme persists across restarts
