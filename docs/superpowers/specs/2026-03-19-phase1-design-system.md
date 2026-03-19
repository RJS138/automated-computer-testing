# Phase 1 — Design System & Theme Spec

**Date:** 2026-03-19
**Status:** Approved

## Goal

Replace the current monolithic `QSS_DARK` with a new two-theme design system. Every visual token (colour, spacing, typography) is defined once. Dark mode is the default; a warm-grey light mode is fully supported and switchable at runtime. The existing widget property system (`class="primary"`, `status="pass"`, etc.) is preserved — this is a visual replacement, not a structural one.

---

## Design Language

**Style:** Data Dashboard (Railway / Grafana aesthetic)
- Dense but readable — data values in monospace, UI chrome in system sans-serif
- Subtle borders, near-zero decoration, colour used only for meaning
- Every status (pass / warn / fail / running) has an unambiguous colour

**Light mode:** Warm grey (`#f5f4f1` base), not cool white — easier on the eyes under shop lighting

---

## 1. Color Tokens

Two complete token sets. The token names are the same in both; only values differ.

### Dark (default)

| Token | Value | Usage |
|-------|-------|-------|
| `bg-base` | `#09090b` | Window background |
| `bg-surface` | `#18181b` | Cards, panels, inputs |
| `bg-elevated` | `#27272a` | Hover fills, dropdown bg |
| `bg-hover` | `#3f3f46` | Pressed state |
| `border-subtle` | `#27272a` | Internal dividers |
| `border` | `#3f3f46` | Widget borders |
| `text-primary` | `#fafafa` | Body copy, values |
| `text-secondary` | `#a1a1aa` | Labels, secondary |
| `text-muted` | `#71717a` | Placeholders, captions |
| `accent` | `#3b82f6` | Primary action, focus ring |
| `accent-hover` | `#2563eb` | Primary button hover |
| `pass` | `#22c55e` | Pass status |
| `warn` | `#f59e0b` | Warning status |
| `fail` | `#ef4444` | Fail status |
| `running` | `#60a5fa` | In-progress status |

### Light

| Token | Value | Usage |
|-------|-------|-------|
| `bg-base` | `#f5f4f1` | Window background (warm grey) |
| `bg-surface` | `#fafaf9` | Cards, panels, inputs |
| `bg-elevated` | `#e7e5e4` | Hover fills |
| `bg-hover` | `#d6d3d1` | Pressed state |
| `border-subtle` | `#e7e5e4` | Internal dividers |
| `border` | `#d6d3d1` | Widget borders |
| `text-primary` | `#1c1917` | Body copy, values |
| `text-secondary` | `#78716c` | Labels, secondary |
| `text-muted` | `#a8a29e` | Placeholders, captions |
| `accent` | `#2563eb` | Primary action (slightly darker for contrast) |
| `accent-hover` | `#1d4ed8` | Primary button hover |
| `pass` | `#16a34a` | Pass status |
| `warn` | `#d97706` | Warning status |
| `fail` | `#dc2626` | Fail status |
| `running` | `#3b82f6` | In-progress status |

---

## 2. Typography

Two font roles:

- **UI font** — system sans-serif per platform (unchanged from current)
  - macOS: `Helvetica Neue, 13px`
  - Windows: `Segoe UI, 11px`
  - Linux: `DejaVu Sans, 11px`
- **Mono font** — `SF Mono, Consolas, Fira Code, monospace` — used for all data values (serial numbers, scores, temperatures, speeds)

### Scale

| Role | Size | Weight | Usage |
|------|------|--------|-------|
| `display` | 20px | 600 | Device name headline |
| `title` | 16px | 600 | Section / panel title |
| `body` | 13px | 400 | Standard body, field labels |
| `small` | 12px | 400 | Table rows, secondary text |
| `caption` | 11px | 500 | Field labels above inputs |
| `label` | 10px | 700 | Category headers (uppercase + letter-spacing 0.1em) |
| `mono-value` | 13px | 400 | Data values in mono font |
| `mono-badge` | 10px | 700 | Status badge text in mono font |

---

## 3. Component Specifications

### 3.1 Buttons

Four variants via `class` property. All buttons: `min-height: 30px`, `border-radius: 6px`, `padding: 5px 14px`, `font-size: 12px`, `font-weight: 500`.

| Class | Resting | Hover | Pressed |
|-------|---------|-------|---------|
| *(default)* | `bg-surface` fill, `border` outline, `text-secondary` | `bg-elevated`, `text-primary` | `bg-hover` |
| `primary` | `accent` fill, no border, white text | `accent-hover` fill | darken 8% |
| `ghost` | transparent, no border, `text-secondary` | `bg-elevated` fill | `bg-hover` fill |
| `danger` | transparent, no border, `fail` text | `#3f0f0f` fill | deeper red fill |

Icon-only buttons (`class="icon-btn"`): `32×32px` fixed, transparent at rest, `bg-elevated` + `border` on hover.

Disabled state for all: `opacity: 0.4`, `cursor: not-allowed` (no separate colour needed).

### 3.2 Status Badges

Used on test result rows. `font-family: mono`, `font-size: 10px`, `font-weight: 700`, `padding: 2px 8px`, `border-radius: 4px`.

| Class / value | Background | Text |
|---------------|------------|------|
| `pass` | `pass` at 15% opacity | `pass` |
| `warn` | `warn` at 15% opacity | `warn` |
| `fail` | `fail` at 15% opacity | `fail` |
| `running` | `running` at 15% opacity | `running` |
| `idle` / `not-run` | `bg-elevated` | `text-muted` |
| `skip` | `bg-elevated` | `text-muted` |

Qt QSS does not support `rgba()` mixing with runtime variables, so hardcoded hex approximations are used for the tinted backgrounds. Pre-computed values (status colour blended at 15% onto the surface background):

| Badge | Dark bg | Light bg |
|-------|---------|----------|
| pass | `#1a2e20` | `#d6f0dc` |
| warn | `#2e2210` | `#f5e6cc` |
| fail | `#2e1414` | `#f5d5d5` |
| running | `#162136` | `#d5e4f7` |

### 3.3 Test Card Border (existing `test-card` class)

Preserves the existing `QFrame[class="test-card"][status="..."]` selector. Update border colours to the new token values:

| Status | Border colour |
|--------|--------------|
| `waiting` | `border-subtle` |
| `running` | `running` |
| `pass` | `pass` |
| `warn` | `warn` |
| `fail` | `fail` |
| `error` | `fail` |
| `skip` | `text-muted` |

### 3.4 Inputs

`QLineEdit`, `QPlainTextEdit`, `QComboBox`: `background: bg-surface`, `border: 1px solid border`, `border-radius: 6px`, `padding: 6px 10px`, `font-size: 13px`, `color: text-primary`. Focus: `border-color: accent`.

`QComboBox` drop-down arrow: use `▾` via `subcontrol` or set `border: none` on the arrow button and style explicitly. Dropdown list background: `bg-elevated`.

### 3.5 Metric Cards

`QFrame[class="metric-card"]`: `background: bg-surface`, `border: 1px solid border-subtle`, `border-radius: 7px`. Internal layout via Python (not QSS). Value label: `font-size: 20px`, `font-weight: 600`, mono font. Progress bar inside: `height: 3px`, `background: bg-elevated`, fill colour from status token.

These are new widget-level cards — defined here for Phase 2 to implement. The QSS class is registered in Phase 1.

### 3.6 Data Table Rows

`QFrame[class="data-row"]`: no background, bottom border `border-subtle`. Key label: `text-secondary`, 12px. Value: `text-primary`, 12px, mono font.

These are also Phase 2 widgets. QSS class registered now.

### 3.7 Tabs

`QTabBar` replacement is done via a custom `QFrame` tab bar (not native `QTabBar`, which is hard to style cross-platform). Each tab is a `QPushButton[class="tab"]`:

| State | Style |
|-------|-------|
| Default | `ghost` button style, `text-muted` |
| Hover | `text-secondary` |
| Active (`checked="true"`) | `text-primary`, `accent` 2px bottom border |

The tab bar container is a `QFrame[class="tab-bar"]` with `border-bottom: 1px solid border-subtle`.

**Active tab border implementation note:** Fusion overrides partial `border-bottom` shorthand on `QPushButton`. Set all four sides explicitly to avoid Fusion painting unwanted borders:
```css
QPushButton[class="tab"][checked="true"] {
    border-top: none;
    border-left: none;
    border-right: none;
    border-bottom: 2px solid #3b82f6;  /* accent token */
    border-radius: 0;
}
```

### 3.8 Progress Bars

`QProgressBar`: `height: 4px`, `border: none`, `border-radius: 2px`, background `bg-elevated`. Chunk: `border-radius: 2px`, colour set per instance via `setProperty("status", "pass|warn|fail|running")`.

### 3.9 Separators

`QFrame[frameShape="4"]` (HLine): `background: border-subtle`, `height: 1px`, `border: none`.

### 3.10 Scroll Bars

Thin (6px wide), rounded. Track: `bg-elevated`. Handle: `bg-hover`. Hover handle: `text-muted`. No arrows.

---

## 4. Theme Architecture

### 4.1 Persistent Theme Storage

A new `src/utils/theme_prefs.py` module manages the single persisted preference (placed in `utils/` alongside `file_manager.py` — it is I/O logic, not a data model). Storage: `~/.touchstone/prefs.json`. Contains `{ "theme": "dark" | "light" }`. Defaults to `"dark"` if file absent or malformed.

`save_theme()` must call `Path.mkdir(parents=True, exist_ok=True)` before writing on first run.

```
src/utils/theme_prefs.py
  load_theme() -> str          # "dark" | "light"
  save_theme(theme: str)       # mkdir + write ~/.touchstone/prefs.json
```

### 4.2 QSS Strings

`src/ui/stylesheet.py` exports two constants and one function:

```python
QSS_DARK: str    # dark theme QSS
QSS_LIGHT: str   # light theme QSS
refresh_style(widget)  # unchanged
```

The two QSS strings are identical in structure; only the hardcoded hex values differ.

### 4.3 QPalette

`src/ui/app_window.py` has two palette builders:

```python
_dark_palette() -> QPalette   # already exists, values updated to new tokens
_light_palette() -> QPalette  # new
```

Updated dark palette roles (stale values from the previous design system replaced):

| Role | Dark value |
|------|------------|
| `Window` | `#09090b` |
| `WindowText` | `#fafafa` |
| `Base` | `#18181b` |
| `AlternateBase` | `#27272a` |
| `Text` | `#fafafa` |
| `PlaceholderText` | `#71717a` |
| `Button` | `#27272a` |
| `ButtonText` | `#fafafa` |
| `BrightText` | `#ffffff` |
| `Highlight` | `#3b82f6` |
| `HighlightedText` | `#fafafa` |
| `Link` | `#3b82f6` |
| `ToolTipBase` | `#27272a` |
| `ToolTipText` | `#fafafa` |
| Disabled text roles | `#52525b` |

Light palette key roles:

| Role | Light value |
|------|-------------|
| `Window` | `#f5f4f1` |
| `WindowText` | `#1c1917` |
| `Base` | `#fafaf9` |
| `AlternateBase` | `#e7e5e4` |
| `Text` | `#1c1917` |
| `PlaceholderText` | `#a8a29e` |
| `Button` | `#e7e5e4` |
| `ButtonText` | `#1c1917` |
| `BrightText` | `#ffffff` |
| `Highlight` | `#2563eb` |
| `HighlightedText` | `#fafafa` |
| `Link` | `#2563eb` |
| `ToolTipBase` | `#e7e5e4` |
| `ToolTipText` | `#1c1917` |
| Disabled text roles | `#a8a29e` |

### 4.4 Theme Switching at Runtime

`TouchstoneWindow` gains a `set_theme(theme: str)` method:

```python
def set_theme(self, theme: str) -> None:
    app = QApplication.instance()
    if theme == "light":
        app.setPalette(_light_palette())
        app.setStyleSheet(QSS_LIGHT)
    else:
        app.setPalette(_dark_palette())
        app.setStyleSheet(QSS_DARK)
    save_theme(theme)
    self._current_theme = theme
```

No restart required. The settings dialog (Phase 3) will call `window.set_theme()` when the user toggles it. For now, the theme is loaded and applied at startup from `theme_prefs.py`.

---

## 5. Toggle Switch Update

`src/ui/widgets/toggle_switch.py` hardcodes colour hex values in its `paintEvent`. Update the two key colours to the new tokens:
Read `QApplication.palette()` at paint time so the toggle responds to runtime theme switches without a restart. Use these palette roles:
- Off track: `QPalette.ColorRole.Button` — maps to `#27272a` dark / `#e7e5e4` light
- On track: `QPalette.ColorRole.Highlight` — maps to `#3b82f6` dark / `#2563eb` light
- Thumb: `QPalette.ColorRole.BrightText` — white in both themes

---

## 6. Files Changed

| File | Change |
|------|--------|
| `src/ui/stylesheet.py` | Complete rewrite — new token values, full light + dark QSS strings, same `refresh_style()` |
| `src/ui/app_window.py` | Add `_light_palette()`, `set_theme()`, load theme at startup |
| `src/utils/theme_prefs.py` | New — `load_theme()` / `save_theme()` backed by `~/.touchstone/prefs.json` |
| `src/ui/widgets/toggle_switch.py` | Update hardcoded colours to palette-aware |

---

## 7. Out of Scope

- No layout changes to any widget (Phase 2)
- No new widgets created (Phase 2)
- No settings dialog fields for theme (Phase 3)
- No changes to test logic, report generation, or data models
- No changes to helper dialogs beyond what inherits from the global stylesheet
