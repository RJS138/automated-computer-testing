"""Theme preference — persisted to ~/.touchstone/prefs.json."""

from __future__ import annotations

import json
from pathlib import Path

_PREFS_PATH = Path.home() / ".touchstone" / "prefs.json"


def load_theme() -> str:
    """Return "dark" or "light". Defaults to "dark" if absent or malformed."""
    try:
        data = json.loads(_PREFS_PATH.read_text())
        return "light" if data.get("theme") == "light" else "dark"
    except Exception:
        return "dark"


def save_theme(theme: str) -> None:
    """Persist theme choice to ~/.touchstone/prefs.json."""
    _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PREFS_PATH.write_text(json.dumps({"theme": theme}))
