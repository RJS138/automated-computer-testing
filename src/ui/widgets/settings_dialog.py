"""SettingsDialog — modal for report output settings."""

from __future__ import annotations

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

from src.models.settings import Settings

_SEG_L_OFF = (
    "QPushButton { background: #3f3f46; color: #a1a1aa; border: none;"
    " border-top-left-radius: 6px; border-bottom-left-radius: 6px;"
    " border-top-right-radius: 0; border-bottom-right-radius: 0;"
    " padding: 5px 14px; font-size: 12px; font-weight: 500; min-height: 30px; }"
    "QPushButton:hover { background: #52525b; color: #fafafa; }"
)
_SEG_L_ON = (
    "QPushButton { background: #3b82f6; color: #ffffff; border: none;"
    " border-top-left-radius: 6px; border-bottom-left-radius: 6px;"
    " border-top-right-radius: 0; border-bottom-right-radius: 0;"
    " padding: 5px 14px; font-size: 12px; font-weight: 600; min-height: 30px; }"
    "QPushButton:hover { background: #2563eb; color: #ffffff; }"
)
_SEG_M_OFF = (
    "QPushButton { background: #3f3f46; color: #a1a1aa; border: none; border-radius: 0;"
    " padding: 5px 14px; font-size: 12px; font-weight: 500; min-height: 30px;"
    " margin-left: 2px; margin-right: 2px; }"
    "QPushButton:hover { background: #52525b; color: #fafafa; }"
)
_SEG_M_ON = (
    "QPushButton { background: #3b82f6; color: #ffffff; border: none; border-radius: 0;"
    " padding: 5px 14px; font-size: 12px; font-weight: 600; min-height: 30px;"
    " margin-left: 2px; margin-right: 2px; }"
    "QPushButton:hover { background: #2563eb; color: #ffffff; }"
)
_SEG_R_OFF = (
    "QPushButton { background: #3f3f46; color: #a1a1aa; border: none;"
    " border-top-left-radius: 0; border-bottom-left-radius: 0;"
    " border-top-right-radius: 6px; border-bottom-right-radius: 6px;"
    " padding: 5px 14px; font-size: 12px; font-weight: 500; min-height: 30px; }"
    "QPushButton:hover { background: #52525b; color: #fafafa; }"
)
_SEG_R_ON = (
    "QPushButton { background: #3b82f6; color: #ffffff; border: none;"
    " border-top-left-radius: 0; border-bottom-left-radius: 0;"
    " border-top-right-radius: 6px; border-bottom-right-radius: 6px;"
    " padding: 5px 14px; font-size: 12px; font-weight: 600; min-height: 30px; }"
    "QPushButton:hover { background: #2563eb; color: #ffffff; }"
)


class SettingsDialog(QDialog):
    """Modal dialog for report output settings.

    Usage:
        dlg = SettingsDialog(copy(window.settings), theme=window.theme, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            window.settings = dlg.result_settings()
            window.set_theme(dlg.result_theme())
    """

    def __init__(self, settings: Settings, theme: str = "dark", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_theme: str = theme
        self._settings = settings  # caller passes a copy; no need to copy again
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        # ── Appearance ────────────────────────────────────────────────────────
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

        # ── Output Format ─────────────────────────────────────────────────────
        root.addWidget(self._section_label("Output Format"))

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(0)

        self._btn_html_pdf = QPushButton("HTML + PDF")
        self._btn_html_pdf.clicked.connect(lambda: self._select_format("html_pdf"))

        self._btn_html_only = QPushButton("HTML only")
        self._btn_html_only.clicked.connect(lambda: self._select_format("html_only"))

        self._btn_pdf_only = QPushButton("PDF only")
        self._btn_pdf_only.clicked.connect(lambda: self._select_format("pdf_only"))

        fmt_row.addWidget(self._btn_html_pdf)
        fmt_row.addWidget(self._btn_html_only)
        fmt_row.addWidget(self._btn_pdf_only)
        fmt_row.addStretch()
        root.addLayout(fmt_row)

        self._select_format(settings.output_format)  # applies styles directly

        # ── Save Location ─────────────────────────────────────────────────────
        root.addWidget(self._section_label("Save Location"))

        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        self._path_edit = QLineEdit(settings.save_path)
        path_row.addWidget(self._path_edit, stretch=1)

        browse_btn = QPushButton("Browse\u2026")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        root.addLayout(path_row)

        # ── Technician Notes ──────────────────────────────────────────────────
        root.addWidget(self._section_label("Technician Notes"))
        self._notes_edit = QPlainTextEdit(settings.notes)
        self._notes_edit.setPlaceholderText("Technician notes\u2026")
        self._notes_edit.setMaximumHeight(80)
        root.addWidget(self._notes_edit)

        # ── Buttons ───────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton { background: #7f1d1d; color: #fca5a5; border: none;"
            " border-radius: 6px; padding: 5px 14px; font-size: 12px; font-weight: 500;"
            " min-height: 30px; }"
            "QPushButton:hover { background: #991b1b; color: #ffffff; }"
            "QPushButton:pressed { background: #b91c1c; }"
        )
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(
            "QPushButton { background: #3b82f6; color: #ffffff; border: none;"
            " border-radius: 6px; padding: 5px 14px; font-size: 12px; font-weight: 600;"
            " min-height: 30px; }"
            "QPushButton:hover { background: #2563eb; }"
            "QPushButton:pressed { background: #1d4ed8; }"
        )
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setProperty("class", "section-title")
        return lbl

    def _select_theme(self, theme: str) -> None:
        self._selected_theme = theme
        self._btn_dark.setStyleSheet(_SEG_L_ON if theme == "dark" else _SEG_L_OFF)
        self._btn_light.setStyleSheet(_SEG_R_ON if theme == "light" else _SEG_R_OFF)

    def _select_format(self, fmt: str) -> None:
        self._settings.output_format = fmt
        self._btn_html_pdf.setStyleSheet(_SEG_L_ON  if fmt == "html_pdf"  else _SEG_L_OFF)
        self._btn_html_only.setStyleSheet(_SEG_M_ON if fmt == "html_only" else _SEG_M_OFF)
        self._btn_pdf_only.setStyleSheet(_SEG_R_ON  if fmt == "pdf_only"  else _SEG_R_OFF)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Save Location", self._path_edit.text()
        )
        if path:
            self._path_edit.setText(path)

    # ── Public API ────────────────────────────────────────────────────────────

    def result_theme(self) -> str:
        """Return "dark" or "light". Call after exec() -> Accepted."""
        return self._selected_theme

    def result_settings(self) -> Settings:
        """Return Settings reflecting current dialog state. Call after exec() -> Accepted."""
        return Settings(
            output_format=self._settings.output_format,
            save_path=self._path_edit.text().strip(),
            notes=self._notes_edit.toPlainText(),
        )
