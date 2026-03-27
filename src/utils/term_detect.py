"""
Terminal capability detection — decides between fancy and simple UI rendering.

Simple mode uses:
  - 256-color ANSI only (no truecolor RGB sequences)
  - ASCII chars for spinners, bars, and status icons
  - Neutral borders (no colored borders that can bleed on limited terminals)

Detection logic:
  Fancy mode requires a CLEAR positive signal from the terminal environment.
  Anything ambiguous defaults to simple mode (safe everywhere).

Override env vars:
  TOUCHSTONE_FANCY=1   — force fancy mode regardless of detection
  TOUCHSTONE_SIMPLE=1  — force simple mode regardless of detection
"""

import os
import sys


def _try_enable_windows_vt() -> bool:
    """
    On Windows, attempt to enable VT/ANSI processing via SetConsoleMode.
    Returns True if VT is now available (Windows 10+), False if not (Windows 8.1 etc.).
    No-op and returns False on non-Windows.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        import ctypes.wintypes

        kernel32 = ctypes.windll.kernel32
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        STD_OUTPUT_HANDLE = -11
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.wintypes.DWORD()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        new_mode = mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(kernel32.SetConsoleMode(handle, new_mode))
    except Exception:
        return False


def _positive_truecolor_signals() -> bool:
    """Return True only if the terminal explicitly claims truecolor support."""
    # Explicit COLORTERM advertisement (de-facto standard)
    colorterm = os.environ.get("COLORTERM", "").lower()
    if colorterm in ("truecolor", "24bit"):
        return True

    # Well-known terminal programs that support truecolor
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    if term_program in ("iterm.app", "hyper", "wezterm", "vscode"):
        return True

    # Windows Terminal sets WT_SESSION; ConEmu sets ConEmuPID
    if os.environ.get("WT_SESSION") or os.environ.get("ConEmuPID"):
        return True

    # Some Linux terminal emulators set COLORTERM or advertise via TERM
    # (e.g. TERM=xterm-direct, TERM=tmux-256color with COLORTERM set)
    term = os.environ.get("TERM", "").lower()
    if term in ("xterm-direct", "xterm-ghostty"):
        return True

    return False


def _utf8_capable() -> bool:
    """Return True if stdout is encoding UTF-8 (needed for Unicode block chars)."""
    enc = getattr(sys.stdout, "encoding", "") or ""
    return enc.lower().replace("-", "") in ("utf8", "utf16", "utf32")


def should_use_simple_ui() -> bool:
    """
    Return True if the UI should use simplified ASCII + basic-color rendering.
    Called once at startup in cli.py; result stored in TOUCHSTONE_SIMPLE env var.
    """
    # Explicit user overrides win
    if os.environ.get("TOUCHSTONE_FANCY") == "1":
        return False
    if os.environ.get("TOUCHSTONE_SIMPLE") == "1":
        return True

    # Dumb / no-colour terminal
    term = os.environ.get("TERM", "").lower()
    if term == "dumb" or os.environ.get("NO_COLOR"):
        return True

    # Non-UTF-8 stdout → ASCII chars only
    if not _utf8_capable():
        return True

    # Default: fancy only if terminal clearly supports truecolor
    # Everything else (Terminal.app, PuTTY, older xterm, SSH sessions without
    # COLORTERM propagation, etc.) gets simple mode to avoid colour bleeding.
    return not _positive_truecolor_signals()


def resize_terminal(cols: int = 100, rows: int = 40) -> None:
    """
    Attempt to resize the terminal window to at least *cols* × *rows*.

    Only expands — never shrinks a terminal that's already larger than the target.
    Silent no-op when the terminal doesn't support resize (SSH, tmux, piped output, etc.).
    """
    if not sys.stdout.isatty():
        return

    try:
        import shutil

        size = shutil.get_terminal_size(fallback=(0, 0))
        if size.columns >= cols and size.lines >= rows:
            return
        target_cols = max(cols, size.columns)
        target_rows = max(rows, size.lines)
    except Exception:
        return

    try:
        if sys.platform == "win32":
            import subprocess

            subprocess.run(
                ["mode", "con:", f"cols={int(target_cols)}", f"lines={int(target_rows)}"],
                capture_output=True,
            )
        else:
            # ANSI resize: CSI 8 ; rows ; cols t
            sys.stdout.write(f"\033[8;{target_rows};{target_cols}t")
            sys.stdout.flush()
    except Exception:
        pass


def configure_for_textual(simple: bool) -> None:
    """
    Adjust environment variables so Textual uses the right colour depth.
    Must be called before PCTesterApp().run().
    """
    if sys.platform == "win32":
        # Try to enable VT processing (succeeds on Windows 10+, fails on 8.1 etc.)
        vt_ok = _try_enable_windows_vt()
        if not vt_ok:
            # Old Windows console — let Textual/Rich use Win32 API directly.
            # Do NOT set TERM here; overriding it would make Rich think ANSI is
            # available and print raw escape codes the console can't render.
            os.environ.pop("COLORTERM", None)
        return

    if simple:
        # Remove truecolor hint — Textual will fall back to 256-colour
        os.environ.pop("COLORTERM", None)
        # Ensure TERM claims 256-colour support (Textual reads this)
        cur = os.environ.get("TERM", "xterm")
        if cur not in ("dumb", "") and "256color" not in cur:
            os.environ["TERM"] = "xterm-256color"
    # If fancy: leave env vars untouched — terminal already advertised support
