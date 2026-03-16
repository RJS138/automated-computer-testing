"""
Installed entry point for the `touchstone` script.

With UV:
    uv run touchstone                   # normal run (prompts for sudo if needed)
    uv run touchstone --dev-manual      # jump straight to manual tests (item 1)
    uv run touchstone --dev-manual lcd  # jump straight to the lcd display test

Or after `uv sync`:
    .venv/bin/touchstone        (Linux/macOS)
    .venv/Scripts/touchstone    (Windows)
"""

import os
import platform
import sys


def _ensure_elevated() -> None:
    """
    Re-exec with elevated privileges if not already running as root/admin.

    macOS/Linux: replaces the current process with `sudo <same args>`.
    Windows:     spawns a UAC-elevated copy via ShellExecuteW and exits.

    Sets TOUCHSTONE_ELEVATED=1 before re-exec so the child skips this check
    and avoids an infinite loop if sudo somehow still returns non-root.
    """
    if os.environ.get("TOUCHSTONE_ELEVATED") == "1":
        return

    sys_name = platform.system()

    if sys_name in ("Linux", "Darwin"):
        if os.geteuid() != 0:
            os.environ["TOUCHSTONE_ELEVATED"] = "1"
            # execvp replaces the current process — no return
            os.execvpe("sudo", ["sudo", "-E"] + sys.argv, os.environ)

    elif sys_name == "Windows":
        import ctypes

        if not ctypes.windll.shell32.IsUserAnAdmin():
            # ShellExecuteW with "runas" triggers the UAC prompt
            args = " ".join(f'"{a}"' for a in sys.argv[1:])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, None, 1)
            sys.exit(0)


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        prog="touchstone",
        description="Touchstone — portable PC hardware diagnostic tool",
    )
    parser.add_argument(
        "--dev-manual",
        metavar="ITEM_ID",
        nargs="?",  # optional value: --dev-manual  OR  --dev-manual lcd
        const="",  # value when flag is given with no argument
        default=None,
        help=(
            "Dev mode: skip directly to the manual tests screen. "
            "Optionally supply an item id (e.g. 'lcd') to start from that test. "
            "Elevation is skipped in dev mode. "
            "Available ids: lcd, speakers, keyboard, touchpad, usb_a, usb_c, hdmi, webcam"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    dev_manual = args.dev_manual  # None → normal; "" → manual screen start; "lcd" → lcd item

    # Skip elevation in dev mode — you're developing, not diagnosing hardware
    if dev_manual is None:
        _ensure_elevated()

    from PySide6.QtWidgets import QApplication

    from .ui.app_window import TouchstoneWindow

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Touchstone")

    window = TouchstoneWindow(dev_manual=dev_manual is not None)
    window.show()

    sys.exit(qt_app.exec())
