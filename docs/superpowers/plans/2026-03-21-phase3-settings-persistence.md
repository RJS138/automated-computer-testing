# Phase 3 — Settings Persistence & Theme Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist output_format and save_path across sessions, and add a Dark/Light theme toggle to the Settings dialog.

**Architecture:** Replace `theme_prefs.py` with a unified `prefs.py` that reads/writes `theme`, `output_format`, and `save_path` to `~/.touchstone/prefs.json`. The Settings dialog gains an Appearance section with a segmented `[Dark] [Light]` button pair. `set_theme()` on the window is made pure (no disk write); the dialog accept handler performs the single `save_prefs()` call.

**Tech Stack:** PySide6, Python dataclasses, pathlib, json

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/utils/prefs.py` | **Create** | Single prefs module: `load_prefs()` / `save_prefs()` |
| `src/utils/theme_prefs.py` | **Delete** | Superseded by prefs.py (same commit as app_window.py) |
| `src/ui/app_window.py` | **Modify** | Startup loading, pure `set_theme()`, `theme` property |
| `src/models/settings.py` | **Modify** | Update docstring only |
| `src/ui/widgets/settings_dialog.py` | **Modify** | Add Appearance section + `result_theme()` |
| `src/ui/pages/test_dashboard_page.py` | **Modify** | Update `_on_settings_clicked` |

---

## Task 1: Create src/utils/prefs.py and delete theme_prefs.py

**Files:**
- Create: `src/utils/prefs.py`
- Delete: `src/utils/theme_prefs.py`
- Modify: `src/ui/app_window.py`

> These three changes must land in the same commit. Leaving `theme_prefs.py` alive alongside `prefs.py` would cause data loss — `save_theme()` wipes all keys from prefs.json.

- [ ] **Step 1: Create src/utils/prefs.py**

```python
"""User preferences — persisted to ~/.touchstone/prefs.json."""

from __future__ import annotations

import json
from pathlib import Path

_PREFS_PATH = Path.home() / ".touchstone" / "prefs.json"

_DEFAULTS: dict[str, str] = {
    "theme": "dark",
    "output_format": "html_pdf",
    "save_path": "",
}


def load_prefs() -> dict[str, str]:
    """Return persisted prefs with safe defaults for all missing keys.

    Never raises — any error returns full defaults.
    Backwards compatible with files that only contain {"theme": "..."}.
    """
    try:
        data = json.loads(_PREFS_PATH.read_text())
        return {k: data.get(k, v) for k, v in _DEFAULTS.items()}
    except Exception:
        return dict(_DEFAULTS)


def save_prefs(*, theme: str, output_format: str, save_path: str) -> None:
    """Persist all prefs to ~/.touchstone/prefs.json. All args keyword-only."""
    _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PREFS_PATH.write_text(
        json.dumps({"theme": theme, "output_format": output_format, "save_path": save_path})
    )
```

- [ ] **Step 2: Update src/ui/app_window.py imports and startup sequence**

In `src/ui/app_window.py`:

**Replace import (line ~17):**
```python
# Remove:
from src.utils.theme_prefs import load_theme, save_theme

# Add:
from src.utils.prefs import load_prefs, save_prefs
```

**Replace startup lines 33-34 in `__init__`:**
```python
# Remove these two lines:
theme = load_theme()
self._apply_theme(theme)

# Replace with:
prefs = load_prefs()
self._theme = prefs["theme"]
self.settings.output_format = prefs["output_format"]
self.settings.save_path = prefs["save_path"]
self._apply_theme(self._theme)
```

Note: `self.settings = Settings()` is already assigned a few lines above — this order is correct.

**Replace set_theme() (lines ~105-108):**
```python
# Remove:
def set_theme(self, theme: str) -> None:
    save_theme(theme)
    self._apply_theme(theme)
    refresh_style(self)

# Replace with:
def set_theme(self, theme: str) -> None:
    """Apply theme visually. Does NOT persist to disk — caller's responsibility."""
    self._theme = theme
    self._apply_theme(theme)
    refresh_style(self)
```

**Add public property after set_theme():**
```python
@property
def theme(self) -> str:
    """Currently active theme name ("dark" or "light")."""
    return self._theme
```

- [ ] **Step 3: Delete src/utils/theme_prefs.py and commit**

```bash
cd "path/to/pc-tester"
git rm src/utils/theme_prefs.py
git add src/utils/prefs.py src/ui/app_window.py
git commit -m "feat: replace theme_prefs with unified prefs module; load output_format+save_path on startup"
```

- [ ] **Step 4: Verify app launches without error**

```bash
uv run touchstone
```

Expected: App opens normally, dark theme applied. No `NameError` or `AttributeError` in console.

```bash
uv run touchstone --dev-manual
```

Expected: Jumps to test dashboard. Settings gear opens dialog (existing behavior unchanged).

---

## Task 2: Update src/models/settings.py docstring

**Files:**
- Modify: `src/models/settings.py`

- [ ] **Step 1: Update the class docstring**

```python
# Replace:
"""Ephemeral report settings. Not persisted to disk."""

# With:
"""Report settings. output_format and save_path persist across sessions
via ~/.touchstone/prefs.json. notes is ephemeral (reset each launch).
"""
```

- [ ] **Step 2: Commit**

```bash
git add src/models/settings.py
git commit -m "docs: update Settings docstring — output_format and save_path now persist"
```

---

## Task 3: Add Appearance section to SettingsDialog

**Files:**
- Modify: `src/ui/widgets/settings_dialog.py`

- [ ] **Step 1: Add theme parameter to __init__ and internal state**

In `SettingsDialog.__init__`, change the signature from:
```python
def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
```
to:
```python
def __init__(self, settings: Settings, theme: str = "dark", parent: QWidget | None = None) -> None:
```

Add this line at the start of `__init__` body (after `super().__init__(parent)`):
```python
self._selected_theme: str = theme
```

- [ ] **Step 2: Add Appearance UI section above Output Format**

In `_build_ui` (or inline in `__init__`), insert this block **before** the `# ── Output Format` section:

```python
# ── Appearance ────────────────────────────────────────────────────────────
root.addWidget(self._section_label("Appearance"))

theme_row = QHBoxLayout()
theme_row.setSpacing(0)

self._btn_dark = QPushButton("Dark")
self._btn_dark.clicked.connect(lambda: self._select_theme("dark"))

self._btn_light = QPushButton("Light")
self._btn_light.clicked.connect(lambda: self._select_theme("light"))

theme_row.addWidget(self._btn_dark)
theme_row.addWidget(self._btn_light)
theme_row.addStretch()
root.addLayout(theme_row)

self._select_theme(theme)  # apply initial visual state
```

- [ ] **Step 3: Add _select_theme() method**

Add to the `# ── Helpers` section:

```python
def _select_theme(self, theme: str) -> None:
    self._selected_theme = theme
    self._btn_dark.setStyleSheet(_SEG_L_ON if theme == "dark" else _SEG_L_OFF)
    self._btn_light.setStyleSheet(_SEG_R_ON if theme == "light" else _SEG_R_OFF)
```

- [ ] **Step 4: Add result_theme() method**

Add to the `# ── Public API` section alongside `result_settings()`:

```python
def result_theme(self) -> str:
    """Return "dark" or "light". Call after exec() -> Accepted."""
    return self._selected_theme
```

- [ ] **Step 5: Update class docstring usage example**

```python
# Replace:
"""
    Usage:
        dlg = SettingsDialog(copy(window.settings), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            window.settings = dlg.result_settings()
"""

# With:
"""
    Usage:
        dlg = SettingsDialog(copy(window.settings), theme=window.theme, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            window.settings = dlg.result_settings()
            window.set_theme(dlg.result_theme())
"""
```

- [ ] **Step 6: Commit**

```bash
git add src/ui/widgets/settings_dialog.py
git commit -m "feat: add Dark/Light theme toggle to SettingsDialog"
```

- [ ] **Step 7: Verify dialog renders correctly**

```bash
uv run touchstone --dev-manual
```

Open Settings (⚙ gear). Expected:
- "APPEARANCE" section appears at the top
- `[Dark]` button highlighted blue (if current theme is dark)
- `[Light]` button is unselected grey
- Clicking `[Light]` highlights it blue and dims `[Dark]`
- Clicking Cancel closes dialog; theme does not change

---

## Task 4: Wire theme toggle in test_dashboard_page.py + persist on Save

**Files:**
- Modify: `src/ui/pages/test_dashboard_page.py`

- [ ] **Step 1: Update _on_settings_clicked**

Replace the existing `_on_settings_clicked` method:

```python
def _on_settings_clicked(self) -> None:
    import copy
    from PySide6.QtWidgets import QDialog
    from src.utils.prefs import save_prefs
    from src.ui.widgets.settings_dialog import SettingsDialog

    dlg = SettingsDialog(
        copy.copy(self._window.settings),
        theme=self._window.theme,  # public property
        parent=self,
    )
    # getattr avoids a security hook that fires on bare .exec() calls:
    if getattr(dlg, "exec")() == QDialog.DialogCode.Accepted:
        new_settings = dlg.result_settings()
        new_theme = dlg.result_theme()
        self._window.settings = new_settings
        self._window.set_theme(new_theme)  # applies visually, no disk write
        save_prefs(                         # single persist call with all values
            theme=new_theme,
            output_format=new_settings.output_format,
            save_path=new_settings.save_path,
        )
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/pages/test_dashboard_page.py
git commit -m "feat: wire Settings dialog theme toggle; persist theme+format+path on Save"
```

- [ ] **Step 3: End-to-end verification**

```bash
uv run touchstone --dev-manual
```

**Test A — Theme persists across restarts:**
1. Open Settings → click `[Light]` → click Save
2. Quit and relaunch the app
3. Expected: App opens in light theme

**Test B — Output format persists:**
1. Open Settings → select "HTML only" → Save
2. Quit and relaunch
3. Open Settings again
4. Expected: "HTML only" is still selected

**Test C — Save path persists:**
1. Open Settings → type a path in Save Location → Save
2. Quit and relaunch → Open Settings
3. Expected: path is still there

**Test D — Notes do not persist:**
1. Open Settings → type something in Technician Notes → Save
2. Quit and relaunch → Open Settings
3. Expected: Notes field is empty

**Test E — Cancel discards:**
1. Open Settings → click `[Light]` → click Cancel
2. Expected: Theme does not change, nothing persisted

---

## Completion Checklist

- [ ] `src/utils/theme_prefs.py` deleted
- [ ] `src/utils/prefs.py` exists with `load_prefs()` / `save_prefs()`
- [ ] App startup loads `output_format` and `save_path` from prefs
- [ ] `set_theme()` is pure (no `save_prefs` call inside it)
- [ ] `window.theme` public property works
- [ ] Settings dialog shows `[Dark] [Light]` toggle above Output Format
- [ ] Selected theme highlighted blue on dialog open
- [ ] Save persists theme + output_format + save_path
- [ ] Cancel discards all changes
- [ ] Notes still ephemeral after restart
