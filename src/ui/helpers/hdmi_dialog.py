"""Full-screen QDialog HDMI / video-out test.

Port of the tkinter _hdmi_helper.py to PySide6 QDialog.
Enumerates displays, highlights newly connected ones, and offers a
colour test window for the external monitor.
"""

import json
import platform
import subprocess

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPalette
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ._utils import make_dialog_btn

# ── Display enumeration (copied from _hdmi_helper.py) ────────────────────


def _enumerate_displays() -> list[dict]:
    """Return list of dicts with keys: name, resolution, connection, status, key."""
    os_name = platform.system()
    displays: list[dict] = []

    if os_name == "Darwin":
        try:
            out = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                timeout=10,
                stderr=subprocess.DEVNULL,
            )
            data = json.loads(out)
            for gpu in data.get("SPDisplaysDataType", []):
                for ndrvs in gpu.get("spdisplays_ndrvs", []):
                    name = ndrvs.get("_name", "Unknown Display").strip()
                    resolution = ndrvs.get("spdisplays_resolution", "").strip()
                    connection = ndrvs.get("spdisplays_connection_type", "").strip()
                    online_raw = ndrvs.get("spdisplays_online", "").strip().lower()
                    status = (
                        "connected" if online_raw in ("yes", "spdisplays_yes") else "disconnected"
                    )
                    key = f"{name}|{resolution}"
                    displays.append(
                        {
                            "name": name,
                            "resolution": resolution,
                            "connection": connection,
                            "status": status,
                            "key": key,
                        }
                    )
        except Exception:
            pass

    elif os_name == "Linux":
        try:
            out = subprocess.check_output(
                ["xrandr", "--query"], timeout=10, stderr=subprocess.DEVNULL
            )
            for line in out.decode("utf-8", errors="replace").splitlines():
                if " connected" in line or " disconnected" in line:
                    parts = line.split()
                    display_name = parts[0] if parts else "Unknown"
                    connected = " connected" in line
                    status = "connected" if connected else "disconnected"
                    resolution = ""
                    for part in parts:
                        if "x" in part and "+" in part:
                            resolution = part.split("+")[0]
                            break
                    displays.append(
                        {
                            "name": display_name,
                            "resolution": resolution,
                            "connection": "",
                            "status": status,
                            "key": display_name,
                        }
                    )
        except Exception:
            pass

    elif os_name == "Windows":
        try:
            ps_cmd = (
                "Get-WmiObject -Class Win32_DesktopMonitor | "
                "Select-Object Name,ScreenWidth,ScreenHeight | "
                "ConvertTo-Json"
            )
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                timeout=15,
                stderr=subprocess.DEVNULL,
            )
            raw = json.loads(out.decode("utf-8", errors="replace"))
            if isinstance(raw, dict):
                raw = [raw]
            for entry in raw:
                name = (entry.get("Name") or "Unknown Monitor").strip()
                w = entry.get("ScreenWidth")
                h = entry.get("ScreenHeight")
                resolution = f"{w}x{h}" if w and h else ""
                displays.append(
                    {
                        "name": name,
                        "resolution": resolution,
                        "connection": "",
                        "status": "connected",
                        "key": name,
                    }
                )
        except Exception:
            pass

    return displays


# ── Colour test dialog ───────────────────────────────────────────────────

_CYCLE_COLOURS = [
    ("Black", "#000000"),
    ("White", "#ffffff"),
    ("Red", "#ff0000"),
    ("Green", "#00ff00"),
    ("Blue", "#0000ff"),
    ("Cyan", "#00ffff"),
    ("Magenta", "#ff00ff"),
    ("Grey", "#7f7f7f"),
]


class _ColourTestDialog(QDialog):
    """Small windowed dialog that cycles through colours on click/key."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Colour Test -- External Monitor")
        self.resize(800, 600)
        self._phase = -1
        self._N = len(_CYCLE_COLOURS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._colour_label = QLabel()
        self._colour_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self._colour_label.setStyleSheet(
            "color: #cccccc; font-family: Courier; font-size: 14px; font-weight: bold; padding-top: 20px;"
        )
        layout.addWidget(self._colour_label)

        self._instr_label = QLabel(
            "Drag this window to the external monitor, then click to cycle colours."
        )
        self._instr_label.setAlignment(Qt.AlignCenter)
        self._instr_label.setStyleSheet("color: #cccccc; font-family: Courier; font-size: 12px;")
        layout.addWidget(self._instr_label, 1)

        hint = QLabel("Click or press any key to advance")
        hint.setStyleSheet(
            "color: #888; background: #1a1a1a; font-family: Courier; font-size: 10px; padding: 4px;"
        )
        layout.addWidget(hint)

        self._set_bg("#000000")

    def _set_bg(self, color: str) -> None:
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(color))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

    def _advance(self) -> None:
        self._phase = (self._phase + 1) % self._N
        name, bg = _CYCLE_COLOURS[self._phase]
        self._set_bg(bg)
        self._instr_label.setVisible(False)
        fg = "#000000" if bg in ("#ffffff", "#00ff00", "#00ffff") else "#ffffff"
        self._colour_label.setStyleSheet(
            f"color: {fg}; font-family: Courier; font-size: 14px; font-weight: bold; padding-top: 20px;"
        )
        self._colour_label.setText(f"{name}  ({self._phase + 1}/{self._N})")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self._advance()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._advance()


# ── Visual constants ──────────────────────────────────────────────────────

_BG = "#1a1a1a"
_FG = "#cccccc"
_ACCENT = "#2a5ab8"
_NEW_BG = "#0d1f0d"


class HdmiDialog(QDialog):
    """Full-screen HDMI / video-out test dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result_str: str = "fail"
        self.setWindowTitle("HDMI / Video Out Test")
        self.setStyleSheet(f"QDialog {{ background: {_BG}; }}")

        self._baseline_keys: set[str] = set()
        self._current_displays: list[dict] = []
        self._colour_dialog: _ColourTestDialog | None = None

        self._build_ui()
        QTimer.singleShot(200, self._set_baseline)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 18)

        # Top bar
        top_bar = QHBoxLayout()
        title = QLabel("HDMI / Video Out Test")
        title.setStyleSheet(
            f"color: #4a9eff; background: {_BG}; font-family: Courier; "
            "font-size: 16px; font-weight: bold;"
        )
        top_bar.addWidget(title)
        top_bar.addStretch()

        self._count_label = QLabel()
        self._count_label.setStyleSheet(
            f"color: {_FG}; background: {_BG}; font-family: Courier; font-size: 11px;"
        )
        top_bar.addWidget(self._count_label)
        root.addLayout(top_bar)

        # Instruction
        instr = QLabel(
            "Connect an external monitor via HDMI / DisplayPort / USB-C, "
            "then click Refresh. Newly detected displays are highlighted in green."
        )
        instr.setWordWrap(True)
        instr.setStyleSheet(
            f"color: #888; background: {_BG}; font-family: Courier; font-size: 11px;"
        )
        root.addWidget(instr)

        # Display list (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { background: #111111; border: none; }"
            "QScrollBar:vertical { background: #111111; width: 10px; }"
            "QScrollBar::handle:vertical { background: #333; border-radius: 4px; }"
        )

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(4, 4, 4, 4)
        self._list_layout.setSpacing(1)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_widget)
        root.addWidget(scroll, 1)

        # Bottom hint
        hint = QLabel("Connect each output one at a time and click Refresh to detect new displays.")
        hint.setStyleSheet(
            f"color: #555; background: {_BG}; font-family: Courier; font-size: 10px;"
        )
        hint.setAlignment(Qt.AlignCenter)
        root.addWidget(hint)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)

        refresh_btn = make_dialog_btn("Refresh", _ACCENT, "#3a6acc")
        refresh_btn.clicked.connect(self._scan)
        btn_row.addWidget(refresh_btn)

        self._colour_btn = make_dialog_btn("Colour Test", "#444466", "#555577")
        self._colour_btn.clicked.connect(self._open_colour_test)
        self._colour_btn.setVisible(False)
        btn_row.addWidget(self._colour_btn)

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
        self.result_str = result
        if self._colour_dialog is not None:
            self._colour_dialog.close()
        self.accept()

    def _set_baseline(self) -> None:
        devs = _enumerate_displays()
        for d in devs:
            self._baseline_keys.add(d["key"])
        self._scan()

    def _scan(self) -> None:
        self._current_displays = _enumerate_displays()
        self._rebuild_rows()
        self._update_count()
        # Show colour test button when > 1 display
        self._colour_btn.setVisible(len(self._current_displays) > 1)

    def _rebuild_rows(self) -> None:
        while self._list_layout.count() > 0:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._current_displays:
            lbl = QLabel("No displays detected.")
            lbl.setStyleSheet("color: #555; font-family: Courier; font-size: 11px; padding: 8px;")
            self._list_layout.addWidget(lbl)
            self._list_layout.addStretch()
            return

        for disp in self._current_displays:
            is_new = disp["key"] not in self._baseline_keys
            row_bg = _NEW_BG if is_new else "#111111"
            name_fg = "#1a9b1a" if is_new else _FG
            name_text = f"* NEW  {disp['name']}" if is_new else f"       {disp['name']}"
            status_fg = "#1a9b1a" if disp["status"] == "connected" else "#555"

            row = QWidget()
            row.setStyleSheet(f"background: {row_bg};")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 3, 8, 3)

            name_lbl = QLabel(name_text)
            name_lbl.setStyleSheet(f"color: {name_fg}; font-family: Courier; font-size: 11px;")
            name_lbl.setMinimumWidth(200)
            rl.addWidget(name_lbl, 1)

            res_lbl = QLabel(disp["resolution"] or "--")
            res_lbl.setStyleSheet("color: #888; font-family: Courier; font-size: 11px;")
            res_lbl.setMinimumWidth(120)
            rl.addWidget(res_lbl)

            conn_lbl = QLabel(disp["connection"] or "--")
            conn_lbl.setStyleSheet("color: #888; font-family: Courier; font-size: 11px;")
            conn_lbl.setMinimumWidth(140)
            rl.addWidget(conn_lbl)

            stat_lbl = QLabel(disp["status"])
            stat_lbl.setStyleSheet(f"color: {status_fg}; font-family: Courier; font-size: 11px;")
            stat_lbl.setMinimumWidth(100)
            rl.addWidget(stat_lbl)

            self._list_layout.addWidget(row)

        self._list_layout.addStretch()

    def _update_count(self) -> None:
        total = len(self._current_displays)
        new_count = sum(1 for d in self._current_displays if d["key"] not in self._baseline_keys)
        if new_count > 0:
            self._count_label.setText(f"{total} display(s) detected  |  {new_count} new")
        else:
            self._count_label.setText(f"{total} display(s) detected")

    def _open_colour_test(self) -> None:
        if self._colour_dialog is not None:
            try:
                self._colour_dialog.raise_()
                self._colour_dialog.activateWindow()
                return
            except Exception:
                self._colour_dialog = None

        self._colour_dialog = _ColourTestDialog(self)
        self._colour_dialog.setWindowFlags(Qt.Window)
        self._colour_dialog.show()

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
        elif event.key() == Qt.Key_Escape:
            return

    def closeEvent(self, event) -> None:
        if self._colour_dialog is not None:
            self._colour_dialog.close()
        if self.result() != QDialog.DialogCode.Accepted:
            self.result_str = "fail"
        event.accept()
