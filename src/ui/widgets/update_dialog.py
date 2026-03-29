"""UpdateDialog — notifies the user that a newer version is available."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.stylesheet import get_colors


class UpdateDialog(QDialog):
    """
    Shown at startup when a newer release is available on GitHub.

    The user can skip (dismiss) or click 'Update USB' which launches a
    terminal running the create_usb script with --update.
    """

    def __init__(
        self,
        current_version: str,
        latest_version: str,
        theme: str = "dark",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.setMinimumWidth(380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(24, 24, 24, 20)

        title = QLabel("A new version of Touchstone is available")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        title.setWordWrap(True)
        root.addWidget(title)

        versions = QLabel(
            f"You are running <b>v{current_version}</b>. "
            f"The latest release is <b>v{latest_version}</b>."
        )
        versions.setWordWrap(True)
        versions.setStyleSheet("font-size: 13px;")
        root.addWidget(versions)

        note = QLabel(
            "Clicking <b>Update USB</b> will open a terminal and refresh the "
            "binaries on this USB drive using the latest release."
        )
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 12px; opacity: 0.75;")
        root.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._skip_btn = QPushButton("Skip")
        self._skip_btn.clicked.connect(self.reject)

        self._update_btn = QPushButton("Update USB")
        self._update_btn.setDefault(True)
        self._update_btn.clicked.connect(self._on_update)

        btn_row.addWidget(self._skip_btn)
        btn_row.addWidget(self._update_btn)
        root.addLayout(btn_row)

        self.apply_theme(theme)

    def _on_update(self) -> None:
        from src.utils.updater import launch_usb_update
        launch_usb_update()
        self.accept()

    def apply_theme(self, theme: str) -> None:
        c = get_colors(theme)
        self.setStyleSheet(f"QDialog {{ background-color: {c['bg_base']}; color: {c['text_primary']}; }}")
        self._skip_btn.setStyleSheet(
            f"QPushButton {{ background: {c['bg_elevated']}; color: {c['text_primary']};"
            f" border: none; border-radius: 6px; padding: 6px 16px; font-size: 12px; min-height: 30px; }}"
            f"QPushButton:hover {{ background: {c['bg_surface']}; }}"
        )
        self._update_btn.setStyleSheet(
            f"QPushButton {{ background: {c['accent']}; color: #ffffff;"
            f" border: none; border-radius: 6px; padding: 6px 16px; font-size: 12px;"
            f" font-weight: 600; min-height: 30px; }}"
            f"QPushButton:hover {{ background: {c['accent_hover']}; }}"
        )
