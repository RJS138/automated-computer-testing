"""Full-screen QDialog webcam test.

Port of the tkinter _webcam_helper.py to PySide6 QDialog.
Shows a live webcam preview using OpenCV, with camera selector dropdown.
"""

import platform

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ._utils import make_dialog_btn

# ── Visual constants ──────────────────────────────────────────────────────

_BG = "#1a1a1a"
_FG = "#cccccc"
_ACCENT = "#2a5ab8"


class WebcamDialog(QDialog):
    """Full-screen webcam test dialog with live preview."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result_str: str = "fail"
        self.setWindowTitle("Webcam Test")
        self.setStyleSheet(f"QDialog {{ background: {_BG}; }}")

        self._cv2 = None
        self._cap = None
        self._running = False
        self._available_indices: list[int] = []

        # Try importing cv2
        try:
            import cv2

            self._cv2 = cv2
        except ImportError:
            pass

        # Probe for cameras (silence OpenCV's stderr noise for missing indices)
        if self._cv2 is not None:
            _set_log = getattr(self._cv2, "setLogLevel", None)
            if _set_log is not None:
                _set_log(0)  # LOG_LEVEL_SILENT
            for i in range(5):
                try:
                    cap_probe = self._cv2.VideoCapture(i)
                    if cap_probe.isOpened():
                        self._available_indices.append(i)
                    cap_probe.release()
                except Exception:
                    pass
            if _set_log is not None:
                _set_log(3)  # restore to LOG_LEVEL_WARNING

        self._no_cameras = not self._available_indices or self._cv2 is None

        # Frame update timer
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 fps
        self._timer.timeout.connect(self._update_frame)

        if self._no_cameras:
            self._build_no_camera_ui()
        else:
            self._build_ui()
            QTimer.singleShot(200, lambda: self._open_camera(self._available_indices[0]))

    def _build_no_camera_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 48, 16, 18)

        title = QLabel("Webcam Test")
        title.setStyleSheet(
            f"color: #4a9eff; background: {_BG}; font-family: Courier; "
            "font-size: 16px; font-weight: bold;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        if platform.system() == "Darwin":
            msg = (
                "No cameras detected.\n\n"
                "On macOS, camera access must be granted to the application\n"
                "running this test (e.g. Terminal or iTerm2).\n\n"
                "To grant access:\n"
                "  System Settings > Privacy & Security > Camera\n"
                "  Enable the toggle for your terminal application.\n\n"
                "Re-launch the app after granting permission."
            )
        else:
            msg = (
                "No cameras detected.\n\n"
                "Ensure a webcam is connected and that this application\n"
                "has permission to access it, then re-launch."
            )

        msg_label = QLabel(msg)
        msg_label.setStyleSheet(
            f"color: #aaa; background: {_BG}; font-family: Courier; font-size: 12px;"
        )
        root.addWidget(msg_label)
        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        fail_btn = make_dialog_btn("Fail", "#8b1a1a", "#a02020")
        fail_btn.clicked.connect(lambda: self._finish("fail"))
        btn_row.addWidget(fail_btn)

        skip_btn = make_dialog_btn("Skip", "#3a3a3a", "#4a4a4a", fg="#aaa")
        skip_btn.clicked.connect(lambda: self._finish("skip"))
        btn_row.addWidget(skip_btn)

        root.addLayout(btn_row)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 18)

        # Top bar
        top_bar = QHBoxLayout()
        title = QLabel("Webcam Test")
        title.setStyleSheet(
            f"color: #4a9eff; background: {_BG}; font-family: Courier; "
            "font-size: 16px; font-weight: bold;"
        )
        top_bar.addWidget(title)
        top_bar.addStretch()

        # Camera selector
        cam_lbl = QLabel("Camera:")
        cam_lbl.setStyleSheet(
            f"color: #888; background: {_BG}; font-family: Courier; font-size: 11px;"
        )
        top_bar.addWidget(cam_lbl)

        self._cam_combo = QComboBox()
        self._cam_combo.setStyleSheet(
            "QComboBox { background: #252525; color: #cccccc; border: 1px solid #444; "
            "padding: 4px 14px; font-family: Courier; font-size: 11px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #252525; color: #cccccc; "
            "selection-background-color: #2a5ab8; }"
        )
        for i in self._available_indices:
            self._cam_combo.addItem(f"Camera {i}", i)
        self._cam_combo.currentIndexChanged.connect(self._on_cam_changed)
        top_bar.addWidget(self._cam_combo)
        root.addLayout(top_bar)

        # Info line
        self._info_label = QLabel("Opening camera...")
        self._info_label.setStyleSheet(
            f"color: #888; background: {_BG}; font-family: Courier; font-size: 11px;"
        )
        root.addWidget(self._info_label)

        # Preview area
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet("background: #0d0d0d;")
        root.addWidget(self._preview_label, 1)

        # Bottom hint
        hint = QLabel("Verify the live preview is clear, then mark Pass or Fail.")
        hint.setStyleSheet(
            f"color: #555; background: {_BG}; font-family: Courier; font-size: 10px;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hint)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        fail_btn = make_dialog_btn("Fail", "#8b1a1a", "#a02020")
        fail_btn.clicked.connect(lambda: self._finish("fail"))
        btn_row.addWidget(fail_btn)

        pass_btn = make_dialog_btn("Pass", "#1a6b1a", "#228822")
        pass_btn.clicked.connect(lambda: self._finish("pass"))
        btn_row.addWidget(pass_btn)

        skip_btn = make_dialog_btn("Skip", "#3a3a3a", "#4a4a4a", fg="#aaa")
        skip_btn.clicked.connect(lambda: self._finish("skip"))
        btn_row.addWidget(skip_btn)

        root.addLayout(btn_row)

    # ── helpers ────────────────────────────────────────────────────────

    def _finish(self, result: str) -> None:
        self._cleanup()
        self.result_str = result
        self.accept()

    def _cleanup(self) -> None:
        self._running = False
        self._timer.stop()
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def _open_camera(self, idx: int) -> None:
        cv2 = self._cv2
        if cv2 is None:
            return

        self._running = False
        self._timer.stop()
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        try:
            new_cap = cv2.VideoCapture(idx)
            if not new_cap.isOpened():
                self._info_label.setText(f"Camera {idx}: failed to open")
                return
            self._cap = new_cap
        except Exception as exc:
            self._info_label.setText(f"Camera {idx}: error -- {exc}")
            return

        fw = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        fh = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self._cap.get(cv2.CAP_PROP_FPS)
        fps_str = f"{fps:.0f}" if fps and fps > 0 else "?"
        self._info_label.setText(f"{fw} x {fh} @ {fps_str} fps")

        self._running = True
        self._timer.start()

    def _on_cam_changed(self, index: int) -> None:
        idx = self._cam_combo.itemData(index)
        if idx is not None:
            self._open_camera(idx)

    def _update_frame(self) -> None:
        cv2 = self._cv2
        if not self._running or self._cap is None or cv2 is None:
            return

        ret, frame = self._cap.read()
        if not ret or frame is None:
            return

        # Fit into preview label
        lw = self._preview_label.width()
        lh = self._preview_label.height()
        if lw < 2 or lh < 2:
            return

        fh_px, fw_px = frame.shape[:2]
        scale = min(lw / fw_px, lh / fh_px)
        new_w = max(1, int(fw_px * scale))
        new_h = max(1, int(fh_px * scale))

        frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)

        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        q_img = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        self._preview_label.setPixmap(pixmap)

    # ── events ────────────────────────────────────────────────────────

    def run(self) -> int:
        """Show full-screen and run the dialog. Use instead of QDialog.exec()."""
        self.showFullScreen()
        return super().exec()

    def keyPressEvent(self, event) -> None:
        key = event.text().lower()
        if key == "p":
            self._finish("pass")
        elif key == "f":
            self._finish("fail")
        elif key == "s":
            self._finish("skip")
        elif event.key() == Qt.Key.Key_Escape:
            return

    def closeEvent(self, event) -> None:
        self._cleanup()
        if self.result() != QDialog.DialogCode.Accepted:
            self.result_str = "fail"
        event.accept()
