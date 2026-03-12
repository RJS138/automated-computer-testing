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


def _run_helper(name: str) -> None:
    """Dispatch to a tkinter helper window and exit with its result code.

    Used by frozen PyInstaller binaries — the exe re-invokes itself with
    ``--run-helper <name>`` rather than trying to run a .py file.

    Exit codes: 0 = pass, 1 = fail/skip, 2 = unavailable.
    """
    def _exit(r: str) -> None:
        sys.exit(0 if r == "pass" else (3 if r == "skip" else 1))

    try:
        if name == "display":
            from .ui._display_helper import run_display_test
            _exit(run_display_test())

        elif name == "keyboard":
            from .ui._keyboard_helper import run_keyboard_test
            _exit(run_keyboard_test())

        elif name == "speakers":
            from .ui._speakers_helper import run_speakers_test
            _exit(run_speakers_test())

        elif name == "touchpad":
            from .ui._touchpad_helper import run_touchpad_test
            _exit(run_touchpad_test())

        elif name == "usb_a":
            from .ui._usb_helper import run_usb_test
            _exit(run_usb_test("USB-A"))

        elif name == "usb_c":
            from .ui._usb_helper import run_usb_test
            _exit(run_usb_test("USB-C"))

        elif name == "hdmi":
            from .ui._hdmi_helper import run_hdmi_test
            _exit(run_hdmi_test())

        elif name == "webcam":
            from .ui._webcam_helper import run_webcam_test
            _exit(run_webcam_test())

        else:
            print(f"Unknown helper: {name}", file=sys.stderr)
            sys.exit(2)

    except SystemExit:
        raise
    except Exception:
        sys.exit(2)


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
            f"Available ids: lcd, speakers, keyboard, touchpad, usb_a, usb_c, hdmi, webcam"
        ),
    )
    parser.add_argument(
        "--run-helper",
        metavar="NAME",
        default=None,
        help=argparse.SUPPRESS,  # internal use only (frozen binary helper dispatch)
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Frozen binary helper dispatch — must happen before any TUI setup
    if args.run_helper:
        _run_helper(args.run_helper)
        return  # _run_helper always calls sys.exit

    dev_manual = args.dev_manual  # None → normal; "" → manual screen start; "lcd" → lcd item

    # Skip elevation in dev mode — you're developing, not diagnosing hardware
    if dev_manual is None:
        _ensure_elevated()

    from .utils.term_detect import configure_for_textual, should_use_simple_ui

    simple = should_use_simple_ui()
    os.environ["TOUCHSTONE_SIMPLE_UI"] = "1" if simple else "0"
    configure_for_textual(simple)

    from .app import PCTesterApp

    PCTesterApp(dev_manual_item=dev_manual).run()
