# Settings Icon & Dialog Styling Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inconsistent ⚙ settings button and unstyled QDialogButtonBox with an SVG sliders icon button and a properly styled primary Save action.

**Architecture:** Three surgical edits — add an `icon-btn` QSS variant to the global stylesheet, swap the gear emoji for an SVG icon rendered via `QSvgRenderer`+`QPainter` in the header bar, and replace `QDialogButtonBox` with an explicit manual footer in the settings dialog.

**Tech Stack:** PySide6 (Qt6), Python 3.11+, QSS, `PySide6.QtSvg`

---

## File Map

| File | Change |
|------|--------|
| `src/ui/stylesheet.py` | Add `icon-btn` QSS block after existing button rules |
| `src/ui/widgets/header_bar.py` | Add `_settings_icon()` helper; swap button construction; add imports |
| `src/ui/widgets/settings_dialog.py` | Fix import block; replace `QDialogButtonBox` with manual footer |

No new files. No test files (this app has no automated test suite — verification is manual).

---

### Task 1: Add `icon-btn` to the global stylesheet

**Files:**
- Modify: `src/ui/stylesheet.py`

- [ ] **Step 1: Open `src/ui/stylesheet.py` and locate the end of the button block**

  The existing button block ends around line 191 (`QPushButton[class="toggle"][checked="true"]`). You will append the new block immediately after it, before the `# ── Line Edits` comment.

- [ ] **Step 2: Insert the `icon-btn` QSS block**

  Add the following text between the toggle-button block and the `# ── Line Edits` comment:

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

- [ ] **Step 3: Verify the file still parses**

  ```bash
  uv run python -c "from src.ui.stylesheet import QSS_DARK; print('OK', len(QSS_DARK))"
  ```
  Expected: `OK <some number>`

- [ ] **Step 4: Commit**

  ```bash
  git add src/ui/stylesheet.py
  git commit -m "feat: add icon-btn QSS variant to stylesheet"
  ```

---

### Task 2: Swap the settings button to use an SVG sliders icon

**Files:**
- Modify: `src/ui/widgets/header_bar.py`

- [ ] **Step 1: Update the imports at the top of `header_bar.py`**

  The existing `PySide6.QtCore` import line (line ~16) currently reads:
  ```python
  from PySide6.QtCore import Qt, QTimer, Signal
  ```
  Change it to:
  ```python
  from PySide6.QtCore import QByteArray, QSize, Qt, QTimer, Signal
  ```

  Add two entirely new import lines after the `PySide6.QtCore` import:
  ```python
  from PySide6.QtGui import QIcon, QPainter, QPixmap
  from PySide6.QtSvg import QSvgRenderer
  ```

- [ ] **Step 2: Add the `_settings_icon()` module-level helper**

  Insert this function before the `_ACTION_STATES` constant (around line 38), after the existing module-level helpers `_is_elevated` and `_restart_as_admin`:

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

- [ ] **Step 3: Replace the settings button construction in `_build_ui`**

  Find this block (around line 219):
  ```python
  self._settings_btn = QPushButton("⚙")
  self._settings_btn.setFixedSize(32, 32)
  self._settings_btn.setToolTip("Settings")
  row1.addWidget(self._settings_btn, alignment=_V)
  ```

  Replace with:
  ```python
  self._settings_btn = QPushButton()
  self._settings_btn.setProperty("class", "icon-btn")
  self._settings_btn.setFixedSize(32, 32)
  self._settings_btn.setIcon(_settings_icon())
  self._settings_btn.setIconSize(QSize(16, 16))
  self._settings_btn.setToolTip("Settings")
  row1.addWidget(self._settings_btn, alignment=_V)
  ```

  Note: `setProperty("class", "icon-btn")` must come before `row1.addWidget(...)` so the property is present on first paint.

- [ ] **Step 4: Verify the app launches and the button renders correctly**

  ```bash
  uv run touchstone --dev-manual
  ```

  Check:
  - The header bar shows a small sliders icon where ⚙ was
  - At rest the button has no visible border
  - On hover a dark border and background appear
  - Clicking it still opens the settings dialog

- [ ] **Step 5: Commit**

  ```bash
  git add src/ui/widgets/header_bar.py
  git commit -m "feat: replace gear emoji with SVG sliders icon on settings button"
  ```

---

### Task 3: Polish the Settings dialog footer

**Files:**
- Modify: `src/ui/widgets/settings_dialog.py`

- [ ] **Step 1: Fix the import block**

  The current `from PySide6.QtWidgets import (...)` block (lines 5–16) includes `QDialogButtonBox` and is missing `QFrame`. Replace the entire block with:

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

- [ ] **Step 2: Replace the `QDialogButtonBox` footer**

  Find this block (around lines 91–96):
  ```python
  # ── Buttons ───────────────────────────────────────────────────────────
  btns = QDialogButtonBox(
      QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
  )
  btns.accepted.connect(self.accept)
  btns.rejected.connect(self.reject)
  root.addWidget(btns)
  ```

  Replace with:
  ```python
  # ── Buttons ───────────────────────────────────────────────────────────
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

- [ ] **Step 3: Verify the dialog looks correct**

  ```bash
  uv run touchstone --dev-manual
  ```

  Click the settings button. Check:
  - Dialog opens normally
  - A separator line divides the fields from the footer
  - Cancel is a default (grey) button on the left
  - Save is a blue primary button on the right
  - Cancel closes the dialog without saving
  - Save closes the dialog and persists the settings

- [ ] **Step 4: Commit**

  ```bash
  git add src/ui/widgets/settings_dialog.py
  git commit -m "feat: replace QDialogButtonBox with styled Save/Cancel footer in settings dialog"
  ```
