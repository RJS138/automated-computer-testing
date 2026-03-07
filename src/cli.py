"""
Installed entry point for the `pctester` script.

With UV:
    uv run pctester          # prompts for sudo password if needed
    sudo uv run pctester     # start already elevated (macOS/Linux)

Or after `uv sync`:
    .venv/bin/pctester        (Linux/macOS)
    .venv/Scripts/pctester    (Windows)
"""

import os
import platform
import sys


def _ensure_elevated() -> None:
    """
    Re-exec with elevated privileges if not already running as root/admin.

    macOS/Linux: replaces the current process with `sudo <same args>`.
    Windows:     spawns a UAC-elevated copy via ShellExecuteW and exits.

    Sets PCTESTER_ELEVATED=1 before re-exec so the child skips this check
    and avoids an infinite loop if sudo somehow still returns non-root.
    """
    if os.environ.get("PCTESTER_ELEVATED") == "1":
        return

    sys_name = platform.system()

    if sys_name in ("Linux", "Darwin"):
        if os.geteuid() != 0:
            os.environ["PCTESTER_ELEVATED"] = "1"
            # execvp replaces the current process — no return
            os.execvpe("sudo", ["sudo", "-E"] + sys.argv, os.environ)

    elif sys_name == "Windows":
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            # ShellExecuteW with "runas" triggers the UAC prompt
            args = " ".join(f'"{a}"' for a in sys.argv[1:])
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, args, None, 1
            )
            sys.exit(0)


def main() -> None:
    _ensure_elevated()
    from .app import PCTesterApp
    PCTesterApp().run()
