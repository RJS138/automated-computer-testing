"""Dark theme QSS for the Touchstone Qt application.

Apply at app level:  QApplication.instance().setStyleSheet(QSS_DARK)

Colour tokens
─────────────
  Background  #0d1117    top-level window fill
  Surface     #161b22    raised surfaces (cards, panels)
  Surface2    #1c2128    slightly elevated (input bg)
  Border      #30363d    default border / separator
  Accent      #3b82f6    primary action colour
  AccentHover #2563eb    accent on hover
  Text        #e6edf3    primary text
  Muted       #7d8590    secondary / placeholder text
  Pass        #22c55e    success / pass
  Warn        #f59e0b    warning
  Fail        #ef4444    error / fail
"""

QSS_DARK = """
/* ── Global reset ───────────────────────────────────────────── */
* {
    font-size: 13px;
    color: #e6edf3;
    outline: none;
}

QMainWindow, QDialog {
    background-color: #0d1117;
}

QWidget {
    background-color: transparent;
}

/* Make top-level widgets have the background colour */
QMainWindow > QWidget,
QDialog > QWidget {
    background-color: #0d1117;
}

/* ── QStackedWidget page containers ─────────────────────────── */
QStackedWidget {
    background-color: #0d1117;
}

/* ── Labels ─────────────────────────────────────────────────── */
QLabel {
    background-color: transparent;
    color: #e6edf3;
}

QLabel[class="muted"] {
    color: #7d8590;
}

QLabel[class="accent"] {
    color: #3b82f6;
}

QLabel[class="pass"] {
    color: #22c55e;
}

QLabel[class="warn"] {
    color: #f59e0b;
}

QLabel[class="fail"] {
    color: #ef4444;
}

QLabel[class="title"] {
    font-size: 20px;
    font-weight: 600;
    color: #e6edf3;
}

QLabel[class="subtitle"] {
    font-size: 13px;
    color: #7d8590;
}

QLabel[class="section-title"] {
    font-size: 11px;
    font-weight: 600;
    color: #7d8590;
}

/* ── Buttons ────────────────────────────────────────────────── */
QPushButton {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 500;
    min-height: 32px;
}

QPushButton:hover {
    background-color: #30363d;
    border-color: #8b949e;
}

QPushButton:pressed {
    background-color: #161b22;
}

QPushButton:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

QPushButton[class="primary"] {
    background-color: #3b82f6;
    color: #ffffff;
    border-color: #3b82f6;
}

QPushButton[class="primary"]:hover {
    background-color: #2563eb;
    border-color: #2563eb;
}

QPushButton[class="primary"]:pressed {
    background-color: #1d4ed8;
}

QPushButton[class="primary"]:disabled {
    background-color: #1e3a5f;
    color: #4b6fa5;
    border-color: #1e3a5f;
}

QPushButton[class="danger"] {
    background-color: #ef4444;
    color: #ffffff;
    border-color: #ef4444;
}

QPushButton[class="danger"]:hover {
    background-color: #dc2626;
    border-color: #dc2626;
}

QPushButton[class="warn"] {
    background-color: #f59e0b;
    color: #000000;
    border-color: #f59e0b;
}

QPushButton[class="warn"]:hover {
    background-color: #d97706;
    border-color: #d97706;
}

QPushButton[class="success"] {
    background-color: #22c55e;
    color: #000000;
    border-color: #22c55e;
}

QPushButton[class="success"]:hover {
    background-color: #16a34a;
    border-color: #16a34a;
}

/* Radio-style toggle buttons */
QPushButton[class="toggle"] {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 10px 20px;
    text-align: left;
    min-height: 44px;
}

QPushButton[class="toggle"]:hover {
    background-color: #1c2128;
    border-color: #3b82f6;
}

QPushButton[class="toggle"][checked="true"] {
    background-color: #1e3a5f;
    border-color: #3b82f6;
    color: #60a5fa;
}

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

/* ── Line Edits ─────────────────────────────────────────────── */
QLineEdit {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 7px 10px;
    min-height: 32px;
    selection-background-color: #1e3a5f;
}

QLineEdit:focus {
    border-color: #3b82f6;
    background-color: #1c2128;
}

QLineEdit:disabled {
    color: #484f58;
    background-color: #0d1117;
}

QLineEdit[class="error"] {
    border-color: #ef4444;
}

/* Placeholder text colour */
QLineEdit[placeholderText] {
    color: #7d8590;
}

/* ── Text Edit ──────────────────────────────────────────────── */
QTextEdit, QPlainTextEdit {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 7px 10px;
    selection-background-color: #1e3a5f;
}

QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #3b82f6;
}

/* ── Scroll Areas ───────────────────────────────────────────── */
QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: #161b22;
    width: 8px;
    margin: 0;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background-color: #484f58;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #6e7681;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #161b22;
    height: 8px;
    margin: 0;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background-color: #484f58;
    border-radius: 4px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #6e7681;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Progress Bar ───────────────────────────────────────────── */
QProgressBar {
    background-color: #21262d;
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 3px;
}

QProgressBar[status="pass"]::chunk {
    background-color: #22c55e;
}

QProgressBar[status="warn"]::chunk {
    background-color: #f59e0b;
}

QProgressBar[status="fail"]::chunk {
    background-color: #ef4444;
}

QProgressBar[status="running"]::chunk {
    background-color: #3b82f6;
}

/* ── Frames / Panels ────────────────────────────────────────── */
QFrame[class="panel"] {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
}

QFrame[class="card"] {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
}

/* TestCard status borders — set via dynamic property 'status' */
QFrame[class="test-card"] {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
}

QFrame[class="test-card"][status="waiting"] {
    border-color: #30363d;
}

QFrame[class="test-card"][status="running"] {
    border-color: #f59e0b;
}

QFrame[class="test-card"][status="pass"] {
    border-color: #22c55e;
}

QFrame[class="test-card"][status="warn"] {
    border-color: #f59e0b;
}

QFrame[class="test-card"][status="fail"] {
    border-color: #ef4444;
}

QFrame[class="test-card"][status="error"] {
    border-color: #ef4444;
}

QFrame[class="test-card"][status="skip"] {
    border-color: #30363d;
}

/* ── Segmented (split) buttons ──────────────────────────────── */
QPushButton[class="seg-left"],
QPushButton[class="seg-right"] {
    background-color: #161b22;
    color: #7d8590;
    border: 1px solid #30363d;
    padding: 7px 14px;
    font-weight: 500;
    min-height: 32px;
}

QPushButton[class="seg-left"] {
    border-top-left-radius: 6px;
    border-bottom-left-radius: 6px;
    border-top-right-radius: 0px;
    border-bottom-right-radius: 0px;
    border-right-width: 0px;
}

QPushButton[class="seg-right"] {
    border-top-left-radius: 0px;
    border-bottom-left-radius: 0px;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QPushButton[class="seg-mid"] {
    background-color: #161b22;
    color: #7d8590;
    border: 1px solid #30363d;
    padding: 7px 14px;
    font-weight: 500;
    min-height: 32px;
    border-radius: 0px;
    border-right-width: 0px;
}

QPushButton[class="seg-mid"]:hover {
    background-color: #1c2128;
    color: #e6edf3;
}

QPushButton[class="seg-mid"][checked="true"] {
    background-color: #1e3a5f;
    border-color: #3b82f6;
    color: #60a5fa;
    font-weight: 600;
}

QPushButton[class="seg-left"]:hover,
QPushButton[class="seg-right"]:hover {
    background-color: #1c2128;
    color: #e6edf3;
}

QPushButton[class="seg-left"][checked="true"],
QPushButton[class="seg-right"][checked="true"] {
    background-color: #1e3a5f;
    border-color: #3b82f6;
    color: #60a5fa;
    font-weight: 600;
}

/* ── Separators ─────────────────────────────────────────────── */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    color: #30363d;
    background-color: #30363d;
}

/* ── Combo Box ──────────────────────────────────────────────── */
QComboBox {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 32px;
}

QComboBox:hover {
    border-color: #8b949e;
}

QComboBox:focus {
    border-color: #3b82f6;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    selection-background-color: #1e3a5f;
}

/* ── Tool Tips ──────────────────────────────────────────────── */
QToolTip {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 8px;
}

/* ── Message Box ────────────────────────────────────────────── */
QMessageBox {
    background-color: #0d1117;
}

QMessageBox QLabel {
    color: #e6edf3;
}
"""


def refresh_style(widget) -> None:
    """Force QSS dynamic property re-evaluation after setProperty().

    Call after widget.setProperty(...) to repaint the widget with the
    updated CSS selector state.
    """
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
