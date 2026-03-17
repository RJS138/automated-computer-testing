"""SettingsDialog — modal for report output settings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.models.settings import Settings
from src.ui.stylesheet import refresh_style


class SettingsDialog(QDialog):
    """Modal dialog for report output settings.

    Usage:
        dlg = SettingsDialog(copy(window.settings), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            window.settings = dlg.result_settings()
    """

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings  # caller passes a copy; no need to copy again
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        # ── Output Format ─────────────────────────────────────────────────────
        root.addWidget(self._section_label("Output Format"))

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(0)

        self._btn_html_pdf = QPushButton("HTML + PDF")
        self._btn_html_pdf.setProperty("class", "seg-left")
        self._btn_html_pdf.setCheckable(False)
        self._btn_html_pdf.clicked.connect(lambda: self._select_format("html_pdf"))

        self._btn_html_only = QPushButton("HTML only")
        self._btn_html_only.setProperty("class", "seg-mid")
        self._btn_html_only.setCheckable(False)
        self._btn_html_only.clicked.connect(lambda: self._select_format("html_only"))

        self._btn_pdf_only = QPushButton("PDF only")
        self._btn_pdf_only.setProperty("class", "seg-right")
        self._btn_pdf_only.setCheckable(False)
        self._btn_pdf_only.clicked.connect(lambda: self._select_format("pdf_only"))

        fmt_row.addWidget(self._btn_html_pdf)
        fmt_row.addWidget(self._btn_html_only)
        fmt_row.addWidget(self._btn_pdf_only)
        fmt_row.addStretch()
        root.addLayout(fmt_row)

        self._select_format(settings.output_format)

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
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("class", "section-title")
        return lbl

    def _select_format(self, fmt: str) -> None:
        self._settings.output_format = fmt
        for btn, key in (
            (self._btn_html_pdf, "html_pdf"),
            (self._btn_html_only, "html_only"),
            (self._btn_pdf_only, "pdf_only"),
        ):
            btn.setProperty("checked", "true" if fmt == key else "false")
            refresh_style(btn)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Save Location", self._path_edit.text()
        )
        if path:
            self._path_edit.setText(path)

    # ── Public API ────────────────────────────────────────────────────────────

    def result_settings(self) -> Settings:
        """Return Settings reflecting current dialog state. Call after exec() -> Accepted."""
        return Settings(
            output_format=self._settings.output_format,
            save_path=self._path_edit.text().strip(),
            notes=self._notes_edit.toPlainText(),
        )
