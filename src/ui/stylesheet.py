"""Touchstone design system — QSS for dark and light themes.

Apply at app level:
    app.setStyleSheet(QSS_DARK)   # or QSS_LIGHT

Colour tokens
─────────────────────────────────────────────
Dark mode
  bg-base       #09090b   window background
  bg-surface    #18181b   cards, panels, inputs
  bg-elevated   #27272a   hover fills, dropdown bg
  bg-hover      #3f3f46   pressed state
  border-subtle #27272a   internal dividers
  border        #3f3f46   widget borders
  text-primary  #fafafa   body copy, values
  text-secondary #a1a1aa  labels, secondary
  text-muted    #71717a   placeholders, captions
  accent        #3b82f6   primary action, focus ring
  accent-hover  #2563eb   primary button hover
  pass          #22c55e   pass status
  warn          #f59e0b   warning status
  fail          #ef4444   fail status
  running       #60a5fa   in-progress status

Light mode
  bg-base       #f5f4f1   window background (warm grey)
  bg-surface    #fafaf9   cards, panels, inputs
  bg-elevated   #e7e5e4   hover fills
  bg-hover      #d6d3d1   pressed state
  border-subtle #e7e5e4   internal dividers
  border        #d6d3d1   widget borders
  text-primary  #1c1917   body copy, values
  text-secondary #78716c  labels, secondary
  text-muted    #a8a29e   placeholders, captions
  accent        #2563eb   primary action
  accent-hover  #1d4ed8   primary button hover
  pass          #16a34a   pass status
  warn          #d97706   warning status
  fail          #dc2626   fail status
  running       #3b82f6   in-progress status

Badge tinted backgrounds (status colour at ~15% on surface bg):
  Dark  pass=#1a2e20  warn=#2e2210  fail=#2e1414  running=#162136
  Light pass=#d6f0dc  warn=#f5e6cc  fail=#f5d5d5  running=#d5e4f7
"""

# ---------------------------------------------------------------------------
# Dark theme
# ---------------------------------------------------------------------------

QSS_DARK = """
/* ── Global reset ──────────────────────────────────────────── */
* {
    font-size: 13px;
    color: #fafafa;
    outline: none;
}

QMainWindow, QDialog {
    background-color: #09090b;
}

QWidget {
    background-color: transparent;
}

QMainWindow > QWidget,
QDialog > QWidget {
    background-color: #09090b;
}

/* Labels must stay transparent — QDialog > QWidget has higher specificity */
QDialog QLabel,
QMainWindow QLabel {
    background-color: transparent;
}

QStackedWidget {
    background-color: #09090b;
}

/* ── Labels ─────────────────────────────────────────────────── */
QLabel {
    background-color: transparent;
    color: #fafafa;
}

QLabel[class="muted"]    { color: #71717a; }
QLabel[class="accent"]   { color: #3b82f6; }
QLabel[class="pass"]     { color: #22c55e; }
QLabel[class="warn"]     { color: #f59e0b; }
QLabel[class="fail"]     { color: #ef4444; }
QLabel[class="running"]  { color: #60a5fa; }

QLabel[class="title"] {
    font-size: 20px;
    font-weight: 600;
}

QLabel[class="subtitle"] {
    font-size: 13px;
    color: #a1a1aa;
}

QLabel[class="section-title"] {
    font-size: 11px;
    font-weight: 600;
    color: #71717a;
}

/* ── Status Badges (QLabel) ─────────────────────────────────── */
QLabel[class="badge"] {
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 700;
}

QLabel[class="badge"][status="pass"] {
    background-color: #1a2e20;
    color: #22c55e;
}

QLabel[class="badge"][status="warn"] {
    background-color: #2e2210;
    color: #f59e0b;
}

QLabel[class="badge"][status="fail"] {
    background-color: #2e1414;
    color: #ef4444;
}

QLabel[class="badge"][status="running"] {
    background-color: #162136;
    color: #60a5fa;
}

QLabel[class="badge"][status="idle"],
QLabel[class="badge"][status="skip"],
QLabel[class="badge"][status="not-run"] {
    background-color: #27272a;
    color: #71717a;
}

/* ── Buttons ─────────────────────────────────────────────────── */
QPushButton {
    background-color: #18181b;
    color: #a1a1aa;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
    min-height: 30px;
}

QPushButton:hover {
    background-color: #27272a;
    color: #fafafa;
    border-color: #3f3f46;
}

QPushButton:pressed {
    background-color: #3f3f46;
}

QPushButton:disabled {
    opacity: 0.4;
}

QPushButton[class="primary"] {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
}

QPushButton[class="primary"]:hover {
    background-color: #2563eb;
}

QPushButton[class="primary"]:pressed {
    background-color: #1d4ed8;
}

QPushButton[class="primary"]:disabled {
    background-color: #3b82f6;
    color: #ffffff;
    opacity: 0.4;
}

QPushButton[class="ghost"] {
    background-color: transparent;
    border: none;
    color: #a1a1aa;
}

QPushButton[class="ghost"]:hover {
    background-color: #27272a;
    color: #fafafa;
}

QPushButton[class="ghost"]:pressed {
    background-color: #3f3f46;
}

QPushButton[class="danger"] {
    background-color: transparent;
    border: none;
    color: #ef4444;
}

QPushButton[class="danger"]:hover {
    background-color: #2e1414;
    color: #ef4444;
}

QPushButton[class="danger"]:pressed {
    background-color: #3f0f0f;
}

/* Tab buttons — all four borders specified to avoid Fusion partial-border bugs */
QPushButton[class="tab"] {
    background-color: transparent;
    border-top: none;
    border-left: none;
    border-right: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    color: #71717a;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 400;
    min-height: 0;
}

QPushButton[class="tab"]:hover {
    background-color: transparent;
    color: #a1a1aa;
    border-top: none;
    border-left: none;
    border-right: none;
    border-bottom: 2px solid transparent;
}

QPushButton[class="tab"][checked="true"] {
    color: #fafafa;
    border-top: none;
    border-left: none;
    border-right: none;
    border-bottom: 2px solid #3b82f6;
}

/* Radio-style toggle buttons */
QPushButton[class="toggle"] {
    background-color: #18181b;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 10px 20px;
    text-align: left;
    min-height: 44px;
    color: #a1a1aa;
    font-size: 13px;
}

QPushButton[class="toggle"]:hover {
    background-color: #27272a;
    border-color: #3b82f6;
}

QPushButton[class="toggle"][checked="true"] {
    background-color: #1e3a5f;
    border-color: #3b82f6;
    color: #60a5fa;
}

/* Icon-only buttons */
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
    background-color: #27272a;
    border-color: #3f3f46;
}

QPushButton[class="icon-btn"]:pressed {
    background-color: #3f3f46;
    border-color: #3f3f46;
}

/* Segmented buttons */
QPushButton[class="seg-left"],
QPushButton[class="seg-right"] {
    background-color: #18181b;
    color: #71717a;
    border: 1px solid #3f3f46;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
    min-height: 30px;
}

QPushButton[class="seg-left"] {
    border-top-left-radius: 6px;
    border-bottom-left-radius: 6px;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
    border-right-width: 0;
}

QPushButton[class="seg-right"] {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QPushButton[class="seg-mid"] {
    background-color: #18181b;
    color: #71717a;
    border: 1px solid #3f3f46;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
    min-height: 30px;
    border-radius: 0;
    border-right-width: 0;
}

QPushButton[class="seg-left"]:hover,
QPushButton[class="seg-mid"]:hover,
QPushButton[class="seg-right"]:hover {
    background-color: #27272a;
    color: #fafafa;
}

QPushButton[class="seg-left"][checked="true"],
QPushButton[class="seg-mid"][checked="true"],
QPushButton[class="seg-right"][checked="true"] {
    background-color: #1e3a5f;
    border-color: #3b82f6;
    color: #60a5fa;
    font-weight: 600;
}

/* ── Inputs ──────────────────────────────────────────────────── */
QLineEdit {
    background-color: #18181b;
    color: #fafafa;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 30px;
    selection-background-color: #1e3a5f;
    font-size: 13px;
}

QLineEdit:focus {
    border-color: #3b82f6;
}

QLineEdit:disabled {
    color: #52525b;
    background-color: #27272a;
}

QLineEdit[class="error"] {
    border-color: #ef4444;
}

QTextEdit,
QPlainTextEdit {
    background-color: #18181b;
    color: #fafafa;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #1e3a5f;
    font-size: 13px;
}

QTextEdit:focus,
QPlainTextEdit:focus {
    border-color: #3b82f6;
}

/* ── Combo Box ───────────────────────────────────────────────── */
QComboBox {
    background-color: #18181b;
    color: #fafafa;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 30px;
    font-size: 13px;
}

QComboBox:hover {
    border-color: #71717a;
}

QComboBox:focus {
    border-color: #3b82f6;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #27272a;
    color: #fafafa;
    border: 1px solid #3f3f46;
    selection-background-color: #3f3f46;
    outline: none;
}

/* ── Progress Bar ────────────────────────────────────────────── */
QProgressBar {
    background-color: #27272a;
    border: none;
    border-radius: 2px;
    height: 4px;
    color: transparent;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 2px;
}

QProgressBar[status="pass"]::chunk    { background-color: #22c55e; }
QProgressBar[status="warn"]::chunk    { background-color: #f59e0b; }
QProgressBar[status="fail"]::chunk    { background-color: #ef4444; }
QProgressBar[status="running"]::chunk { background-color: #60a5fa; }

/* ── Frames / Panels ─────────────────────────────────────────── */
QFrame[class="panel"] {
    background-color: #18181b;
    border: 1px solid #3f3f46;
    border-radius: 8px;
}

QFrame[class="card"] {
    background-color: #18181b;
    border: 1px solid #3f3f46;
    border-radius: 6px;
}

QFrame[class="metric-card"] {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 7px;
}

QFrame[class="data-row"] {
    background-color: transparent;
    border: none;
    border-bottom: 1px solid #27272a;
}

QFrame[class="tab-bar"] {
    background-color: transparent;
    border: none;
    border-bottom: 1px solid #27272a;
}

/* Test card status borders */
QFrame[class="test-card"] {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 6px;
}

QFrame[class="test-card"][status="waiting"] { border-color: #27272a; }
QFrame[class="test-card"][status="running"] { border-color: #60a5fa; }
QFrame[class="test-card"][status="pass"]    { border-color: #22c55e; }
QFrame[class="test-card"][status="warn"]    { border-color: #f59e0b; }
QFrame[class="test-card"][status="fail"]    { border-color: #ef4444; }
QFrame[class="test-card"][status="error"]   { border-color: #ef4444; }
QFrame[class="test-card"][status="skip"]    { border-color: #71717a; }

/* ── Scroll Bars ─────────────────────────────────────────────── */
QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: transparent;
    width: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #3f3f46;
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #71717a;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 6px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #3f3f46;
    border-radius: 3px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #71717a;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Separators ──────────────────────────────────────────────── */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    background-color: #27272a;
    border: none;
    max-height: 1px;
}

/* ── Tool Tips ───────────────────────────────────────────────── */
QToolTip {
    background-color: #27272a;
    color: #fafafa;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}

/* ── Message Box ─────────────────────────────────────────────── */
QMessageBox {
    background-color: #09090b;
}

QMessageBox QLabel {
    color: #fafafa;
}
"""

# ---------------------------------------------------------------------------
# Light theme
# ---------------------------------------------------------------------------

QSS_LIGHT = """
/* ── Global reset ──────────────────────────────────────────── */
* {
    font-size: 13px;
    color: #1c1917;
    outline: none;
}

QMainWindow, QDialog {
    background-color: #f5f4f1;
}

QWidget {
    background-color: transparent;
}

QMainWindow > QWidget,
QDialog > QWidget {
    background-color: #f5f4f1;
}

QDialog QLabel,
QMainWindow QLabel {
    background-color: transparent;
}

QStackedWidget {
    background-color: #f5f4f1;
}

/* ── Labels ─────────────────────────────────────────────────── */
QLabel {
    background-color: transparent;
    color: #1c1917;
}

QLabel[class="muted"]    { color: #a8a29e; }
QLabel[class="accent"]   { color: #2563eb; }
QLabel[class="pass"]     { color: #16a34a; }
QLabel[class="warn"]     { color: #d97706; }
QLabel[class="fail"]     { color: #dc2626; }
QLabel[class="running"]  { color: #3b82f6; }

QLabel[class="title"] {
    font-size: 20px;
    font-weight: 600;
}

QLabel[class="subtitle"] {
    font-size: 13px;
    color: #78716c;
}

QLabel[class="section-title"] {
    font-size: 11px;
    font-weight: 600;
    color: #a8a29e;
}

/* ── Status Badges (QLabel) ─────────────────────────────────── */
QLabel[class="badge"] {
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 700;
}

QLabel[class="badge"][status="pass"] {
    background-color: #d6f0dc;
    color: #16a34a;
}

QLabel[class="badge"][status="warn"] {
    background-color: #f5e6cc;
    color: #d97706;
}

QLabel[class="badge"][status="fail"] {
    background-color: #f5d5d5;
    color: #dc2626;
}

QLabel[class="badge"][status="running"] {
    background-color: #d5e4f7;
    color: #3b82f6;
}

QLabel[class="badge"][status="idle"],
QLabel[class="badge"][status="skip"],
QLabel[class="badge"][status="not-run"] {
    background-color: #e7e5e4;
    color: #a8a29e;
}

/* ── Buttons ─────────────────────────────────────────────────── */
QPushButton {
    background-color: #fafaf9;
    color: #78716c;
    border: 1px solid #d6d3d1;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
    min-height: 30px;
}

QPushButton:hover {
    background-color: #e7e5e4;
    color: #1c1917;
    border-color: #d6d3d1;
}

QPushButton:pressed {
    background-color: #d6d3d1;
}

QPushButton:disabled {
    opacity: 0.4;
}

QPushButton[class="primary"] {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
}

QPushButton[class="primary"]:hover {
    background-color: #1d4ed8;
}

QPushButton[class="primary"]:pressed {
    background-color: #1e40af;
}

QPushButton[class="primary"]:disabled {
    background-color: #2563eb;
    color: #ffffff;
    opacity: 0.4;
}

QPushButton[class="ghost"] {
    background-color: transparent;
    border: none;
    color: #78716c;
}

QPushButton[class="ghost"]:hover {
    background-color: #e7e5e4;
    color: #1c1917;
}

QPushButton[class="ghost"]:pressed {
    background-color: #d6d3d1;
}

QPushButton[class="danger"] {
    background-color: transparent;
    border: none;
    color: #dc2626;
}

QPushButton[class="danger"]:hover {
    background-color: #f5d5d5;
    color: #dc2626;
}

QPushButton[class="danger"]:pressed {
    background-color: #fecaca;
}

QPushButton[class="tab"] {
    background-color: transparent;
    border-top: none;
    border-left: none;
    border-right: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    color: #a8a29e;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 400;
    min-height: 0;
}

QPushButton[class="tab"]:hover {
    background-color: transparent;
    color: #78716c;
    border-top: none;
    border-left: none;
    border-right: none;
    border-bottom: 2px solid transparent;
}

QPushButton[class="tab"][checked="true"] {
    color: #1c1917;
    border-top: none;
    border-left: none;
    border-right: none;
    border-bottom: 2px solid #2563eb;
}

QPushButton[class="toggle"] {
    background-color: #fafaf9;
    border: 1px solid #d6d3d1;
    border-radius: 6px;
    padding: 10px 20px;
    text-align: left;
    min-height: 44px;
    color: #78716c;
    font-size: 13px;
}

QPushButton[class="toggle"]:hover {
    background-color: #e7e5e4;
    border-color: #2563eb;
}

QPushButton[class="toggle"][checked="true"] {
    background-color: #dbeafe;
    border-color: #2563eb;
    color: #2563eb;
}

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
    background-color: #e7e5e4;
    border-color: #d6d3d1;
}

QPushButton[class="icon-btn"]:pressed {
    background-color: #d6d3d1;
    border-color: #d6d3d1;
}

QPushButton[class="seg-left"],
QPushButton[class="seg-right"] {
    background-color: #fafaf9;
    color: #a8a29e;
    border: 1px solid #d6d3d1;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
    min-height: 30px;
}

QPushButton[class="seg-left"] {
    border-top-left-radius: 6px;
    border-bottom-left-radius: 6px;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
    border-right-width: 0;
}

QPushButton[class="seg-right"] {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QPushButton[class="seg-mid"] {
    background-color: #fafaf9;
    color: #a8a29e;
    border: 1px solid #d6d3d1;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
    min-height: 30px;
    border-radius: 0;
    border-right-width: 0;
}

QPushButton[class="seg-left"]:hover,
QPushButton[class="seg-mid"]:hover,
QPushButton[class="seg-right"]:hover {
    background-color: #e7e5e4;
    color: #1c1917;
}

QPushButton[class="seg-left"][checked="true"],
QPushButton[class="seg-mid"][checked="true"],
QPushButton[class="seg-right"][checked="true"] {
    background-color: #dbeafe;
    border-color: #2563eb;
    color: #2563eb;
    font-weight: 600;
}

/* ── Inputs ──────────────────────────────────────────────────── */
QLineEdit {
    background-color: #fafaf9;
    color: #1c1917;
    border: 1px solid #d6d3d1;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 30px;
    selection-background-color: #bfdbfe;
    font-size: 13px;
}

QLineEdit:focus {
    border-color: #2563eb;
}

QLineEdit:disabled {
    color: #a8a29e;
    background-color: #e7e5e4;
}

QLineEdit[class="error"] {
    border-color: #dc2626;
}

QTextEdit,
QPlainTextEdit {
    background-color: #fafaf9;
    color: #1c1917;
    border: 1px solid #d6d3d1;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #bfdbfe;
    font-size: 13px;
}

QTextEdit:focus,
QPlainTextEdit:focus {
    border-color: #2563eb;
}

/* ── Combo Box ───────────────────────────────────────────────── */
QComboBox {
    background-color: #fafaf9;
    color: #1c1917;
    border: 1px solid #d6d3d1;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 30px;
    font-size: 13px;
}

QComboBox:hover {
    border-color: #a8a29e;
}

QComboBox:focus {
    border-color: #2563eb;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #e7e5e4;
    color: #1c1917;
    border: 1px solid #d6d3d1;
    selection-background-color: #d6d3d1;
    outline: none;
}

/* ── Progress Bar ────────────────────────────────────────────── */
QProgressBar {
    background-color: #e7e5e4;
    border: none;
    border-radius: 2px;
    height: 4px;
    color: transparent;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 2px;
}

QProgressBar[status="pass"]::chunk    { background-color: #16a34a; }
QProgressBar[status="warn"]::chunk    { background-color: #d97706; }
QProgressBar[status="fail"]::chunk    { background-color: #dc2626; }
QProgressBar[status="running"]::chunk { background-color: #3b82f6; }

/* ── Frames / Panels ─────────────────────────────────────────── */
QFrame[class="panel"] {
    background-color: #fafaf9;
    border: 1px solid #d6d3d1;
    border-radius: 8px;
}

QFrame[class="card"] {
    background-color: #fafaf9;
    border: 1px solid #d6d3d1;
    border-radius: 6px;
}

QFrame[class="metric-card"] {
    background-color: #fafaf9;
    border: 1px solid #e7e5e4;
    border-radius: 7px;
}

QFrame[class="data-row"] {
    background-color: transparent;
    border: none;
    border-bottom: 1px solid #e7e5e4;
}

QFrame[class="tab-bar"] {
    background-color: transparent;
    border: none;
    border-bottom: 1px solid #e7e5e4;
}

QFrame[class="test-card"] {
    background-color: #fafaf9;
    border: 1px solid #e7e5e4;
    border-radius: 6px;
}

QFrame[class="test-card"][status="waiting"] { border-color: #e7e5e4; }
QFrame[class="test-card"][status="running"] { border-color: #3b82f6; }
QFrame[class="test-card"][status="pass"]    { border-color: #16a34a; }
QFrame[class="test-card"][status="warn"]    { border-color: #d97706; }
QFrame[class="test-card"][status="fail"]    { border-color: #dc2626; }
QFrame[class="test-card"][status="error"]   { border-color: #dc2626; }
QFrame[class="test-card"][status="skip"]    { border-color: #a8a29e; }

/* ── Scroll Bars ─────────────────────────────────────────────── */
QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: transparent;
    width: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #d6d3d1;
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #a8a29e;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 6px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #d6d3d1;
    border-radius: 3px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #a8a29e;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Separators ──────────────────────────────────────────────── */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    background-color: #e7e5e4;
    border: none;
    max-height: 1px;
}

/* ── Tool Tips ───────────────────────────────────────────────── */
QToolTip {
    background-color: #e7e5e4;
    color: #1c1917;
    border: 1px solid #d6d3d1;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}

/* ── Message Box ─────────────────────────────────────────────── */
QMessageBox {
    background-color: #f5f4f1;
}

QMessageBox QLabel {
    color: #1c1917;
}
"""

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def refresh_style(widget) -> None:
    """Force QSS dynamic property re-evaluation after setProperty().

    Call after widget.setProperty(...) to repaint the widget with the
    updated CSS selector state.
    """
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
