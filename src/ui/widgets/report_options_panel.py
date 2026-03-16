"""ReportOptionsPanel — compact panel shown in Advanced mode above the test grid."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
)


def _default_save_path() -> str:
    try:
        from src.utils.file_manager import find_usb_drive
        usb = find_usb_drive()
        return str(usb) if usb else str(Path.home() / "touchstone_reports")
    except Exception:
        return str(Path.home() / "touchstone_reports")


class ReportOptionsPanel(QFrame):
    """Horizontal panel with output format, save path, and technician notes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("class", "panel")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(16)

        # ── Left: output format ───────────────────────────────────────────────
        fmt_layout = QVBoxLayout()
        fmt_layout.setSpacing(4)

        fmt_title = QLabel("Output Format")
        fmt_title.setProperty("class", "section-title")
        fmt_layout.addWidget(fmt_title)

        self._rb_html_pdf = QRadioButton("HTML + PDF")
        self._rb_html_only = QRadioButton("HTML only")
        self._rb_pdf_only = QRadioButton("PDF only")
        self._rb_html_pdf.setChecked(True)

        self._fmt_group = QButtonGroup(self)
        self._fmt_group.addButton(self._rb_html_pdf)
        self._fmt_group.addButton(self._rb_html_only)
        self._fmt_group.addButton(self._rb_pdf_only)

        fmt_layout.addWidget(self._rb_html_pdf)
        fmt_layout.addWidget(self._rb_html_only)
        fmt_layout.addWidget(self._rb_pdf_only)
        fmt_layout.addStretch()

        outer.addLayout(fmt_layout)

        # ── Middle: save path ─────────────────────────────────────────────────
        path_layout = QVBoxLayout()
        path_layout.setSpacing(4)

        path_title = QLabel("Save Path")
        path_title.setProperty("class", "section-title")
        path_layout.addWidget(path_title)

        self._path_edit = QLineEdit(_default_save_path())
        path_layout.addWidget(self._path_edit)
        path_layout.addStretch()

        outer.addLayout(path_layout, stretch=1)

        # ── Right: notes ──────────────────────────────────────────────────────
        notes_layout = QVBoxLayout()
        notes_layout.setSpacing(4)

        notes_title = QLabel("Notes")
        notes_title.setProperty("class", "section-title")
        notes_layout.addWidget(notes_title)

        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText("Technician notes…")
        self._notes_edit.setMaximumHeight(60)
        notes_layout.addWidget(self._notes_edit)
        notes_layout.addStretch()

        outer.addLayout(notes_layout, stretch=1)

    # ── Public accessors ──────────────────────────────────────────────────────

    def output_format(self) -> str:
        """Return selected format: 'html_pdf' | 'html_only' | 'pdf_only'."""
        if self._rb_html_only.isChecked():
            return "html_only"
        if self._rb_pdf_only.isChecked():
            return "pdf_only"
        return "html_pdf"

    def save_path(self) -> str:
        """Return the current save path string."""
        return self._path_edit.text().strip()

    def notes(self) -> str:
        """Return technician notes text."""
        return self._notes_edit.toPlainText()
