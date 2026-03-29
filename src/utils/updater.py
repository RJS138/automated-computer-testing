"""Version checking and USB update launcher."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request

from ..config import GITHUB_REPO


def fetch_latest_version(timeout: int = 5) -> str | None:
    """
    Query GitHub releases API for the latest published version.

    Returns the version string without the leading 'v' (e.g. '0.1.8'),
    or None if the check fails (no internet, rate limit, etc.).
    Never raises.
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Touchstone-app"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            tag = data.get("tag_name", "")
            return tag.lstrip("v") if tag else None
    except Exception:
        return None


def is_update_available(current: str, latest: str) -> bool:
    """Return True if latest is strictly newer than current."""
    def _parse(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in v.split("."))
        except Exception:
            return (0,)
    return _parse(latest) > _parse(current)


def launch_usb_update() -> None:
    """
    Open a new terminal window and run the create_usb script with --update.

    The script auto-detects the USB drive, re-runs Ventoy update, and
    downloads the latest binaries. Runs with admin/sudo as required by the
    platform. Never raises — silently no-ops if no terminal is available.
    """
    RAW = "https://raw.githubusercontent.com/RJS138/touchstone/main/scripts"

    try:
        if sys.platform == "win32":
            # Download and run create_usb.ps1 -Update in a visible PowerShell window.
            # & ([scriptblock]::Create(...)) passes -Update to the script, not to iex.
            ps_cmd = (
                f"& ([scriptblock]::Create("
                f"(Invoke-RestMethod '{RAW}/create_usb.ps1')"
                f")) -Update; "
                f"Write-Host ''; Read-Host 'Done — press Enter to close'"
            )
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )

        elif sys.platform == "darwin":
            bash_cmd = (
                f'sudo bash -c "$(curl -fsSL {RAW}/create_usb.sh)" -- --update'
            )
            # osascript opens a new Terminal.app tab
            subprocess.Popen([
                "osascript", "-e",
                f'tell application "Terminal" to do script "{bash_cmd}"',
            ])

        else:
            # Linux — try common terminal emulators in preference order
            bash_cmd = (
                f'sudo bash -c "$(curl -fsSL {RAW}/create_usb.sh)" -- --update'
                "; echo; read -rp 'Done — press Enter to close'"
            )
            terminals = [
                ["x-terminal-emulator", "-e", f"bash -c '{bash_cmd}'"],
                ["gnome-terminal", "--", "bash", "-c", bash_cmd],
                ["konsole", "-e", "bash", "-c", bash_cmd],
                ["xfce4-terminal", "-e", f"bash -c '{bash_cmd}'"],
                ["xterm", "-e", f"bash -c '{bash_cmd}'"],
            ]
            for args in terminals:
                try:
                    subprocess.Popen(args)
                    break
                except FileNotFoundError:
                    continue

    except Exception:
        pass
