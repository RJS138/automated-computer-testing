"""Full-screen QDialog USB port test.

Port of the tkinter _usb_helper.py to PySide6 QDialog.
Enumerates USB devices and highlights newly connected ones.
"""

import json
import platform
import subprocess

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ._utils import make_dialog_btn

# ── USB enumeration (copied from _usb_helper.py) ─────────────────────────


def _enumerate_usb() -> list[dict]:
    """Return list of dicts with keys: name, speed, key."""
    os_name = platform.system()
    devices: list[dict] = []

    if os_name == "Darwin":
        try:
            out = subprocess.check_output(
                ["system_profiler", "SPUSBDataType", "-json"],
                timeout=10,
                stderr=subprocess.DEVNULL,
            )
            data = json.loads(out)

            def _walk(items):
                for item in items:
                    name = item.get("_name", "").strip()
                    manufacturer = item.get("manufacturer", "").strip()
                    speed = item.get("device_speed", "").strip()
                    if name:
                        key = f"{name}|{manufacturer}"
                        devices.append({"name": name, "speed": speed, "key": key})
                    for sub_key in ("_items", "hubs", "devices"):
                        sub = item.get(sub_key)
                        if isinstance(sub, list):
                            _walk(sub)

            for top_key in ("SPUSBDataType",):
                top = data.get(top_key, [])
                for controller in top:
                    items = controller.get("_items", [])
                    _walk(items)
                    name = controller.get("_name", "").strip()
                    manufacturer = controller.get("manufacturer", "").strip()
                    speed = controller.get("device_speed", "").strip()
                    if name and name not in (
                        "USB 3.0 Bus",
                        "USB 2.0 Bus",
                        "USB31Bus",
                        "USB30Bus",
                        "USB Bus",
                        "AppleUSBHub",
                    ):
                        key = f"{name}|{manufacturer}"
                        devices.append({"name": name, "speed": speed, "key": key})
        except Exception:
            pass

    elif os_name == "Linux":
        try:
            out = subprocess.check_output(["lsusb"], timeout=10, stderr=subprocess.DEVNULL)
            for line in out.decode("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(":", 2)
                name = parts[2].strip() if len(parts) >= 3 else line
                if "root hub" in name.lower():
                    continue
                devices.append({"name": name, "speed": "", "key": line})
        except Exception:
            pass

    elif os_name == "Windows":
        try:
            ps_cmd = "Get-PnpDevice -Class USB | Select-Object FriendlyName,Status | ConvertTo-Json"
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                timeout=15,
                stderr=subprocess.DEVNULL,
            )
            raw = json.loads(out.decode("utf-8", errors="replace"))
            if isinstance(raw, dict):
                raw = [raw]
            for entry in raw:
                friendly = (entry.get("FriendlyName") or "").strip()
                if not friendly:
                    continue
                status = (entry.get("Status") or "").strip()
                devices.append({"name": friendly, "speed": status, "key": friendly})
        except Exception:
            pass

    return devices


# ── Visual constants ──────────────────────────────────────────────────────

_BG = "#1a1a1a"
_FG = "#cccccc"
_ACCENT = "#2a5ab8"
_NEW_BG = "#0d1f0d"


class UsbDialog(QDialog):
    """Full-screen USB port test dialog."""

    def __init__(self, port_type: str = "USB-A", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result_str: str = "fail"
        self._port_type = port_type
        self.setWindowTitle(f"{port_type} Port Test")
        self.setStyleSheet(f"QDialog {{ background: {_BG}; }}")

        self._baseline_keys: set[str] = set()
        self._current_devices: list[dict] = []

        self._build_ui()

        # Capture baseline after a short delay
        QTimer.singleShot(200, self._set_baseline)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 18)

        # Top bar
        top_bar = QHBoxLayout()
        title = QLabel(f"{self._port_type} Port Test")
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
            f"Plug a known-good device into each {self._port_type} port, click Scan, "
            f"verify it appears highlighted below. Test each port individually."
        )
        instr.setWordWrap(True)
        instr.setStyleSheet(
            f"color: #888; background: {_BG}; font-family: Courier; font-size: 11px;"
        )
        root.addWidget(instr)

        # Device list (scrollable)
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
        hint = QLabel("Plug in a device to each port one at a time, scan after each.")
        hint.setStyleSheet(
            f"color: #555; background: {_BG}; font-family: Courier; font-size: 10px;"
        )
        hint.setAlignment(Qt.AlignCenter)
        root.addWidget(hint)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)

        scan_btn = make_dialog_btn("Scan Again", _ACCENT, "#3a6acc")
        scan_btn.clicked.connect(self._scan)
        btn_row.addWidget(scan_btn)

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
        self.accept()

    def _set_baseline(self) -> None:
        devs = _enumerate_usb()
        for d in devs:
            self._baseline_keys.add(d["key"])
        self._scan()

    def _scan(self) -> None:
        self._current_devices = _enumerate_usb()
        self._rebuild_rows()
        self._update_count()

    def _rebuild_rows(self) -> None:
        # Clear existing
        while self._list_layout.count() > 0:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._current_devices:
            lbl = QLabel("No USB devices detected.")
            lbl.setStyleSheet("color: #555; font-family: Courier; font-size: 11px; padding: 8px;")
            self._list_layout.addWidget(lbl)
            self._list_layout.addStretch()
            return

        for dev in self._current_devices:
            is_new = dev["key"] not in self._baseline_keys
            row_bg = _NEW_BG if is_new else "#111111"
            name_fg = "#1a9b1a" if is_new else _FG
            name_text = f"* NEW  {dev['name']}" if is_new else f"       {dev['name']}"

            row = QWidget()
            row.setStyleSheet(f"background: {row_bg};")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 3, 8, 3)

            name_lbl = QLabel(name_text)
            name_lbl.setStyleSheet(f"color: {name_fg}; font-family: Courier; font-size: 11px;")
            rl.addWidget(name_lbl, 1)

            speed_lbl = QLabel(dev["speed"] or "--")
            speed_lbl.setStyleSheet("color: #888; font-family: Courier; font-size: 11px;")
            rl.addWidget(speed_lbl)

            self._list_layout.addWidget(row)

        self._list_layout.addStretch()

    def _update_count(self) -> None:
        total = len(self._current_devices)
        new_count = sum(1 for d in self._current_devices if d["key"] not in self._baseline_keys)
        if new_count > 0:
            self._count_label.setText(f"{total} device(s) detected  |  {new_count} new")
        else:
            self._count_label.setText(f"{total} device(s) detected")

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
        if self.result() != QDialog.DialogCode.Accepted:
            self.result_str = "fail"
        event.accept()
