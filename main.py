"""
Entry point for the PC Tester application.

Preferred:          uv run pctester
Also works:         uv run python main.py
Without UV (dev):   python main.py  (requires dependencies already installed)

When frozen by PyInstaller this binary also serves as the helper runner for
the full-screen tkinter display/keyboard test windows, invoked as:

    <exe> --run-helper display
    <exe> --run-helper keyboard
"""

import sys


def main() -> None:
    # In frozen builds (PyInstaller), the binary re-invokes itself with
    # --run-helper <name> to launch the tkinter helper windows in a subprocess.
    if len(sys.argv) >= 3 and sys.argv[1] == "--run-helper":
        _run_helper(sys.argv[2])
        return

    from src.cli import main as _main
    _main()


def _run_helper(name: str) -> None:
    """Run a tkinter helper window and exit with an appropriate code."""
    try:
        if name == "display":
            from src.ui._display_helper import run_display_test
            result = run_display_test()
            sys.exit(0 if result else 1)
        elif name == "keyboard":
            from src.ui._keyboard_helper import run_keyboard_test
            result = run_keyboard_test()
            sys.exit(0 if result else 1)
        else:
            sys.exit(2)
    except SystemExit:
        raise
    except Exception:
        sys.exit(2)


if __name__ == "__main__":
    main()
