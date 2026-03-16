"""OS and architecture detection."""

import platform
import sys


def get_os() -> str:
    """Return 'windows', 'linux', 'darwin', or 'unknown'."""
    s = platform.system().lower()
    if s == "windows":
        return "windows"
    elif s == "linux":
        return "linux"
    elif s == "darwin":
        return "darwin"
    return "unknown"


def get_arch() -> str:
    """Return 'x64', 'arm64', 'x86', or the raw machine string."""
    m = platform.machine().lower()
    if m in ("amd64", "x86_64"):
        return "x64"
    elif m in ("aarch64", "arm64"):
        return "arm64"
    elif m in ("i386", "i686", "x86"):
        return "x86"
    return m


def is_windows() -> bool:
    return get_os() == "windows"


def is_linux() -> bool:
    return get_os() == "linux"


def is_macos() -> bool:
    return get_os() == "darwin"


def is_frozen() -> bool:
    """Return True if running as a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def get_exe_dir():
    """Return the directory containing the running executable (or script)."""
    from pathlib import Path

    if is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.parent  # pc-tester/ root
