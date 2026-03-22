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
from src.ui.stylesheet import build_seg_styles, get_colors


class SettingsDialog(QDialog):
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

    def __init__(
        self,
        settings: Settings,
        theme: str = "dark",
        window=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._original_theme = theme
        self._window = window
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

        # ── Save Location ─────────────────────────────────────────────────────
        root.addWidget(self._section_label("Save Location"))

        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        self._path_edit = QLineEdit(settings.save_path)
        self._path_edit.setPlaceholderText("Auto — USB drive, then local reports folder")
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
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

        self._cancel_btn = cancel_btn
        self._save_btn = save_btn

        self.apply_theme(theme)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setProperty("class", "section-title")
        return lbl

    def _select_theme(self, theme: str) -> None:
        self._selected_theme = theme
        if self._window is not None:
            self._window.set_theme(theme)  # live preview
        self.apply_theme(theme)  # re-theme dialog bg + buttons for new theme

    def _select_format(self, fmt: str) -> None:
        self._settings.output_format = fmt
        seg = build_seg_styles(self._selected_theme)
        self._btn_html_pdf.setStyleSheet(seg["L_ON"]  if fmt == "html_pdf"  else seg["L_OFF"])
        self._btn_html_only.setStyleSheet(seg["M_ON"] if fmt == "html_only" else seg["M_OFF"])
        self._btn_pdf_only.setStyleSheet(seg["R_ON"]  if fmt == "pdf_only"  else seg["R_OFF"])

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Save Location", self._path_edit.text()
        )
        if path:
            self._path_edit.setText(path)

    def reject(self) -> None:
        """Revert live preview theme before dismissing (Cancel or X button)."""
        if self._window is not None and self._selected_theme != self._original_theme:
            self._window.set_theme(self._original_theme)
        super().reject()

    def apply_theme(self, theme: str) -> None:
        """Re-apply button styles. Called at init and can be called on theme change."""
        c = get_colors(theme)
        seg = build_seg_styles(theme)
        self.setStyleSheet(
            f"QDialog {{ background-color: {c['bg_base']}; }}"
            f"QLineEdit {{"
            f"  background-color: {c['bg_elevated']}; color: {c['text_primary']};"
            f"  border: none; border-radius: 6px; padding: 6px 10px; min-height: 30px;"
            f"  font-size: 13px;"
            f"}}"
            f"QPlainTextEdit {{"
            f"  background-color: {c['bg_elevated']}; color: {c['text_primary']};"
            f"  border: none; border-radius: 6px; padding: 6px 10px; font-size: 13px;"
            f"}}"
        )
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
