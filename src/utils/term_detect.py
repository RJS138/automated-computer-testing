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


def configure_for_textual(simple: bool) -> None:
    """
    Adjust environment variables so Textual uses the right colour depth.
    Must be called before PCTesterApp().run().
    """
    if simple:
        # Remove truecolor hint — Textual will fall back to 256-colour
        os.environ.pop("COLORTERM", None)
        # Ensure TERM claims 256-colour support (Textual reads this)
        cur = os.environ.get("TERM", "xterm")
        if cur not in ("dumb", "") and "256color" not in cur:
            os.environ["TERM"] = "xterm-256color"
    # If fancy: leave env vars untouched — terminal already advertised support
