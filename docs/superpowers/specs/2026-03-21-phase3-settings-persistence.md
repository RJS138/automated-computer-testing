# Phase 3 — Settings Persistence & Theme Toggle

**Date:** 2026-03-21
**Status:** Draft

## Goal

Persist user preferences (theme, output format, save path) across sessions, and expose a theme toggle in the Settings dialog. Notes remain ephemeral (reset each launch).

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Persistence module | Single `prefs.py` replacing `theme_prefs.py` | One file, one JSON, avoids fragmentation |
| What persists | `theme`, `output_format`, `save_path` | Job-specific notes stay ephemeral |
| Theme toggle UI | `[Dark] [Light]` segmented button in Settings dialog | Consistent with existing segmented button pattern |
| Persistence trigger | On Settings dialog Save — caller saves all prefs | Keeps set_theme() pure; no hidden side effects |
| Current theme source | `window.theme` public property | Cleaner cross-class access; avoids private attribute leak |
| save_prefs signature | Keyword-only arguments | Forward-compatible; avoids brittle positional call sites |
| Light-mode button variants | Deferred | Hardcoded dark colors in seg constants; acceptable for Phase 3 |
| Migration atomicity | prefs.py creation + app_window.py update in one commit | Prevents data-loss window where old save_theme() wipes new keys |

---

## 1. src/utils/prefs.py (replaces src/utils/theme_prefs.py)

Single module managing ~/.touchstone/prefs.json.

### Functions

```python
def load_prefs() -> dict:
    """Return persisted prefs with safe defaults for missing keys.

    Keys: theme ("dark"|"light"), output_format (str), save_path (str).
    Backwards compatible: {"theme": "..."}-only files from the old
    theme_prefs.py format are handled — missing keys fall back to defaults.

    Must never raise. Catch all exceptions and return full defaults,
    identical to load_theme()'s existing behavior.
    """

def save_prefs(*, theme: str, output_format: str, save_path: str) -> None:
    """Persist all prefs to ~/.touchstone/prefs.json. All args keyword-only."""
```

### Defaults: `theme="dark"`, `output_format="html_pdf"`, `save_path=""`

---

## 2. src/ui/app_window.py

### Complete set_theme() replacement

Current code (lines 105-108):
```python
def set_theme(self, theme: str) -> None:
    save_theme(theme)        # <-- REMOVE this call
    self._apply_theme(theme)
    refresh_style(self)
```

New code:
```python
def set_theme(self, theme: str) -> None:
    """Apply theme visually. Does NOT persist to disk — caller's responsibility."""
    self._theme = theme
    self._apply_theme(theme)
    refresh_style(self)
```

`save_theme()` call is removed. Persisting is the dialog accept handler's responsibility.

### Public property (add to class)
```python
@property
def theme(self) -> str:
    """Currently active theme name ("dark" or "light")."""
    return self._theme
```

### Startup sequence — replaces existing lines 33-34

Current lines 33-34:
```python
theme = load_theme()
self._apply_theme(theme)
```

Replace entirely with:
```python
prefs = load_prefs()
self._theme = prefs["theme"]
self.settings.output_format = prefs["output_format"]
self.settings.save_path = prefs["save_path"]
self._apply_theme(self._theme)
```

Note: `self.settings = Settings()` is already assigned at line 30 — this order is preserved. `self._theme` is set here and does not exist before this point; `set_theme()` must only be called after `__init__` completes (guaranteed by the dialog flow).

### Import change
Remove: `from src.utils.theme_prefs import load_theme, save_theme`
Add: `from src.utils.prefs import load_prefs, save_prefs`

### Migration note
`theme_prefs.py` and `app_window.py` must be updated in the same commit. Leaving `save_theme()` from the old module alive alongside the new `save_prefs()` would cause data loss (old code wipes all prefs keys).

---

## 3. src/models/settings.py

Update docstring to reflect that `output_format` and `save_path` are now persisted:

```python
@dataclass
class Settings:
    """Report settings. output_format and save_path persist across sessions.
    notes is ephemeral (reset each launch).
    """
```

---

## 4. src/ui/widgets/settings_dialog.py

### New parameter
`SettingsDialog.__init__(self, settings: Settings, theme: str = "dark", parent=None)`

Internally: `self._selected_theme: str = theme`

### New UI section — Appearance (inserted above Output Format)

```
APPEARANCE
[Dark] [Light]
```

Two-button segmented pair — `_SEG_L_ON/OFF` (Dark, left) and `_SEG_R_ON/OFF` (Light, right). No middle segment needed.

```python
def _select_theme(self, theme: str) -> None:
    self._selected_theme = theme
    self._btn_dark.setStyleSheet(_SEG_L_ON if theme == "dark" else _SEG_L_OFF)
    self._btn_light.setStyleSheet(_SEG_R_ON if theme == "light" else _SEG_R_OFF)
```

Called on button click and once during `__init__` to render initial state.

### Cancel behaviour
Cancel discards all dialog state including `_selected_theme`. `result_theme()` is only ever called inside the `Accepted` branch — nothing is persisted on Cancel.

### New method
```python
def result_theme(self) -> str:
    """Return "dark" or "light". Call after exec() -> Accepted."""
    return self._selected_theme
```

`result_settings()` unchanged — it still returns `notes` as entered. `save_prefs()` intentionally omits `notes`; only `output_format` and `save_path` are persisted.

---

## 5. src/ui/pages/test_dashboard_page.py

### _on_settings_clicked update

```python
def _on_settings_clicked(self) -> None:
    import copy
    from PySide6.QtWidgets import QDialog
    from src.utils.prefs import save_prefs
    from src.ui.widgets.settings_dialog import SettingsDialog

    dlg = SettingsDialog(
        copy.copy(self._window.settings),
        theme=self._window.theme,   # public property — no private access
        parent=self,
    )
    # getattr avoids a security hook that fires on bare .exec() calls:
    if getattr(dlg, "exec")() == QDialog.DialogCode.Accepted:
        new_settings = dlg.result_settings()
        new_theme = dlg.result_theme()
        self._window.settings = new_settings
        self._window.set_theme(new_theme)   # applies visually, no disk write
        save_prefs(                          # single persist call
            theme=new_theme,
            output_format=new_settings.output_format,
            save_path=new_settings.save_path,
        )
```

---

## 6. File Changes Summary

| File | Action |
|------|--------|
| `src/utils/prefs.py` | New — replaces theme_prefs.py |
| `src/utils/theme_prefs.py` | Delete (same commit as prefs.py + app_window.py changes) |
| `src/ui/app_window.py` | Replace startup lines 33-34, rewrite set_theme(), add theme property, update imports |
| `src/models/settings.py` | Update docstring |
| `src/ui/widgets/settings_dialog.py` | Add theme param + Appearance section + _select_theme() + result_theme(); update class docstring usage example |
| `src/ui/pages/test_dashboard_page.py` | Update _on_settings_clicked |

---

## Out of Scope

- Notes persistence (intentionally ephemeral)
- Light-mode variants for segmented button constants (deferred)
- Theme toggle outside of Settings dialog
- Any other prefs (window size, etc.)
